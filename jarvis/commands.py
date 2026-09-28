# jarvis/commands.py
"""JARVIS commands - Wire into bot.py."""
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import pytz

from jarvis.ai_parser import parse_event_smart_async
from jarvis import event_manager as em

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

EVENT_ICONS = {
    "gym": "🏋️", "run": "🏃", "bike": "🚴", "swim": "🏊", "yoga": "🧘",
    "class": "🎓", "exam": "📝", "meeting": "👥",
    "study": "📚", "task": "✅", "other": "📌",
}


def _fmt_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    else:
        dt = dt.astimezone(TZ)
    return dt.strftime("%H:%M %a %d/%m")


def _fmt_event(ev: dict) -> str:
    icon = EVENT_ICONS.get(ev.get("event_type", "task"), "📌")
    start = ev.get("start_time")
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    time_str = _fmt_time(start)
    extras = []
    if ev.get("distance_km"):
        extras.append(f"{ev['distance_km']}km")
    if ev.get("location"):
        extras.append(f"@ {ev['location']}")
    extra_str = f" ({', '.join(extras)})" if extras else ""
    return f"`#{ev['id']}` {icon} **{time_str}** — {ev['title']}{extra_str}"


async def _parse_and_add(ctx, text: str, force_ai: bool = False):
    """Helper: parse text -> event -> save DB -> reply."""
    user_id = str(ctx.author.id)
    member = ctx.author.display_name

    msg = await ctx.send(f"🔍 Đang phân tích: `{text}`...")

    parsed = await parse_event_smart_async(text, force_ai=force_ai)
    if parsed is None or parsed.start_time is None:
        await msg.edit(content=f"❌ Không parse được: `{text}`")
        return

    ev_id = em.create_event(
        user_id=user_id,
        member=member,
        title=parsed.title,
        event_type=parsed.event_type,
        start_time=parsed.start_time,
        end_time=parsed.end_time,
        location=parsed.location,
        priority="normal",
    )

    source = getattr(parsed, "_source", "?")

    embed = discord.Embed(
        title=f"✅ Đã thêm event #{ev_id}",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="📌 Event",
        value=f"{EVENT_ICONS.get(parsed.event_type, '📌')} **{parsed.title}**",
        inline=False,
    )
    embed.add_field(name="🕐 Bắt đầu", value=_fmt_time(parsed.start_time), inline=True)
    embed.add_field(name="🕓 Kết thúc", value=_fmt_time(parsed.end_time), inline=True)
    embed.add_field(name="⏱️ Thời lượng", value=f"{parsed.duration_min} phút", inline=True)
    if parsed.distance_km:
        embed.add_field(name="📏 Quãng đường", value=f"{parsed.distance_km} km", inline=True)
    if parsed.location:
        embed.add_field(name="📍 Địa điểm", value=parsed.location, inline=True)
    embed.add_field(name="🔧 Parse by", value=f"`{source}`", inline=True)
    embed.set_footer(text=f"ID: {ev_id} | !cancel_event {ev_id} để huỷ")

    await msg.edit(content=None, embed=embed)


def setup_jarvis_commands(bot, is_admin):
    """Register tat ca JARVIS commands."""

    # ============ !add_event ============
    @bot.command(name="add_event")
    async def add_event_cmd(ctx, *, text: str = None):
        """Thêm event: !add_event mai 6h chạy bộ 5km"""
        if not text:
            await ctx.send(
                "**Cách dùng:** `!add_event <mô tả>`\n"
                "**Ví dụ:**\n"
                "• `!add_event mai 6h chạy bộ 5km`\n"
                "• `!add_event tối nay gym 7h`\n"
                "• `!add_event 3h chiều thứ 4 họp nhóm`"
            )
            return
        await _parse_and_add(ctx, text)

    # ============ !add_event_ai (force AI) ============
    @bot.command(name="add_event_ai")
    async def add_event_ai_cmd(ctx, *, text: str = None):
        """Force AI parse: !add_event_ai sau khi ăn trưa đi bơi"""
        if not text:
            await ctx.send("**Cách dùng:** `!add_event_ai <mô tả>` (force AI)")
            return
        await _parse_and_add(ctx, text, force_ai=True)

    # ============ !list_events ============
    @bot.command(name="list_events")
    async def list_events_cmd(ctx, days: int = 7, member: str = None):
        """List events 7 ngày tới. !list_events 14 để xem 14 ngày."""
        if member:
            user_id = None  # TODO: lookup by name
        else:
            user_id = None  # Show all của mình? -> default chỉ của mình
            
        # Default: chỉ show của mình
        user_id = str(ctx.author.id) if not member else None

        events = em.list_events(user_id=user_id, days_ahead=days)
        if not events:
            await ctx.send(f"📭 Không có event nào trong {days} ngày tới.")
            return

        lines = [f"# 📅 EVENTS — {days} ngày tới\n"]
        current_day = None
        for ev in events:
            start = ev["start_time"]
            if isinstance(start, str):
                start = datetime.fromisoformat(start)
            if start.tzinfo is None:
                start = TZ.localize(start)
            else:
                start = start.astimezone(TZ)
            day_label = start.strftime("%A %d/%m/%Y")
            if day_label != current_day:
                lines.append(f"\n**📆 {day_label}**")
                current_day = day_label
            lines.append(_fmt_event(ev))

        # Split if too long
        text = "\n".join(lines)
        if len(text) > 1900:
            chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(text)

    # ============ !today ============
    @bot.command(name="today")
    async def today_cmd(ctx):
        """Xem events hôm nay."""
        user_id = str(ctx.author.id)
        events = em.get_today_events(user_id=user_id)
        if not events:
            await ctx.send("📭 Hôm nay không có event nào.")
            return
        lines = ["# 📅 HÔM NAY\n"]
        for ev in events:
            lines.append(_fmt_event(ev))
        await ctx.send("\n".join(lines))

    # ============ !cancel_event ============
    @bot.command(name="cancel_event")
    async def cancel_event_cmd(ctx, event_id: int):
        """Huỷ event: !cancel_event 5"""
        ev = em.get_event(event_id)
        if not ev:
            await ctx.send(f"❌ Không tìm thấy event #{event_id}.")
            return
        if ev["user_id"] != str(ctx.author.id) and not is_admin(ctx):
            await ctx.send("❌ Chỉ owner hoặc admin mới huỷ được.")
            return
        em.cancel_event(event_id)
        await ctx.send(f"✅ Đã huỷ event #{event_id}: **{ev['title']}**")

    # ============ !done_event ============
    @bot.command(name="done_event")
    async def done_event_cmd(ctx, event_id: int):
        """Đánh dấu done: !done_event 5"""
        ev = em.get_event(event_id)
        if not ev:
            await ctx.send(f"❌ Không tìm thấy event #{event_id}.")
            return
        if ev["user_id"] != str(ctx.author.id) and not is_admin(ctx):
            await ctx.send("❌ Chỉ owner hoặc admin.")
            return
        em.mark_done(event_id)
        await ctx.send(f"✅ Done event #{event_id}: **{ev['title']}**")

    # ============ !delete_event ============
    @bot.command(name="delete_event")
    async def delete_event_cmd(ctx, event_id: int):
        """Xoá vĩnh viễn (admin): !delete_event 5"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ admin mới xoá vĩnh viễn.")
            return
        ev = em.get_event(event_id)
        if not ev:
            await ctx.send(f"❌ Không tìm thấy event #{event_id}.")
            return
        em.delete_event(event_id)
        await ctx.send(f"✅ Đã xoá event #{event_id}: **{ev['title']}**")

    # ============ !event_stats ============
    @bot.command(name="event_stats")
    async def event_stats_cmd(ctx):
        """Stats cá nhân."""
        stats = em.get_event_stats(str(ctx.author.id))
        embed = discord.Embed(title="📊 EVENT STATS", color=discord.Color.blue())
        embed.add_field(name="⏰ Upcoming", value=stats.get("upcoming", 0), inline=True)
        embed.add_field(name="✅ Done", value=stats.get("done", 0), inline=True)
        embed.add_field(name="❌ Cancelled", value=stats.get("cancelled", 0), inline=True)
        embed.add_field(name="📅 Hôm nay", value=stats.get("today", 0), inline=True)
        await ctx.send(embed=embed)

    print("[JARVIS] ✅ 7 commands registered: add_event, add_event_ai, list_events, today, cancel_event, done_event, delete_event, event_stats")