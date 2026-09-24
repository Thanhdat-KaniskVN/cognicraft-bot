# progress_predictor.py
"""
Progress Predictor - Dự đoán tiến bộ
- Phân tích xu hướng (linear regression)
- Dự đoán 2-4 tuần tới
- Cảnh báo plateau
- Gợi ý cải thiện
"""
import sqlite3
import statistics
from datetime import datetime
from ai_provider import call_ai_json


class ProgressPredictor:
    """Dự đoán tiến bộ của member"""

    # Ngưỡng cảnh báo
    PLATEAU_THRESHOLD = 0.05   # Slope < 0.05/tuần = plateau
    IMPROVING_THRESHOLD = 0.1  # Slope > 0.1/tuần = improving
    DECLINING_THRESHOLD = -0.1 # Slope < -0.1/tuần = declining

    def __init__(self, db_path="scores.db"):
        self.db_path = db_path

    # ============================================================
    # DATA LOADING
    # ============================================================

    def _get_history(self, member, weeks=8):
        """Lấy lịch sử điểm của member"""
        member_clean = member.split("-NR.")[0].strip()

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT week, total, accuracy, depth, connection, presentation, source
            FROM scores
            WHERE member = ?
            ORDER BY week ASC
            LIMIT ?
        """, (member_clean, weeks)).fetchall()
        conn.close()

        return [
            {
                "week": r[0],
                "total": r[1],
                "accuracy": r[2],
                "depth": r[3],
                "connection": r[4],
                "presentation": r[5],
                "source": r[6],
            }
            for r in rows
        ]

    def _get_all_members(self):
        """Lấy danh sách members có scores"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT DISTINCT member FROM scores ORDER BY member
        """).fetchall()
        conn.close()
        return [r[0] for r in rows]

    # ============================================================
    # STATISTICAL ANALYSIS
    # ============================================================

    def _linear_regression(self, values):
        """
        Tính slope của linear regression.

        Returns:
            (slope, intercept)
        """
        n = len(values)
        if n < 2:
            return 0, values[0] if values else 0

        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        num = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((x[i] - x_mean) ** 2 for i in range(n))

        if den == 0:
            return 0, y_mean

        slope = num / den
        intercept = y_mean - slope * x_mean
        return slope, intercept

    def _calculate_trend(self, slope):
        """Xác định xu hướng từ slope"""
        if slope > self.IMPROVING_THRESHOLD:
            return "improving", "📈", "Đang cải thiện"
        elif slope < self.DECLINING_THRESHOLD:
            return "declining", "📉", "Đang giảm"
        elif abs(slope) < self.PLATEAU_THRESHOLD:
            return "plateau", "➡️", "Đang chững lại"
        else:
            return "slowly_improving", "↗️", "Cải thiện chậm"

    # ============================================================
    # PREDICTION
    # ============================================================

    def predict(self, member, weeks_ahead=4):
        """
        Dự đoán điểm của member trong N tuần tới.

        Args:
            member: Tên member
            weeks_ahead: Số tuần dự đoán (2-8)

        Returns:
            dict: {
                "member": str,
                "history": [{week, total}],
                "current_avg": float,
                "trend": str,
                "trend_icon": str,
                "trend_desc": str,
                "slope": float,
                "predictions": [{week, predicted_score, confidence}],
                "warnings": [str],
                "summary": str,
            }
        """
        weeks_ahead = max(2, min(8, weeks_ahead))

        history = self._get_history(member, weeks=8)
        if not history:
            return {"error": f"Không có dữ liệu cho {member}"}

        if len(history) < 3:
            return {
                "error": f"Cần ít nhất 3 tuần dữ liệu. Hiện có {len(history)} tuần."
            }

        # Extract scores
        scores = [h["total"] for h in history]
        weeks = [h["week"] for h in history]

        # Statistics
        current_avg = round(statistics.mean(scores), 2)
        slope, intercept = self._linear_regression(scores)
        volatility = round(statistics.stdev(scores), 3) if len(scores) > 1 else 0

        # Trend
        trend, trend_icon, trend_desc = self._calculate_trend(slope)

        # Predictions
        last_week = weeks[-1]
        n = len(scores)
        predictions = []

        for i in range(1, weeks_ahead + 1):
            # Predict using linear regression
            predicted = intercept + slope * (n - 1 + i)
            predicted = max(0, min(5, predicted))  # Clamp 0-5

            # Confidence decreases with distance
            confidence = max(0.3, 1.0 - (i * 0.15))

            # Adjust confidence by volatility
            if volatility > 0.5:
                confidence *= 0.7

            predictions.append({
                "week": last_week + i,
                "predicted_score": round(predicted, 2),
                "confidence": round(confidence, 2),
            })

        # Warnings
        warnings = self._generate_warnings(
            member, scores, slope, volatility, predictions
        )

        # Summary (AI)
        summary = self._generate_summary(
            member, scores, weeks, slope, trend, predictions, warnings
        )

        return {
            "member": member,
            "history": [{"week": w, "total": s} for w, s in zip(weeks, scores)],
            "current_avg": current_avg,
            "last_score": scores[-1],
            "slope": round(slope, 3),
            "volatility": volatility,
            "trend": trend,
            "trend_icon": trend_icon,
            "trend_desc": trend_desc,
            "predictions": predictions,
            "warnings": warnings,
            "summary": summary,
        }

    def predict_all(self, weeks_ahead=4):
        """Dự đoán cho tất cả members"""
        members = self._get_all_members()
        results = []

        for member in members:
            result = self.predict(member, weeks_ahead)
            if "error" not in result:
                results.append(result)

        # Sort by current_avg desc
        results.sort(key=lambda x: x["current_avg"], reverse=True)

        return results

    # ============================================================
    # WARNINGS
    # ============================================================

    def _generate_warnings(self, member, scores, slope, volatility, predictions):
        """Sinh cảnh báo"""
        warnings = []

        # 1. Plateau warning
        if abs(slope) < self.PLATEAU_THRESHOLD and len(scores) >= 4:
            warnings.append({
                "type": "plateau",
                "severity": "medium",
                "message": (
                    "⚠️ Điểm đang chững lại trong 4 tuần qua. "
                    "Cần thay đổi cách học để đột phá."
                ),
            })

        # 2. Declining warning
        if slope < self.DECLINING_THRESHOLD:
            warnings.append({
                "type": "declining",
                "severity": "high",
                "message": (
                    f"🚨 Điểm đang giảm ({slope:.2f}/tuần). "
                    "Cần xem lại phương pháp học ngay!"
                ),
            })

        # 3. High volatility
        if volatility > 0.5:
            warnings.append({
                "type": "volatility",
                "severity": "medium",
                "message": (
                    f"📊 Điểm dao động lớn (std={volatility:.2f}). "
                    "Cần ổn định phong độ."
                ),
            })

        # 4. Low score warning
        if scores[-1] < 3.0:
            warnings.append({
                "type": "low_score",
                "severity": "high",
                "message": (
                    f"🚨 Điểm gần nhất chỉ {scores[-1]}/5. "
                    "Cần tập trung cải thiện cơ bản."
                ),
            })

        # 5. Prediction ceiling
        if predictions and predictions[-1]["predicted_score"] >= 4.5:
            warnings.append({
                "type": "near_ceiling",
                "severity": "info",
                "message": (
                    "🎯 Sắp đạt điểm tối đa (4.5+). "
                    "Cần focus vào depth và connection."
                ),
            })

        return warnings

    # ============================================================
    # SUMMARY (AI)
    # ============================================================

    def _generate_summary(self, member, scores, weeks, slope, trend, predictions, warnings):
        """Sinh summary bằng AI"""
        # Build context
        history_text = " | ".join(
            f"W{w}: {s}/5" for w, s in zip(weeks, scores)
        )
        pred_text = " | ".join(
            f"W{p['week']}: {p['predicted_score']}/5" for p in predictions
        )
        warn_text = "\n".join(f"- {w['message']}" for w in warnings[:3])

        prompt = f"""Phân tích tiến bộ của member:

**Member:** {member}
**Lịch sử:** {history_text}
**Xu hướng:** {trend} (slope={slope:.3f}/tuần)
**Dự đoán:** {pred_text}
**Cảnh báo:**
{warn_text if warn_text else "(không có)"}

**Yêu cầu:**
- Tổng kết ngắn gọn (2-3 câu)
- Đưa ra 2-3 gợi ý cụ thể để cải thiện
- Tone: khích lệ, không chỉ trích

**Trả về JSON:**
{{
  "summary": "<tổng kết>",
  "recommendations": ["<gợi ý 1>", "<gợi ý 2>", "<gợi ý 3>"]
}}

Chỉ trả về JSON."""

        try:
            result = call_ai_json(prompt, task_type="progress_predict")
            return {
                "summary": result.get("summary", ""),
                "recommendations": result.get("recommendations", []),
            }
        except Exception as e:
            print(f"[ProgressPredictor] Summary error: {e}")
            return {
                "summary": f"Điểm TB: {statistics.mean(scores):.2f}/5. Xu hướng: {trend}.",
                "recommendations": [],
            }

    # ============================================================
    # UTILS
    # ============================================================

    def get_cohort_overview(self):
        """Tổng quan toàn cohort"""
        members = self._get_all_members()
        overview = {
            "total_members": len(members),
            "with_data": 0,
            "improving": 0,
            "plateau": 0,
            "declining": 0,
            "avg_score": 0,
        }

        all_scores = []
        for m in members:
            history = self._get_history(m, weeks=8)
            if not history:
                continue

            overview["with_data"] += 1
            scores = [h["total"] for h in history]
            all_scores.extend(scores)

            if len(scores) >= 3:
                slope, _ = self._linear_regression(scores)
                if slope > self.IMPROVING_THRESHOLD:
                    overview["improving"] += 1
                elif slope < self.DECLINING_THRESHOLD:
                    overview["declining"] += 1
                elif abs(slope) < self.PLATEAU_THRESHOLD:
                    overview["plateau"] += 1

        if all_scores:
            overview["avg_score"] = round(statistics.mean(all_scores), 2)

        return overview