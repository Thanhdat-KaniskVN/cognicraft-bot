# store/backend/database.py
"""
Database connection - Supabase PostgreSQL
- Connection pool (min 1, max 10)
- Retry logic khi connection drop
- Keepalive + sslmode
"""
import os
import time
from pathlib import Path
from typing import Optional, List, Dict
import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env")


class Database:
    """PostgreSQL connection wrapper with pooling + retry"""

    MAX_RETRIES = 3
    RETRY_DELAY = 0.5  # seconds

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self._pool: Optional[pg_pool.ThreadedConnectionPool] = None

    def _get_pool(self) -> pg_pool.ThreadedConnectionPool:
        """Lazy init pool"""
        if self._pool is None or self._pool.closed:
            if not self.database_url:
                raise RuntimeError("DATABASE_URL not set")

            self._pool = pg_pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.database_url,
                cursor_factory=RealDictCursor,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
                sslmode="require",
            )
        return self._pool

    def _get_conn(self):
        """Get connection từ pool với retry"""
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                pool = self._get_pool()
                conn = pool.getconn()
                # Test connection alive
                if conn.closed:
                    pool.putconn(conn, close=True)
                    raise psycopg2.OperationalError("Connection closed")
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    # Reset pool nếu cần
                    if self._pool:
                        try:
                            self._pool.closeall()
                        except Exception:
                            pass
                        self._pool = None

        raise last_error or RuntimeError("Cannot get DB connection")

    def _release_conn(self, conn, close: bool = False):
        """Return connection về pool"""
        try:
            if self._pool and not self._pool.closed:
                self._pool.putconn(conn, close=close)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute SELECT với retry"""
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            conn = None
            try:
                conn = self._get_conn()
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return [dict(row) for row in cur.fetchall()]
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_error = e
                if conn:
                    self._release_conn(conn, close=True)
                    conn = None
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise
            except Exception:
                raise
            finally:
                if conn:
                    self._release_conn(conn)

        raise last_error or RuntimeError("Query failed")

    def query_one(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple = ()) -> int:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            conn = None
            try:
                conn = self._get_conn()
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    conn.commit()
                    return cur.rowcount
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_error = e
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    self._release_conn(conn, close=True)
                    conn = None
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise
            except Exception:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                raise
            finally:
                if conn:
                    self._release_conn(conn)

        raise last_error or RuntimeError("Execute failed")

    def execute_returning(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            conn = None
            try:
                conn = self._get_conn()
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    result = cur.fetchone()
                    conn.commit()
                    return dict(result) if result else None
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_error = e
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    self._release_conn(conn, close=True)
                    conn = None
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise
            except Exception:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                raise
            finally:
                if conn:
                    self._release_conn(conn)

        raise last_error or RuntimeError("Execute returning failed")


# Singleton
_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db