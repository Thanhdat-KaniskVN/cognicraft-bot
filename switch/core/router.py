# switch/core/router.py
"""
Event Router - "Dây dẫn điện"
Nối các sockets với nhau qua events

Ví dụ:
    - Khi CogniBot có "score.confirmed"
    - → Tự động gọi GoogleCalendar.add_event()
"""
import asyncio
from collections import defaultdict
from typing import Any, Callable, Dict, List, Awaitable


class EventRouter:
    """
    Router nối các socket (như dây điện)
    
    - Subscribe events
    - Emit events
    - Tự động route đến đúng socket
    """

    def __init__(self, registry=None):
        self.registry = registry
        self.listeners: Dict[str, List[dict]] = defaultdict(list)
        self.history: List[dict] = []
        self.max_history = 100

    # ============================================================
    # WIRING (nối dây)
    # ============================================================

    def wire(
        self,
        event_name: str,
        socket_name: str,
        action: str,
        transform: Callable[[dict], dict] = None,
        condition: Callable[[dict], bool] = None,
    ):
        """
        Nối 1 event → 1 action của socket
        
        Args:
            event_name: Tên event (VD: "cogni.score.confirmed")
            socket_name: Socket sẽ nhận (VD: "google_calendar")
            action: Action gọi (VD: "add_event")
            transform: Hàm biến đổi payload (tùy chọn)
            condition: Điều kiện để chạy (tùy chọn)
        """
        self.listeners[event_name].append({
            "socket": socket_name,
            "action": action,
            "transform": transform,
            "condition": condition,
        })
        print(f"[Router] 🔌 Wired: {event_name} → {socket_name}.{action}()")

    def unwire(self, event_name: str, socket_name: str = None):
        """Ngắt dây"""
        if socket_name:
            self.listeners[event_name] = [
                l for l in self.listeners[event_name]
                if l["socket"] != socket_name
            ]
        else:
            self.listeners[event_name] = []
        print(f"[Router] ✂️ Unwired: {event_name}")

    # ============================================================
    # EMIT (truyền điện)
    # ============================================================

    async def emit(self, event_name: str, payload: dict) -> List[dict]:
        """
        Phát event → Router tự tìm socket để gọi
        
        Returns:
            List kết quả từ mỗi socket
        """
        listeners = self.listeners.get(event_name, [])
        if not listeners:
            return []

        # Log
        self.history.append({
            "event": event_name,
            "payload": payload,
            "listeners": len(listeners),
        })
        self.history = self.history[-self.max_history:]

        results = []
        for listener in listeners:
            # Check condition
            if listener["condition"] and not listener["condition"](payload):
                continue

            # Transform payload
            data = payload
            if listener["transform"]:
                data = listener["transform"](payload)

            # Get socket
            socket = self.registry.get(listener["socket"]) if self.registry else None
            if not socket:
                results.append({
                    "socket": listener["socket"],
                    "error": "Socket not registered",
                })
                continue

            # Call action
            try:
                result = await socket.call(listener["action"], **data)
                results.append({
                    "socket": listener["socket"],
                    "action": listener["action"],
                    "result": result,
                })
                print(f"[Router] ⚡ {event_name} → {listener['socket']}.{listener['action']}() ✅")
            except Exception as e:
                results.append({
                    "socket": listener["socket"],
                    "action": listener["action"],
                    "error": str(e),
                })
                print(f"[Router] ⚡ {event_name} → {listener['socket']}.{listener['action']}() ❌ {e}")

        return results

    # ============================================================
    # INFO
    # ============================================================

    def list_wires(self) -> dict:
        """Xem tất cả dây đã nối"""
        return {
            event: [
                {"socket": l["socket"], "action": l["action"]}
                for l in listeners
            ]
            for event, listeners in self.listeners.items()
        }

    def get_history(self, limit: int = 20) -> List[dict]:
        return self.history[-limit:]