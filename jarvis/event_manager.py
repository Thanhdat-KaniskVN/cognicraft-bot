# jarvis/event_manager.py
"""Event Manager - CRUD events trong Supabase."""
from datetime import datetime, timedelta
from typing import Optional, List
import pytz

from database import get_cursor

TZ = pytz.timezone("Asia/Ho_Chi_Minh")


def create_event(user_id, member, title, event_type, start_time,
                 end_time=None, location=None, description=None,
                 priority="normal", reminder_flags=None, knowledge_link=None):
    if end_time is None:
        end_time = start_time + timedelta(minutes=60)
    if reminder_flags is None:
        reminder_flags = ["30", "15", "5"]
    with get_cursor() as cur:
        # DEDUPE: check window +/- 5 phut (tranh duplicate khi add lai)
        window_start = start_time - timedelta(minutes=5)
        window_end = start_time + timedelta(minutes=5)
        cur.execute("""
            SELECT id FROM jarvis_events
            WHERE user_id = %s AND title = %s
              AND start_time BETWEEN %s AND %s
              AND status = 'scheduled'
            LIMIT 1
        """, (user_id, title, window_start, window_end))
        existing = cur.fetchone()
        if existing:
            print(f"[EventManager] DEDUPE: event exists #{existing['id']}")
            return existing["id"]
        cur.execute("""
            INSERT INTO jarvis_events
            (user_id, member, title, event_type, start_time, end_time,
             location, description, priority, knowledge_link, reminder_flags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, member, title, event_type, start_time, end_time,
              location, description, priority, knowledge_link, reminder_flags))
        row = cur.fetchone()
        return row["id"] if row else None


def get_event(event_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM jarvis_events WHERE id = %s", (event_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def list_events(user_id=None, days_ahead=7, event_type=None, status="scheduled"):
    now = datetime.now(TZ)
    end = now + timedelta(days=days_ahead)
    sql = "SELECT * FROM jarvis_events WHERE start_time >= %s AND start_time <= %s"
    params = [now, end]
    if user_id:
        sql += " AND user_id = %s"
        params.append(user_id)
    if event_type:
        sql += " AND event_type = %s"
        params.append(event_type)
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY start_time ASC LIMIT 100"
    with get_cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_today_events(user_id=None):
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    sql = "SELECT * FROM jarvis_events WHERE start_time >= %s AND start_time < %s AND status = 'scheduled'"
    params = [start, end]
    if user_id:
        sql += " AND user_id = %s"
        params.append(user_id)
    sql += " ORDER BY start_time ASC"
    with get_cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def update_event(event_id, **fields):
    if not fields:
        return False
    allowed = {"title", "event_type", "start_time", "end_time", "location",
               "description", "priority", "status", "knowledge_link",
               "gcal_event_id", "gcal_html_link", "reminder_flags"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = datetime.now(TZ)
    cols = ", ".join(f"{k} = %s" for k in updates.keys())
    vals = list(updates.values()) + [event_id]
    with get_cursor() as cur:
        cur.execute(f"UPDATE jarvis_events SET {cols} WHERE id = %s", tuple(vals))
        return cur.rowcount > 0


def cancel_event(event_id):
    return update_event(event_id, status="cancelled")


def mark_done(event_id):
    return update_event(event_id, status="done")


def delete_event(event_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM jarvis_events WHERE id = %s", (event_id,))
        return cur.rowcount > 0


def get_pending_reminders(within_minutes=30):
    now = datetime.now(TZ)
    threshold = now + timedelta(minutes=within_minutes)
    with get_cursor() as cur:
        cur.execute("""
            SELECT e.*,
                   EXTRACT(EPOCH FROM (e.start_time - NOW())) / 60 AS minutes_until
            FROM jarvis_events e
            WHERE e.status = 'scheduled'
              AND e.start_time > NOW()
              AND e.start_time <= %s
            ORDER BY e.start_time ASC
        """, (threshold,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def log_reminder(event_id, user_id, minutes_before, channel="dm"):
    """Insert reminder log. Return True neu moi insert (chua ton tai)."""
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO jarvis_reminders (event_id, user_id, minutes_before, channel)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_id, minutes_before) DO NOTHING
                RETURNING id
            """, (event_id, user_id, minutes_before, channel))
            row = cur.fetchone()
        return row is not None  # True = insert moi, False = da ton tai
    except Exception as e:
        print(f"[EventManager] log_reminder err: {e}")
        return False


def was_reminded(event_id, minutes_before):
    with get_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM jarvis_reminders WHERE event_id = %s AND minutes_before = %s",
            (event_id, minutes_before))
        return cur.fetchone() is not None


def get_event_stats(user_id=None):
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'scheduled' AND start_time > NOW()) AS upcoming,
            COUNT(*) FILTER (WHERE status = 'done') AS done,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
            COUNT(*) FILTER (WHERE start_time::date = NOW()::date AND status = 'scheduled') AS today
        FROM jarvis_events
    """
    params = []
    if user_id:
        sql += " WHERE user_id = %s"
        params.append(user_id)
    with get_cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
    return dict(row) if row else {}


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("=" * 60)
    print("EVENT MANAGER TEST")
    print("=" * 60)

    test_uid = "test_user_999"
    test_member = "TestUser"

    for ev in list_events(user_id=test_uid, days_ahead=365, status=None):
        delete_event(ev["id"])
    print("[Cleanup] Done")

    now = datetime.now(TZ)
    ev_id = create_event(test_uid, test_member, "Test event", "task",
                         now + timedelta(hours=2), description="Test")
    print(f"[Create] id={ev_id}")

    ev = get_event(ev_id)
    print(f"[Read] {ev['title']} @ {ev['start_time']}")

    events = list_events(user_id=test_uid, days_ahead=7)
    print(f"[List] {len(events)} events")

    update_event(ev_id, title="Test event UPDATED", priority="high")
    ev = get_event(ev_id)
    print(f"[Update] {ev['title']} | priority={ev['priority']}")

    log_reminder(ev_id, test_uid, 30)
    print(f"[Reminder] was_reminded(30)={was_reminded(ev_id, 30)}")
    print(f"[Reminder] was_reminded(15)={was_reminded(ev_id, 15)}")

    stats = get_event_stats(test_uid)
    print(f"[Stats] {stats}")

    cancel_event(ev_id)
    ev = get_event(ev_id)
    print(f"[Cancel] status={ev['status']}")

    delete_event(ev_id)
    print(f"[Cleanup] Deleted")
    print("\n[OK] All tests passed")