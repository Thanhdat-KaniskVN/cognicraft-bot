# switch/sockets/ml_sandbox.py
"""
ML Sandbox Socket - Bridge giữa Switch Board và ML Mini
"""
import sys
from pathlib import Path

# Add bot root
_BOT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOT_ROOT))

from core.socket import Socket


class MLSandboxSocket(Socket):
    NAME = "ml_sandbox"
    TYPE = "internal_service"
    VERSION = "1.0.0"
    DESCRIPTION = "ML Mini Bridge - Emit ML events"

    async def _on_start(self):
        print("[MLSocket] ✅ ML Sandbox ready")
        return True

    async def _on_call(self, action: str, **kwargs):
        if action == "predict":
            return await self._predict(**kwargs)
        elif action == "anomaly":
            return await self._anomaly(**kwargs)
        elif action == "tokens":
            return await self._tokens(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _predict(self, member: str, weeks_ahead: int = 4):
        from ml_mini.integration.ml_manager import get_ml_manager
        ml = get_ml_manager()
        return await ml.predict_score(member, weeks_ahead)

    async def _anomaly(self, member: str = None):
        from ml_mini.integration.ml_manager import get_ml_manager
        ml = get_ml_manager()
        return await ml.detect_anomalies(member)

    async def _tokens(self, task_type: str, prompt_length: int = 1500):
        from ml_mini.integration.ml_manager import get_ml_manager
        ml = get_ml_manager()
        return await ml.predict_tokens(task_type, prompt_length)