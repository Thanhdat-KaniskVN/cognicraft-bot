# weekly_planner.py
"""
Weekly Planner - Lập kế hoạch tuần tự động
- Phân tích data: scores, errors, GHS, trends
- AI sinh kế hoạch cho từng member
- Đề xuất task cụ thể
- Lưu vào Sheets + Post Discord
"""
import json
import hashlib
import os
import sqlite3
from datetime import datetime
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class WeeklyPlanner:
    """Lập kế hoạch tuần tự động"""

    def __init__(self, db_path="scores.db"):
        self.db_path = db_path
        self.cache_dir = os.path.join(CACHE_DIR, "planner")
        os.makedirs(self.cache_dir, exist_ok=True)

    # ============================================================
    # DATA GATHERING
    # ============================================================

    def _get_week_data(self, week):
        """Thu thập toàn bộ data của tuần"""
        data = {
            "week": week,
            "scores": self._get_scores(week),
            "participation": self._get_participation(week),
            "errors": self._get_errors(week),
            "ghs": self._get_ghs(week),
            "member_stats": {},
        }

        # Tổng hợp stats per member
        for member in self._get_members():
            data["member_stats"][member] = {
                "recent_scores": self._get_recent_scores(member, weeks=4),
                "repeated_errors": self._get_repeated_errors(member),
                "trend": self._get_trend(member),
            }

        return data

    def _get_scores(self, week):
        """Lấy điểm của tuần"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT member, total, accuracy, depth, connection, presentation
            FROM scores WHERE week = ?
        """, (week,)).fetchall()
        conn.close()

        return [
            {
                "member": r[0],
                "total": r[1],
                "accuracy": r[2],
                "depth": r[3],
                "connection": r[4],
                "presentation": r[5],
            }
            for r in rows
        ]

    def _get_participation(self, week):
        """Lấy participation của tuần"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT member, submitted FROM participation WHERE week = ?
        """, (week,)).fetchall()
        conn.close()

        return [{"member": r[0], "submitted": bool(r[1])} for r in rows]

    def _get_errors(self, week):
        """Lấy errors của tuần"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT member, error_type, error_detail, severity
            FROM member_errors WHERE week = ?
        """, (week,)).fetchall()
        conn.close()

        return [
            {
                "member": r[0],
                "type": r[1],
                "detail": r[2],
                "severity": r[3],
            }
            for r in rows
        ]
    def _get_ghs(self, week):
        """Tính GHS từ scores (thay vì đọc bảng ghs)"""
        try:
            conn = sqlite3.connect(self.db_path)

            # Lấy AQ (trung bình điểm)
            scores = conn.execute("""
                SELECT AVG(total) FROM scores WHERE week = ?
            """, (week,)).fetchone()
            aq = scores[0] if scores and scores[0] else 0

            # Lấy P (participation)
            part = conn.execute("""
                SELECT 
                    COUNT(CASE WHEN submitted = 1 THEN 1 END) as submitted,
                    COUNT(*) as total
                FROM participation WHERE week = ?
            """, (week,)).fetchone()
            submitted, total = (part[0], part[1]) if part else (0, 5)
            p_score = 1 + 4 * (submitted / total) if total > 0 else 1

            conn.close()

            # WB mặc định 3.0 (vì không có feedback data)
            wb = 3.0

            # Tính GHS
            ghs = 0.4 * aq + 0.4 * p_score + 0.2 * wb

            # Xác định status
            if ghs >= 4.0:
                status = "Healthy"
            elif ghs >= 3.0:
                status = "Warning"
            else:
                status = "Critical"

            return {
                "aq": round(aq, 2),
                "p": round(p_score, 2),
                "wb": round(wb, 2),
                "ghs": round(ghs, 2),
                "status": status,
            }
        except Exception as e:
            print(f"[Planner] GHS calc error: {e}")
            return None

    def _get_members(self):
        """Lấy danh sách members"""
        from config import ALL_MEMBERS
        return [m.split("-NR.")[0].strip() for m in ALL_MEMBERS]

    def _get_recent_scores(self, member, weeks=4):
        """Lấy điểm N tuần gần nhất"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT week, total FROM scores
            WHERE member = ?
            ORDER BY week DESC
            LIMIT ?
        """, (member, weeks)).fetchall()
        conn.close()

        return [{"week": r[0], "total": r[1]} for r in rows]

    def _get_repeated_errors(self, member):
        """Lấy lỗi lặp lại của member"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT error_type, COUNT(*) as cnt
            FROM member_errors
            WHERE member = ?
            GROUP BY error_type
            HAVING cnt >= 2
            ORDER BY cnt DESC
            LIMIT 3
        """, (member,)).fetchall()
        conn.close()

        return [{"type": r[0], "count": r[1]} for r in rows]

    def _get_trend(self, member):
        """Lấy xu hướng điểm"""
        scores = self._get_recent_scores(member, weeks=4)
        if len(scores) < 2:
            return "unknown"

        values = [s["total"] for s in reversed(scores)]
        slope = values[-1] - values[0]

        if slope > 0.2:
            return "improving"
        elif slope < -0.2:
            return "declining"
        else:
            return "stable"

    # ============================================================
    # PLAN GENERATION
    # ============================================================

    def generate_plan(self, week, mode="Academic"):
        """
        Sinh kế hoạch tuần.

        Returns:
            dict: {
                "week": int,
                "mode": str,
                "overview": str,
                "group_tasks": [str],
                "member_tasks": {member: [task]},
                "warnings": [str],
                "focus_topics": [str],
            }
        """
        # Cache key
        cache_key = hashlib.md5(
            f"{PROMPT_VERSION}|plan|{week}|{mode}".encode()
        ).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    print(f"[Planner] Cache hit for week {week}")
                    return json.load(f)
            except Exception:
                pass

        # Gather data
        data = self._get_week_data(week)

        # Build prompt
        prompt = self._build_prompt(week, mode, data)

        try:
            result = call_ai_json(prompt, task_type="planner")

            # Save cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result
        except Exception as e:
            print(f"[Planner] Generate error: {e}")
            return self._fallback_plan(week, mode)

    def _build_prompt(self, week, mode, data):
        """Build prompt cho AI"""

        # Scores summary
        scores_text = ""
        if data["scores"]:
            for s in data["scores"]:
                scores_text += (
                    f"- {s['member']}: {s['total']}/5 "
                    f"(Accuracy: {s['accuracy']}, Depth: {s['depth']}, "
                    f"Connection: {s['connection']}, Presentation: {s['presentation']})\n"
                )
        else:
            scores_text = "(Chưa có điểm)\n"

        # Participation
        part_text = ""
        submitted = [p["member"] for p in data["participation"] if p["submitted"]]
        missing = [p["member"] for p in data["participation"] if not p["submitted"]]
        part_text = f"- Đã nộp: {', '.join(submitted) if submitted else 'không có'}\n"
        part_text += f"- Chưa nộp: {', '.join(missing) if missing else 'không có'}\n"

        # Errors
        errors_text = ""
        if data["errors"]:
            for e in data["errors"][:10]:
                errors_text += f"- {e['member']}: [{e['type']}] {e['detail'][:100]}\n"
        else:
            errors_text = "(Không có lỗi)\n"

        # GHS
        ghs_text = "(Chưa có GHS)\n"
        if data["ghs"]:
            ghs_text = (
                f"- AQ: {data['ghs']['aq']}\n"
                f"- P: {data['ghs']['p']}\n"
                f"- WB: {data['ghs']['wb']}\n"
                f"- GHS: {data['ghs']['ghs']} ({data['ghs']['status']})\n"
            )

        # Member stats
        stats_text = ""
        for member, stats in data["member_stats"].items():
            stats_text += f"\n**{member}:**\n"
            if stats["recent_scores"]:
                scores_str = " → ".join(
                    f"W{s['week']}: {s['total']}"
                    for s in reversed(stats["recent_scores"])
                )
                stats_text += f"- Điểm 4 tuần: {scores_str}\n"
            stats_text += f"- Xu hướng: {stats['trend']}\n"
            if stats["repeated_errors"]:
                errs = ", ".join(f"{e['type']} (x{e['count']})" for e in stats["repeated_errors"])
                stats_text += f"- Lỗi lặp lại: {errs}\n"

        prompt = f"""Bạn là AI Coach của CogniCraft. Lập KẾ HOẠCH TUẦN {week} cho cohort.

**Mode:** {mode}

**ĐIỂM TUẦN NÀY:**
{scores_text}

**THAM GIA:**
{part_text}

**LỖI PHÁT HIỆN:**
{errors_text}

**GHS (Sức khỏe nhóm):**
{ghs_text}

**STATS TỪNG MEMBER:**
{stats_text}

**YÊU CẦU:**
1. **Overview:** Tổng kết tình hình tuần (2-3 câu)
2. **Group tasks:** 3-5 task chung cho cả nhóm
3. **Member tasks:** Với mỗi member, đề xuất 2-3 task cụ thể dựa vào:
   - Điểm yếu của họ
   - Lỗi lặp lại của họ
   - Xu hướng
4. **Warnings:** Cảnh báo nếu có vấn đề (GHS thấp, member declining, etc.)
5. **Focus topics:** 2-3 topic cần tập trung tuần này

**Trả về JSON:**
{{
  "overview": "<tổng kết 2-3 câu>",
  "group_tasks": ["<task 1>", "<task 2>", "<task 3>"],
  "member_tasks": {{
    "<member_name>": ["<task 1>", "<task 2>"]
  }},
  "warnings": ["<cảnh báo 1>", "<cảnh báo 2>"],
  "focus_topics": ["<topic 1>", "<topic 2>"]
}}

Chỉ trả về JSON. Không giải thích thêm."""

        return prompt

    def _fallback_plan(self, week, mode):
        """Plan fallback nếu AI fail"""
        return {
            "overview": f"Kế hoạch tuần {week} ({mode}) – dùng template mặc định.",
            "group_tasks": [
                "Hoàn thành checkpoint đúng hạn",
                "Review chéo bài của đồng đội",
                "Tham gia họp cuối tuần đầy đủ",
            ],
            "member_tasks": {},
            "warnings": [],
            "focus_topics": [],
        }

    # ============================================================
    # NOTIFICATION
    # ============================================================

    def format_plan_for_discord(self, plan):
        """Format plan thành text để post Discord"""
        msg = f"# 📋 KẾ HOẠCH TUẦN {plan.get('week', '?')}\n"
        msg += f"**Mode:** {plan.get('mode', '?')}\n\n"

        # Overview
        if plan.get("overview"):
            msg += f"## 📊 Tổng quan\n{plan['overview']}\n\n"

        # Group tasks
        if plan.get("group_tasks"):
            msg += f"## 🎯 Task nhóm\n"
            for task in plan["group_tasks"]:
                msg += f"- {task}\n"
            msg += "\n"

        # Member tasks
        if plan.get("member_tasks"):
            msg += f"## 👥 Task cá nhân\n"
            for member, tasks in plan["member_tasks"].items():
                msg += f"**{member}:**\n"
                for task in tasks:
                    msg += f"- {task}\n"
                msg += "\n"

        # Warnings
        if plan.get("warnings"):
            msg += f"## ⚠️ Cảnh báo\n"
            for w in plan["warnings"]:
                msg += f"- {w}\n"
            msg += "\n"

        # Focus topics
        if plan.get("focus_topics"):
            msg += f"## 📚 Topic cần tập trung\n"
            for t in plan["focus_topics"]:
                msg += f"- {t}\n"

        return msg