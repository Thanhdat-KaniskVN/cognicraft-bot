# exercise_generator.py
"""
Sinh bài tập luyện tập dựa trên điểm yếu
"""
import json
import hashlib
import os
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class ExerciseGenerator:
    """Sinh bài tập cá nhân hóa"""

    def __init__(self):
        self.cache_dir = os.path.join(CACHE_DIR, "exercises")
        os.makedirs(self.cache_dir, exist_ok=True)

    def generate(self, member, topic, scores, level="auto"):
        """Sinh 3-5 bài tập tăng dần độ khó"""

        # Xác định điểm yếu
        sorted_scores = sorted(scores.items(), key=lambda x: x[1])
        weakest = sorted_scores[0]
        second = sorted_scores[1]

        # Auto level
        if level == "auto":
            avg = sum(scores.values()) / len(scores)
            if avg >= 4.5:
                level = "Hard"
            elif avg >= 3.5:
                level = "Medium"
            else:
                level = "Easy"

        # Cache key
        cache_key = hashlib.md5(
            f"{PROMPT_VERSION}|ex|{member}|{topic}|{weakest[0]}|{level}".encode()
        ).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    print(f"[ExerciseGenerator] Cache hit for {member}")
                    return json.load(f)
            except Exception:
                pass

        prompt = f"""Sinh bai tap luyen tap cho member:

**Member:** {member}
**Topic:** {topic}
**Diem:** {scores}
**Diem yeu nhat:** {weakest[0]} ({weakest[1]}/5)
**Diem yeu thu 2:** {second[0]} ({second[1]}/5)
**Level:** {level}

**Yeu cau:**
1. Sinh 3-5 bai tap tap trung vao 2 diem yeu
2. Do kho TANG DAN (Easy -> Medium -> Hard)
3. Moi bai co: de bai, goi y, dap an, thoi gian uoc tinh
4. Them 2-3 tai lieu tham khao (MIT/ETH)

**Tra ve JSON:**
{{
  "focus": "{weakest[0]}, {second[0]}",
  "exercises": [
    {{
      "id": 1,
      "difficulty": "Easy",
      "question": "<de bai>",
      "hint": "<goi y>",
      "answer": "<dap an ngan>",
      "time_estimate": "<15 phut>"
    }}
  ],
  "resources": ["<tai lieu 1>", "<tai lieu 2>"]
}}

Chi tra ve JSON."""

        try:
            result = call_ai_json(prompt, task_type="exercises")

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result
        except Exception as e:
            print(f"[ExerciseGenerator] Error: {e}")
            return self._fallback()

    def _fallback(self):
        return {
            "focus": "",
            "exercises": [],
            "resources": [],
        }