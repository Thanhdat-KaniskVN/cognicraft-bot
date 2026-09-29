# jarvis/natural_input.py
"""Natural input - on_message listener for NO prefix commands."""
import asyncio
import discord
from datetime import datetime

from jarvis.intent import classify
from jarvis import personality as pers


# Rate limit per user (in-memory)
_LAST_MSG = {}  # user_id -> datetime
RATE_LIMIT_SEC = 0.8  # Cho phep burst nhanh

# Whitelist channels - CHI respond trong cac channel nay
# Match theo ten channel (lowercase) hoac ID
NATURAL_INPUT_CHANNELS = {
    "admin-review",
    "checkpoint",
    "report",
    "m?c-ti?u-tu?n",
    "quan-ly-lich",
    "jarvis",
    "bot-test",
}

# Channels IGNORE - luon skip (chat chung)
NATURAL_INPUT_IGNORE = {
    "th?o-lu?n-t?-do",
    "thao-luan-tu-do",
    "gi?i-tr?",
    "giai-tri",
    "ch?o-h?i-gi?i-thi?u",
    "chao-hoi-gioi-thieu",
    "cozy study",
    "trao ??i kinh nghi?m",
    "trao-doi-kinh-nghiem",
    "s?nh chung",
    "sanh-chung",
    "th?ng-b?o-chung",
    "noi-quy",
}


def _is_ratelimited(user_id: str) -> bool:
    now = datetime.now()
    last = _LAST_MSG.get(user_id)
    if last and (now - last).total_seconds() < RATE_LIMIT_SEC:
        return True
    _LAST_MSG[user_id] = now
    return False


def _is_allowed_channel(channel) -> bool:
    """Check channel co nam trong whitelist khong."""
    if channel is None:
        return False
    ch_name = (getattr(channel, "name", "") or "").strip().lower()

    # Explicit ignore first (chat chung)
    if ch_name in NATURAL_INPUT_IGNORE:
        return False

    # Whitelist
    if ch_name in NATURAL_INPUT_CHANNELS:
        return True

    # Fallback: check channel category / parent
    parent = getattr(channel, "parent", None) or getattr(channel, "category", None)
    if parent:
        p_name = (getattr(parent, "name", "") or "").strip().lower()
        if p_name in ("g1-a - cohort", "g1-a-cohort"):
            return True

    return False


def _should_process(message: discord.Message, bot) -> bool:
    """Filter messages truoc khi xu ly."""
    # Skip bot
    if message.author.bot:
        return False

    # ?? CRITICAL: Chi respond trong channel whitelist
    if not _is_allowed_channel(message.channel):
        return False

    # Skip command prefix (do prefix handler lo)
    if message.content.startswith("!"):
        return False

    # Skip system messages
    if not message.content or not message.content.strip():
        return False

    # Skip qua ngan
    if len(message.content.strip()) < 5:
        return False

    # Rate limit
    if _is_ratelimited(str(message.author.id)):
        print(f"[NaturalInput] Rate limited: {message.author.id}")
        return False

    # Chi process trong guild (khong DM)
    if not message.guild:
        return False

    return True


async def handle_natural_message(message: discord.Message, bot, is_admin_fn,
                                  do_add_fn):
    """Xu ly 1 tin nhan tu nhien.

    Args:
        message: Discord message
        bot: Discord bot
        is_admin_fn: Func kiem tra admin (ctx-like)
        do_add_fn: _do_add function tu commands.py
    """
    if not _should_process(message, bot):
        return

    text = message.content.strip()

    # SUGGESTION check FIRST (before classify)
    from jarvis.intent import _norm
    nq = _norm(text)
    is_suggestion = any(kw in nq for kw in [
        "lam gi", "nen lam", "co nen", "suggest", "goi y", "the nao",
    ]) and any(t in nq for t in [
        "hom nay", "chieu nay", "toi nay", "sang nay", "trua nay",
        "sang mai", "chieu mai", "toi mai", "mai", "tuan",
    ])

    if is_suggestion:
        print(f"[NaturalInput] SUGGESTION: {text!r}")
        try:
            from jarvis.suggester import build_suggestion_embed
            embed = await asyncio.to_thread(
                build_suggestion_embed,
                str(message.author.id),
                message.author.display_name,
                text,
            )
            await message.channel.send(embed=embed)
            return
        except Exception as e:
            print(f"[NaturalInput] Suggestion error: {e}")
            import traceback
            traceback.print_exc()
            return

    result = await asyncio.to_thread(classify, text)
    intent = result["intent"]
    conf = result["confidence"]

    print(f"[NaturalInput] {message.author.display_name}: {text!r} -> {intent} ({conf})")

    # Ignore low confidence
    if intent == "ignore":
        return

    # Schedule -> parse + add
    if intent == "schedule":
        # Tao fake ctx de reuse _do_add
        class FakeCtx:
            def __init__(self, message, bot):
                self.author = message.author
                self.channel = message.channel
                self.guild = message.guild
                self.message = message
                self.bot = bot
            async def send(self, content=None, embed=None, view=None, **kw):
                if embed or view:
                    return await self.channel.send(content=content, embed=embed, view=view)
                return await self.channel.send(content=content)
        ctx = FakeCtx(message, bot)
        try:
            await do_add_fn(ctx, text, force_ai=False)
        except Exception as e:
            print(f"[NaturalInput] _do_add error: {e}")
            await message.add_reaction("❌")
        return

    # Context (sick/tired) -> advisor
    if intent == "context":
        try:
            from jarvis.advisor import analyze as advisor_analyze
            from jarvis.commands import _show_advisor  # optional
        except Exception:
            pass

        try:
            from jarvis.advisor import analyze as advisor_analyze
            # Fake ctx
            class FakeCtx2:
                def __init__(self, message, bot):
                    self.author = message.author
                    self.channel = message.channel
                    self.guild = message.guild
                    self.message = message
                    self.bot = bot
                async def send(self, content=None, embed=None, view=None, **kw):
                    return await self.channel.send(content=content, embed=embed, view=view)
            ctx2 = FakeCtx2(message, bot)
            ctx_result = await asyncio.to_thread(advisor_analyze, str(message.author.id), text)
            if ctx_result:
                from jarvis.interactive import build_conflict_embed
                import discord as _d
                # Reuse _show_advisor neu co
                try:
                    from jarvis.commands import _show_advisor
                    await _show_advisor(ctx2, ctx_result, text)
                except ImportError:
                    # Fallback: simple embed
                    advice = ctx_result.get("advice", "")
                    embed = _d.Embed(
                        title=pers.get("context_" + ctx_result["context"]["context_type"],
                                       default="") or "JARVIS ADVISOR",
                        description=advice,
                        color=_d.Color.orange(),
                    )
                    await message.channel.send(embed=embed)
        except Exception as e:
            print(f"[NaturalInput] context error: {e}")
        return

    # Query -> route to !j list/today
    if intent == "query":
        try:
            from jarvis.commands import _fmt_event
        except Exception:
            pass
        try:
            from jarvis import event_manager as em
            events = await asyncio.to_thread(em.get_today_events, str(message.author.id))
            if not events:
                await message.channel.send(pers.get("empty_today"))
                return
            lines = [f"# {pers.get('list_intro')}\n"]
            for ev in events:
                from jarvis.commands import _fmt_event
                lines.append(_fmt_event(ev))
            await message.channel.send("\n".join(lines))
        except Exception as e:
            print(f"[NaturalInput] query error: {e}")
        return

    # Chat -> simple reply
    if intent == "chat":
        from jarvis.intent import _norm
        t = _norm(text)

        # Check greeting/thanks sau khi normalize
        if any(w in t for w in ["cam on", "thank", "thanks", "cam on ban", "cam on em"]):
            reply = pers.get("thanks")
        elif any(w in t for w in ["xin chao", "chao", "hello", "hi", "hey", "helo"]):
            h = datetime.now().hour
            if h < 12:
                reply = pers.get("greeting_morning")
            elif h < 18:
                reply = pers.get("greeting_general")
            else:
                reply = pers.get("greeting_evening")
        else:
            reply = pers.get("unknown")
        await message.channel.send(reply)
        return