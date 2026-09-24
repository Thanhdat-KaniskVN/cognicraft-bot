# ml_mini/__init__.py
"""
ML Mini - Self-Healing Sandbox Mesh
- Coordinator với circuit breaker
- Adaptive heartbeat
- Subprocess isolation
- Auto-reconnect sau 15s
- Persistence

Version: 0.2.0
"""

from .coordinator import SandboxCoordinator
from .sandbox.base import BaseSandbox, SandboxState
from .config import MLConfig

__version__ = "0.2.0"

__all__ = [
    "SandboxCoordinator",
    "BaseSandbox",
    "SandboxState",
    "MLConfig",
]