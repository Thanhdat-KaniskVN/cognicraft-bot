# collector.py
import discord
import re
import aiohttp
import base64
import traceback
from typing import Optional
from config import (
    MAX_THREAD_CONTENT, MAX_GITHUB_CONTENT, MAX_TOTAL_CONTENT,
    BLACKLIST_THREADS,
)
from code_analyzer import CodeAnalyzer


class CheckpointCollector:
    def __init__(self, bot, all_members):
        self.bot = bot
        self.all_members = all_members
        # Cho phép khoảng trắng trước dấu ]
        self.thread_pattern = re.compile(r"\[Tu\S+\s*(\d+)\s*\]\s*(.+)")
        self.template_pattern = re.compile(
            r"Topic:\s*(.+?)\s*\n"
            r"Link:\s*(.+?)\s*\n"
            r"Tự đánh giá:\s*(\d+)\s*/\s*5",
            re.MULTILINE | re.IGNORECASE
        )

    async def collect_week(self, channel, week):
        submissions = []
        submitted_members = set()

        # === FIX: Force refresh channel ===
        try:
            channel = await self.bot.fetch_channel(channel.id)
            print(f"[Collector] Channel refreshed")
        except Exception as e:
            print(f"[Collector] Refresh fail: {e}")

        # === Đọc cached threads ===
        threads_to_check = list(channel.threads)
        print(f"[Collector] Cached: {[t.name for t in threads_to_check]}")

        # === Fetch active threads từ API ===
        try:
            if hasattr(channel.guild, 'fetch_active_threads'):
                response = await channel.guild.fetch_active_threads()
                existing_ids = {t.id for t in threads_to_check}
                for t in response.threads:
                    if t.parent_id == channel.id and t.id not in existing_ids:
                        threads_to_check.append(t)
                        existing_ids.add(t.id)
                print(f"[Collector] After fetch_active: {len(threads_to_check)}")
        except Exception as e:
            print(f"[Collector] Fetch active not available: {e}")

        # === Archived threads ===
        try:
            existing_ids = {t.id for t in threads_to_check}
            async for t in channel.archived_threads(limit=100):
                if t.id not in existing_ids:
                    threads_to_check.append(t)
                    existing_ids.add(t.id)
        except discord.Forbidden:
            print("[Collector] Khong co quyen doc archived")
        except Exception as e:
            print(f"[Collector] Archived error: {e}")

        # === De-duplicate by ID ===
        seen_ids = set()
        unique_threads = []
        for t in threads_to_check:
            if t.id not in seen_ids:
                seen_ids.add(t.id)
                unique_threads.append(t)

        print(f"[Collector] Unique threads (before validate): {len(unique_threads)}")

        # ✅ Validate threads - loại bỏ thread đã xóa
        valid_threads = []
        for t in unique_threads:
            try:
                fetched = await self.bot.fetch_channel(t.id)
                valid_threads.append(fetched)
            except discord.NotFound:
                print(f"[Collector] Thread '{t.name}' đã xóa - SKIP")
            except Exception as e:
                print(f"[Collector] Thread '{t.name}' error: {e} - SKIP")

        unique_threads = valid_threads
        print(f"[Collector] Valid threads: {len(unique_threads)}")

        # ✅ BLACKLIST filter
        filtered_threads = []
        for t in unique_threads:
            if t.name in BLACKLIST_THREADS:
                print(f"[Collector] Thread '{t.name}' in BLACKLIST - SKIP")
                continue
            filtered_threads.append(t)

        unique_threads = filtered_threads
        print(f"[Collector] After blacklist: {len(unique_threads)}")

        # === Match threads theo tuần ===
        for thread in unique_threads:
            match = self.thread_pattern.match(thread.name)
            if not match:
                continue

            thread_week = int(match.group(1))
            if thread_week != week:
                continue

            print(f"[Collector] Matching: '{thread.name}'")
            try:
                sub = await self._extract_submission(thread)
                if sub:
                    member_base = sub["member"].split("-")[0].strip()
                    all_bases = [m.split("-")[0].strip() for m in self.all_members]

                    if member_base not in all_bases:
                        print(f"[Collector] UNKNOWN '{sub['member']}' -> SKIP")
                        continue

                    submissions.append(sub)
                    submitted_members.add(member_base)
                    print(f"[Collector] OK: {member_base}")
                else:
                    print(f"[Collector] SKIP: {thread.name}")
            except Exception as e:
                print(f"[Collector] EXCEPTION in {thread.name}: {e}")
                traceback.print_exc()

        # Tính missing
        missing = [
            m for m in self.all_members
            if m.split("-")[0].strip() not in submitted_members
        ]
        print(f"[Collector] Found {len(submissions)}, Missing {len(missing)}")
        return submissions, missing

    async def _extract_submission(self, thread):
        author_id = None
        author_name = None
        all_messages = []

        try:
            async for msg in thread.history(limit=20, oldest_first=True):
                if msg.author.bot:
                    continue

                if author_id is None:
                    author_id = msg.author.id

                    name_match = re.search(r"\]\s*(.+)", thread.name)
                    if name_match:
                        author_name = name_match.group(1).strip()
                    else:
                        raw_name = msg.author.display_name
                        author_name = raw_name.split("-")[0].strip()

                    print(f"[Collector]   Author (from thread): {author_name}")

                if msg.author.id == author_id and msg.content:
                    all_messages.append(msg.content)

            if author_id is None:
                print(f"[Collector]   No author")
                return None

            combined = "\n".join(all_messages)
            preview = combined[:200].replace("\n", " | ")
            print(f"[Collector]   Combined: {preview}")

            parsed = self._parse_template(combined)
            if not parsed:
                print(f"[Collector]   NO TEMPLATE found")
                return None

            print(f"[Collector]   Template OK: {parsed['topic']}")

            try:
                external_content = await self._fetch_external_content(
                    parsed["link"]
                )
            except Exception as e:
                print(f"[Collector]   External fail: {e}")
                external_content = None

            full_content = self._build_full_content(
                parsed.get("raw", ""),
                combined,
                external_content
            )

            return {
                "topic": parsed["topic"],
                "link": parsed["link"],
                "self_score": parsed["self_score"],
                "content": full_content,
                "thread_id": thread.id,
                "url": thread.jump_url,
                "member": author_name,
                "author_id": author_id,
            }

        except Exception as e:
            print(f"[Collector]   EXCEPTION: {e}")
            traceback.print_exc()
            return None

    async def _fetch_thread_content(self, thread, author_id, exclude_msg_id=None):
        contents = []
        total_len = 0
        try:
            async for msg in thread.history(limit=50, oldest_first=True):
                if msg.author.id != author_id:
                    continue
                if exclude_msg_id and msg.id == exclude_msg_id:
                    continue
                if not msg.content:
                    continue
                if total_len + len(msg.content) > MAX_THREAD_CONTENT:
                    break
                contents.append(msg.content)
                total_len += len(msg.content)
        except Exception as e:
            print(f"[Collector] Cannot fetch thread {thread.id}: {e}")
        return "\n\n".join(contents)

    def _build_full_content(self, template, thread, external):
        parts = [f"=== TEMPLATE ===\n{template}"]
        if thread:
            parts.append(f"=== THREAD ===\n{thread}")
        if external:
            parts.append(f"=== EXTERNAL ===\n{external}")

        full = "\n\n".join(parts)
        if len(full) > MAX_TOTAL_CONTENT:
            full = full[:MAX_TOTAL_CONTENT] + "\n\n[... truncated ...]"
        return full

    def _parse_template(self, content):
        match = self.template_pattern.search(content)
        if not match:
            return None
        return {
            "topic": match.group(1).strip(),
            "link": match.group(2).strip(),
            "self_score": int(match.group(3)),
            "raw": content,
        }

    async def _fetch_external_content(self, url):
        if not url:
            return None
        if "github.com" in url:
            return await self._fetch_github_readme(url)
        elif "docs.google.com/document" in url:
            return await self._fetch_gdoc_content(url)
        return None

    async def _fetch_github_readme(self, url):
        """Đọc code sâu từ GitHub repo (không chỉ README)"""
        if "github.com" not in url:
            return None

        # Thử đọc README trước
        readme_content = await self._fetch_readme_only(url)

        # Đọc code sâu
        try:
            analysis = self.code_analyzer.analyze_github_repo(url)
            if analysis and analysis["files"]:
                code_content = self.code_analyzer.build_content_for_ai(analysis)
                # Gộp README + code
                if readme_content:
                    return f"{readme_content}\n\n{code_content}"
                return code_content
        except Exception as e:
            print(f"[Collector] Code analyze error: {e}")

        # Fallback: chỉ README
        return readme_content

    async def _fetch_readme_only(self, url):
        """Chỉ đọc README (fallback)"""
        if "github.com" not in url:
            return None
        match = re.match(r"https?://github\.com/([^/]+)/([^/\s?#]+)", url)
        if not match:
            return None
        owner = match.group(1)
        repo = match.group(2).replace(".git", "")
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    github_content = base64.b64decode(
                        data["content"]
                    ).decode("utf-8")
                    return github_content[:MAX_GITHUB_CONTENT]
        except Exception as e:
            print(f"[Collector] README error: {e}")
            return None

    async def _fetch_gdoc_content(self, url):
        if "docs.google.com/document" not in url:
            return None
        match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
        if not match:
            return None
        doc_id = match.group(1)
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        timeout = aiohttp.ClientTimeout(total=15)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(export_url) as resp:
                    if resp.status != 200:
                        print(f"[Collector]   GDocs {resp.status}")
                        return None
                    text = await resp.text()
                    return text[:MAX_GITHUB_CONTENT]
        except Exception as e:
            print(f"[Collector]   GDocs error: {e}")
            return None