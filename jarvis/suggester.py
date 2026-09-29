# jarvis/suggester.py
"""Smart suggestions - "chieu nay lam gi?" + habit analysis."""
from datetime import datetime, timedelta
from collections import Counter
import pytz

from jarvis import event_manager as em
from jarvis.conflict_detector import _parse_dt

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

ICONS = {
    "gym": "GYM", "run": "RUN", "bike": "BIKE", "swim": "SWIM", "yoga": "YOGA",
    "class": "CLASS", "exam": "EXAM", "meeting": "MEET",
    "study": "STUDY", "task": "TASK", "other": "TASK",
}


def get_habits(user_id, weeks=4):
    """Phan tich habit tu events 4 tuan qua."""
    now = datetime.now(TZ)
    start = now - timedelta(weeks=weeks)

    # Get ALL events 4 tuan (past + future 1 week)
    events = em.list_events(user_id=user_id, days_ahead=7)
    # Need past events too - manual query
    from database import get_cursor
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM jarvis_events
            WHERE user_id = %s
              AND start_time >= %s
              AND start_time <= %s
            ORDER BY start_time
        """, (user_id, start, now + timedelta(days=7)))
        rows = cur.fetchall()
    all_events = [dict(r) for r in rows]

    if not all_events:
        return {"total": 0, "by_type": {}, "by_hour": {}, "by_weekday": {}, "top_activities": []}

    # Analyze
    type_counter = Counter()
    hour_counter = Counter()
    weekday_counter = Counter()

    for ev in all_events:
        try:
            ev_start = _parse_dt(ev["start_time"])
        except Exception:
            continue

        ev_type = ev.get("event_type", "other")
        type_counter[ev_type] += 1
        hour_counter[ev_start.hour] += 1
        weekday_counter[ev_start.weekday()] += 1

    top_activities = []
    for ev_type, count in type_counter.most_common(5):
        top_activities.append({"type": ev_type, "count": count})

    return {
        "total": len(all_events),
        "by_type": dict(type_counter),
        "by_hour": dict(hour_counter),
        "by_weekday": dict(weekday_counter),
        "top_activities": top_activities,
    }


def suggest_time_slot(user_id, target_date=None):
    """Suggest what to do in free time slot."""
    now = datetime.now(TZ)
    if target_date is None:
        target_date = now.date()

    # Events on target day
    events = em.list_events(user_id=user_id, days_ahead=7)
    day_start = TZ.localize(datetime.combine(target_date, datetime.min.time()))
    day_end = day_start + timedelta(days=1)

    day_events = []
    for ev in events:
        try:
            ev_start = _parse_dt(ev["start_time"])
            ev_end = _parse_dt(ev["end_time"]) if ev.get("end_time") else ev_start + timedelta(hours=1)
            if day_start <= ev_start < day_end:
                day_events.append((ev_start, ev_end, ev))
        except Exception:
            continue

    day_events.sort(key=lambda x: x[0])

    # Find free slots 14:00-22:00 today
    if target_date == now.date():
        cursor = max(now, TZ.localize(datetime.combine(target_date, datetime.min.time().replace(hour=14))))
    else:
        cursor = TZ.localize(datetime.combine(target_date, datetime.min.time().replace(hour=14)))

    end_of_day = TZ.localize(datetime.combine(target_date, datetime.min.time().replace(hour=22)))

    free_slots = []
    for ev_start, ev_end, ev in day_events:
        if ev_start <= cursor:
            cursor = max(cursor, ev_end)
            continue
        if ev_start > cursor:
            duration = int((ev_start - cursor).total_seconds() / 60)
            if duration >= 30:
                free_slots.append({"start": cursor, "end": ev_start, "duration": duration})
        cursor = max(cursor, ev_end)

    if cursor < end_of_day:
        duration = int((end_of_day - cursor).total_seconds() / 60)
        if duration >= 30:
            free_slots.append({"start": cursor, "end": end_of_day, "duration": duration})

    # Get habit-based suggestions
    habits = get_habits(user_id)

    suggestions = []
    if free_slots:
        # Priority: pending tasks first, then habits
        pending = [e for e in day_events if e[2].get("status") == "scheduled"
                   and e[1] < now]
        if pending:
            for _, _, ev in pending[:2]:
                suggestions.append({
                    "activity": ev["title"],
                    "reason": "Overdue",
                    "icon": ICONS.get(ev.get("event_type"), "TASK"),
                })

        # Habit suggestions - pick top 2 bat ky (task/study/gym)
        for item in habits["top_activities"][:3]:
            ev_type = item["type"]
            count = item["count"]
            if ev_type == "other":
                continue
            suggestions.append({
                "activity": ev_type.upper(),
                "reason": f"Habit ({count}x in last 4 weeks)",
                "icon": ICONS.get(ev_type, "?"),
            })
            if len(suggestions) >= 2:
                break

        # Fallback generic
        if not suggestions:
            suggestions.append({
                "activity": "Review pending tasks",
                "reason": "No habit pattern yet",
                "icon": "TASK",
            })

    return {
        "free_slots": free_slots[:3],
        "suggestions": suggestions[:3],
        "habits": habits,
        "day_events": [(e[0], e[1], e[2]) for e in day_events],
    }


def build_suggestion_embed(user_id, member, query_text=""):
    """Build embed cho "chieu nay lam gi?" query."""
    import discord
    now = datetime.now(TZ)

    # Detect target day from query
    from jarvis.intent import _norm
    nq = _norm(query_text)

    # Uu tien "mai" chinh xac (word boundary)
    import re as _re
    if _re.search(r"\bmai\b", nq):
        target = (now + timedelta(days=1)).date()
        day_label = "Tomorrow"
    elif "tuan" in nq:
        target = now.date()
        day_label = "This week"
    else:
        target = now.date()
        day_label = "Today"

    result = suggest_time_slot(user_id, target)
    habits = result["habits"]

    embed = discord.Embed(
        title=f"Suggestion for {day_label.lower()}, {member}",
        description=f"Based on your last 4 weeks ({habits['total']} events).",
        color=discord.Color.purple(),
    )

    # Free slots
    if result["free_slots"]:
        lines = []
        for slot in result["free_slots"]:
            st = slot["start"].strftime("%H:%M")
            en = slot["end"].strftime("%H:%M")
            lines.append(f"`{st} - {en}` ({slot['duration']}p free)")
        embed.add_field(name="Free slots", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Free slots", value="Fully booked, sir.", inline=False)

    # Suggestions
    if result["suggestions"]:
        lines = []
        for s in result["suggestions"]:
            lines.append(f"{s['icon']} **{s['activity']}** - _{s['reason']}_")
        embed.add_field(name="I suggest", value="\n".join(lines), inline=False)

    # Habits
    if habits["top_activities"]:
        lines = []
        for item in habits["top_activities"][:3]:
            lines.append(f"`{ICONS.get(item['type'], '?')}` {item['type']}: **{item['count']}x**")
        embed.add_field(name="Your top activities", value="\n".join(lines), inline=False)

    embed.set_footer(text="!j help | Ask: 'mai lam gi' | 'sang mai lam gi'")
    return embed


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("=" * 60)
    print("SUGGESTER TEST")
    print("=" * 60)

    TEST_UID = "test_sug_999"
    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])

    now = datetime.now(TZ)

    # Fake habits: 5 gyms, 3 studies over past 2 weeks
    for i in range(5):
        dt = now - timedelta(days=i*2)
        dt = dt.replace(hour=17, minute=0, second=0, microsecond=0)
        em.create_event(TEST_UID, "T", f"Gym {i}", "gym", dt, dt + timedelta(hours=1))
    for i in range(3):
        dt = now - timedelta(days=i*3)
        dt = dt.replace(hour=20, minute=0, second=0, microsecond=0)
        em.create_event(TEST_UID, "T", f"Study {i}", "study", dt, dt + timedelta(hours=1))

    # Today event 15:00-16:00
    today_15 = now.replace(hour=15, minute=0, second=0, microsecond=0)
    em.create_event(TEST_UID, "T", "Hop nhom", "meeting",
                    today_15, today_15 + timedelta(hours=1))

    habits = get_habits(TEST_UID)
    print(f"\n[Habits] Total: {habits['total']} events")
    print(f"  By type: {habits['by_type']}")
    print(f"  Top: {habits['top_activities'][:3]}")

    result = suggest_time_slot(TEST_UID)
    print(f"\n[Free slots]")
    for s in result["free_slots"]:
        print(f"  {s['start'].strftime('%H:%M')}-{s['end'].strftime('%H:%M')} ({s['duration']}p)")
    print(f"\n[Suggestions]")
    for s in result["suggestions"]:
        print(f"  {s['icon']} {s['activity']} - {s['reason']}")

    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])
    print("\n[Cleanup] Done")