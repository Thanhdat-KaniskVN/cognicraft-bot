# jarvis/reminder.py
"""JARVIS Reminder - check + send DM before events (30/15/5 min)."""
from datetime import datetime, timedelta
import pytz
import discord

from jarvis import event_manager as em

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

ICONS = {
    "gym": "GYM", "run": "RUN", "bike": "BIKE", "swim": "SWIM", "yoga": "YOGA",
    "class": "CLASS", "exam": "EXAM", "meeting": "MEET",
    "study": "STUDY", "task": "TASK", "other": "OTHER",
}

REMINDER_MINUTES = [30, 15, 5]


def _fmt_dt(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    else:
        dt = dt.astimezone(TZ)
    return dt.strftime("%H:%M %a %d/%m")


def _build_dm(ev, minutes_before, knowledge_link=None, minutes_until=None):
    icon = ICONS.get(ev.get("event_type", "task"), "TASK")
    start = ev.get("start_time")
    title = ev.get("title", "?")
    etype = ev.get("event_type", "task")

    # Dung minutes_until (thuc te) neu co, khong thi fallback config
    display_min = int(minutes_until) if minutes_until is not None else minutes_before

    urgency = "NGAY" if display_min <= 5 else (
        "SAP TOI" if display_min <= 15 else "NHAC NHO"
    )

    content = f"**[{urgency}] Con {display_min} phut** truoc su kien:"
    embed = discord.Embed(
        title=f"{icon} {title}",
        description=f"Bat dau luc **{_fmt_dt(start)}**",
        color=(
            discord.Color.red() if display_min <= 5
            else discord.Color.orange() if display_min <= 15
            else discord.Color.blue()
        ),
    )
    embed.add_field(name="Loai", value=f"`{etype}`", inline=True)
    embed.add_field(name="Con lai", value=f"`{display_min} phut`", inline=True)

    if ev.get("location"):
        embed.add_field(name="Dia diem", value=ev["location"], inline=False)

    if knowledge_link:
        embed.add_field(name="Tai lieu", value=knowledge_link[:1000], inline=False)

    hints = {
        "class": "Chuan bi vo, but, tai lieu",
        "exam": "Check lai kien thuc quan trong, ngu du",
        "meeting": "Doc lai agenda + notes lan truoc",
        "gym": "Mang theo nuoc + khan",
        "run": "Khoi dong 5 phut truoc khi chay",
    }
    if etype in hints:
        embed.add_field(name="Tip", value=hints[etype], inline=False)

    return content, embed


async def check_and_send(bot):
    sent = []
    pending = em.get_pending_reminders(within_minutes=35)

    if not pending:
        return sent

    for ev in pending:
        minutes_until = ev.get("minutes_until", 0)
        if minutes_until is None:
            continue
        try:
            minutes_until = float(minutes_until)
        except (TypeError, ValueError):
            continue

        # Skip event qua khu (da bat dau)
        if minutes_until < 0:
            continue

        for mb in REMINDER_MINUTES:
            if minutes_until > mb:
                continue
            if em.was_reminded(ev["id"], mb):
                continue

            user_id = ev["user_id"]
            try:
                user = await bot.fetch_user(int(user_id))
            except Exception as e:
                print(f"[Reminder] Cannot fetch user {user_id}: {e}")
                continue

            # ATOMIC: log truoc khi send (dam bao khong duplicate)
            if not em.log_reminder(ev["id"], user_id, mb, channel="dm"):
                # log fail = da co reminder nay roi
                continue

            content, embed = _build_dm(
                ev, mb, ev.get("knowledge_link"),
                minutes_until=minutes_until,
            )

            try:
                await user.send(content=content, embed=embed)
                sent.append((user_id, mb, ev["id"]))
                print(f"[Reminder] Sent DM {user_id} - {mb}p (actual {minutes_until:.0f}p) - {ev['title']}")
            except discord.Forbidden:
                print(f"[Reminder] User {user_id} closed DM")
            except Exception as e:
                print(f"[Reminder] Send error: {e}")

    return sent


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from datetime import datetime, timedelta
    print("=" * 60)
    print("REMINDER TEST (dry)")
    print("=" * 60)

    TEST_UID = "test_reminder_999"
    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])

    now = datetime.now(TZ)
    ev_id = em.create_event(
        TEST_UID, "TestUser", "Hoc mon ADP", "class",
        now + timedelta(minutes=20),
    )
    print(f"[Setup] Created #{ev_id} starting in 20 min")

    pending = em.get_pending_reminders(within_minutes=35)
    my = [p for p in pending if p["user_id"] == TEST_UID]
    print(f"[Check] {len(my)} pending")
    for p in my:
        print(f"  - #{p['id']} {p['title']} in {p.get('minutes_until'):.1f} min")

    em.delete_event(ev_id)
    print("[Cleanup] Done")