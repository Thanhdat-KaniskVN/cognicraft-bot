# switch/core/socket.py
"""
Socket - Base class cho mọi adapter (ổ cắm)
Mọi service muốn kết nối phải "cắm" qua Socket này
"""
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class SocketStatus(Enum):
    """Trạng thái của ổ cắm (đèn báo)"""
    OFF = "off"          # ⚪ Chưa bật
    STARTING = "starting" # 🟡 Đang khởi động
    ON = "on"            # 🟢 Đang chạy
    WARNING = "warning"  # 🟠 Cảnh báo
    ERROR = "error"      # 🔴 Lỗi
    DISABLED = "disabled" # ⚫ Bị tắt


@dataclass
class SocketInfo:
    """Thông tin của 1 socket"""
    name: str
    type: str
    version: str = "1.0.0"
    description: str = ""
    enabled: bool = False
    status: SocketStatus = SocketStatus.OFF
    last_error: Optional[str] = None
    last_check: Optional[str] = None
    stats: Dict[str, int] = field(default_factory=lambda: {
        "success": 0,
        "failed": 0,
        "calls": 0,
    })


class Socket(ABC):
    """
    Base Socket - "Ổ cắm điện"
    
    Mọi adapter (Google Calendar, Notion, CogniBot...) phải kế thừa class này.
    
    Ví dụ:
        class GoogleCalendarSocket(Socket):
            async def _on_start(self):
                # Kết nối Google Calendar
                ...
            
            async def _on_call(self, action, **kwargs):
                # Xử lý action
                ...
    """

    # Metadata (override trong subclass)
    NAME = "unnamed"
    TYPE = "generic"
    VERSION = "1.0.0"
    DESCRIPTION = ""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.info = SocketInfo(
            name=self.NAME,
            type=self.TYPE,
            version=self.VERSION,
            description=self.DESCRIPTION,
        )
        self._started = False

    # ============================================================
    # PUBLIC API (không cần override)
    # ============================================================

    async def start(self) -> bool:
        """Bật ổ cắm (công tắc ON)"""
        if self.info.status == SocketStatus.ON:
            return True

        self.info.status = SocketStatus.STARTING
        try:
            ok = await self._on_start()
            if ok:
                self.info.status = SocketStatus.ON
                self.info.enabled = True
                self.info.last_error = None
                self._started = True
                print(f"[Socket:{self.NAME}] 🟢 ON")
                return True
            else:
                self.info.status = SocketStatus.ERROR
                self.info.last_error = "start() returned False"
                return False
        except Exception as e:
            self.info.status = SocketStatus.ERROR
            self.info.last_error = str(e)
            print(f"[Socket:{self.NAME}] 🔴 START ERROR: {e}")
            return False

    async def stop(self) -> bool:
        """Tắt ổ cắm (công tắc OFF)"""
        if not self._started:
            self.info.status = SocketStatus.OFF
            return True

        try:
            await self._on_stop()
            self.info.status = SocketStatus.OFF
            self.info.enabled = False
            self._started = False
            print(f"[Socket:{self.NAME}] ⚪ OFF")
            return True
        except Exception as e:
            print(f"[Socket:{self.NAME}] stop error: {e}")
            return False

    async def call(self, action: str, **kwargs) -> Any:
        """
        Gọi 1 chức năng của socket
        
        Ví dụ:
            await socket.call("add_event", title="Meeting", date="2026-09-25")
        """
        if not self._started:
            raise RuntimeError(f"Socket {self.NAME} chưa được bật")

        self.info.stats["calls"] += 1
        try:
            result = await self._on_call(action, **kwargs)
            self.info.stats["success"] += 1
            return result
        except Exception as e:
            self.info.stats["failed"] += 1
            self.info.last_error = f"{action}: {e}"
            self.info.status = SocketStatus.WARNING
            raise

    async def health_check(self) -> bool:
        """Kiểm tra sức khỏe (như test ổ điện)"""
        try:
            ok = await self._on_health()
            self.info.last_check = datetime.now().isoformat()
            if ok and self.info.status not in (SocketStatus.ON,):
                self.info.status = SocketStatus.ON
            return ok
        except Exception as e:
            self.info.status = SocketStatus.ERROR
            self.info.last_error = str(e)
            return False

    # ============================================================
    # OVERRIDE TRONG SUBCLASS
    # ============================================================

    @abstractmethod
    async def _on_start(self) -> bool:
        """Khởi động socket (kết nối service)"""
        pass

    async def _on_stop(self) -> None:
        """Dừng socket (đóng kết nối)"""
        pass

    @abstractmethod
    async def _on_call(self, action: str, **kwargs) -> Any:
        """Xử lý action được gọi"""
        pass

    async def _on_health(self) -> bool:
        """Health check (mặc định: OK)"""
        return True

    # ============================================================
    # UTILS
    # ============================================================

    def to_dict(self) -> Dict:
        """Serialize info"""
        return {
            "name": self.info.name,
            "type": self.info.type,
            "version": self.info.version,
            "description": self.info.description,
            "enabled": self.info.enabled,
            "status": self.info.status.value,
            "last_error": self.info.last_error,
            "last_check": self.info.last_check,
            "stats": self.info.stats,
        }