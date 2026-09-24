# switch/sockets/cogni_bot.py
"""
Cogni Bot Socket - "Phích cắm Bot"
Đọc trực tiếp từ SQLite database
"""
import asyncio
import sqlite3
from pathlib import Path
from typing import List, Dict

from core.socket import Socket


class CogniBotSocket(Socket):
    NAME = "cogni_bot"
    TYPE = "internal_service"
    VERSION = "1.0.0"
    DESCRIPTION = "Đọc data từ Cogni Bot SQLite"

    async def _on_start(self) -> bool:
        db_path = self.config.get("db_path", "../scores.db")
        self.db_path = Path(db_path).resolve()

        if not self.db_path.exists():
            raise FileNotFoundError(f"❌ DB không tìm thấy: {self.db_path}")

        print(f"[CogniBot] ✅ Connected DB: {self.db_path}")
        return True

    async def _on_call(self, action: str, **kwargs):
        if action == "get_scores":
            return await self._get_scores(**kwargs)
        elif action == "get_member_score":
            return await self._get_member_score(**kwargs)
        elif action == "get_members":
            return await self._get_members()
        elif action == "get_stats":
            return await self._get_stats()
        else:
            raise ValueError(f"Unknown action: {action}")

    def _query(self, sql: str, params: tuple = ()):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    async def _get_scores(self, week: int):
        return await asyncio.to_thread(
            self._query,
            "SELECT * FROM scores WHERE week = ? ORDER BY member",
            (week,),
        )

    async def _get_member_score(self, week: int, member: str):
        rows = await asyncio.to_thread(
            self._query,
            "SELECT * FROM scores WHERE week = ? AND member = ?",
            (week, member),
        )
        return rows[0] if rows else None

    async def _get_members(self):
        rows = await asyncio.to_thread(
            self._query,
            "SELECT DISTINCT member FROM scores ORDER BY member",
        )
        return [r["member"] for r in rows]

    async def _get_stats(self):
        rows = await asyncio.to_thread(
            self._query,
            "SELECT COUNT(*) as c, AVG(total) as a FROM scores",
        )
        return {
            "total_scores": rows[0]["c"],
            "avg_score": round(rows[0]["a"] or 0, 2),
        }