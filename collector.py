# collector.py
import discord
import re
import aiohttp
import base64
import traceback
import unicodedata
from config import MAX_THREAD_CONTENT, MAX_GITHUB_CONTENT, MAX_TOTAL_CONTENT, BLACKLIST_THREADS
from curriculum_classifier import CurriculumClassifier


class CheckpointCollector:
    def __init__(self, bot, all_members):
        self.bot = bot
        self.all_members = all_members
        self.thread_pattern = re.compile(r"\[Tu\S+\s*(\d+)\s*\]\s*(.+)")
        self.template_pattern = re.compile(
            r"Topic:\s*(.+?)\s*\nLink:\s*(.+?)\s*\n(?:Tự đánh giá|Tu danh gia|T[uự]\s*[dđ]\s*[aá]nh\s*gi[aá]):\s*(\d+)\s*/\s*5",
            re.MULTILINE | re.IGNORECASE)
        self.classifier = CurriculumClassifier("roadmap.json")

    async def collect_week(self, channel, week):
        submissions = []
        submitted_members = set()
        try:
            channel = await self.bot.fetch_channel(channel.id)
        except Exception as e:
            print(f"[Collector] Refresh fail: {e}")

        threads = list(channel.threads)
        try:
            if hasattr(channel.guild, "fetch_active_threads"):
                resp = await channel.guild.fetch_active_threads()
                ids = {t.id for t in threads}
                for t in resp.threads:
                    if t.parent_id == channel.id and t.id not in ids:
                        threads.append(t); ids.add(t.id)
        except Exception as e:
            print(f"[Collector] fetch_active err: {e}")

        try:
            ids = {t.id for t in threads}
            async for t in channel.archived_threads(limit=100):
                if t.id not in ids:
                    threads.append(t); ids.add(t.id)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[Collector] archived err: {e}")

        seen, uniq = set(), []
        for t in threads:
            if t.id not in seen:
                seen.add(t.id); uniq.append(t)

        valid = []
        for t in uniq:
            try:
                valid.append(await self.bot.fetch_channel(t.id))
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"[Collector] thread '{t.name}' err: {e}")

        uniq = [t for t in valid if t.name not in BLACKLIST_THREADS]
        print(f"[Collector] Valid threads: {len(uniq)}")

        for thread in uniq:
            m = self.thread_pattern.match(thread.name)
            if not m:
                continue
            tw = int(m.group(1))
            if tw != week:
                continue
            try:
                sub = await self._extract_submission(thread)
                if not sub:
                    continue
                base = sub["member"].split("-")[0].strip()
                bases = [x.split("-")[0].strip() for x in self.all_members]
                if base not in bases:
                    continue
                cls = self.classifier.classify(sub.get("content", ""), thread_week=tw)
                sub.update({
                    "classified_week": cls["week"],
                    "classification_confidence": cls["confidence"],
                    "classification_method": cls["method"],
                    "classification_topic": cls.get("topic_name"),
                    "classification_phase": cls.get("phase_name"),
                    "classification_keywords": cls.get("keywords_found", []),
                    "thread_week": tw,
                    "classification": cls,
                })
                print(f"[Collector] {base}: W{tw} -> W{cls['week']} ({cls['method']}, {cls['confidence']})")
                submissions.append(sub)
                submitted_members.add(base)
            except Exception as e:
                print(f"[Collector] EXC {thread.name}: {e}")
                traceback.print_exc()

        missing = [x for x in self.all_members if x.split("-")[0].strip() not in submitted_members]
        print(f"[Collector] Found {len(submissions)}, Missing {len(missing)}")
        return submissions, missing

    async def _extract_submission(self, thread):
        aid, aname, msgs = None, None, []
        try:
            async for msg in thread.history(limit=20, oldest_first=True):
                if msg.author.bot:
                    continue
                if aid is None:
                    aid = msg.author.id
                    nm = re.search(r"\]\s*(.+)", thread.name)
                    aname = nm.group(1).strip() if nm else msg.author.display_name.split("-")[0].strip()
                if msg.author.id == aid and msg.content:
                    msgs.append(msg.content)
            if aid is None:
                return None
            combined = "\n".join(msgs)
            parsed = self._parse_template(combined)
            if not parsed:
                return None
            try:
                ext = await self._fetch_external_content(parsed["link"])
            except Exception:
                ext = None
            full = self._build_full_content(parsed.get("raw", ""), combined, ext)
            return {"topic": parsed["topic"], "link": parsed["link"],
                    "self_score": parsed["self_score"], "content": full,
                    "thread_id": thread.id, "url": thread.jump_url,
                    "member": aname, "author_id": aid}
        except Exception as e:
            print(f"[Collector] _extract err: {e}")
            return None

    def _build_full_content(self, tpl, th, ext):
        parts = [f"=== TEMPLATE ===\n{tpl}"]
        if th: parts.append(f"=== THREAD ===\n{th}")
        if ext: parts.append(f"=== EXTERNAL ===\n{ext}")
        full = "\n\n".join(parts)
        return full[:MAX_TOTAL_CONTENT] if len(full) > MAX_TOTAL_CONTENT else full

    def _parse_template(self, content):
        content = unicodedata.normalize("NFC", content)
        m = self.template_pattern.search(content)
        if not m:
            return None
        return {"topic": m.group(1).strip(), "link": m.group(2).strip(),
                "self_score": int(m.group(3)), "raw": content}

    async def _fetch_external_content(self, url):
        if not url:
            return None
        if "github.com" in url:
            return await self._fetch_github_readme(url)
        if "docs.google.com/document" in url:
            return await self._fetch_gdoc_content(url)
        return None

    async def _fetch_github_readme(self, url):
        if "github.com" not in url:
            return None
        m = re.match(r"https?://github\.com/([^/]+)/([^/\s?#]+)", url)
        if not m:
            return None
        owner, repo = m.group(1), m.group(2).replace(".git", "")
        api = f"https://api.github.com/repos/{owner}/{repo}/readme"
        to = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=to) as s:
                async with s.get(api) as r:
                    if r.status != 200:
                        return None
                    d = await r.json()
                    return base64.b64decode(d["content"]).decode("utf-8")[:MAX_GITHUB_CONTENT]
        except Exception:
            return None

    async def _fetch_gdoc_content(self, url):
        if "docs.google.com/document" not in url:
            return None
        m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
        if not m:
            return None
        doc = m.group(1)
        ex = f"https://docs.google.com/document/d/{doc}/export?format=txt"
        to = aiohttp.ClientTimeout(total=15)
        try:
            async with aiohttp.ClientSession(timeout=to) as s:
                async with s.get(ex) as r:
                    if r.status != 200:
                        return None
                    return (await r.text())[:MAX_GITHUB_CONTENT]
        except Exception:
            return None