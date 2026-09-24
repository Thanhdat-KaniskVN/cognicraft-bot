# ml_mini/sandbox/base.py
"""
Base Sandbox - Class cha cho mọi sandbox
- Health check protocol
- State management
- Error tracking
- Lifecycle hooks
"""
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime
from typing import Any, Dict, Optional


class SandboxState(Enum):
    """Trạng thái sandbox"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    RECOVERING = "recovering"
    RESTARTING = "restarting"
    DEAD = "dead"           # Chết hẳn, không auto-restart


class BaseSandbox(ABC):
    """
    Base class cho mọi sandbox
    
    Mọi sandbox PHẢI kế thừa class này và implement:
    - run(**kwargs) -> Any
    - (optional) health_check() -> bool
    - (optional) on_start() -> None
    - (optional) on_stop() -> None
    """
    
    # Metadata (override trong subclass)
    NAME = "unnamed"
    VERSION = "1.0.0"
    DESCRIPTION = ""
    CATEGORY = "general"
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.state = SandboxState.HEALTHY
        self.error_count = 0
        self.restart_count = 0
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.last_run_time: Optional[datetime] = None
        self.last_run_duration: float = 0.0
        self.created_at = datetime.now()
        self._is_running = True
        self._on_stop_called = False
    
    # ============================================================
    # ABSTRACT METHODS (Phải override)
    # ============================================================
    
    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """
        Chạy sandbox - đây là logic chính
        """
        pass
    
    # ============================================================
    # LIFECYCLE HOOKS (Optional override)
    # ============================================================
    
    async def on_start(self):
        """Gọi khi sandbox khởi động"""
        pass
    
    async def on_stop(self):
        """Gọi khi sandbox dừng"""
        self._on_stop_called = True
    
    async def on_error(self, error: Exception):
        """Gọi khi sandbox gặp lỗi"""
        pass
    
    # ============================================================
    # HEALTH CHECK
    # ============================================================
    
    async def health_check(self) -> bool:
        """
        Check sandbox có khỏe không
        Override nếu cần custom logic
        """
        # Default: alive nếu đang chạy và không ở trạng thái DOWN
        return self._is_running and self.state not in (
            SandboxState.DOWN,
            SandboxState.DEAD,
        )
    
    # ============================================================
    # STATE MANAGEMENT
    # ============================================================
    
    def record_error(self, error: str):
        """Ghi nhận lỗi"""
        self.error_count += 1
        self.last_error = error
        self.last_error_time = datetime.now()
        
        # Nếu vượt ngưỡng → chuyển DOWN
        max_errors = self.config.get("max_errors", 5)
        if self.error_count >= max_errors:
            self.state = SandboxState.DOWN
            self._is_running = False
    
    def reset_errors(self):
        """Reset lỗi (khi phục hồi)"""
        self.error_count = 0
        self.last_error = None
    
    def mark_down(self, reason: str = ""):
        """Đánh dấu DOWN"""
        self.state = SandboxState.DOWN
        self._is_running = False
        if reason:
            self.last_error = reason
            self.last_error_time = datetime.now()
    
    def mark_healthy(self):
        """Đánh dấu HEALTHY"""
        self.state = SandboxState.HEALTHY
        self._is_running = True
        self.reset_errors()
    
    def mark_dead(self):
        """Chết hẳn - không auto-restart"""
        self.state = SandboxState.DEAD
        self._is_running = False
    
    # ============================================================
    # RESTART
    # ============================================================
    
    async def restart(self):
        """Restart sandbox"""
        old_state = self.state
        self.state = SandboxState.RESTARTING
        print(f"[{self.NAME}] 🔄 Restarting... (from {old_state.value})")
        
        try:
            await self.on_stop()
        except Exception as e:
            print(f"[{self.NAME}] on_stop error: {e}")
        
        self._on_stop_called = False
        self._is_running = True
        self.reset_errors()
        
        try:
            await self.on_start()
        except Exception as e:
            print(f"[{self.NAME}] on_start error: {e}")
            self.mark_down(str(e))
            return False
        
        self.restart_count += 1
        self.state = SandboxState.HEALTHY
        print(f"[{self.NAME}] ✅ Restarted (count={self.restart_count})")
        return True
    
    # ============================================================
    # INFO
    # ============================================================
    
    def to_dict(self) -> Dict:
        """Export state"""
        return {
            "name": self.NAME,
            "version": self.VERSION,
            "description": self.DESCRIPTION,
            "category": self.CATEGORY,
            "state": self.state.value,
            "error_count": self.error_count,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "last_run_duration": round(self.last_run_duration, 3),
            "created_at": self.created_at.isoformat(),
            "is_running": self._is_running,
        }
    
    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.NAME} state={self.state.value}>"