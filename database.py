import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

DB_PATH = "scores.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER NOT NULL,
                member TEXT NOT NULL,
                accuracy REAL NOT NULL,
                depth REAL NOT NULL,
                connection REAL NOT NULL,
                presentation REAL NOT NULL,
                total REAL NOT NULL,
                self_score REAL,
                source TEXT NOT NULL DEFAULT 'ai_suggested',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(week, member)
            );

            CREATE TABLE IF NOT EXISTS score_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER NOT NULL,
                member TEXT NOT NULL,
                accuracy REAL NOT NULL,
                depth REAL NOT NULL,
                connection REAL NOT NULL,
                presentation REAL NOT NULL,
                total REAL NOT NULL,
                source TEXT NOT NULL,
                changed_by TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS participation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER NOT NULL,
                member TEXT NOT NULL,
                submitted INTEGER NOT NULL,
                submitted_at TIMESTAMP,
                UNIQUE(week, member)
            );

            CREATE INDEX IF NOT EXISTS idx_scores_week ON scores(week);
            CREATE INDEX IF NOT EXISTS idx_history_week ON score_history(week);
            CREATE INDEX IF NOT EXISTS idx_participation_week ON participation(week);
        ''')


def _log_history(db, week, member, scores, source, changed_by=None, note=None):
    total = (
        0.3 * scores["accuracy"] + 0.3 * scores["depth"] +
        0.2 * scores["connection"] + 0.2 * scores["presentation"]
    )
    db.execute('''
        INSERT INTO score_history
        (week, member, accuracy, depth, connection, presentation,
         total, source, changed_by, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
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
    with get_db() as db:
        db.execute('''
            INSERT OR REPLACE INTO scores
            (week, member, accuracy, depth, connection, presentation,
             total, self_score, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            week, member,
            scores["accuracy"], scores["depth"],
            scores["connection"], scores["presentation"],
            round(total, 2), self_score, source, datetime.now()
        ))
        _log_history(db, week, member, scores, source, changed_by, note)


def get_week_scores(week):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM scores WHERE week = ? ORDER BY member", (week,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_score_history(week, member=None):
    with get_db() as db:
        if member:
            rows = db.execute(
                "SELECT * FROM score_history WHERE week = ? AND member = ? ORDER BY changed_at DESC",
                (week, member)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM score_history WHERE week = ? ORDER BY changed_at DESC",
                (week,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_pending_score(week, member):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM scores WHERE week = ? AND member = ? AND source = 'ai_suggested'",
            (week, member)
        ).fetchone()
    return dict(row) if row else None


def update_score_source(week, member, new_source, changed_by=None):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM scores WHERE week = ? AND member = ?",
            (week, member)
        ).fetchone()

        if row:
            db.execute(
                "UPDATE scores SET source = ? WHERE week = ? AND member = ?",
                (new_source, week, member)
            )
            scores = {
                "accuracy": row["accuracy"], "depth": row["depth"],
                "connection": row["connection"], "presentation": row["presentation"],
            }
            _log_history(db, week, member, scores, new_source, changed_by,
                         note=f"Source: {row['source']} -> {new_source}")


def save_participation(week, member, submitted):
    with get_db() as db:
        db.execute('''
            INSERT OR REPLACE INTO participation
            (week, member, submitted, submitted_at)
            VALUES (?, ?, ?, ?)
        ''', (week, member, 1 if submitted else 0,
              datetime.now() if submitted else None))


def get_week_participation(week):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM participation WHERE week = ? ORDER BY member", (week,)
        ).fetchall()
    return [dict(r) for r in rows]
