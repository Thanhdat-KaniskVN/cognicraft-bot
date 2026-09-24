# code_room/backend/ai_fixer.py
"""
AI Code Fixer - Đề xuất sửa code bằng AI (VN + EN)
"""
import json
import asyncio
from typing import List, Dict


class AICodeFixer:
    """Phân tích code và đề xuất fix"""

    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider

    async def analyze(self, code: str, language: str = "python") -> Dict:
        """Phân tích code, trả về suggestions"""
        if not self.ai_provider:
            return self._fallback_analyze(code)

        prompt = (
            f"Phân tích code {language} sau và đề xuất cải thiện.\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Trả về JSON với format CHÍNH XÁC:\n"
            "{\n"
            '  "summary": "Tóm tắt ngắn gọn (tiếng Việt)",\n'
            '  "suggestions": [\n'
            "    {\n"
            '      "vn": "Mô tả lỗi/cải thiện bằng tiếng Việt (ngắn gọn)",\n'
            '      "en": "Description in English (brief)",\n'
            '      "code": "Đoạn code sửa (nếu có)"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "YÊU CẦU:\n"
            "- Tối đa 5 suggestions\n"
            "- Mỗi suggestion ngắn gọn\n"
            "- Tập trung vào: bugs, style, performance, security\n"
            "- Nếu code OK → suggestions rỗng\n"
            "- Chỉ trả về JSON."
        )

        try:
            result = await asyncio.to_thread(
                self.ai_provider, prompt, 2000, 3, "code_fix"
            )

            # Validate
            if not isinstance(result, dict):
                return self._fallback_analyze(code)

            if "suggestions" not in result:
                result["suggestions"] = []
            if "summary" not in result:
                result["summary"] = "Đã phân tích xong"

            return result

        except Exception as e:
            print(f"[AICodeFixer] Error: {e}")
            return self._fallback_analyze(code)

    def _fallback_analyze(self, code: str) -> Dict:
        """Fallback khi AI không available"""
        suggestions = []
        lines = code.split("\n")

        # Check: print statements
        print_count = sum(1 for line in lines if "print(" in line)
        if print_count > 5:
            suggestions.append({
                "vn": f"Có {print_count} lệnh print – có thể dùng logging thay vì print trong production",
                "en": f"Found {print_count} print statements – consider using logging in production",
                "code": "import logging\nlogger = logging.getLogger(__name__)",
            })

        # Check: try/except too broad
        if "except Exception" in code and "except Exception as e" not in code:
            suggestions.append({
                "vn": "Nên bắt exception cụ thể, tránh `except Exception` mà không log lỗi",
                "en": "Catch specific exceptions, avoid bare `except Exception` without logging",
                "code": "try:\n    ...\nexcept ValueError as e:\n    logger.error(f'Error: {e}')",
            })

        # Check: TODO/FIXME
        todos = [l for l in lines if "TODO" in l or "FIXME" in l]
        if todos:
            suggestions.append({
                "vn": f"Có {len(todos)} TODO/FIXME cần xử lý",
                "en": f"Found {len(todos)} TODO/FIXME items to handle",
                "code": "",
            })

        # Check: long lines
        long_lines = [i + 1 for i, l in enumerate(lines) if len(l) > 120]
        if long_lines:
            suggestions.append({
                "vn": f"Có {len(long_lines)} dòng quá dài (>120 ký tự) ở dòng: {long_lines[:5]}",
                "en": f"Found {len(long_lines)} long lines (>120 chars) at: {long_lines[:5]}",
                "code": "",
            })

        # Check: no docstring
        if '"""' not in code and "'''" not in code and len(lines) > 20:
            suggestions.append({
                "vn": "Nên thêm docstring cho functions/classes để dễ maintain",
                "en": "Add docstrings for better maintainability",
                "code": 'def foo():\n    """Mô tả function."""\n    pass',
            })

        if suggestions:
            summary = f"✅ Phân tích xong. {len(suggestions)} gợi ý."
        else:
            summary = "✅ Code ổn, không có vấn đề lớn."

        return {
            "summary": summary,
            "suggestions": suggestions,
        }