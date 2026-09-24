# ml_mini/sandbox/score_predictor.py
"""
Score Predictor Sandbox - Linear Regression với fallback
FIX: Lazy init + correct cohort avg
"""
from .base import BaseSandbox
from ..data.loader import DataLoader


class ScorePredictorSandbox(BaseSandbox):
    NAME = "score_predictor"
    VERSION = "1.2.0"
    DESCRIPTION = "Dự đoán điểm số bằng Linear Regression (fallback)"
    CATEGORY = "prediction"
    
    MIN_SAMPLES_FOR_REGRESSION = 3
    
    def __init__(self, config=None):
        super().__init__(config)
        self.loader = DataLoader()
        self.trained_models = {}
        self.cohort_avg = None      # None = chưa compute
        self._initialized = False
    
    # ============================================================
    # LAZY INIT
    # ============================================================
    
    def _ensure_initialized(self):
        """Compute cohort stats lần đầu"""
        if self._initialized:
            return
        
        print(f"[{self.NAME}] 🔧 Lazy init: computing cohort stats...")
        self.cohort_avg = self._compute_cohort_avg()
        print(f"[{self.NAME}]    cohort_avg = {self.cohort_avg}")
        
        members = self.loader.get_all_members()
        for member in members:
            self._train_member(member)
        print(f"[{self.NAME}]    trained {len(self.trained_models)} models")
        
        self._initialized = True
    
    async def on_start(self):
        """Optional: có thể gọi trước, hoặc lazy"""
        self._ensure_initialized()
        print(f"[{self.NAME}] ✅ Ready")
    
    # ============================================================
    # COHORT AVG
    # ============================================================
    
    def _compute_cohort_avg(self) -> float:
        """Compute average của toàn cohort"""
        try:
            all_scores = self.loader.get_all_scores()
            totals = [s["total"] for s in all_scores if s.get("total") is not None]
            
            if not totals:
                print(f"[{self.NAME}] ⚠️ Không có data → dùng default 3.0")
                return 3.0
            
            avg = sum(totals) / len(totals)
            print(f"[{self.NAME}]    Computed from {len(totals)} scores")
            return round(avg, 2)
        except Exception as e:
            print(f"[{self.NAME}] ❌ Cohort avg error: {e}")
            return 3.0
    
    # ============================================================
    # TRAIN
    # ============================================================
    
    def _train_member(self, member: str) -> bool:
        scores = self.loader.get_member_history(member, limit=20)
        
        if not scores:
            return False
        
        # Fallback 1: 1 sample
        if len(scores) == 1:
            self.trained_models[member] = {
                "type": "single_sample",
                "last_score": scores[0],
                "cohort_avg": self.cohort_avg or 3.0,
                "n_samples": 1,
            }
            return True
        
        # Fallback 2: 2 samples
        if len(scores) < self.MIN_SAMPLES_FOR_REGRESSION:
            diff = scores[-1] - scores[-2]
            self.trained_models[member] = {
                "type": "two_samples",
                "last_score": scores[-1],
                "cohort_avg": self.cohort_avg or 3.0,
                "slope": diff,
                "n_samples": len(scores),
            }
            return True
        
        # Full Linear Regression
        n = len(scores)
        x_vals = list(range(n))
        y_vals = scores
        
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)
        
        if denominator == 0:
            return False
        
        a = numerator / denominator
        b = y_mean - a * x_mean
        
        y_pred = [a * x + b for x in x_vals]
        ss_res = sum((y - yp) ** 2 for y, yp in zip(y_vals, y_pred))
        ss_tot = sum((y - y_mean) ** 2 for y in y_vals)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        self.trained_models[member] = {
            "type": "linear_regression",
            "a": a,
            "b": b,
            "r2": round(r2, 3),
            "n_samples": n,
            "last_score": scores[-1],
            "cohort_avg": self.cohort_avg or 3.0,
        }
        return True
    
    # ============================================================
    # RUN
    # ============================================================
    
    async def run(self, member: str, weeks_ahead: int = 4) -> dict:
        """Predict với lazy init"""
        self._ensure_initialized()
        
        if member not in self.trained_models:
            self._train_member(member)
        
        if member not in self.trained_models:
            return {
                "member": member,
                "error": "Không có dữ liệu cho member này",
                "predictions": [],
                "model": "none",
            }
        
        model = self.trained_models[member]
        model_type = model["type"]
        
        # ============================================================
        # FALLBACK: SINGLE SAMPLE
        # ============================================================
        if model_type == "single_sample":
            last = model["last_score"]
            cohort = model["cohort_avg"]
            
            # ✅ FIX: Predict = weight sum, drift nhẹ về cohort
            # Nếu member tốt hơn cohort → giảm nhẹ
            # Nếu member kém hơn cohort → tăng nhẹ
            
            predictions = []
            for i in range(1, weeks_ahead + 1):
                # Pull towards cohort: 10% per week, max 30%
                pull = min(0.3, 0.1 * i)
                pred = last * (1 - pull) + cohort * pull
                pred = max(0, min(5, pred))
                predictions.append({
                    "week_ahead": i,
                    "predicted_score": round(pred, 2),
                })
            
            return {
                "member": member,
                "current_score": last,
                "cohort_avg": cohort,
                "trend": "unknown (insufficient data)",
                "slope": 0.0,
                "r2_score": 0.0,
                "n_samples": 1,
                "predictions": predictions,
                "model": "single_sample_fallback",
                "note": "Chỉ có 1 data point. Predict = blend(current, cohort).",
            }
        
        # ============================================================
        # FALLBACK: TWO SAMPLES
        # ============================================================
        if model_type == "two_samples":
            last = model["last_score"]
            slope = model["slope"]
            cohort = model["cohort_avg"]
            
            predictions = []
            for i in range(1, weeks_ahead + 1):
                # Dự đoán theo slope nhưng giới hạn pull về cohort
                pred = last + slope * i * 0.5  # 0.5 = conservative
                # Pull nhẹ về cohort
                pull = min(0.2, 0.05 * i)
                pred = pred * (1 - pull) + cohort * pull
                pred = max(0, min(5, pred))
                predictions.append({
                    "week_ahead": i,
                    "predicted_score": round(pred, 2),
                })
            
            return {
                "member": member,
                "current_score": last,
                "cohort_avg": cohort,
                "trend": "improving" if slope > 0.1 else ("declining" if slope < -0.1 else "stable"),
                "slope": round(slope, 3),
                "r2_score": 0.0,
                "n_samples": 2,
                "predictions": predictions,
                "model": "two_samples_fallback",
            }
        
        # ============================================================
        # LINEAR REGRESSION
        # ============================================================
        a = model["a"]
        b = model["b"]
        n = model["n_samples"]
        
        predictions = []
        for i in range(1, weeks_ahead + 1):
            x = n - 1 + i
            y = a * x + b
            y = max(0, min(5, y))
            predictions.append({
                "week_ahead": i,
                "predicted_score": round(y, 2),
            })
        
        return {
            "member": member,
            "current_score": model["last_score"],
            "cohort_avg": model["cohort_avg"],
            "trend": "improving" if a > 0.05 else ("declining" if a < -0.05 else "stable"),
            "slope": round(a, 3),
            "r2_score": model["r2"],
            "n_samples": n,
            "predictions": predictions,
            "model": "linear_regression",
        }
    
    async def predict_all(self, weeks_ahead: int = 4) -> dict:
        self._ensure_initialized()
        members = self.loader.get_all_members()
        results = []
        for member in members:
            result = await self.run(member, weeks_ahead)
            results.append(result)
        return {"predictions": results}