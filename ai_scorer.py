# ai_scorer.py
import json
import os
import hashlib
from typing import Optional
from config import CACHE_DIR, PROMPT_VERSION
from ai_provider import call_ai_json


class AIScorer:
    def __init__(self):
        self.cache_dir = os.path.join(CACHE_DIR, "scoring")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, member: str, week: int, content: str) -> str:
        raw = f"{PROMPT_VERSION}_{member}_{week}_{content}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _load_cache(self, key: str) -> Optional[dict]:
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _save_cache(self, key: str, data: dict):
        path = os.path.join(self.cache_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def score_submission(self, member: str, week: int, content: str) -> dict:
        cache_key = self._cache_key(member, week, content)
        cached = self._load_cache(cache_key)
        if cached:
            cached["source"] = "ai_suggested_cached"
            return cached

        prompt = f'''Ban la giam khao hoc thuat. Cham bai nop sau theo 4 tieu chi (thang 0-5):

**Bai nop cua {member}:**
{content}

**4 tieu chi:**
1. Chinh xac (accuracy): Noi dung co dung khong? Co sai sot logic/cong thuc khong?
2. Do sau (depth): Co giai thich duoc "tai sao" khong? Co phan bien khong?
3. Lien ket (connection): Co ket noi voi kien thuc khac/ung dung thuc te khong?
4. Trinh bay (presentation): Co ro rang, co cau truc, de doc khong?

**YEU CAU QUAN TRONG:**
Ngoai 4 tieu chi, hay PHAT HIEN LỖI cu the trong bai nop:

- **Logic errors**: Sai logic, nguoc menh de
- **Proof errors**: Chứng minh sai, thieu buoc
- **Induction errors**: Quy nap sai, thieu buoc
- **Code smell**: Code kho doc, hardcoded, bare except
- **Algorithm errors**: Thuat toan sai, do phuc tap cao
- **Complexity errors**: Big-O sai
- **SQL errors**: Query sai, thieu index
- **Concept missing**: Thieu khai niem quan trong

Moi loi can co:
- type: loai loi
- detail: mo ta cu the
- severity: low | medium | high

**Tra ve JSON:**
{{
  "accuracy": <so 0-5>,
  "depth": <so 0-5>,
  "connection": <so 0-5>,
  "presentation": <so 0-5>,
  "reason": "<ly do ngan gon>",
  "errors": [
    {{
      "type": "<loai loi>",
      "detail": "<mo ta cu the>",
      "severity": "low|medium|high"
    }}
  ],
  "strengths": ["<diem manh 1>", "<diem manh 2>"],
  "weaknesses": ["<diem yeu 1>", "<diem yeu 2>"]
}}

Chi tra ve JSON.'''

        try:
            result = call_ai_json(prompt, task_type="scoring")

            for key in ["accuracy", "depth", "connection", "presentation"]:
                if key not in result:
                    result[key] = 0
                result[key] = max(0, min(5, float(result[key])))

            if "errors" not in result:
                result["errors"] = []
            if "strengths" not in result:
                result["strengths"] = []
            if "weaknesses" not in result:
                result["weaknesses"] = []

            result["source"] = "ai_suggested"
            self._save_cache(cache_key, result)
            return result

        except Exception as e:
            print(f"[AIScorer] Error: {e}")
            return self._fallback_scores()

    def _fallback_scores(self) -> dict:
        return {
            "accuracy": 0, "depth": 0, "connection": 0, "presentation": 0,
            "reason": "Khong phan tich duoc", "source": "fallback",
            "errors": [], "strengths": [], "weaknesses": [],
        }