# jarvis/priority_scorer.py
"""Score event priority (0-20). Higher = more important = keep."""
from datetime import datetime
import pytz

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

TYPE_BASE = {
    "exam": 10, "class": 8, "meeting": 7,
    "study": 5, "task": 4,
    "gym": 2, "run": 2, "bike": 2, "yoga": 2, "swim": 2,
    "other": 3,
}

IMPORTANT_KW = ["quan trong", "important", "deadline", "gap", "khan cap", "bat buoc", "batbuoc"]
LOW_KW = ["tuy chon", "optional", "co the bo", "khong gap"]


def score_event(ev, now=None):
    """Return (score, reasons)."""
    if now is None:
        now = datetime.now(TZ)
    reasons = []
    score = TYPE_BASE.get(ev.get("event_type", "other"), 3)
    reasons.append(f"type={ev.get('event_type')} -> base {score}")

    start = ev.get("start_time")
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if start.tzinfo is None:
        start = TZ.localize(start)
    hours_until = (start - now).total_seconds() / 3600
    if 0 <= hours_until < 2:
        score += 5
        reasons.append("within 2h (+5)")
    elif 0 <= hours_until < 24:
        score += 2
        reasons.append("within 24h (+2)")

    title = (ev.get("title") or "").lower()
    for kw in IMPORTANT_KW:
        if kw in title:
            score += 5
            reasons.append(f"kw '{kw}' (+5)")
            break
    for kw in LOW_KW:
        if kw in title:
            score -= 3
            reasons.append(f"kw '{kw}' (-3)")
            break

    if ev.get("priority") == "critical":
        score += 5
        reasons.append("priority=critical (+5)")
    elif ev.get("priority") == "high":
        score += 3
        reasons.append("priority=high (+3)")

    return max(0, score), reasons


def classify(score, severity):
    """Return action based on score + severity."""
    thresh = {"critical": 9, "high": 6, "medium": 3, "low": 0}.get(severity, 3)
    if severity == "critical":
        return "cancel"
    if score >= thresh:
        return "keep"
    if score >= 3:
        return "reschedule"
    return "cancel"