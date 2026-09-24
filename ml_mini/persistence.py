# ml_mini/persistence.py
"""
Persistence - Save/load state vào JSON
- Auto-save mỗi 30s
- Load khi khởi động
- Backup khi save
"""
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional


class Persistence:
    """Save/load state cho ML Mini"""
    
    def __init__(self, state_file: Path, auto_save_interval: int = 30):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.auto_save_interval = auto_save_interval
        self._running = False
        self._last_save = datetime.now()
        self._save_lock = asyncio.Lock()
        self._save_count = 0
    
    # ============================================================
    # SAVE
    # ============================================================
    
    async def save(self, data: dict) -> bool:
        """Save state vào file (async-safe)"""
        async with self._save_lock:
            try:
                # Backup file cũ
                if self.state_file.exists():
                    backup = self.state_file.with_suffix(".backup.json")
                    backup.write_bytes(self.state_file.read_bytes())
                
                # Thêm metadata
                data["_metadata"] = {
                    "saved_at": datetime.now().isoformat(),
                    "save_count": self._save_count + 1,
                }
                
                # Write với encoding UTF-8
                tmp_file = self.state_file.with_suffix(".tmp")
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                
                # Atomic rename
                tmp_file.replace(self.state_file)
                
                self._save_count += 1
                self._last_save = datetime.now()
                return True
                
            except Exception as e:
                print(f"[Persistence] ❌ Save error: {e}")
                return False
    
    # ============================================================
    # LOAD
    # ============================================================
    
    def load(self) -> Optional[dict]:
        """Load state từ file"""
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Persistence] ❌ Load error: {e}")
            
            # Thử load backup
            backup = self.state_file.with_suffix(".backup.json")
            if backup.exists():
                print(f"[Persistence] 🔄 Trying backup...")
                try:
                    with open(backup, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e2:
                    print(f"[Persistence] ❌ Backup load error: {e2}")
            
            return None
    
    # ============================================================
    # AUTO-SAVE LOOP
    # ============================================================
    
    async def auto_save_loop(self, get_data_func):
        """
        Vòng lặp auto-save
        get_data_func: callable trả về dict để save
        """
        self._running = True
        while self._running:
            try:
                await asyncio.sleep(self.auto_save_interval)
                data = get_data_func()
                if data:
                    await self.save(data)
            except Exception as e:
                print(f"[Persistence] Auto-save error: {e}")
                await asyncio.sleep(5)
    
    def stop_auto_save(self):
        """Dừng auto-save"""
        self._running = False
    
    # ============================================================
    # INFO
    # ============================================================
    
    def get_info(self) -> dict:
        return {
            "state_file": str(self.state_file),
            "exists": self.state_file.exists(),
            "size_bytes": self.state_file.stat().st_size if self.state_file.exists() else 0,
            "last_save": self._last_save.isoformat(),
            "save_count": self._save_count,
        }