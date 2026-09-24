# time_tracker.py
"""
Time Tracker - 2 tầng:
- TẦNG 1: Time Gốc (Ground Truth) - do Admin/SOP thiết lập
- TẦNG 2: Time AI Đo Lường - phân tích timestamps thực tế
- TẦNG 3: Đối Chiếu - so sánh 2 nguồn, phát hiện lệch
"""
from datetime import datetime, timedelta
from collections import Counter
import pytz
import config
from config import (
    ROADMAP_START_DATE,
    WEEK_DURATION_DAYS,
    BREAK_WEEKS,
    CYCLE_MODES,
    TIMEZONE,
)


class TimeTracker:
    """Quản lý thời gian: gốc + AI đo lường + đối chiếu"""

    def __init__(self):
        self.tz = pytz.timezone(TIMEZONE)

    # ============================================================
    # TẦNG 1: TIME GỐC
    # ============================================================

    def get_ground_truth_week(self, dt=None):
        """
        Tính tuần theo TIME GỐC (lộ trình chính thức).

        Args:
            dt: datetime (mặc định = now)

        Returns:
            int: Tuần thứ mấy (1-72)
        """
        # Nếu Admin override → dùng override
        if config.OVERRIDE_WEEK is not None:
            return config.OVERRIDE_WEEK

        if dt is None:
            dt = datetime.now(self.tz)

        # Localize start date
        start = self.tz.localize(datetime(*ROADMAP_START_DATE))
        days_passed = (dt - start).days

        if days_passed < 0:
            return 0  # Chưa bắt đầu

        return days_passed // WEEK_DURATION_DAYS + 1

    def is_break_week(self, week):
        """Kiểm tra tuần có phải Break Week không"""
        return week in BREAK_WEEKS

    def get_week_mode(self, week):
        """Xác định Mode của tuần (Academic/Research/Project/Break)"""
        if self.is_break_week(week):
            return "Break"

        # Chu kỳ 4 tuần, bỏ qua break weeks
        effective_week = week
        for bw in sorted(BREAK_WEEKS):
            if week > bw:
                effective_week -= 1

        cycle_pos = (effective_week - 1) % 4 + 1
        return CYCLE_MODES.get(cycle_pos, "Unknown")

    def get_week_start_end(self, week):
        """Trả về ngày bắt đầu + kết thúc của tuần"""
        start = self.tz.localize(datetime(*ROADMAP_START_DATE))
        week_start = start + timedelta(days=(week - 1) * WEEK_DURATION_DAYS)
        week_end = week_start + timedelta(days=WEEK_DURATION_DAYS - 1)
        return week_start, week_end

    def get_current_info(self):
        """Lấy toàn bộ thông tin tuần hiện tại"""
        week = self.get_ground_truth_week()
        start, end = self.get_week_start_end(week)
        now = datetime.now(self.tz)
        days_remaining = (end - now).days

        return {
            "week": week,
            "mode": self.get_week_mode(week),
            "is_break": self.is_break_week(week),
            "start_date": start.strftime("%d/%m/%Y"),
            "end_date": end.strftime("%d/%m/%Y"),
            "days_remaining": max(days_remaining, 0),
        }

    # ============================================================
    # TẦNG 2: TIME AI ĐO LƯỜNG
    # ============================================================

    def measure_actual_week(self, submissions=None, scores=None):
        """
        Đo tuần thực tế dựa trên timestamps.

        Args:
            submissions: List submissions với timestamps
            scores: List scores với 'created_at'

        Returns:
            dict: {
                "measured_week": int,
                "confidence": float,
                "evidence": {...}
            }
        """
        submissions = submissions or []
        scores = scores or []

        if not submissions and not scores:
            return {
                "measured_week": 0,
                "confidence": 0.0,
                "evidence": {},
            }

        timestamps = []

        # Lấy timestamps từ submissions
        for sub in submissions:
            ts = (sub.get("thread_created_at") or
                  sub.get("submitted_at") or
                  sub.get("created_at"))
            if ts:
                timestamps.append(("submission", ts, sub.get("member", "?")))

        # Lấy timestamps từ scores
        for score in scores:
            ts = score.get("created_at")
            if ts:
                timestamps.append(("score", ts, score.get("member", "?")))

        if not timestamps:
            return {
                "measured_week": 0,
                "confidence": 0.0,
                "evidence": {},
            }

        # Tính tuần cho mỗi timestamp
        start = self.tz.localize(datetime(*ROADMAP_START_DATE))
        weeks = []

        for ts_type, ts, member in timestamps:
            # Parse string → datetime
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except ValueError:
                    continue

            # Localize nếu chưa có tz
            if ts.tzinfo is None:
                ts = self.tz.localize(ts)

            days = (ts - start).days
            if days < 0:
                continue
            week = days // WEEK_DURATION_DAYS + 1
            weeks.append(week)

        if not weeks:
            return {
                "measured_week": 0,
                "confidence": 0.0,
                "evidence": {},
            }

        # Mode = tuần xuất hiện nhiều nhất
        week_counts = Counter(weeks)
        measured_week = week_counts.most_common(1)[0][0]
        confidence = week_counts[measured_week] / len(weeks)

        # Lấy earliest / latest
        earliest = min(timestamps, key=lambda x: str(x[1]))
        latest = max(timestamps, key=lambda x: str(x[1]))

        return {
            "measured_week": measured_week,
            "confidence": round(confidence, 2),
            "evidence": {
                "total_timestamps": len(weeks),
                "week_distribution": dict(week_counts),
                "earliest": str(earliest[1]),
                "latest": str(latest[1]),
            },
        }

    # ============================================================
    # TẦNG 3: ĐỐI CHIẾU
    # ============================================================

    def verify(self, submissions=None, scores=None):
        """
        Đối chiếu time gốc vs AI đo lường.

        Returns:
            dict: {
                "ground_truth_week": int,
                "ai_measured_week": int,
                "match": bool,
                "diff": int,
                "alert": str,
                "details": {...}
            }
        """
        ground_truth = self.get_ground_truth_week()
        ai_result = self.measure_actual_week(submissions, scores)
        ai_measured = ai_result["measured_week"]

        diff = ai_measured - ground_truth
        match = (diff == 0)

        # Xác định alert
        if match:
            alert = "✅ OK – Time gốc và AI đo lường khớp nhau"
        elif ai_measured == 0:
            alert = "⚠️ Chưa có dữ liệu để AI đo lường"
        elif abs(diff) == 1:
            alert = f"⚠️ Lệch 1 tuần (AI đo: {ai_measured}, Gốc: {ground_truth})"
        else:
            alert = f"🚨 Lệch {abs(diff)} tuần (AI đo: {ai_measured}, Gốc: {ground_truth})"

        return {
            "ground_truth_week": ground_truth,
            "ai_measured_week": ai_measured,
            "match": match,
            "diff": diff,
            "alert": alert,
            "ground_truth_mode": self.get_week_mode(ground_truth),
            "ai_confidence": ai_result["confidence"],
            "evidence": ai_result["evidence"],
        }

    # ============================================================
    # OVERRIDE
    # ============================================================

    def set_override_week(self, week):
        """Set override tuần (Admin)"""
        config.OVERRIDE_WEEK = week
        return True

    def clear_override_week(self):
        """Xóa override tuần"""
        config.OVERRIDE_WEEK = None
        return True

    def is_override_active(self):
        """Kiểm tra có override không"""
        return config.OVERRIDE_WEEK is not None

    # ============================================================
    # DEBUG
    # ============================================================

    def debug_info(self):
        """Trả về thông tin debug đầy đủ"""
        return {
            "roadmap_start_date": f"{ROADMAP_START_DATE[0]}-{ROADMAP_START_DATE[1]:02d}-{ROADMAP_START_DATE[2]:02d}",
            "week_duration_days": WEEK_DURATION_DAYS,
            "break_weeks": BREAK_WEEKS,
            "override_week": config.OVERRIDE_WEEK,
            "override_active": self.is_override_active(),
            "current_week": self.get_ground_truth_week(),
            "current_info": self.get_current_info(),
        }