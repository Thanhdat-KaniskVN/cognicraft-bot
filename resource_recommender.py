# resource_recommender.py
"""
Resource Recommender - Đề xuất tài liệu dựa trên lỗi
"""
import json
import hashlib
import os
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class ResourceRecommender:
    """Đề xuất tài liệu học tập dựa trên lỗi của member"""

    # Resource bank (local)
    RESOURCE_BANK = {
        "logic_error": [
            {
                "title": "MIT 6.042J – Logic and Proofs",
                "url": "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/",
                "type": "course",
            },
            {
                "title": "Book of Proof – Chapter 2",
                "url": "https://www.people.vcu.edu/~rhammack/BookOfProof/",
                "type": "book",
            },
        ],
        "proof_error": [
            {
                "title": "Book of Proof – Chapter 4-5 (Direct Proof)",
                "url": "https://www.people.vcu.edu/~rhammack/BookOfProof/",
                "type": "book",
            },
            {
                "title": "ETH Discrete Mathematics – Chapter 2",
                "url": "https://www.research-collection.ethz.ch/bitstream/handle/20.500.11850/548053/9783728141101.pdf",
                "type": "pdf",
            },
        ],
        "induction_error": [
            {
                "title": "MIT 6.042J – Lecture 7-8 (Induction)",
                "url": "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/",
                "type": "course",
            },
            {
                "title": "Book of Proof – Chapter 10 (Induction)",
                "url": "https://www.people.vcu.edu/~rhammack/BookOfProof/",
                "type": "book",
            },
        ],
        "code_smell": [
            {
                "title": "Clean Code – Robert C. Martin",
                "url": "https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882",
                "type": "book",
            },
            {
                "title": "PEP 8 – Python Style Guide",
                "url": "https://peps.python.org/pep-0008/",
                "type": "docs",
            },
        ],
        "algorithm_error": [
            {
                "title": "MIT 6.006 – Introduction to Algorithms",
                "url": "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/",
                "type": "course",
            },
            {
                "title": "LeetCode – Practice Problems",
                "url": "https://leetcode.com/problemset/all/",
                "type": "practice",
            },
        ],
        "complexity_error": [
            {
                "title": "Big-O Cheat Sheet",
                "url": "https://www.bigocheatsheet.com/",
                "type": "reference",
            },
            {
                "title": "MIT 6.046J – Advanced Algorithms",
                "url": "https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/",
                "type": "course",
            },
        ],
        "sql_error": [
            {
                "title": "SQLBolt – Interactive SQL Tutorial",
                "url": "https://sqlbolt.com/",
                "type": "tutorial",
            },
            {
                "title": "CMU 15-445 – Database Systems",
                "url": "https://15445.courses.cs.cmu.edu/",
                "type": "course",
            },
        ],
        "default": [
            {
                "title": "MIT OpenCourseWare",
                "url": "https://ocw.mit.edu/",
                "type": "portal",
            },
            {
                "title": "Stack Overflow",
                "url": "https://stackoverflow.com/",
                "type": "qa",
            },
        ],
    }

    def __init__(self):
        self.cache_dir = os.path.join(CACHE_DIR, "resources")
        os.makedirs(self.cache_dir, exist_ok=True)

    def recommend(self, member, topic, errors, error_patterns=None):
        """
        Đề xuất tài liệu dựa trên lỗi.

        Args:
            member: Tên member
            topic: Topic bài nộp
            errors: List of errors (từ AI scorer)
            error_patterns: Kết quả từ ErrorTracker.get_error_patterns()

        Returns:
            dict: {
                "resources": [{"title": str, "url": str, "type": str, "reason": str}],
                "focus": str,
                "priority": str,
            }
        """
        # Cache key
        cache_key = hashlib.md5(
            f"{PROMPT_VERSION}|rr|{member}|{topic}|{len(errors)}".encode()
        ).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Bước 1: Map errors → resource categories
        categories = self._map_errors_to_categories(errors, error_patterns)

        # Bước 2: Lấy resources từ bank
        resources = []
        for cat in categories[:3]:  # Top 3 categories
            bank_resources = self.RESOURCE_BANK.get(cat, self.RESOURCE_BANK["default"])
            for res in bank_resources[:2]:  # 2 resources/category
                resources.append({
                    "title": res["title"],
                    "url": res["url"],
                    "type": res["type"],
                    "reason": f"Bổ trợ cho lỗi: {cat}",
                })

        # Bước 3: Xác định focus
        if categories:
            focus = categories[0]
        else:
            focus = "general"

        # Bước 4: Priority
        if error_patterns and error_patterns.get("has_repeated"):
            priority = "high"
        elif len(errors) >= 3:
            priority = "high"
        elif len(errors) >= 1:
            priority = "medium"
        else:
            priority = "low"

        result = {
            "resources": resources[:5],
            "focus": focus,
            "priority": priority,
            "categories": categories,
        }

        # Save cache
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result

    def _map_errors_to_categories(self, errors, error_patterns):
        """Map errors → resource categories"""
        categories = []

        # Từ errors hiện tại
        for err in errors or []:
            err_type = err.get("type", "").lower()
            err_detail = err.get("detail", "").lower()

            # Keyword matching
            if "logic" in err_type or "logic" in err_detail or "mệnh đề" in err_detail:
                categories.append("logic_error")
            elif "proof" in err_type or "chứng minh" in err_detail:
                categories.append("proof_error")
            elif "induction" in err_type or "quy nạp" in err_detail:
                categories.append("induction_error")
            elif "algorithm" in err_type or "thuật toán" in err_detail:
                categories.append("algorithm_error")
            elif "complexity" in err_type or "độ phức tạp" in err_detail:
                categories.append("complexity_error")
            elif "sql" in err_type or "database" in err_detail:
                categories.append("sql_error")
            elif "code" in err_type or "smell" in err_type:
                categories.append("code_smell")

        # Từ patterns (lỗi lặp lại)
        if error_patterns and error_patterns.get("patterns"):
            for p in error_patterns["patterns"][:3]:
                p_type = p.get("type", "").lower()
                if "logic" in p_type:
                    categories.append("logic_error")
                elif "proof" in p_type:
                    categories.append("proof_error")
                elif "induction" in p_type:
                    categories.append("induction_error")
                elif "code" in p_type:
                    categories.append("code_smell")

        # Deduplicate + preserve order
        seen = set()
        result = []
        for c in categories:
            if c not in seen:
                seen.add(c)
                result.append(c)

        return result

    def build_recommendation_text(self, recommendation, error_patterns=None):
        """Build text để hiển thị trong Discord"""
        if not recommendation["resources"]:
            return ""

        msg = f"## 📚 TÀI LIỆU BỔ TRỢ\n\n"

        # Priority
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        icon = priority_icons.get(recommendation["priority"], "⚪")
        msg += f"**Mức độ ưu tiên:** {icon} {recommendation['priority'].upper()}\n"
        msg += f"**Focus:** `{recommendation['focus']}`\n\n"

        # Resources
        for res in recommendation["resources"]:
            msg += f"- **[{res['title']}]({res['url']})** `[{res['type']}]`\n"
            msg += f"  _{res['reason']}_\n"

        # Warning nếu lỗi lặp lại
        if error_patterns and error_patterns.get("has_repeated"):
            msg += f"\n⚠️ **LƯU Ý:** Bạn có lỗi lặp lại – cần tập trung cải thiện!\n"

        return msg