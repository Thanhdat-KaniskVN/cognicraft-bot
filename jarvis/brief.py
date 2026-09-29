# jarvis/brief.py
"""Proactive daily brief - Morning (6h) + Evening (21h)."""
from datetime import datetime, timedelta
import pytz
import discord

from jarvis import event_manager as em
from jarvis import personality as pers
from jarvis.conflict_detector import _parse_dt

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

ICONS = {
    "gym": "GYM", "run": "RUN", "bike": "BIKE", "swim": "SWIM", "yoga": "YOGA",
    "class": "CLASS", "exam": "EXAM", "meeting": "MEET",
    "study": "STUDY", "task": "TASK", "other": "TASK",
}


def _today_events(user_id):
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = em.list_events(user_id=user_id, days_ahead=1)
    result = []
    for ev in events:
        try:
            ev_start = _parse_dt(ev["start_time"])
            if start <= ev_start < end:
                result.append(ev)
        except Exception:
            continue
    return sorted(result, key=lambda e: _parse_dt(e["start_time"]))


def _tomorrow_events(user_id):
    now = datetime.now(TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day_after = tomorrow + timedelta(days=1)
    events = em.list_events(user_id=user_id, days_ahead=2)
    result = []
    for ev in events:
        try:
            ev_start = _parse_dt(ev["start_time"])
            if tomorrow <= ev_start < day_after:
                result.append(ev)
        except Exception:
            continue
    return sorted(result, key=lambda e: _parse_dt(e["start_time"]))


def build_morning_brief(user_id, member):
    """Build morning brief embed."""
    events = _today_events(user_id)
    hour = datetime.now(TZ).hour

    if hour < 12:
        greet = pers.get("greeting_morning")
    else:
        greet = pers.get("greeting_general")

    embed = discord.Embed(
        title=f"Good morning, {member}",
        description=greet,
        color=discord.Color.gold(),
    )

    if not events:
        embed.add_field(
            name="Today",
            value="Nothing on the agenda, sir. A rare pleasure.",
            inline=False,
        )
    else:
        lines = []
        for ev in events:
            start = _parse_dt(ev["start_time"])
            icon = ICONS.get(ev.get("event_type", "task"), "TASK")
            time_str = start.strftime("%H:%M")
            lines.append(f"`{time_str}` {icon} **{ev['title']}**")
        embed.add_field(
            name=f"Today ({len(events)} events)",
            value="\n".join(lines[:15]),
            inline=False,
        )

        # Next event
        now = datetime.now(TZ)
        upcoming = [e for e in events if _parse_dt(e["start_time"]) > now]
        if upcoming:
            nxt = upcoming[0]
            nxt_start = _parse_dt(nxt["start_time"])
            delta_min = int((nxt_start - now).total_seconds() / 60)
            embed.add_field(
                name="Next up",
                value=f"**{nxt['title']}** in `{delta_min} min` ({nxt_start.strftime('%H:%M')})",
                inline=False,
            )

    # Pending tasks check
    now = datetime.now(TZ)
    overdue = []
    for ev in events:
        try:
            if _parse_dt(ev["start_time"]) < now and ev.get("status") == "scheduled":
                overdue.append(ev)
        except Exception:
            continue
    if overdue:
        embed.add_field(
            name="Pending",
            value=f"You have **{len(overdue)}** unmarked events from earlier, sir.",
            inline=False,
        )

    embed.set_footer(text="JARVIS - Your day at a glance")
    return embed


def build_evening_review(user_id, member):
    """Build evening review embed."""
    today = _today_events(user_id)
    tomorrow = _tomorrow_events(user_id)
    now = datetime.now(TZ)

    embed = discord.Embed(
        title=f"Good evening, {member}",
        description="Your day in review, sir.",
        color=discord.Color.dark_blue(),
    )

    if today:
        done = [e for e in today if e.get("status") == "done"]
        pending = [e for e in today if e.get("status") == "scheduled"]
        embed.add_field(
            name=f"Today's Summary",
            value=(
                f"Completed: **{len(done)}**\n"
                f"Pending: **{len(pending)}**\n"
                f"Total: **{len(today)}**"
            ),
            inline=False,
        )

        if pending:
            lines = []
            for ev in pending[:5]:
                start = _parse_dt(ev["start_time"])
                icon = ICONS.get(ev.get("event_type", "task"), "TASK")
                lines.append(f"`{start.strftime('%H:%M')}` {icon} {ev['title']}")
            embed.add_field(
                name="Unfinished",
                value="\n".join(lines),
                inline=False,
            )
    else:
        embed.add_field(name="Today", value="No events today, sir.", inline=False)

    if tomorrow:
        lines = []
        for ev in tomorrow[:5]:
            start = _parse_dt(ev["start_time"])
            icon = ICONS.get(ev.get("event_type", "task"), "TASK")
            lines.append(f"`{start.strftime('%H:%M')}` {icon} {ev['title']}")
        embed.add_field(
            name=f"Tomorrow ({len(tomorrow)} events)",
            value="\n".join(lines),
            inline=False,
        )

    embed.set_footer(text="Rest well, sir. JARVIS will be here.")
    return embed


async def send_morning_brief(bot, user_ids):
    """Send morning brief to list of users."""
    sent = 0
    for uid in user_ids:
        try:
            user = await bot.fetch_user(int(uid))
            embed = build_morning_brief(uid, user.display_name)
            await user.send(embed=embed)
            sent += 1
            print(f"[Brief] Morning sent to {user.display_name}")
        except discord.Forbidden:
            print(f"[Brief] User {uid} closed DM")
        except Exception as e:
            print(f"[Brief] Error {uid}: {e}")
    return sent


async def send_evening_review(bot, user_ids):
    sent = 0
    for uid in user_ids:
        try:
            user = await bot.fetch_user(int(uid))
            embed = build_evening_review(uid, user.display_name)
            await user.send(embed=embed)
            sent += 1
            print(f"[Brief] Evening sent to {user.display_name}")
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[Brief] Error {uid}: {e}")
    return sent


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("=" * 60)
    print("BRIEF TEST")
    print("=" * 60)

    TEST_UID = "test_brief_999"
    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])

    now = datetime.now(TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    em.create_event(TEST_UID, "T", "Gym", "gym", tomorrow, tomorrow + timedelta(hours=1))
    em.create_event(TEST_UID, "T", "Hop nhom", "meeting",
                    tomorrow + timedelta(hours=2), tomorrow + timedelta(hours=3))

    # Test morning (buil tomorrow, khong phai today)
    tonight = now.replace(hour=21, minute=0, second=0, microsecond=0)
    em.create_event(TEST_UID, "T", "Hoc Python", "class",
                    tonight, tonight + timedelta(hours=1))

    # Morning brief
    embed_m = build_morning_brief(TEST_UID, "DatPT")
    print("\n[MORNING BRIEF]")
    print(f"  Title: {embed_m.title}")
    for field in embed_m.fields:
        print(f"  {field.name}:")
        print(f"    {field.value[:200]}")

    # Evening
    embed_e = build_evening_review(TEST_UID, "DatPT")
    print("\n[EVENING REVIEW]")
    print(f"  Title: {embed_e.title}")
    for field in embed_e.fields:
        print(f"  {field.name}:")
        print(f"    {field.value[:200]}")

    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])
    print("\n[Cleanup] Done")