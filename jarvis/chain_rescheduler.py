# jarvis/chain_rescheduler.py
"""Chain reschedule - quet + de xuat doi cascade."""
from datetime import datetime, timedelta
from typing import List, Optional
import pytz

from jarvis import event_manager as em
from jarvis.conflict_detector import (
    EXCLUSIVE_TYPES, _parse_dt, _has_conflict, TZ,
)

MIN_GAP_MIN = 5    # Khoang nghi toi thieu giua events


def build_chain(user_id, new_event_start, new_event_end, new_event_type=None,
                max_chain=5, day_window=7):
    """Build chain reschedule plan.

    Returns:
        {
            "chain": [
                {
                    "event": {...},           # event trong DB
                    "old_start": datetime,
                    "old_end": datetime,
                    "new_start": datetime,
                    "new_end": datetime,
                    "reason": "conflict" | "shifted",
                },
                ...
            ],
            "final_end": datetime,            # thoi diem ket thuc cuoi cung
            "has_conflicts": bool,
            "exclusive": bool,                # co phai exclusive type khong
        }
    """
    if new_event_type and new_event_type not in EXCLUSIVE_TYPES:
        return {"chain": [], "has_conflicts": False, "exclusive": False,
                "final_end": new_event_end}

    new_event_start = _parse_dt(new_event_start)
    new_event_end = _parse_dt(new_event_end)

    duration_new = new_event_end - new_event_start

    # Fetch events 7 ngay toi
    events = em.list_events(user_id=user_id, days_ahead=day_window)
    events_sorted = sorted(
        events,
        key=lambda e: _parse_dt(e["start_time"])
    )

    chain = []
    cursor_start = new_event_start  # Su kien moi chiem slot nay
    cursor_end = new_event_end

    for ev in events_sorted:
        ev_type = ev.get("event_type")
        ev_start = _parse_dt(ev["start_time"])
        ev_end = _parse_dt(ev["end_time"]) if ev.get("end_time") else ev_start + timedelta(hours=1)

        # Skip event khong overlap cursor
        if ev_end <= cursor_start or ev_start >= cursor_end:
            continue

        # Event flexible -> skip (khong can doi)
        if ev_type not in EXCLUSIVE_TYPES:
            continue

        # Conflict -> move event nay ra sau cursor_end + gap
        new_start = cursor_end + timedelta(minutes=MIN_GAP_MIN)
        new_end = new_start + (ev_end - ev_start)

        chain.append({
            "event": ev,
            "old_start": ev_start,
            "old_end": ev_end,
            "new_start": new_start,
            "new_end": new_end,
            "reason": "conflict" if not chain else "shifted",
        })

        # Cursor tiep tuc
        cursor_start = new_start
        cursor_end = new_end

        if len(chain) >= max_chain:
            break

    return {
        "chain": chain,
        "has_conflicts": len(chain) > 0,
        "exclusive": True,
        "final_end": cursor_end,
    }


def apply_chain(user_id, chain):
    """Apply chain reschedule len DB. Returns list (event_id, new_start)."""
    applied = []
    for item in chain:
        ev = item["event"]
        try:
            em.update_event(
                ev["id"],
                start_time=item["new_start"],
                end_time=item["new_end"],
            )
            applied.append((ev["id"], item["new_start"]))
            print(f"[ChainResched] Moved #{ev['id']} -> {item['new_start'].strftime('%H:%M')}")
        except Exception as e:
            print(f"[ChainResched] Apply fail #{ev['id']}: {e}")
    return applied


def format_chain_preview(chain):
    """Format text preview."""
    if not chain:
        return "Khong co event nao bi anh huong."
    lines = [f"**CHAIN RESCHEDULE ({len(chain)} events):**"]
    for i, item in enumerate(chain, 1):
        ev = item["event"]
        old_start = item["old_start"]
        new_start = item["new_start"]
        icon = "CONFLICT" if item["reason"] == "conflict" else "SHIFTED"
        lines.append(
            f"  `#{ev['id']}` [{icon}] {ev['title']}\n"
            f"    {old_start.strftime('%H:%M')} -> **{new_start.strftime('%H:%M')}** "
            f"({(new_start - old_start).total_seconds()/60:+.0f}p)"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from jarvis import event_manager as em

    UID = "test_chain_999"
    for ev in em.list_events(user_id=UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])

    now = datetime.now(TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)

    # Chain: 3 meeting lien tiep
    em.create_event(UID, "T", "Hop nhom", "meeting", tomorrow, tomorrow + timedelta(hours=1))
    em.create_event(UID, "T", "Hoc Python", "class", tomorrow + timedelta(hours=1, minutes=30),
                    tomorrow + timedelta(hours=3))
    em.create_event(UID, "T", "Thi Toan", "exam", tomorrow + timedelta(hours=3, minutes=30),
                    tomorrow + timedelta(hours=5))

    print("=" * 70)
    print("CHAIN RESCHEDULER TEST")
    print("=" * 70)
    print(f"Setup: 3 events starting at {tomorrow.strftime('%H:%M')}")

    # New event overlap dau tien
    new_start = tomorrow + timedelta(minutes=30)
    new_end = new_start + timedelta(hours=1)
    print(f"\nNew event: {new_start.strftime('%H:%M')} - {new_end.strftime('%H:%M')} (meeting)")

    plan = build_chain(UID, new_start, new_end, new_event_type="meeting")
    print(f"\nChain: {len(plan['chain'])} events")
    print(format_chain_preview(plan["chain"]))

    # Cleanup
    for ev in em.list_events(user_id=UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])
    print("\n[Cleanup] Done")