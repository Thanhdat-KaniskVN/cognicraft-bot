# jarvis/conflict_detector.py
"""Conflict detector + smart slot suggestions."""
from datetime import datetime, timedelta
from typing import List, Optional
import pytz

from jarvis import event_manager as em

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

WORK_START = 6    # 6h sang
WORK_END = 23     # 11h toi


def _parse_dt(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    return dt


def detect_conflicts(user_id, start_dt, end_dt, exclude_id=None):
    """Tim events overlap voi [start_dt, end_dt]."""
    if start_dt.tzinfo is None:
        start_dt = TZ.localize(start_dt)
    if end_dt.tzinfo is None:
        end_dt = TZ.localize(end_dt)

    events = em.list_events(user_id=user_id, days_ahead=3)
    conflicts = []

    for ev in events:
        if exclude_id and ev["id"] == exclude_id:
            continue
        try:
            ev_start = _parse_dt(ev["start_time"])
            ev_end = _parse_dt(ev["end_time"]) if ev.get("end_time") else ev_start + timedelta(hours=1)
        except Exception:
            continue

        # Overlap: NOT (end <= ev_start OR start >= ev_end)
        if not (end_dt <= ev_start or start_dt >= ev_end):
            conflicts.append(ev)

    return conflicts


def _has_conflict(slot_start, slot_end, events):
    for ev in events:
        try:
            ev_start = _parse_dt(ev["start_time"])
            ev_end = _parse_dt(ev["end_time"]) if ev.get("end_time") else ev_start + timedelta(hours=1)
        except Exception:
            continue
        if not (slot_end <= ev_start or slot_start >= ev_end):
            return True
    return False


def suggest_slots(start_dt, duration_min, user_id, n=3, day_window=7):
    """Suggest n khung gio trong gan nhat (khong conflict)."""
    if start_dt.tzinfo is None:
        start_dt = TZ.localize(start_dt)
    duration = timedelta(minutes=duration_min)

    # Preload existing events 7 ngay
    existing = em.list_events(user_id=user_id, days_ahead=day_window)
    now = datetime.now(TZ)

    suggestions = []
    base = start_dt.replace(minute=0, second=0, microsecond=0)

    for day_offset in range(day_window):
        if len(suggestions) >= n:
            break
        day = (base + timedelta(days=day_offset)).date()

        # Khung gio uu tien: neu cung ngay -> sau start_dt; neu khac ngay -> ca ngay
        hour_start = WORK_START
        if day_offset == 0 and base.hour > WORK_START:
            hour_start = base.hour + 1

        for hour in range(hour_start, WORK_END):
            if len(suggestions) >= n:
                break

            slot_start = TZ.localize(datetime.combine(day, datetime.min.time().replace(hour=hour)))
            slot_end = slot_start + duration

            if slot_start <= now:
                continue

            if not _has_conflict(slot_start, slot_end, existing):
                # Check khong overlap voi chinh suggestion khac
                overlap_self = False
                for s in suggestions:
                    if not (slot_end <= s["start"] or slot_start >= s["end"]):
                        overlap_self = True
                        break
                if not overlap_self:
                    suggestions.append({"start": slot_start, "end": slot_end})

    return suggestions[:n]


def format_conflict_warning(conflicts, suggestions):
    """Format text hien thi."""
    lines = []
    if conflicts:
        lines.append(f"**XUNG DOT ({len(conflicts)}):**")
        for c in conflicts[:3]:
            st = _parse_dt(c["start_time"])
            en = _parse_dt(c["end_time"]) if c.get("end_time") else st + timedelta(hours=1)
            lines.append(f"  `#{c['id']}` {st.strftime('%H:%M')}-{en.strftime('%H:%M')} {c['title']}")
    if suggestions:
        lines.append(f"\n**KHUNG GIO TRONG:**")
        for i, s in enumerate(suggestions, 1):
            lines.append(f"  {i}. {s['start'].strftime('%a %d/%m %H:%M')} -> {s['end'].strftime('%H:%M')}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    TEST_UID = "test_conflict_999"
    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])

    now = datetime.now(TZ)
    # Event 15:00-16:00 ngay mai
    tomorrow = (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    em.create_event(TEST_UID, "Test", "Hop nhom", "meeting", tomorrow,
                    tomorrow + timedelta(hours=1))

    print("=" * 60)
    print("CONFLICT DETECTOR TEST")
    print("=" * 60)

    # Test 1: overlap
    test_start = tomorrow + timedelta(minutes=30)
    test_end = test_start + timedelta(hours=1)
    conflicts = detect_conflicts(TEST_UID, test_start, test_end)
    print(f"\n[Test 1] Check {test_start.strftime('%H:%M')}-{test_end.strftime('%H:%M')}")
    print(f"  Conflicts: {len(conflicts)}")

    # Test 2: suggest
    suggestions = suggest_slots(test_start, 60, TEST_UID, n=3)
    print(f"\n[Test 2] Suggest 3 slots:")
    for s in suggestions:
        print(f"  {s['start'].strftime('%a %d/%m %H:%M')} -> {s['end'].strftime('%H:%M')}")

    # Cleanup
    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])
    print("\n[Cleanup] Done")