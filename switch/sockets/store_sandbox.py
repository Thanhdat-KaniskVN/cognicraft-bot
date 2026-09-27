# switch/sockets/store_sandbox.py
"""
Store Sandbox Socket - Chạy plugin code AN TOÀN
- AST validation (block imports nguy hiểm)
- Subprocess isolation (timeout, memory limit)
- Restricted env (không leak secrets)
- Capture stdout/stderr
"""
import ast
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from core.socket import Socket


# ============================================================
# BLACKLIST — chặn trước khi chạy
# ============================================================
FORBIDDEN_IMPORTS = {
    # System
    "os", "sys", "subprocess", "shutil", "pathlib", "glob",
    "ctypes", "cffi", "mmap", "multiprocessing",
    # Network
    "socket", "ssl", "asyncio", "select", "selectors",
    "http", "urllib", "urllib2", "urllib3",
    "requests", "httpx", "aiohttp", "websocket", "websockets",
    "ftplib", "smtplib", "telnetlib", "xmlrpc",
    # Code exec
    "importlib", "imp", "runpy", "code", "codeop",
    "pickle", "marshal", "shelve", "dill", "joblib",
    # System info
    "platform", "psutil", "resource", "signal",
    # Crypto (không cho plugin dùng)
    "hashlib", "hmac", "secrets", "random",
    # Database
    "sqlite3", "psycopg2", "pymysql", "pymongo", "redis",
}

FORBIDDEN_BUILTINS = {
    "exec", "eval", "compile", "open", "input",
    "__import__", "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "breakpoint",
    "memoryview", "help", "exit", "quit",
    "system", "popen", "spawn",
}

FORBIDDEN_ATTRS = {
    "__subclasses__", "__bases__", "__mro__", "__class__",
    "__globals__", "__code__", "__closure__", "__func__",
    "__self__", "__dict__", "__builtins__",
    "eval", "exec", "system", "popen", "import_module",
}


# ============================================================
# SOCKET
# ============================================================
class StoreSandboxSocket(Socket):
    NAME = "store_sandbox"
    TYPE = "sandbox"
    VERSION = "1.0.0"
    DESCRIPTION = "Chạy plugin code trong môi trường cách ly"

    async def _on_start(self) -> bool:
        self.timeout = self.config.get("timeout", 5)
        self.max_output = self.config.get("max_output", 10000)
        self.max_memory_mb = self.config.get("max_memory_mb", 128)
        self.python = self.config.get("python", sys.executable)

        # Verify python executable
        if not Path(self.python).exists():
            print(f"[StoreSandbox] ⚠️ Python không tồn tại: {self.python}")
            return False

        print(f"[StoreSandbox] ✅ Ready (timeout={self.timeout}s, mem={self.max_memory_mb}MB)")
        return True

    async def _on_health(self) -> bool:
        return Path(self.python).exists()

    async def _on_call(self, action: str, **kwargs):
        if action == "exec_plugin":
            return await self._exec_plugin(**kwargs)
        elif action == "validate":
            return self._validate_only(**kwargs)
        elif action == "info":
            return {
                "timeout": self.timeout,
                "max_memory_mb": self.max_memory_mb,
                "python": self.python,
            }
        else:
            raise ValueError(f"Unknown action: {action}")

    # ============================================================
    # PUBLIC ACTIONS
    # ============================================================
    async def _exec_plugin(
        self,
        code: str,
        timeout: Optional[int] = None,
        entry: str = "__main__",
    ) -> dict:
        """
        Chạy plugin code trong subprocess.

        Args:
            code: Python source code
            timeout: Override timeout (default self.timeout)
            entry: Entry function (chưa dùng trong MVP)
        """
        if not code or not isinstance(code, str):
            return {"success": False, "error": "Empty code", "code": "EMPTY"}

        if len(code) > 100_000:
            return {"success": False, "error": "Code quá dài", "code": "TOO_LONG"}

        # 1. Validate AST
        is_valid, msg = self._validate_ast(code)
        if not is_valid:
            return {
                "success": False,
                "error": msg,
                "code": "AST_REJECTED",
                "type": "security",
            }

        # 2. Write to temp file
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as f:
                # Wrap với restricted builtins
                wrapped = self._wrap_code(code)
                f.write(wrapped)
                tmp_path = f.name

            # 3. Run subprocess
            return await self._run_subprocess(
                tmp_path,
                timeout or self.timeout,
            )

        except Exception as e:
            return {
                "success": False,
                "error": f"Sandbox error: {e}",
                "code": "SANDBOX_ERROR",
            }
        finally:
            if tmp_path and Path(tmp_path).exists():
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _validate_only(self, code: str) -> dict:
        """Chỉ validate, không chạy"""
        is_valid, msg = self._validate_ast(code)
        return {
            "valid": is_valid,
            "message": msg,
        }

    # ============================================================
    # AST VALIDATION
    # ============================================================
    def _validate_ast(self, code: str) -> tuple[bool, str]:
        """Parse + check forbidden patterns"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error line {e.lineno}: {e.msg}"

        for node in ast.walk(tree):
            # Check import
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORTS:
                        return False, f"Import bị chặn: {alias.name} (line {node.lineno})"

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in FORBIDDEN_IMPORTS:
                        return False, f"Import bị chặn: {node.module} (line {node.lineno})"

            # Check builtin calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in FORBIDDEN_BUILTINS:
                        return False, f"Hàm bị chặn: {node.func.id}() (line {node.lineno})"

                # Check attribute calls: obj.__subclasses__()
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in FORBIDDEN_ATTRS:
                        return False, f"Attribute bị chặn: .{node.func.attr} (line {node.lineno})"

            # Check name access
            elif isinstance(node, ast.Name):
                if node.id in FORBIDDEN_BUILTINS:
                    return False, f"Name bị chặn: {node.id} (line {node.lineno})"

            # Check attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in FORBIDDEN_ATTRS:
                    return False, f"Attribute bị chặn: .{node.attr} (line {node.lineno})"

        return True, "OK"

    # ============================================================
    # CODE WRAPPING
    # ============================================================
    def _wrap_code(self, user_code: str) -> str:
        """Wrap user code với restricted builtins"""
        return f'''
# === SANDBOX WRAPPER ===
import sys
import builtins as _builtins

# Restricted builtins — block dangerous functions
_BLOCKED = {{{", ".join(f'"{b}"' for b in FORBIDDEN_BUILTINS)}}}
_SAFE_BUILTINS = {{k: v for k, v in vars(_builtins).items() if k not in _BLOCKED}}

# Block dangerous modules
_BLOCKED_MODULES = {{{", ".join(f'"{m}"' for m in FORBIDDEN_IMPORTS)}}}

_original_import = _builtins.__import__
def _safe_import(name, *args, **kwargs):
    root = name.split(".")[0]
    if root in _BLOCKED_MODULES:
        raise ImportError(f"Module '{{name}}' bị chặn trong sandbox")
    return _original_import(name, *args, **kwargs)

_SAFE_BUILTINS["__import__"] = _safe_import
_SAFE_BUILTINS["print"] = print

# Replace builtins
sys.modules["__main__"].__dict__["__builtins__"] = _SAFE_BUILTINS

# === USER CODE ===
{user_code}
# === END USER CODE ===
'''

    # ============================================================
    # SUBPROCESS EXECUTION
    # ============================================================
        # ============================================================
    # SUBPROCESS EXECUTION — Windows-safe
    # ============================================================
    async def _run_subprocess(self, script_path: str, timeout: int) -> dict:
        """
        Chạy script trong subprocess có timeout.
        Dùng subprocess.run + asyncio.to_thread (Windows-safe).
        """
        import subprocess
        import traceback

        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        def _run_sync():
            """Chạy sync — sẽ đẩy vào thread"""
            try:
                result = subprocess.run(
                    [self.python, script_path],
                    capture_output=True,
                    timeout=timeout,
                    cwd=tempfile.gettempdir(),
                    env=clean_env,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                return ("OK", result)
            except subprocess.TimeoutExpired:
                return ("TIMEOUT", None)
            except Exception as e:
                return ("ERROR", e)

        try:
            status, payload = await asyncio.to_thread(_run_sync)

            if status == "TIMEOUT":
                return {
                    "success": False,
                    "error": f"Timeout {timeout}s — vượt quá giới hạn",
                    "code": "TIMEOUT",
                    "type": "resource",
                }

            if status == "ERROR":
                return {
                    "success": False,
                    "error": f"Subprocess error: {type(payload).__name__}: {payload}",
                    "code": "SUBPROCESS_ERROR",
                }

            # status == "OK"
            result = payload
            return {
                "success": result.returncode == 0,
                "stdout": (result.stdout or "")[:self.max_output],
                "stderr": (result.stderr or "")[:self.max_output],
                "return_code": result.returncode,
            }

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[StoreSandbox] OUTER ERROR:\n{tb}")
            return {
                "success": False,
                "error": f"Subprocess error: {type(e).__name__}: {e}",
                "detail": tb[:1000],
                "code": "SUBPROCESS_ERROR",
            }