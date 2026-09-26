# store/backend/switch_bridge.py
"""
Switch Board Bridge
- Tích hợp với Switch Board API để sandbox plugin execution
- Circuit breaker: nếu plugin crash 3 lần → block
- Rate limit: mỗi plugin chỉ được chạy X lần/phút
"""
import os
import time
import json
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
from collections import defaultdict


# Switch Board API endpoint — local hoặc remote
SWITCH_API_URL = os.getenv("SWITCH_API_URL", "http://localhost:8000/api/switch")
SWITCH_ENABLED = os.getenv("SWITCH_ENABLED", "false").lower() == "true"


# ============================================================
# CIRCUIT BREAKER — in-memory
# ============================================================
class CircuitBreaker:
    def __init__(self, max_failures: int = 3, reset_timeout: int = 300):
        self.failures: Dict[str, int] = defaultdict(int)
        self.last_failure: Dict[str, float] = {}
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout

    def is_open(self, key: str) -> bool:
        """Circuit đang mở = block calls"""
        if self.failures.get(key, 0) < self.max_failures:
            return False

        # Check reset timeout
        last = self.last_failure.get(key, 0)
        if time.time() - last > self.reset_timeout:
            # Auto reset
            self.failures[key] = 0
            return False

        return True

    def record_failure(self, key: str):
        self.failures[key] += 1
        self.last_failure[key] = time.time()

    def record_success(self, key: str):
        self.failures[key] = 0

    def status(self) -> Dict[str, Any]:
        return {
            'breakers': {
                k: {
                    'failures': v,
                    'is_open': self.is_open(k),
                }
                for k, v in self.failures.items()
            }
        }


# ============================================================
# RATE LIMITER — in-memory
# ============================================================
class RateLimiter:
    def __init__(self, max_per_minute: int = 10):
        self.calls: Dict[str, List[float]] = defaultdict(list)
        self.max_per_minute = max_per_minute

    def allow(self, key: str) -> bool:
        now = time.time()
        # Clean old
        self.calls[key] = [t for t in self.calls[key] if now - t < 60]

        if len(self.calls[key]) >= self.max_per_minute:
            return False

        self.calls[key].append(now)
        return True


# Global instances
breaker = CircuitBreaker()
limiter = RateLimiter()


# ============================================================
# SWITCH CLIENT
# ============================================================
class SwitchClient:
    """
    Client cho Switch Board API
    Giao tiếp với Switch Panel để chạy sandbox
    """

    def __init__(self, base_url: str = SWITCH_API_URL):
        self.base_url = base_url.rstrip('/')

    async def is_available(self) -> bool:
        """Check Switch Board đang chạy"""
        if not SWITCH_ENABLED:
            return False
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f'{self.base_url}/health')
                return r.status_code == 200
        except Exception:
            return False

    async def health(self) -> Dict[str, Any]:
        """Lấy health của Switch Board"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f'{self.base_url}/health')
                return r.json() if r.status_code == 200 else {'status': 'down'}
        except Exception as e:
            return {'status': 'down', 'error': str(e)}

    async def list_sockets(self) -> List[Dict[str, Any]]:
        """List các socket đã đăng ký"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f'{self.base_url}/sockets')
                return r.json().get('sockets', []) if r.status_code == 200 else []
        except Exception:
            return []

    async def exec_plugin(
        self,
        plugin_slug: str,
        method: str = 'run',
        args: Optional[List[Any]] = None,
        timeout: int = 5,
    ) -> Dict[str, Any]:
        """
        Chạy plugin qua Switch Board sandbox.
        """
        key = f'plugin:{plugin_slug}'

        # Circuit breaker
        if breaker.is_open(key):
            return {
                'success': False,
                'error': 'Circuit breaker OPEN — plugin đã fail nhiều lần',
                'code': 'CIRCUIT_OPEN',
            }

        # Rate limit
        if not limiter.allow(key):
            return {
                'success': False,
                'error': 'Rate limit — vui lòng thử lại sau',
                'code': 'RATE_LIMITED',
            }

        # Nếu Switch disabled → trả error
        if not SWITCH_ENABLED:
            return {
                'success': False,
                'error': 'Switch Board chưa bật',
                'code': 'SWITCH_DISABLED',
                'hint': 'Set env SWITCH_ENABLED=true',
            }

        try:
            async with httpx.AsyncClient(timeout=timeout + 2) as c:
                r = await c.post(
                    f'{self.base_url}/exec',
                    json={
                        'plugin': plugin_slug,
                        'method': method,
                        'args': args or [],
                        'timeout': timeout,
                    },
                    timeout=timeout + 2,
                )

                if r.status_code != 200:
                    breaker.record_failure(key)
                    return {
                        'success': False,
                        'error': f'Switch API lỗi {r.status_code}',
                        'code': 'SWITCH_ERROR',
                        'detail': r.text[:200],
                    }

                breaker.record_success(key)
                return r.json()

        except httpx.TimeoutException:
            breaker.record_failure(key)
            return {
                'success': False,
                'error': f'Timeout {timeout}s',
                'code': 'TIMEOUT',
            }
        except Exception as e:
            breaker.record_failure(key)
            return {
                'success': False,
                'error': str(e)[:200],
                'code': 'EXCEPTION',
            }


# Singleton
_switch_client: Optional[SwitchClient] = None


def get_switch() -> SwitchClient:
    global _switch_client
    if _switch_client is None:
        _switch_client = SwitchClient()
    return _switch_client


def get_status() -> Dict[str, Any]:
    """Status tổng hợp của bridge"""
    return {
        'switch_enabled': SWITCH_ENABLED,
        'switch_api_url': SWITCH_API_URL,
        'circuit_breaker': breaker.status(),
        'rate_limit': {
            'max_per_minute': limiter.max_per_minute,
        },
    }