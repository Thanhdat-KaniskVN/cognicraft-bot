# advanced_mode.py
"""
Advanced Mode - Phân tầng mode theo lộ trình
- 3 tầng: Foundation / Advanced / Mastery
- Kết hợp với Roadmap Mode (Academic/Research/Project)
- Adaptive recommendations theo tier
- Track tier progression
"""
import json
import hashlib
import os
import sqlite3
import statistics
from datetime import datetime
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class AdvancedMode:
    """Phân tầng mode theo lộ trình"""

    # Tier definitions
    TIER_FOUNDATION = "Foundation"
    TIER_ADVANCED = "Advanced"
    TIER_MASTERY = "Mastery"

    # Ngưỡng điểm
    FOUNDATION_MAX = 3.5
    ADVANCED_MAX = 4.5

    # Tier icons
    TIER_ICONS = {
        TIER_FOUNDATION: "🌱",
        TIER_ADVANCED: "🌿",
        TIER_MASTERY: "🌳",
    }

    # Tier descriptions
    TIER_DESCRIPTIONS = {
        TIER_FOUNDATION: "Củng cố cơ bản - tập trung hiểu concepts",
        TIER_ADVANCED: "Cân bằng lý thuyết + thực hành",
        TIER_MASTERY: "Chuyên sâu - research, project, mở rộng",
    }

    def __init__(self, db_path="scores.db"):
        self.db_path = db_path
        self.cache_dir = os.path.join(CACHE_DIR, "advanced_mode")
        os.makedirs(self.cache_dir, exist_ok=True)

    # ============================================================
    # TIER CLASSIFICATION
    # ============================================================

    def get_tier(self, member, weeks=4):
        """
        Xác định tier của member dựa vào điểm gần đây.

        Args:
            member: Tên member
            weeks: Số tuần gần đây để tính

        Returns:
            dict: {
                "tier": str,
                "icon": str,
                "description": str,
                "avg_score": float,
                "score_count": int,
            }
        """
        member_clean = member.split("-NR.")[0].strip()
        scores = self._get_recent_scores(member_clean, weeks)

        if not scores:
            return {
                "tier": self.TIER_FOUNDATION,
                "icon": self.TIER_ICONS[self.TIER_FOUNDATION],
                "description": self.TIER_DESCRIPTIONS[self.TIER_FOUNDATION],
                "avg_score": 0,
                "score_count": 0,
            }

        values = [s["total"] for s in scores]
        avg_score = round(statistics.mean(values), 2)

        if avg_score < self.FOUNDATION_MAX:
            tier = self.TIER_FOUNDATION
        elif avg_score < self.ADVANCED_MAX:
            tier = self.TIER_ADVANCED
        else:
            tier = self.TIER_MASTERY

        return {
            "tier": tier,
            "icon": self.TIER_ICONS[tier],
            "description": self.TIER_DESCRIPTIONS[tier],
            "avg_score": avg_score,
            "score_count": len(scores),
        }

    def get_all_tiers(self):
        """Lấy tier của tất cả members"""
        from config import ALL_MEMBERS

        result = {}
        for m in ALL_MEMBERS:
            member_clean = m.split("-NR.")[0].strip()
            result[member_clean] = self.get_tier(member_clean)
        return result

    # ============================================================
    # ROADMAP MODE (từ time_tracker)
    # ============================================================

    def get_roadmap_mode(self, week):
        """Lấy roadmap mode từ time_tracker"""
        from time_tracker import TimeTracker
        tt = TimeTracker()
        return tt.get_week_mode(week)

    # ============================================================
    # ADAPTIVE RECOMMENDATIONS
    # ============================================================

    def get_recommendations(self, member, week):
        """
        Đề xuất nội dung học tập dựa vào:
        - Tier của member
        - Roadmap mode của tuần

        Returns:
            dict: {
                "member": str,
                "tier": str,
                "tier_icon": str,
                "roadmap_mode": str,
                "focus": [str],
                "activities": [str],
                "resources": [str],
                "next_tier": dict,
                "progress_pct": float,
            }
        """
        member_clean = member.split("-NR.")[0].strip()

        # Get tier
        tier_info = self.get_tier(member_clean)
        tier = tier_info["tier"]

        # Get roadmap mode
        roadmap_mode = self.get_roadmap_mode(week)

        # AI recommendations
        cache_key = hashlib.md5(
            f"{PROMPT_VERSION}|adv|{member_clean}|{week}|{tier}|{roadmap_mode}".encode()
        ).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        recommendations = self._generate_recommendations(
            member_clean, tier, roadmap_mode, tier_info
        )

        # Calculate next tier progress
        avg_score = tier_info["avg_score"]
        next_tier = self._get_next_tier_info(tier, avg_score)

        result = {
            "member": member_clean,
            "tier": tier,
            "tier_icon": self.TIER_ICONS[tier],
            "tier_description": self.TIER_DESCRIPTIONS[tier],
            "avg_score": avg_score,
            "roadmap_mode": roadmap_mode,
            "focus": recommendations.get("focus", []),
            "activities": recommendations.get("activities", []),
            "resources": recommendations.get("resources", []),
            "next_tier": next_tier,
        }

        # Save cache
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result

    def _generate_recommendations(self, member, tier, roadmap_mode, tier_info):
        """Sinh recommendations bằng AI"""
        prompt = f"""Bạn là AI Coach của CogniCraft. Đề xuất nội dung học tập cho member.

**Member:** {member}
**Tier:** {tier}
**Điểm TB 4 tuần:** {tier_info['avg_score']}/5
**Roadmap Mode tuần này:** {roadmap_mode}

**Định nghĩa tier:**
- Foundation (< 3.5): Củng cố cơ bản, hiểu concepts
- Advanced (3.5-4.5): Cân bằng lý thuyết + thực hành
- Mastery (> 4.5): Chuyên sâu, research, project

**Định nghĩa roadmap mode:**
- Academic: Học + checkpoint
- Research Literacy: Đọc paper + viết Research Note
- Project: Code + Report + Demo

**YÊU CẦU:**
- Đề xuất 3-5 focus points (điểm cần tập trung)
- Đề xuất 3-5 activities (hoạt động cụ thể)
- Đề xuất 2-3 resources (tài liệu)

**Trả về JSON:**
{{
  "focus": ["<focus 1>", "<focus 2>", "<focus 3>"],
  "activities": ["<activity 1>", "<activity 2>", "<activity 3>"],
  "resources": ["<resource 1>", "<resource 2>"]
}}

Chỉ trả về JSON."""

        try:
            return call_ai_json(prompt, task_type="advanced_mode")
        except Exception as e:
            print(f"[AdvancedMode] Generate error: {e}")
            return self._fallback_recommendations(tier, roadmap_mode)

    def _fallback_recommendations(self, tier, roadmap_mode):
        """Fallback recommendations"""
        return {
            "focus": [
                f"Tier: {tier}",
                f"Mode: {roadmap_mode}",
                "Hoàn thành bài tập đúng hạn",
            ],
            "activities": [
                "Đọc tài liệu theo roadmap",
                "Làm bài tập thực hành",
                "Review chéo với đồng đội",
            ],
            "resources": [
                "MIT OCW",
                "Book of Proof",
            ],
        }

    def _get_next_tier_info(self, current_tier, avg_score):
        """Tính thông tin tier tiếp theo"""
        if current_tier == self.TIER_FOUNDATION:
            target = self.FOUNDATION_MAX
            next_tier = self.TIER_ADVANCED
        elif current_tier == self.TIER_ADVANCED:
            target = self.ADVANCED_MAX
            next_tier = self.TIER_MASTERY
        else:
            return {
                "next_tier": None,
                "target_score": 5.0,
                "gap": 0,
                "progress_pct": 100,
                "message": "Đã đạt tier cao nhất! Duy trì phong độ.",
            }

        gap = round(target - avg_score, 2)
        progress_pct = round((avg_score / target) * 100, 1) if target > 0 else 0

        return {
            "next_tier": next_tier,
            "target_score": target,
            "gap": gap,
            "progress_pct": progress_pct,
            "message": f"Cần +{gap} điểm để lên {next_tier}",
        }

    # ============================================================
    # TIER STATS
    # ============================================================

    def get_tier_distribution(self):
        """Thống kê phân bố tier của cohort"""
        tiers = self.get_all_tiers()

        distribution = {
            self.TIER_FOUNDATION: [],
            self.TIER_ADVANCED: [],
            self.TIER_MASTERY: [],
        }

        for member, info in tiers.items():
            distribution[info["tier"]].append({
                "member": member,
                "avg_score": info["avg_score"],
            })

        return {
            "total": len(tiers),
            "foundation": len(distribution[self.TIER_FOUNDATION]),
            "advanced": len(distribution[self.TIER_ADVANCED]),
            "mastery": len(distribution[self.TIER_MASTERY]),
            "distribution": distribution,
        }

    # ============================================================
    # UTILS
    # ============================================================

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

    def format_tier_for_discord(self, info):
        """Format tier info cho Discord"""
        msg = f"# {info['tier_icon']} TIER: {info['tier'].upper()}\n\n"
        msg += f"**{info['member']}**\n"
        msg += f"_{info['tier_description']}_\n\n"
        msg += f"**Điểm TB 4 tuần:** {info['avg_score']}/5\n"
        msg += f"**Roadmap mode:** {info['roadmap_mode']}\n\n"

        if info.get("focus"):
            msg += f"## 🎯 Focus\n"
            for f in info["focus"][:5]:
                msg += f"- {f}\n"
            msg += "\n"

        if info.get("activities"):
            msg += f"## 📝 Activities\n"
            for a in info["activities"][:5]:
                msg += f"- {a}\n"
            msg += "\n"

        if info.get("resources"):
            msg += f"## 📚 Resources\n"
            for r in info["resources"][:3]:
                msg += f"- {r}\n"
            msg += "\n"

        next_tier = info.get("next_tier", {})
        if next_tier and next_tier.get("next_tier"):
            msg += f"## 📈 Tiến độ lên tier\n"
            msg += f"- **Next:** {next_tier['next_tier']}\n"
            msg += f"- **Target:** {next_tier['target_score']}/5\n"
            msg += f"- **Cần thêm:** +{next_tier['gap']} điểm\n"
            msg += f"- **Progress:** {next_tier['progress_pct']}%\n"
        elif next_tier and next_tier.get("message"):
            msg += f"## 🏆 {next_tier['message']}\n"

        return msg


# ============================================================
# TEST BLOCK
# ============================================================

if __name__ == "__main__":
    adv = AdvancedMode()

    print("=" * 60)
    print("ADVANCED MODE TEST")
    print("=" * 60)

    # Test tier classification
    print("\n=== TIER CLASSIFICATION ===")
    tiers = adv.get_all_tiers()
    for member, info in tiers.items():
        icon = info["icon"]
        print(f"{icon} {member:15s} | {info['tier']:12s} | {info['avg_score']}/5")

    # Test distribution
    print("\n=== TIER DISTRIBUTION ===")
    dist = adv.get_tier_distribution()
    print(f"Total: {dist['total']}")
    print(f"🌱 Foundation: {dist['foundation']}")
    print(f"🌿 Advanced: {dist['advanced']}")
    print(f"🌳 Mastery: {dist['mastery']}")