# switch/core/circuit.py
"""
Circuit Breaker - Cầu chì bảo vệ
Tự động "ngắt điện" khi service lỗi liên tục
"""
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Any


class CircuitBreaker:
    """
    Cầu chì: Bảo vệ service khỏi bị quá tải
    
    - Sau N lỗi liên tiếp → NGẮT (OPEN)
    - Sau X giây → thử lại (HALF-OPEN)
    - Thành công → đóng (CLOSED)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Gọi function qua cầu chì"""

        # Nếu đang OPEN → check xem hết timeout chưa
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                print(f"[Circuit] 🟡 HALF-OPEN – thử lại")
            else:
                remaining = (
                    self.recovery_timeout
                    - (datetime.now() - self.last_failure_time).seconds
                )
                raise RuntimeError(
                    f"Circuit OPEN. Thử lại sau {remaining}s"
                )

        # Thực thi
        try:
            result = await func(*args, **kwargs)

            # Thành công → reset
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                print(f"[Circuit] 🟢 CLOSED – hồi phục")
            self.failure_count = 0
            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                print(f"[Circuit] 🔴 OPEN – {self.failure_count} lỗi liên tiếp")

            raise

    def _should_attempt_reset(self) -> bool:
        """Đã đủ thời gian để thử lại chưa?"""
        if not self.last_failure_time:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }