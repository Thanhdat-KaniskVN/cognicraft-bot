# ml_mini/heartbeat.py
"""
Adaptive Heartbeat - Heartbeat interval tự điều chỉnh
- Stable state → tăng interval (tiết kiệm CPU)
- Error state → giảm interval (phát hiện nhanh)
"""
from typing import Dict, Optional
from datetime import datetime


class AdaptiveHeartbeat:
    """
    Adaptive Heartbeat Manager
    
    Rules:
    - HEALTHY streak >= 5 → tăng interval (max = 15s)
    - Error occurred → giảm interval (min = 1s)
    """
    
    def __init__(self, base: int = 3, min_i: int = 1, max_i: int = 15):
        self.base = base
        self.min = min_i
        self.max = max_i
        self.current = base
        
        # Per-sandbox tracking
        self.healthy_streaks: Dict[str, int] = {}
        self.error_counts: Dict[str, int] = {}
        self.last_intervals: Dict[str, int] = {}
    
    # ============================================================
    # UPDATE LOGIC
    # ============================================================
    
    def record_success(self, sandbox_id: str) -> int:
        """Ghi nhận heartbeat thành công"""
        self.healthy_streaks[sandbox_id] = self.healthy_streaks.get(sandbox_id, 0) + 1
        self.error_counts[sandbox_id] = 0
        
        # Nếu healthy streak đủ dài → tăng interval
        if self.healthy_streaks[sandbox_id] >= 5:
            interval = self._increase_interval(sandbox_id)
            self.healthy_streaks[sandbox_id] = 0  # Reset streak
            return interval
        
        return self.get_interval(sandbox_id)
    
    def record_error(self, sandbox_id: str) -> int:
        """Ghi nhận heartbeat lỗi"""
        self.error_counts[sandbox_id] = self.error_counts.get(sandbox_id, 0) + 1
        self.healthy_streaks[sandbox_id] = 0
        
        # Giảm interval ngay
        interval = self._decrease_interval(sandbox_id)
        return interval
    
    # ============================================================
    # INTERVAL ADJUSTMENT
    # ============================================================
    
    def _increase_interval(self, sandbox_id: str) -> int:
        """Tăng interval (khi ổn định)"""
        current = self.get_interval(sandbox_id)
        
        # Tăng theo bậc: 3 → 5 → 8 → 12 → 15
        if current < 5:
            new = 5
        elif current < 8:
            new = 8
        elif current < 12:
            new = 12
        else:
            new = self.max
        
        new = min(new, self.max)
        self.last_intervals[sandbox_id] = new
        print(f"[Heartbeat] {sandbox_id}: ⬆️ interval {current}s → {new}s")
        return new
    
    def _decrease_interval(self, sandbox_id: str) -> int:
        """Giảm interval (khi có lỗi)"""
        current = self.get_interval(sandbox_id)
        
        # Giảm xuống min ngay
        new = max(self.min, current // 2)
        if new == current:
            new = self.min
        
        self.last_intervals[sandbox_id] = new
        print(f"[Heartbeat] {sandbox_id}: ⬇️ interval {current}s → {new}s")
        return new
    
    def get_interval(self, sandbox_id: str) -> int:
        """Lấy interval hiện tại"""
        return self.last_intervals.get(sandbox_id, self.base)
    
    # ============================================================
    # STATS
    # ============================================================
    
    def get_stats(self) -> dict:
        """Stats của heartbeat"""
        return {
            "base_interval": self.base,
            "min_interval": self.min,
            "max_interval": self.max,
            "sandboxes": {
                sid: {
                    "current_interval": self.get_interval(sid),
                    "healthy_streak": self.healthy_streaks.get(sid, 0),
                    "error_count": self.error_counts.get(sid, 0),
                }
                for sid in set(list(self.healthy_streaks.keys()) + list(self.error_counts.keys()))
            },
        }