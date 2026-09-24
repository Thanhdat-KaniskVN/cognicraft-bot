# distiller.py
from ai_provider import call_ai_json


class Distiller:
    """Chắt lọc tinh túy từ bài nộp"""

    MAX_INSIGHT_LEN = 80
    MAX_PERSPECTIVE_LEN = 150
    MAX_APPLICATION_LEN = 150
    MAX_CODE_LEN = 500

    def extract(self, member, topic, content):
        """Trích xuất insights + code từ bài nộp"""
        prompt = f"""Phan tich bai nop sau va TRICH XUAT tinh tuy:

**Bai nop cua {member} ve topic: {topic}**
{content[:6000]}

**Yeu cau:**
1. 3 insights chinh (moi cai 1 cau, KHONG QUA 80 KY TU)
2. Goc nhin doc dao cua tac gia (1 cau, KHONG QUA 150 KY TU)
3. Ung dung thuc te (1 cau, KHONG QUA 150 KY TU)
4. Code snippet TU BAI NOP (neu bai nop KHONG co code thuc su, tra ve chuoi rong "")
   - KHONG duoc tu tao code minh hoa
   - Chi extract code CO SAN trong bai nop
   - Neu bai chi co link Google Docs hoac PDF, tra ve rong
   - Neu bai chi noi ve ly thuyet, tra ve rong

**Tra ve JSON:**
{{
  "insights": [
    "<insight 1>",
    "<insight 2>",
    "<insight 3>"
  ],
  "unique_perspective": "<goc nhin doc dao>",
  "real_world_application": "<ung dung thuc te>",
  "code_snippet": "<code THUC SU CO trong bai hoac chuoi rong>",
  "code_language": "<python|javascript|cpp|java|sql|none>"
}}

**QUAN TRONG:**
- Neu bai nop khong co code snippet that su → code_snippet = "" va code_language = "none"
- KHONG duoc bia code SQL, Python, hay bat ky ngon ngu nao khong co trong bai
- Chi tra ve JSON, khong giai thich them"""

        try:
            result = call_ai_json(prompt, task_type="distiller")
            return self._trim(result)
        except Exception as e:
            print(f"[Distiller] Error: {e}")
            return self._fallback()

    def _trim(self, result):
        """Cắt ngắn các trường nếu quá dài"""
        # Cắt insights
        if "insights" in result and isinstance(result["insights"], list):
            result["insights"] = [
                self._cut(i, self.MAX_INSIGHT_LEN)
                for i in result["insights"]
            ]

        # Cắt unique_perspective
        if result.get("unique_perspective"):
            result["unique_perspective"] = self._cut(
                result["unique_perspective"],
                self.MAX_PERSPECTIVE_LEN
            )

        # Cắt real_world_application
        if result.get("real_world_application"):
            result["real_world_application"] = self._cut(
                result["real_world_application"],
                self.MAX_APPLICATION_LEN
            )

        # Cắt code_snippet
        if result.get("code_snippet"):
            result["code_snippet"] = result["code_snippet"][:self.MAX_CODE_LEN]

        return result

    def _cut(self, text, max_len):
        """Cắt text nếu quá dài, thêm '...'"""
        if not text:
            return ""
        text = str(text).strip()
        if len(text) <= max_len:
            return text
        return text[:max_len - 3].rstrip() + "..."

    def _fallback(self):
        return {
            "insights": ["(Khong trich xuat duoc)"],
            "unique_perspective": "",
            "real_world_application": "",
            "code_snippet": "",
            "code_language": "none",
        }