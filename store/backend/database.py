# store/backend/database.py
"""
Database connection - Supabase PostgreSQL
- Transaction pooler (port 6543) with keepalive
"""
import os
from pathlib import Path
from typing import Optional, List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


# Load .env from root
_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env")


class Database:
    """PostgreSQL connection wrapper with keepalive"""

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")

    def _connect(self):
        """Create new connection với keepalive + sslmode"""
        if not self.database_url:
            raise RuntimeError("DATABASE_URL not set")

        return psycopg2.connect(
            self.database_url,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
            sslmode="require",
        )

    def query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute SELECT query"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def query_one(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """Execute SELECT, return first row"""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Execute INSERT/UPDATE/DELETE, return rowcount"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()
                return cur.rowcount
        finally:
            conn.close()

    def execute_returning(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """Execute INSERT with RETURNING"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                result = cur.fetchone()
                conn.commit()
                return dict(result) if result else None
        finally:
            conn.close()


# Singleton
_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db