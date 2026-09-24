# ml_mini/integration/switch_hook.py
"""
Switch Board Hook - Emit ML events to Switch Board
"""
from .ml_manager import get_ml_manager


class MLSwitchHook:
    """
    Hook để ML Mini emit events sang Switch Board
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.manager = get_ml_manager()
    
    async def emit_anomaly_detected(self, member: str, anomalies: list):
        """Emit event khi phát hiện anomaly"""
        if not self.event_bus:
            return
        
        await self.event_bus.emit("ml.anomaly.detected", {
            "member": member,
            "anomalies": anomalies,
            "count": len(anomalies),
        })
    
    async def emit_model_trained(self, sandbox_id: str, metrics: dict):
        """Emit event khi model train xong"""
        if not self.event_bus:
            return
        
        await self.event_bus.emit("ml.model.trained", {
            "sandbox": sandbox_id,
            "metrics": metrics,
        })
    
    async def emit_prediction_ready(self, member: str, predictions: list):
        """Emit event khi có prediction mới"""
        if not self.event_bus:
            return
        
        await self.event_bus.emit("ml.prediction.ready", {
            "member": member,
            "predictions": predictions,
        })
    
    async def run_anomaly_scan(self):
        """Chạy full anomaly scan và emit events"""
        result = await self.manager.detect_anomalies()
        
        for r in result.get("results", []):
            if r.get("is_anomaly"):
                await self.emit_anomaly_detected(
                    r["member"],
                    r.get("anomalies", []),
                )
        
        return result