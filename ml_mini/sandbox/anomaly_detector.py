# ml_mini/sandbox/anomaly_detector.py
"""
Anomaly Detector Sandbox - Z-score với fallback
FIX: Lazy init + safe KeyError handling
"""
import math
from .base import BaseSandbox
from ..data.loader import DataLoader


class AnomalyDetectorSandbox(BaseSandbox):
    NAME = "anomaly_detector"
    VERSION = "1.2.0"
    DESCRIPTION = "Phát hiện bất thường bằng Z-score (fallback)"
    CATEGORY = "detection"
    
    Z_SCORE_THRESHOLD = 2.0
    SUDDEN_DROP_THRESHOLD = 1.5
    LOW_SCORE_THRESHOLD = 3.0
    MIN_SAMPLES = 3
    
    def __init__(self, config=None):
        super().__init__(config)
        self.loader = DataLoader()
        self.stats_cache = {}
        self.cohort_stats = None
        self._initialized = False
    
    # ============================================================
    # LAZY INIT
    # ============================================================
    
    def _ensure_initialized(self):
        """Compute stats lần đầu"""
        if self._initialized:
            return
        
        print(f"[{self.NAME}] 🔧 Lazy init: computing stats...")
        
        # ✅ FIX: Compute cohort TRƯỚC, ensure luôn có dict
        self.cohort_stats = self._compute_cohort_stats()
        print(f"[{self.NAME}]    cohort: mean={self.cohort_stats['mean']}, std={self.cohort_stats['std']}")
        
        members = self.loader.get_all_members()
        for member in members:
            self._compute_member_stats(member)
        print(f"[{self.NAME}]    computed {len(self.stats_cache)} member stats")
        
        self._initialized = True
    
    async def on_start(self):
        self._ensure_initialized()
        print(f"[{self.NAME}] ✅ Ready")
    
    # ============================================================
    # COHORT STATS
    # ============================================================
    
    def _compute_cohort_stats(self) -> dict:
        """Stats toàn cohort (luôn trả dict hợp lệ)"""
        try:
            all_scores = self.loader.get_all_scores()
            totals = [s["total"] for s in all_scores if s.get("total") is not None]
            
            if not totals:
                print(f"[{self.NAME}] ⚠️ No data → default stats")
                return {
                    "mean": 3.0,
                    "std": 1.0,
                    "min": 0.0,
                    "max": 5.0,
                    "n": 0,
                }
            
            n = len(totals)
            mean = sum(totals) / n
            variance = sum((s - mean) ** 2 for s in totals) / n
            std = math.sqrt(variance)
            
            return {
                "mean": round(mean, 3),
                "std": round(std, 3) if std > 0.01 else 0.5,  # Min std
                "min": round(min(totals), 2),
                "max": round(max(totals), 2),
                "n": n,
            }
        except Exception as e:
            print(f"[{self.NAME}] ❌ Cohort stats error: {e}")
            return {"mean": 3.0, "std": 1.0, "min": 0.0, "max": 5.0, "n": 0}
    
    # ============================================================
    # MEMBER STATS
    # ============================================================
    
    def _compute_member_stats(self, member: str):
        """Compute member stats (có fallback)"""
        scores = self.loader.get_member_history(member, limit=20)
        
        if not scores:
            return
        
        # ✅ FIX: Ensure cohort_stats có trước
        if self.cohort_stats is None:
            self.cohort_stats = self._compute_cohort_stats()
        
        # Fallback cho ít data
        if len(scores) < self.MIN_SAMPLES:
            self.stats_cache[member] = {
                "type": "fallback",
                "scores": scores,
                "mean": self.cohort_stats["mean"],
                "std": self.cohort_stats["std"],
                "min": min(scores),
                "max": max(scores),
                "n": len(scores),
            }
            return
        
        # Full stats
        n = len(scores)
        mean = sum(scores) / n
        variance = sum((s - mean) ** 2 for s in scores) / n
        std = math.sqrt(variance)
        
        self.stats_cache[member] = {
            "type": "full",
            "mean": round(mean, 3),
            "std": round(std, 3) if std > 0.01 else 0.5,
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "scores": scores,
            "n": n,
        }
    
    # ============================================================
    # RUN
    # ============================================================
    
    async def run(self, member: str = None) -> dict:
        self._ensure_initialized()
        
        if member:
            return await self._detect_member(member)
        else:
            return await self._detect_all()
    
    async def _detect_member(self, member: str) -> dict:
        if member not in self.stats_cache:
            self._compute_member_stats(member)
        
        if member not in self.stats_cache:
            return {
                "member": member,
                "error": "Không có dữ liệu",
                "anomalies": [],
                "is_anomaly": False,
            }
        
        stats = self.stats_cache[member]
        scores = stats["scores"]
        mean = stats["mean"]
        std = stats["std"]
        is_fallback = stats["type"] == "fallback"
        
        anomalies = []
        latest = scores[-1]
        
        # Check 1: Z-score
        if std > 0:
            z_score = (latest - mean) / std
            if abs(z_score) > self.Z_SCORE_THRESHOLD:
                anomalies.append({
                    "type": "outlier",
                    "severity": "high" if abs(z_score) > 3 else "medium",
                    "message": f"Điểm {latest} lệch {abs(z_score):.2f} std so với mean {mean}",
                    "z_score": round(z_score, 2),
                })
        
        # Check 2: Sudden drop
        if len(scores) >= 2:
            diff = latest - scores[-2]
            if diff < -self.SUDDEN_DROP_THRESHOLD:
                anomalies.append({
                    "type": "sudden_drop",
                    "severity": "high",
                    "message": f"Điểm giảm {abs(diff):.2f} so với tuần trước",
                    "drop": round(diff, 2),
                })
        
        # Check 3: Low score
        if latest < self.LOW_SCORE_THRESHOLD:
            anomalies.append({
                "type": "low_score",
                "severity": "medium",
                "message": f"Điểm {latest} dưới ngưỡng {self.LOW_SCORE_THRESHOLD}",
                "score": latest,
            })
        
        anomaly_score = min(1.0, len(anomalies) * 0.3)
        
        result = {
            "member": member,
            "latest_score": latest,
            "mean": mean,
            "std": std,
            "n_samples": stats["n"],
            "anomalies": anomalies,
            "anomaly_score": round(anomaly_score, 2),
            "is_anomaly": len(anomalies) > 0,
        }
        
        if is_fallback:
            result["note"] = f"Dùng cohort stats làm baseline (mean={self.cohort_stats['mean']})"
        
        return result
    
    async def _detect_all(self) -> dict:
        members = self.loader.get_all_members()
        results = []
        for m in members:
            r = await self._detect_member(m)
            results.append(r)
        
        anomalies = [r for r in results if r.get("is_anomaly")]
        
        return {
            "total_members": len(members),
            "anomalies_found": len(anomalies),
            "results": results,
        }