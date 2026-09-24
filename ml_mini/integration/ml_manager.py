# ml_mini/integration/ml_manager.py
"""
ML Manager - Singleton quản lý ML Mini toàn cục
- Init coordinator + sandboxes 1 lần
- Chia sẻ giữa các module (bot, token, switch)
"""
import asyncio
from typing import Optional

from ..coordinator import SandboxCoordinator
from ..sandbox import (
    ScorePredictorSandbox,
    AnomalyDetectorSandbox,
    TokenPredictorSandbox,
)


class MLManager:
    """
    Singleton ML Manager
    Khởi tạo 1 lần, dùng mọi nơi
    """
    
    _instance: Optional["MLManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Tránh reinit
        if hasattr(self, "_initialized"):
            return
        
        self.coordinator = SandboxCoordinator()
        self.score_sandbox = ScorePredictorSandbox()
        self.anomaly_sandbox = AnomalyDetectorSandbox()
        self.token_sandbox = TokenPredictorSandbox()
        
        self._started = False
        self._initialized = True
    
    async def start(self):
        """Khởi động ML Mini"""
        if self._started:
            return
        
        print("\n" + "=" * 60)
        print("🧠 ML MINI - STARTING")
        print("=" * 60)
        
        # Register sandboxes
        self.coordinator.register_sandbox("score", self.score_sandbox)
        self.coordinator.register_sandbox("anomaly", self.anomaly_sandbox)
        self.coordinator.register_sandbox("token", self.token_sandbox)
        
        # Create mesh links
        self.coordinator.create_link("score", "anomaly")
        self.coordinator.create_link("anomaly", "token")
        self.coordinator.create_link("token", "score")
        
        # Start coordinator (heartbeat)
        await self.coordinator.start()
        
        self._started = True
        print("[MLManager] ✅ ML Mini ready")
        print()
    
    async def stop(self):
        """Dừng ML Mini"""
        if not self._started:
            return
        await self.coordinator.stop()
        self._started = False
    
    # ============================================================
    # CONVENIENCE METHODS
    # ============================================================
    
    async def predict_score(self, member: str, weeks_ahead: int = 4) -> dict:
        return await self.score_sandbox.run(member=member, weeks_ahead=weeks_ahead)
    
    async def detect_anomalies(self, member: str = None) -> dict:
        return await self.anomaly_sandbox.run(member=member)
    
    async def predict_tokens(self, task_type: str, prompt_length: int) -> dict:
        return await self.token_sandbox.run(
            task_type=task_type,
            prompt_length=prompt_length,
        )
    
    def get_status(self) -> dict:
        return self.coordinator.get_status()
    
    def get_stats(self) -> dict:
        return self.coordinator.get_stats()
    
    def get_events(self, limit: int = 20) -> list:
        return self.coordinator.get_event_log(limit)


# Global singleton
_manager: Optional[MLManager] = None


def get_ml_manager() -> MLManager:
    """Lấy ML Manager singleton"""
    global _manager
    if _manager is None:
        _manager = MLManager()
    return _manager