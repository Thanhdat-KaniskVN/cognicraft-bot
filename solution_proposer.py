# solution_proposer.py
"""
Đề xuất giải pháp mới - Bot gợi ý cách tiếp cận KHÁC
"""
import json
import hashlib
import os
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class SolutionProposer:
    """Đề xuất giải pháp mới cho bài toán"""

    def __init__(self):
        self.cache_dir = os.path.join(CACHE_DIR, "solutions")
        os.makedirs(self.cache_dir, exist_ok=True)

    def propose(self, member, topic, content, scores):
        """Đề xuất 2-3 cách tiếp cận khác"""

        # Cache key
        cache_key = hashlib.md5(
            f"{PROMPT_VERSION}|sol|{member}|{topic}|{content[:500]}".encode()
        ).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        # Check cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    print(f"[SolutionProposer] Cache hit for {member}")
                    return json.load(f)
            except Exception:
                pass

        prompt = f"""Phan tich bai nop va de xuat CAC CACH TIEP CAN KHAC:

**Member:** {member}
**Topic:** {topic}
**Diem:** {scores}

**Bai nop:**
{content[:4000]}

**Yeu cau:**
1. Tom tat cach tiep can HIEN TAI cua member (1-2 cau)
2. De xuat 2-3 cach tiep can KHAC (khong trung voi cach hien tai)
3. Moi cach can co: mo ta, uu diem, nhuoc diem, khi nao dung, do kho

**Tra ve JSON:**
{{
  "current_approach": "<cach hien tai>",
  "alternative_solutions": [
    {{
      "name": "<ten cach>",
      "description": "<mo ta ngan>",
      "pros": ["<uu diem 1>", "<uu diem 2>"],
      "cons": ["<nhuoc diem 1>"],
      "when_to_use": "<khi nao dung>",
      "difficulty": "Easy|Medium|Hard"
    }}
  ],
  "recommended": "<cach khuyen dung nhat>"
}}

Chi tra ve JSON."""

        try:
            result = call_ai_json(prompt, task_type="solutions")

            # Save cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result
        except Exception as e:
            print(f"[SolutionProposer] Error: {e}")
            return self._fallback()

    def _fallback(self):
        return {
            "current_approach": "(Khong phan tich duoc)",
            "alternative_solutions": [],
            "recommended": "",
        }