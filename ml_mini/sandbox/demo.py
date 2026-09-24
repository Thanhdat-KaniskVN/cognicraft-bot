# ml_mini/sandbox/demo.py
"""
Demo Sandboxes - 3 sandbox để test
"""
import asyncio
from .base import BaseSandbox


class ScorePredictorSandbox(BaseSandbox):
    NAME = "score_predictor"
    VERSION = "0.1.0"
    DESCRIPTION = "Dự đoán điểm số dựa trên lịch sử"
    CATEGORY = "prediction"
    
    async def on_start(self):
        print(f"[{self.NAME}] 📊 Loading model...")
        await asyncio.sleep(0.1)
    
    async def on_stop(self):
        print(f"[{self.NAME}] 💾 Saving model...")
    
    async def run(self, member: str, weeks_ahead: int = 4) -> dict:
        """Predict scores"""
        await asyncio.sleep(0.05)
        return {
            "member": member,
            "predictions": [4.2, 4.3, 4.4, 4.5][:weeks_ahead],
            "confidence": 0.85,
            "model": "linear_regression",
        }


class AnomalyDetectorSandbox(BaseSandbox):
    NAME = "anomaly_detector"
    VERSION = "0.1.0"
    DESCRIPTION = "Phát hiện bất thường trong điểm số"
    CATEGORY = "detection"
    
    async def run(self, member: str) -> dict:
        """Detect anomalies"""
        await asyncio.sleep(0.05)
        return {
            "member": member,
            "anomalies": [],
            "anomaly_score": 0.2,
            "is_anomaly": False,
        }


class TokenPredictorSandbox(BaseSandbox):
    NAME = "token_predictor"
    VERSION = "0.1.0"
    DESCRIPTION = "Dự đoán tokens cho AI calls"
    CATEGORY = "optimization"
    
    async def run(self, task_type: str, prompt_length: int) -> dict:
        """Predict tokens"""
        await asyncio.sleep(0.05)
        # Simple estimation
        estimated = prompt_length * 1.5 + 500
        return {
            "task_type": task_type,
            "predicted_tokens": int(estimated),
            "confidence": 0.78,
        }