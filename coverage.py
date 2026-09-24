import json
import os
import hashlib
from config import CACHE_DIR, PROMPT_VERSION
from ai_provider import call_ai_json


class CoverageAnalyzer:
    def __init__(self, roadmap_path):
        with open(roadmap_path, "r", encoding="utf-8") as f:
            self.roadmap = json.load(f)
        self.cache_dir = os.path.join(CACHE_DIR, "coverage")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, submissions, week):
        roadmap_hash = hashlib.md5(
            json.dumps(self.roadmap, sort_keys=True).encode()
        ).hexdigest()[:8]
        data_hash = hashlib.md5(
            json.dumps(submissions, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]
        return f"{PROMPT_VERSION}_w{week}_{roadmap_hash}_{data_hash}"

    def analyze(self, submissions, week):
        cache_key = self._cache_key(submissions, week)
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        topics = self._extract_topics()

        if not submissions:
            return self._fallback_coverage(topics)

        compact_subs = [{
            "member": s.get("member", ""),
            "topic": s.get("topic", ""),
            "content_preview": s.get("content", "")[:2000],
        } for s in submissions]

        prompt = f"""Phan tich muc do cover cac topic sau dua tren bai nop.

TOPICS (danh sach day du):
{json.dumps(topics, ensure_ascii=False, indent=2)}

SUBMISSIONS:
{json.dumps(compact_subs, ensure_ascii=False, indent=2)}

**YEU CAU QUAN TRONG:**
- CHI tra ve cac topic CO IT NHAT 1 member cover (covered > 0)
- KHONG liet ke cac topic chua duoc cover (de tiet kiem token)
- Moi topic covered: diem 0-100, score 0-5, danh sach members

Tra ve JSON:
{{
  "coverage": {{
    "<topic_id>": {{"covered": <0-100>, "score": <0-5>, "members": ["ten"]}}
  }},
  "summary": "<nhan xet toi da 200 tu>"
}}

Vi du: neu chi co topic "induction" duoc cover boi DatPT va QuanAP:
{{
  "coverage": {{
    "induction": {{"covered": 85, "score": 4.5, "members": ["DatPT", "QuanAP"]}}
  }},
  "summary": "Nhom da cover tot chu de induction..."
}}

Chi tra ve JSON."""

        try:
            result = call_ai_json(prompt, task_type="coverage")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return result
        except Exception as e:
            print(f"[Coverage] Error: {e}")
            return self._fallback_coverage(topics)

    def _extract_topics(self):
        topics = []
        for phase in self.roadmap["phases"]:
            for topic in phase["topics"]:
                topics.append({
                    "id": topic["id"],
                    "name": topic["name"],
                    "keywords": topic.get("keywords", []),
                })
        return topics

    def _fallback_coverage(self, topics):
        return {
            "coverage": {},  # Không list 25 topics nữa
            "summary": "Coverage analyzer gap loi - kiem tra log.",
            "error": True,
        }