# ml_mini/sandbox/token_predictor.py
"""
Token Predictor Sandbox - Exponential Smoothing
Dự đoán tokens cho AI calls
"""
import json
import math
from pathlib import Path
from .base import BaseSandbox


class TokenPredictorSandbox(BaseSandbox):
    NAME = "token_predictor"
    VERSION = "1.0.0"
    DESCRIPTION = "Dự đoán tokens bằng Exponential Smoothing"
    CATEGORY = "optimization"
    
    # Task-specific base multipliers
    TASK_MULTIPLIERS = {
        "scoring": 1.0,
        "socratic": 0.6,
        "quiz": 1.5,
        "chat": 0.8,
        "distiller": 0.9,
        "exercises": 1.8,
        "coverage": 2.5,
        "default": 1.0,
    }
    
    # Prompt/response ratio
    PROMPT_TO_OUTPUT_RATIO = 0.4  # Input chiếm 40%, output 60%
    
    # Base tokens per 100 chars prompt
    BASE_TOKENS_PER_100_CHARS = 100
    
    def __init__(self, config=None):
        super().__init__(config)
        self.history_file = Path(__file__).parent.parent.parent / "ml_state" / "token_history.json"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()
    
    def _load_history(self) -> dict:
        """Load history từ file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_history(self):
        """Save history"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TokenPredictor] Save error: {e}")
    
    async def on_start(self):
        print(f"[{self.NAME}] 📊 Loaded {len(self.history)} task histories")
    
    async def on_stop(self):
        self._save_history()
    
    # ============================================================
    # PREDICT
    # ============================================================
    
    async def run(
        self,
        task_type: str = "default",
        prompt_length: int = 1000,
        use_history: bool = True,
    ) -> dict:
        """
        Predict tokens cho 1 task
        
        Args:
            task_type: loại task
            prompt_length: độ dài prompt (chars)
            use_history: dùng history smoothing không
        """
        
        # 1. Base estimate
        base = (prompt_length / 100) * self.BASE_TOKENS_PER_100_CHARS
        
        # 2. Task multiplier
        multiplier = self.TASK_MULTIPLIERS.get(task_type, 1.0)
        
        # 3. Prompt/output ratio
        # Nếu prompt dài → output ngắn hơn (thường)
        ratio = self.PROMPT_TO_OUTPUT_RATIO
        estimate = base * multiplier * (1 / ratio if prompt_length < 2000 else 1.0)
        
        # 4. Apply exponential smoothing with history
        if use_history and task_type in self.history:
            hist = self.history[task_type]
            if isinstance(hist, list) and len(hist) > 0:
                # Exponential smoothing with alpha=0.3
                alpha = 0.3
                smoothed = hist[-1]
                for val in hist[-10:]:
                    smoothed = alpha * val + (1 - alpha) * smoothed
                estimate = 0.7 * estimate + 0.3 * smoothed
        
        # 5. Clamp
        estimate = max(50, min(10000, estimate))
        
        # 6. Confidence based on history
        confidence = 0.5
        if task_type in self.history and len(self.history[task_type]) > 5:
            confidence = 0.85
        elif task_type in self.history and len(self.history[task_type]) > 2:
            confidence = 0.7
        
        return {
            "task_type": task_type,
            "prompt_length": prompt_length,
            "predicted_tokens": int(estimate),
            "confidence": round(confidence, 2),
            "breakdown": {
                "base": int(base),
                "multiplier": multiplier,
                "final": int(estimate),
            },
            "model": "exponential_smoothing",
        }
    
    # ============================================================
    # RECORD ACTUAL
    # ============================================================
    
    async def record_actual(self, task_type: str, actual_tokens: int):
        """Ghi nhận token thực tế để cải thiện prediction"""
        if task_type not in self.history:
            self.history[task_type] = []
        
        self.history[task_type].append(actual_tokens)
        
        # Keep last 50
        self.history[task_type] = self.history[task_type][-50:]
        self._save_history()
    
    async def get_accuracy(self, task_type: str = None) -> dict:
        """Tính accuracy của predictions"""
        if task_type:
            tasks = [task_type] if task_type in self.history else []
        else:
            tasks = list(self.history.keys())
        
        results = {}
        for t in tasks:
            hist = self.history.get(t, [])
            if len(hist) < 2:
                continue
            
            # Compare last predictions vs next values
            errors = []
            for i in range(len(hist) - 1):
                if hist[i] > 0:
                    err = abs(hist[i+1] - hist[i]) / hist[i]
                    errors.append(err)
            
            if errors:
                mape = sum(errors) / len(errors)
                results[t] = {
                    "samples": len(hist),
                    "mape": round(mape * 100, 2),
                    "accuracy": round((1 - mape) * 100, 2),
                }
        
        return results