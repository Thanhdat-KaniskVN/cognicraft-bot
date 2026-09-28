# jarvis/commands.py
"""JARVIS - 1 command !j voi subcommands."""
import asyncio
import discord
from datetime import datetime, timedelta
import pytz

from jarvis.ai_parser import parse_event_smart_async
from jarvis.multi_parser import parse_multi_events
from jarvis import event_manager as em
from jarvis.advisor import analyze as advisor_analyze

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

ICONS = {
    "gym": "GYM", "run": "RUN", "bike": "BIKE", "swim": "SWIM", "yoga": "YOGA",
    "class": "CLASS", "exam": "EXAM", "meeting": "MEET",
    "study": "STUDY", "task": "TASK", "other": "OTHER",
}

HELP_TEXT = """JARVIS - Schedule Manager

Add events (multi-event + AI fallback):
  !j sang mai chay bo 5h sang roi hoc adp 7h30-1h chieu
  !j toi nay gym 7h va hoc bai 9h
  !j mai 6h chay 5km, 8h hoc, 5h chieu gym

Xem events:
  !j           -> hom nay
  !j list      -> 7 ngay toi
  !j list 30   -> 30 ngay toi

Actions:
  !j done 5       -> danh dau xong #5
  !j cancel 5     -> huy #5
  !j delete 5     -> xoa (admin)
  !j stats        -> thong ke

Force AI parse:
  !j ai sau khi an trua xong di boi 30 phut
"""


def _fmt_time(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    else:
        dt = dt.astimezone(TZ)
    return dt.strftime("%H:%M %a %d/%m")


def _fmt_event(ev):
    icon = ICONS.get(ev.get("event_type", "task"), "TASK")
    start = ev.get("start_time")
    end = ev.get("end_time")
    extras = []
    if ev.get("distance_km"):
        extras.append(f"{ev['distance_km']}km")
    if ev.get("location"):
        extras.append(ev["location"])
    extra = f" - {', '.join(extras)}" if extras else ""
    if end:
        end_str = _fmt_time(end).split()[0]
        time_str = f"{_fmt_time(start)} -> {end_str}"
    else:
        time_str = _fmt_time(start)
    return f"`#{ev['id']}` {icon} {time_str} **{ev['title']}**{extra}"


async def _show_advisor(ctx, result, raw_text):
    """Hien thi advisor report."""
    import discord
    ctx_info = result["context"]
    sev = result["severity"]

    sev_icon = {"critical": "CRITICAL", "high": "HIGH", "medium": "MED", "low": "LOW"}.get(sev, "?")
    color_map = {"critical": 0xE74C3C, "high": 0xE67E22, "medium": 0xF1C40F, "low": 0x2ECC71}
    color = color_map.get(sev, 0x3498DB)

    src = result.get("advice_source", "?")
    src_icon = "AI" if src == "ai" else "RULE"

    embed = discord.Embed(
        title=f"JARVIS ADVISOR - {sev_icon}",
        description=result.get("advice", ""),
        color=color,
    )
    embed.add_field(
        name="Context",
        value=f"`{ctx_info['context_type']}` | `{sev}` | via `{src_icon}`",
        inline=False,
    )

    tip = result.get("tip", "")
    if tip:
        embed.add_field(name="Tip", value=tip[:500], inline=False)

    resch = result.get("reschedule_suggestion", "")
    if resch:
        embed.add_field(name="Goi y doi lich", value=f"`{resch}`", inline=False)

    actions = result.get("actions", [])
    if not actions:
        embed.add_field(name="Events", value="Khong co event nao sap toi", inline=False)
        await ctx.send(embed=embed)
        return

    keep = [a for a in actions if a["action"] == "keep"]
    move = [a for a in actions if a["action"] == "reschedule"]
    cancel = [a for a in actions if a["action"] == "cancel"]

    if cancel:
        txt = "\n".join(f"`#{a['event']['id']}` {a['event']['title']} (score {a['score']})" for a in cancel[:5])
        embed.add_field(name=f"NEN HUY ({len(cancel)})", value=txt[:1000], inline=False)

    if move:
        txt = "\n".join(f"`#{a['event']['id']}` {a['event']['title']} (score {a['score']})" for a in move[:5])
        embed.add_field(name=f"NEN DOI ({len(move)})", value=txt[:1000], inline=False)

    if keep:
        txt = "\n".join(f"`#{a['event']['id']}` {a['event']['title']} (score {a['score']})" for a in keep[:5])
        embed.add_field(name=f"GIU LAI ({len(keep)})", value=txt[:1000], inline=False)

    embed.set_footer(text="Go `!j cancel <id>` de huy tung event")
    await ctx.send(embed=embed)


async def _do_add(ctx, text, force_ai=False):
    user_id = str(ctx.author.id)
    member = ctx.author.display_name

    msg = await ctx.send("Dang phan tich...")

    events = []
    if force_ai:
        parsed = await parse_event_smart_async(text, force_ai=True)
        if parsed and parsed.start_time:
            events = [parsed]
    else:
        events = await asyncio.to_thread(parse_multi_events, text)
        if len(events) <= 1:
            parsed = await parse_event_smart_async(text)
            if parsed and parsed.start_time:
                events = [parsed]

    if not events:
        await msg.edit(content=f"Khong parse duoc: `{text}`")
        return

    # DEBUG: log tung event
    for i, ev in enumerate(events, 1):
        print(f"[JARVIS DEBUG] event[{i}] {ev.title!r} start={ev.start_time} src={getattr(ev, '_source', '?')}")

    saved = []
    for ev in events:
        ev_id = await asyncio.to_thread(
            em.create_event,
            user_id, member,
            ev.title, ev.event_type,
            ev.start_time, ev.end_time,
            ev.location,
        )
        if ev_id:
            saved.append((ev_id, ev))

    if not saved:
        await msg.edit(content="Loi khi luu event.")
        return

    lines = []
    for ev_id, ev in saved:
        icon = ICONS.get(ev.event_type, "TASK")
        end_str = ev.end_time.strftime("%H:%M") if ev.end_time else "?"
        extras = []
        if ev.distance_km:
            extras.append(f"{ev.distance_km}km")
        if ev.duration_min:
            extras.append(f"{ev.duration_min}p")
        extra = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"`#{ev_id}` {icon} **{_fmt_time(ev.start_time)} -> {end_str}** - {ev.title}{extra}")

    embed = discord.Embed(
        title=f"Da them {len(saved)} event",
        description="\n".join(lines),
        color=discord.Color.green(),
    )
    embed.set_footer(text="!j de xem hom nay | !j help")
    await msg.edit(content=None, embed=embed)


def setup_jarvis_commands(bot, is_admin):

    @bot.command(name="j")
    async def j_cmd(ctx, *, args: str = None):
        """JARVIS. Go !j help de xem huong dan."""
        if not args or args.strip() == "":
            events = await asyncio.to_thread(em.get_today_events, str(ctx.author.id))
            if not events:
                await ctx.send("Hom nay khong co event. Go `!j help`.")
                return
            lines = ["# HOM NAY\n"]
            for ev in events:
                lines.append(_fmt_event(ev))
            await ctx.send("\n".join(lines))
            return

        a = args.strip()
        al = a.lower()

        if not al.startswith(("list", "stats", "cancel", "done", "delete", "help", "ai ")):
            ctx_result = await asyncio.to_thread(advisor_analyze, str(ctx.author.id), a)
            if ctx_result:
                await _show_advisor(ctx, ctx_result, a)
                return

        if al in ("help", "?", "-h"):
            await ctx.send(HELP_TEXT)
            return

        if al == "list" or al.startswith("list "):
            parts = al.split()
            days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7
            events = await asyncio.to_thread(em.list_events, str(ctx.author.id), days, None, "scheduled")
            if not events:
                await ctx.send(f"Khong co event nao trong {days} ngay toi.")
                return
            lines = [f"# {days} NGAY TOI\n"]
            cur_day = None
            for ev in events:
                start = ev["start_time"]
                if isinstance(start, str):
                    start = datetime.fromisoformat(start)
                if start.tzinfo is None:
                    start = TZ.localize(start)
                else:
                    start = start.astimezone(TZ)
                label = start.strftime("%A %d/%m")
                if label != cur_day:
                    lines.append(f"\n**{label}**")
                    cur_day = label
                lines.append(_fmt_event(ev))
            txt = "\n".join(lines)
            for chunk in [txt[i:i+1900] for i in range(0, len(txt), 1900)]:
                await ctx.send(chunk)
            return

        if al == "stats":
            s = await asyncio.to_thread(em.get_event_stats, str(ctx.author.id))
            embed = discord.Embed(title="JARVIS STATS", color=discord.Color.blue())
            embed.add_field(name="Upcoming", value=s.get("upcoming", 0))
            embed.add_field(name="Done", value=s.get("done", 0))
            embed.add_field(name="Cancelled", value=s.get("cancelled", 0))
            embed.add_field(name="Hom nay", value=s.get("today", 0))
            await ctx.send(embed=embed)
            return

        for action in ("cancel", "done", "delete"):
            if al.startswith(action + " "):
                parts = a.split()
                try:
                    ev_id = int(parts[1])
                except (IndexError, ValueError):
                    await ctx.send(f"Cu phap: `!j {action} <id>`")
                    return
                ev = await asyncio.to_thread(em.get_event, ev_id)
                if not ev:
                    await ctx.send(f"Khong tim thay event #{ev_id}")
                    return
                if ev["user_id"] != str(ctx.author.id) and not is_admin(ctx):
                    await ctx.send("Khong co quyen.")
                    return
                if action == "cancel":
                    await asyncio.to_thread(em.cancel_event, ev_id)
                    await ctx.send(f"Da huy #{ev_id}: **{ev['title']}**")
                elif action == "done":
                    await asyncio.to_thread(em.mark_done, ev_id)
                    await ctx.send(f"Done #{ev_id}: **{ev['title']}**")
                elif action == "delete":
                    if not is_admin(ctx):
                        await ctx.send("Chi admin moi xoa duoc.")
                        return
                    await asyncio.to_thread(em.delete_event, ev_id)
                    await ctx.send(f"Da xoa #{ev_id}: **{ev['title']}**")
                return

        if al.startswith("ai "):
            await _do_add(ctx, a[3:].strip(), force_ai=True)
            return

        await _do_add(ctx, a, force_ai=False)

    print("[JARVIS] OK - 1 main command '!j' registered")
