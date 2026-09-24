# code_room/backend/sandbox_runner.py
"""
Code Sandbox - Chạy code Python an toàn với timeout
- Hỗ trợ UTF-8 emoji
- Timeout protection
- Output size limit
"""
import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path


class CodeSandbox:
    """Chạy Python code trong sandbox với timeout"""

    def __init__(self, timeout: int = 10, max_output: int = 50000):
        self.timeout = timeout
        self.max_output = max_output

    def run_python(self, code: str, timeout: int = None) -> dict:
        """Chạy Python code với UTF-8 emoji support"""
        timeout = timeout or self.timeout
        start = time.time()

        # Write code to temp file with UTF-8
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            tmp_path = f.name

        # Force UTF-8 environment for subprocess
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            result = subprocess.run(
                [sys.executable, "-X", "utf8", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                env=env,
            )

            duration = round(time.time() - start, 3)

            stdout = result.stdout[:self.max_output] if result.stdout else ""
            stderr = result.stderr[:self.max_output] if result.stderr else ""

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode,
                "duration": duration,
                "error": None,
            }

        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"⏱️ Timeout sau {timeout}s",
                "exit_code": -1,
                "duration": round(time.time() - start, 3),
                "error": f"Timeout sau {timeout}s",
            }

        except Exception as e:
            return {
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "duration": round(time.time() - start, 3),
                "error": str(e),
            }

        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass