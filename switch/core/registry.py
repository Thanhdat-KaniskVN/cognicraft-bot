# switch/core/registry.py
"""
Registry - Danh sách tất cả socket
Tự động discover + quản lý vòng đời
"""
import asyncio
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Type

from .socket import Socket, SocketStatus


class SocketRegistry:
    """
    Registry quản lý tất cả sockets
    
    - Auto-discover từ folder switch/sockets/
    - Start/stop từng socket
    - List status
    """

    def __init__(self, sockets_dir: str = "sockets"):
        self.sockets_dir = Path(__file__).parent.parent / sockets_dir
        self.sockets: Dict[str, Socket] = {}
        self.socket_classes: Dict[str, Type[Socket]] = {}

    # ============================================================
    # DISCOVERY
    # ============================================================

    def discover(self):
        """Tự động tìm tất cả socket classes"""
        self.socket_classes = {}

        if not self.sockets_dir.exists():
            print(f"[Registry] ⚠️ Folder không tồn tại: {self.sockets_dir}")
            return

        for file in self.sockets_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue

            module_name = file.stem
            try:
                # Import module
                module = importlib.import_module(
                    f"sockets.{module_name}"
                )

                # Tìm Socket subclasses
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, Socket)
                        and obj is not Socket
                    ):
                        socket_name = obj.NAME
                        self.socket_classes[socket_name] = obj
                        print(f"[Registry] 🔍 Found socket: {socket_name} ({module_name})")

            except Exception as e:
                print(f"[Registry] ⚠️ Load {module_name} failed: {e}")

    # ============================================================
    # REGISTRATION
    # ============================================================

    def register(self, socket_name: str, config: dict = None) -> Optional[Socket]:
        """Cắm 1 socket vào board"""
        if socket_name in self.sockets:
            return self.sockets[socket_name]

        cls = self.socket_classes.get(socket_name)
        if not cls:
            print(f"[Registry] ❌ Socket không tìm thấy: {socket_name}")
            return None

        instance = cls(config=config or {})
        self.sockets[socket_name] = instance
        print(f"[Registry] 🔌 Plugged: {socket_name}")
        return instance

    def unregister(self, socket_name: str) -> bool:
        """Rút socket ra khỏi board"""
        if socket_name in self.sockets:
            del self.sockets[socket_name]
            print(f"[Registry] 🔌 Unplugged: {socket_name}")
            return True
        return False

    # ============================================================
    # LIFECYCLE
    # ============================================================

    async def start_all(self):
        """Bật tất cả socket đã cắm"""
        for name, socket in self.sockets.items():
            await socket.start()

    async def stop_all(self):
        """Tắt tất cả socket"""
        for name, socket in self.sockets.items():
            await socket.stop()

    async def start(self, socket_name: str) -> bool:
        """Bật 1 socket (công tắc ON)"""
        socket = self.sockets.get(socket_name)
        if not socket:
            return False
        return await socket.start()

    async def stop(self, socket_name: str) -> bool:
        """Tắt 1 socket (công tắc OFF)"""
        socket = self.sockets.get(socket_name)
        if not socket:
            return False
        return await socket.stop()

    # ============================================================
    # STATUS
    # ============================================================

    def get(self, socket_name: str) -> Optional[Socket]:
        return self.sockets.get(socket_name)

    def list_all(self) -> List[dict]:
        """List tất cả sockets + status"""
        return [s.to_dict() for s in self.sockets.values()]

    async def health_check_all(self) -> Dict[str, bool]:
        """Health check tất cả sockets"""
        results = {}
        for name, socket in self.sockets.items():
            try:
                results[name] = await socket.health_check()
            except Exception:
                results[name] = False
        return results

    def get_board_status(self) -> dict:
        """Trạng thái toàn board (cho dashboard)"""
        by_status = {s.value: 0 for s in SocketStatus}
        for s in self.sockets.values():
            by_status[s.info.status.value] += 1

        return {
            "total": len(self.sockets),
            "available": len(self.socket_classes),
            "by_status": by_status,
            "sockets": self.list_all(),
        }