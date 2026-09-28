# sqlite_shim.py
"""
Compatibility shim: chan sqlite3.connect("scores.db") -> PostgreSQL.
Code cu dung sqlite3 van chay, nhung thuc te query Supabase.
"""
import re
import sqlite3 as _real_sqlite3

_orig_connect = _real_sqlite3.connect

TABLE_MAP = {
    "scores": "bot_scores",
    "score_history": "bot_score_history",
    "participation": "bot_participation",
}


def _convert_sql(sql: str) -> str:
    s = sql

    # SQLite -> PostgreSQL schema translations
    s = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
               "BIGSERIAL PRIMARY KEY", s, flags=re.IGNORECASE)
    s = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTO_INCREMENT",
               "BIGSERIAL PRIMARY KEY", s, flags=re.IGNORECASE)
    s = re.sub(r"AUTOINCREMENT", "", s, flags=re.IGNORECASE)
    s = re.sub(r"DATETIME\b", "TIMESTAMPTZ", s, flags=re.IGNORECASE)

    # Placeholder
    s = s.replace("?", "%s")

    # Table name mapping
    for old, new in TABLE_MAP.items():
        s = re.sub(rf"\b{old}\b", new, s, flags=re.IGNORECASE)

    return s


class HybridRow:
    __slots__ = ("_d", "_v")
    def __init__(self, mapping):
        self._d = dict(mapping)
        self._v = list(mapping.values())
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._v[key]
        return self._d[key]
    def __getattr__(self, name):
        try:
            return self._d[name]
        except KeyError:
            raise AttributeError(name)
    def __iter__(self):
        return iter(self._v)
    def __len__(self):
        return len(self._v)
    def __contains__(self, key):
        return key in self._d
    def __repr__(self):
        return f"HybridRow({self._d})"
    def get(self, k, d=None):
        return self._d.get(k, d)
    def keys(self):
        return self._d.keys()
    def values(self):
        return self._d.values()
    def items(self):
        return self._d.items()


class PGCursor:
    def __init__(self, pg_conn):
        self._pg = pg_conn
        self._cur = pg_conn.cursor()
        self._cache = []
        self._idx = 0
    def execute(self, sql, params=None):
        pg_sql = _convert_sql(sql)
        if params is None:
            self._cur.execute(pg_sql)
        else:
            self._cur.execute(pg_sql, tuple(params) if not isinstance(params, dict) else params)
        try:
            self._cache = self._cur.fetchall() if self._cur.description else []
        except Exception:
            self._cache = []
        self._idx = 0
        return self
    def executemany(self, sql, seq):
        self._cur.executemany(_convert_sql(sql), seq)
        self._cache = []
        self._idx = 0
        return self
    def fetchone(self):
        if self._idx >= len(self._cache):
            return None
        r = self._cache[self._idx]
        self._idx += 1
        return HybridRow(r) if isinstance(r, dict) else r
    def fetchall(self):
        rows = self._cache[self._idx:]
        self._idx = len(self._cache)
        return [HybridRow(r) if isinstance(r, dict) else r for r in rows]
    def fetchmany(self, size=1):
        rows = self._cache[self._idx:self._idx + size]
        self._idx += len(rows)
        return [HybridRow(r) if isinstance(r, dict) else r for r in rows]
    @property
    def description(self):
        return getattr(self._cur, "description", None)
    @property
    def rowcount(self):
        return getattr(self._cur, "rowcount", -1)
    @property
    def lastrowid(self):
        return None
    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass
    def __enter__(self):
        return self
    def __exit__(self, *a):
        self.close()
        return False


class PGConnection:
    def __init__(self):
        import database as _db
        import psycopg2
        import psycopg2.extras
        self._conn = psycopg2.connect(
            _db.DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    def cursor(self, *a, **kw):
        return PGCursor(self._conn)
    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur
    def executemany(self, sql, seq):
        cur = self.cursor()
        cur.executemany(sql, seq)
        return cur
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
    def __enter__(self):
        return self
    def __exit__(self, *a):
        try:
            self._conn.commit()
        except Exception:
            self._conn.rollback()
        self.close()
        return False


def _patched_connect(database, *args, **kwargs):
    db_str = str(database) if database else ""
    if "scores.db" in db_str or db_str.endswith(".db"):
        print(f"[sqlite_shim] Intercept: {database} -> PostgreSQL")
        return PGConnection()
    return _orig_connect(database, *args, **kwargs)


_real_sqlite3.connect = _patched_connect
print("[sqlite_shim] Installed - sqlite3.connect(scores.db) -> PostgreSQL")