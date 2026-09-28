# database.py - PostgreSQL version (Supabase)
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL chua duoc set trong .env")


@contextmanager
def get_db():
    """Context manager cho PostgreSQL connection."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(dict_rows=True):
    """Context manager tra ve cursor (RealDictCursor mac dinh)."""
    with get_db() as conn:
        if dict_rows:
            cursor_factory = psycopg2.extras.RealDictCursor
        else:
            cursor_factory = None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()


def init_db():
    """Tables da tao tren Supabase (khong can tao lai)."""
    # Chi verify connection
    with get_cursor() as cur:
        cur.execute("SELECT 1")
    print("[DB] Connected to Supabase")


def _log_history(cur, week, member, scores, source, changed_by=None, note=None):
    total = (
        0.3 * scores["accuracy"] + 0.3 * scores["depth"] +
        0.2 * scores["connection"] + 0.2 * scores["presentation"]
    )
    cur.execute("""
        INSERT INTO bot_score_history
        (week, member, accuracy, depth, connection, presentation,
         total, source, changed_by, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        week, member,
        scores["accuracy"], scores["depth"],
        scores["connection"], scores["presentation"],
        round(total, 2), source, changed_by, note
    ))


def save_score(week, member, scores, self_score=None,
               source="ai_suggested", changed_by=None, note=None):
    total = (
        0.3 * scores["accuracy"] + 0.3 * scores["depth"] +
        0.2 * scores["connection"] + 0.2 * scores["presentation"]
    )
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO bot_scores
            (week, member, accuracy, depth, connection, presentation,
             total, self_score, source, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (week, member) DO UPDATE SET
                accuracy = EXCLUDED.accuracy,
                depth = EXCLUDED.depth,
                connection = EXCLUDED.connection,
                presentation = EXCLUDED.presentation,
                total = EXCLUDED.total,
                self_score = EXCLUDED.self_score,
                source = EXCLUDED.source,
                created_at = EXCLUDED.created_at
        """, (
            week, member,
            scores["accuracy"], scores["depth"],
            scores["connection"], scores["presentation"],
            round(total, 2), self_score, source, datetime.now()
        ))
        _log_history(cur, week, member, scores, source, changed_by, note)


def get_week_scores(week):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM bot_scores WHERE week = %s ORDER BY member",
            (week,)
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_score_history(week, member=None):
    with get_cursor() as cur:
        if member:
            cur.execute(
                "SELECT * FROM bot_score_history WHERE week = %s AND member = %s ORDER BY changed_at DESC",
                (week, member)
            )
        else:
            cur.execute(
                "SELECT * FROM bot_score_history WHERE week = %s ORDER BY changed_at DESC",
                (week,)
            )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_pending_score(week, member):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM bot_scores WHERE week = %s AND member = %s AND source = 'ai_suggested'",
            (week, member)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def update_score_source(week, member, new_source, changed_by=None):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM bot_scores WHERE week = %s AND member = %s",
            (week, member)
        )
        row = cur.fetchone()

        if row:
            cur.execute(
                "UPDATE bot_scores SET source = %s WHERE week = %s AND member = %s",
                (new_source, week, member)
            )
            scores = {
                "accuracy": row["accuracy"], "depth": row["depth"],
                "connection": row["connection"], "presentation": row["presentation"],
            }
            _log_history(cur, week, member, scores, new_source, changed_by,
                         note=f"Source: {row['source']} -> {new_source}")


def save_participation(week, member, submitted):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO bot_participation
            (week, member, submitted, submitted_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (week, member) DO UPDATE SET
                submitted = EXCLUDED.submitted,
                submitted_at = EXCLUDED.submitted_at
        """, (
            week, member,
            1 if submitted else 0,
            datetime.now() if submitted else None
        ))


def get_week_participation(week):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM bot_participation WHERE week = %s ORDER BY member",
            (week,)
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]



def save_classification(week, member, classification):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO bot_classifications
            (week, member, thread_week, classified_week, confidence,
             method, topic_id, topic_name, phase_id, phase_name, keywords_found)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (week, member) DO UPDATE SET
                thread_week = EXCLUDED.thread_week,
                classified_week = EXCLUDED.classified_week,
                confidence = EXCLUDED.confidence,
                method = EXCLUDED.method,
                topic_id = EXCLUDED.topic_id,
                topic_name = EXCLUDED.topic_name,
                phase_id = EXCLUDED.phase_id,
                phase_name = EXCLUDED.phase_name,
                keywords_found = EXCLUDED.keywords_found,
                classified_at = NOW()
        """, (
            week, member,
            classification.get("thread_week"),
            classification["week"],
            classification.get("confidence", 0),
            classification.get("method", "unknown"),
            classification.get("topic_id"),
            classification.get("topic_name"),
            classification.get("phase_id"),
            classification.get("phase_name"),
            classification.get("keywords_found", []),
        ))


def get_classification(week, member):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM bot_classifications WHERE week = %s AND member = %s",
            (week, member))
        row = cur.fetchone()
    return dict(row) if row else None
