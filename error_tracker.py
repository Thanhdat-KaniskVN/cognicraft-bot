# error_tracker.py
"""
Error Tracker - Theo dõi lỗi của từng thành viên
- Lưu errors vào DB
- Phát hiện lỗi lặp lại
- Trending errors
"""
import sqlite3
import json
from datetime import datetime
from config import TIMEZONE
import pytz


class ErrorTracker:
    """Theo dõi và phân tích lỗi của thành viên"""

    def __init__(self, db_path="scores.db"):
        self.db_path = db_path
        self.tz = pytz.timezone(TIMEZONE)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS member_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER,
                member TEXT,
                error_type TEXT,
                error_detail TEXT,
                topic TEXT,
                severity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_member_error
            ON member_errors(member, week)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_error_type
            ON member_errors(error_type)
        """)
        conn.commit()
        conn.close()

    def save_errors(self, week, member, topic, errors):
        """
        Lưu errors của member vào DB.

        Args:
            week: Tuần
            member: Tên member
            topic: Topic
            errors: List of dict {type, detail, severity}
        """
        if not errors:
            return

        conn = sqlite3.connect(self.db_path)
        for err in errors:
            conn.execute("""
                INSERT INTO member_errors
                (week, member, error_type, error_detail, topic, severity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                week,
                member,
                err.get("type", "unknown"),
                err.get("detail", "")[:500],
                topic,
                err.get("severity", "medium"),
            ))
        conn.commit()
        conn.close()
        print(f"[ErrorTracker] Saved {len(errors)} errors for {member}")

    def get_member_errors(self, member, weeks=8):
        """Lấy errors của member trong N tuần gần đây"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT week, error_type, error_detail, topic, severity, created_at
            FROM member_errors
            WHERE member = ?
            ORDER BY week DESC, created_at DESC
            LIMIT 100
        """, (member,)).fetchall()
        conn.close()

        return [
            {
                "week": r[0],
                "type": r[1],
                "detail": r[2],
                "topic": r[3],
                "severity": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    def detect_repeated_errors(self, member, weeks=8):
        """
        Phát hiện lỗi lặp lại của member.

        Returns:
            dict: {
                "repeated": [
                    {"type": str, "count": int, "weeks": [int], "severity": str}
                ],
                "total_errors": int,
                "top_error": str,
            }
        """
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT error_type, week, severity
            FROM member_errors
            WHERE member = ?
            ORDER BY week DESC
            LIMIT 200
        """, (member,)).fetchall()
        conn.close()

        if not rows:
            return {
                "repeated": [],
                "total_errors": 0,
                "top_error": None,
            }

        # Group by error_type
        from collections import defaultdict
        grouped = defaultdict(list)
        for error_type, week, severity in rows:
            grouped[error_type].append({"week": week, "severity": severity})

        # Tìm lỗi lặp >= 2 lần
        repeated = []
        for error_type, entries in grouped.items():
            if len(entries) >= 2:
                repeated.append({
                    "type": error_type,
                    "count": len(entries),
                    "weeks": sorted(set(e["week"] for e in entries), reverse=True)[:5],
                    "severity": max((e["severity"] for e in entries),
                                    key=lambda s: {"low": 0, "medium": 1, "high": 2}.get(s, 0)),
                })

        # Sort by count
        repeated.sort(key=lambda x: x["count"], reverse=True)

        # Top error
        top_error = repeated[0]["type"] if repeated else None

        return {
            "repeated": repeated,
            "total_errors": len(rows),
            "top_error": top_error,
        }

    def get_error_patterns(self, member):
        """Lấy patterns lỗi để phân tích"""
        errors = self.get_member_errors(member)

        if not errors:
            return {
                "has_repeated": False,
                "patterns": [],
                "recommendation": "Chưa có đủ dữ liệu để phân tích pattern.",
            }

        repeated = self.detect_repeated_errors(member)

        if repeated["repeated"]:
            # Có lỗi lặp
            top = repeated["repeated"][0]
            recommendation = (
                f"⚠️ **Lỗi lặp lại phát hiện:**\n"
                f"- **{top['type']}** – xuất hiện **{top['count']} lần** "
                f"(tuần: {', '.join(map(str, top['weeks']))})\n"
                f"- Cần tập trung cải thiện lỗi này!\n"
                f"- Đã gợi ý tài liệu bổ trợ bên dưới."
            )
        else:
            recommendation = (
                f"✅ Chưa phát hiện lỗi lặp lại.\n"
                f"- Tổng lỗi ghi nhận: {repeated['total_errors']}\n"
                f"- Tiếp tục phát huy!"
            )

        return {
            "has_repeated": bool(repeated["repeated"]),
            "patterns": repeated["repeated"],
            "total_errors": repeated["total_errors"],
            "recommendation": recommendation,
        }

    def get_stats(self):
        """Thống kê tổng quan"""
        conn = sqlite3.connect(self.db_path)
        total = conn.execute("SELECT COUNT(*) FROM member_errors").fetchone()[0]
        members = conn.execute(
            "SELECT DISTINCT member FROM member_errors"
        ).fetchall()
        conn.close()

        return {
            "total_errors": total,
            "members_tracked": len(members),
            "members": [m[0] for m in members],
        }

    def reset(self, member=None):
        """Xóa errors (của member hoặc tất cả)"""
        conn = sqlite3.connect(self.db_path)
        if member:
            conn.execute("DELETE FROM member_errors WHERE member = ?", (member,))
        else:
            conn.execute("DELETE FROM member_errors")
        conn.commit()
        conn.close()
        print(f"[ErrorTracker] Reset {'all' if not member else member}")