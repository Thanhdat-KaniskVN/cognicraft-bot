# spaced_repetition.py
"""
Spaced Repetition - Lên lịch ôn tập theo 1-3-7-14-30-60
"""
import sqlite3
from datetime import datetime, timedelta
import pytz
from config import TIMEZONE


class SpacedRepetition:
    """Quản lý lịch ôn tập lặp lại ngắt quãng"""

    INTERVALS = [1, 3, 7, 14, 30, 60]

    def __init__(self, db_path="scores.db"):
        self.db_path = db_path
        self.tz = pytz.timezone(TIMEZONE)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER,
                member TEXT,
                topic TEXT,
                learned_at TIMESTAMP,
                review_stage INTEGER DEFAULT 0,
                next_review_at TIMESTAMP,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(week, member, topic)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_next_review
            ON review_schedule(next_review_at, status)
        """)
        conn.commit()
        conn.close()

    def schedule_review(self, week, member, topic, learned_at=None):
        if learned_at is None:
            learned_at = datetime.now(self.tz)
        elif isinstance(learned_at, str):
            learned_at = datetime.fromisoformat(learned_at)

        next_review = learned_at + timedelta(days=self.INTERVALS[0])

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO review_schedule
                (week, member, topic, learned_at, review_stage, next_review_at, status)
                VALUES (?, ?, ?, ?, 0, ?, 'pending')
            """, (week, member, topic, learned_at.isoformat(),
                  next_review.isoformat()))
            conn.commit()
        except Exception as e:
            print(f"[SpacedRep] Schedule error: {e}")
        finally:
            conn.close()

        return {
            "week": week,
            "member": member,
            "topic": topic,
            "learned_at": learned_at.strftime("%d/%m/%Y"),
            "next_review": next_review.strftime("%d/%m/%Y"),
            "stage": 0,
        }

    def complete_review(self, week, member, topic):
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT review_stage FROM review_schedule
            WHERE week = ? AND member = ? AND topic = ?
        """, (week, member, topic)).fetchone()

        if not row:
            conn.close()
            return None

        current_stage = row[0]
        next_stage = current_stage + 1

        if next_stage >= len(self.INTERVALS):
            conn.execute("""
                UPDATE review_schedule
                SET status = 'completed', review_stage = ?
                WHERE week = ? AND member = ? AND topic = ?
            """, (next_stage, week, member, topic))
            conn.commit()
            conn.close()
            return {"status": "completed", "stage": next_stage}

        now = datetime.now(self.tz)
        next_review = now + timedelta(days=self.INTERVALS[next_stage])

        conn.execute("""
            UPDATE review_schedule
            SET review_stage = ?, next_review_at = ?
            WHERE week = ? AND member = ? AND topic = ?
        """, (next_stage, next_review.isoformat(), week, member, topic))
        conn.commit()
        conn.close()

        return {
            "status": "scheduled",
            "stage": next_stage,
            "next_review": next_review.strftime("%d/%m/%Y"),
            "interval_days": self.INTERVALS[next_stage],
        }

    def get_due_reviews(self, member=None):
        now = datetime.now(self.tz).isoformat()
        conn = sqlite3.connect(self.db_path)

        if member:
            rows = conn.execute("""
                SELECT week, member, topic, review_stage, next_review_at
                FROM review_schedule
                WHERE status = 'pending' AND next_review_at <= ? AND member = ?
                ORDER BY next_review_at ASC
            """, (now, member)).fetchall()
        else:
            rows = conn.execute("""
                SELECT week, member, topic, review_stage, next_review_at
                FROM review_schedule
                WHERE status = 'pending' AND next_review_at <= ?
                ORDER BY next_review_at ASC
            """, (now,)).fetchall()

        conn.close()

        return [
            {
                "week": r[0],
                "member": r[1],
                "topic": r[2],
                "stage": r[3],
                "next_review": r[4],
                "days_overdue": self._days_overdue(r[4]),
            }
            for r in rows
        ]

    def get_member_schedule(self, member):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT week, topic, review_stage, next_review_at, status
            FROM review_schedule
            WHERE member = ?
            ORDER BY next_review_at ASC
        """, (member,)).fetchall()
        conn.close()

        return [
            {"week": r[0], "topic": r[1], "stage": r[2],
             "next_review": r[3], "status": r[4]}
            for r in rows
        ]

    def get_stats(self):
        conn = sqlite3.connect(self.db_path)
        total = conn.execute("SELECT COUNT(*) FROM review_schedule").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM review_schedule WHERE status = 'pending'"
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM review_schedule WHERE status = 'completed'"
        ).fetchone()[0]
        conn.close()
        due_now = len(self.get_due_reviews())
        return {
            "total": total, "pending": pending,
            "completed": completed, "due_now": due_now,
        }

    def _days_overdue(self, next_review_str):
        try:
            next_review = datetime.fromisoformat(next_review_str)
            now = datetime.now(self.tz)
            return max((now - next_review).days, 0)
        except Exception:
            return 0