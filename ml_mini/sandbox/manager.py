# ml_mini/sandbox/manager.py
"""
Subprocess Manager - Chạy sandbox trong subprocess để cách ly
- Isolation: 1 sandbox lỗi không ảnh hưởng sandbox khác
- Timeout control
- Resource limits
"""
import asyncio
import json
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class SubprocessManager:
    """
    Manager chạy sandbox trong subprocess riêng biệt
    
    Use cases:
    - Sandbox cần isolation hoàn toàn
    - Sandbox có thể crash (subprocess crash không ảnh hưởng main)
    - Sandbox cần timeout control
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 60)
    
    async def run_in_subprocess(
        self,
        module_path: str,
        function_name: str,
        args: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Dict:
        """
        Chạy function trong subprocess
        """
        timeout = timeout or self.timeout
        
        # Tạo wrapper script
        wrapper_code = f"""
import sys
import json
sys.path.insert(0, r"{Path(module_path).parent}")

from {Path(module_path).stem} import {function_name}

args = json.loads({json.dumps(json.dumps(args))})
try:
    result = {function_name}(**args)
    print(json.dumps({{"success": True, "result": result}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
        
        wrapper_path = Path(module_path).parent / "_wrapper_tmp.py"
        wrapper_path.write_text(wrapper_code, encoding="utf-8")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(wrapper_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "success": False,
                    "error": f"Timeout sau {timeout}s",
                }
            
            if stderr:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8", errors="replace"),
                }
            
            output = stdout.decode("utf-8", errors="replace").strip()
            if not output:
                return {"success": False, "error": "No output from subprocess"}
            
            # Parse last line (JSON)
            last_line = output.split("\n")[-1]
            return json.loads(last_line)
            
        finally:
            if wrapper_path.exists():
                wrapper_path.unlink()
    
    async def health_check_subprocess(
        self,
        sandbox_class_path: str,
        config: dict = None,
    ) -> bool:
        """Check sandbox có thể khởi tạo được không"""
        try:
            # Đơn giản: check import
            result = await self.run_in_subprocess(
                module_path=sandbox_class_path,
                function_name="__init__",
                args=config or {},
                timeout=5,
            )
            return result.get("success", False)
        except Exception:
            return False