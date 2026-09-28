# jarvis/nl_parser.py
"""Natural Language Parser - Parse cau tieng Viet tu nhien thanh Event."""
import re
from datetime import datetime, timedelta, time
from typing import Optional
import pytz

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

ACTIVITY_PATTERNS = {
    "gym":     [r"\bgym\b", r"the hinh", r"tap the hinh", r"tap gym"],
    "run":     [r"chay bo", r"\brun\b", r"chay\s*\d+\s*km", r"jog"],
    "bike":    [r"dap xe", r"\bbike\b", r"cycling", r"xe dap"],
    "swim":    [r"boi", r"\bswim\b"],
    "yoga":    [r"yoga", r"thien"],
    "class":   [r"hoc mon", r"di hoc", r"len lop", r"\bclass\b", r"tiet hoc"],
    "exam":    [r"\bthi cuoi\b", r"\bthi giua\b", r"\bthi hoc ki\b", r"thi toan|thi ly|thi hoa|thi van|thi anh",
                r"kiem tra", r"\bexam\b", r"\bbai thi\b"],
    "meeting": [r"hop nhom", r"cuoc hop", r"\bmeeting\b", r"\bhop\b", r"hoi hop"],
    "study":   [r"\bon bai\b", r"\bon lai\b", r"\blam bai\b", r"\bstudy\b",
                r"\bdoc sach\b", r"\bhoc bai\b", r"\bon tap\b", r"\bhoc\b"],
    "task":    [r"lam\s+", r"hoan thanh", r"\btask\b"],
}

DAY_KEYWORDS = {
    "today":     [r"\bhom nay\b", r"\btoday\b"],
    "tomorrow":  [r"\bmai\b", r"\bngay mai\b", r"\btomorrow\b"],
    "day_after": [r"\bngay mot\b", r"\bmot\b", r"ngay kia"],
}

WEEKDAY_MAP = {
    "thu 2": 0, "thu hai": 0, "monday": 0, "mon": 0,
    "thu 3": 1, "thu ba": 1, "tuesday": 1, "tue": 1,
    "thu 4": 2, "thu tu": 2, "wednesday": 2, "wed": 2,
    "thu 5": 3, "thu nam": 3, "thursday": 3, "thu": 3,
    "thu 6": 4, "thu sau": 4, "friday": 4, "fri": 4,
    "thu 7": 5, "thu bay": 5, "saturday": 5, "sat": 5,
    "chu nhat": 6, "cn": 6, "sunday": 6, "sun": 6,
}


def _normalize(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower().strip()


def _parse_time(text: str) -> Optional[time]:
    t = _normalize(text)
    period = None
    if re.search(r"\b(sang|am|morning)\b", t):
        period = "am"
    elif re.search(r"\b(chieu|pm|afternoon)\b", t):
        period = "pm"
    elif re.search(r"\b(toi|dem|evening|night)\b", t):
        period = "pm"

    patterns = [
        r"(\d{1,2})\s*[h:]\s*(\d{1,2})\b",
        r"(\d{1,2})\s*gio\s*(\d{1,2})?\b",
        r"(\d{1,2})\s*[h:]\b",
        r"\b(\d{1,2})\s*(?:gio|h)\b",
    ]
    h, m = None, 0
    for pat in patterns:
        match = re.search(pat, t)
        if match:
            h = int(match.group(1))
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                try:
                    m = int(match.group(2))
                except (ValueError, IndexError):
                    m = 0
            break

    if h is None:
        return None
    if period == "pm" and h < 12:
        h += 12
    elif period == "am" and h == 12:
        h = 0
    if not (0 <= h <= 23) or not (0 <= m <= 59):
        return None
    return time(hour=h, minute=m)


def _parse_date(text: str, base_date: datetime = None):
    if base_date is None:
        base_date = datetime.now(TZ)
    t = _normalize(text)
    today = base_date.date()

    for kw, patterns in DAY_KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, t):
                if kw == "today":
                    return today
                if kw == "tomorrow":
                    return today + timedelta(days=1)
                if kw == "day_after":
                    return today + timedelta(days=2)

    for kw, weekday in WEEKDAY_MAP.items():
        if re.search(rf"\b{kw}\b", t):
            days_ahead = (weekday - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            return today + timedelta(days=days_ahead)

    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        if y < 100:
            y += 2000
        try:
            return datetime(y, mo, d).date()
        except ValueError:
            pass
    return today


def _parse_duration(text: str) -> Optional[int]:
    """Parse duration.
    CHI match khi co 'phut' hoac 'trong Xh' hoac 'keo dai Xh'.
    KHONG match '6h sang' (do la gio, khong phai duration).
    """
    t = _normalize(text)

    # "X phut" luon la duration
    m = re.search(r"(\d+)\s*phut", t)
    if m:
        return int(m.group(1))

    # "Xh Yphut" (co phut di kem) -> duration
    m = re.search(r"(\d+)\s*(?:h|gio)\s*(\d+)\s*phut", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))

    # "trong Xh" / "keo dai Xh" / "mat Xh" / "X tieng" -> duration
    m = re.search(r"(?:trong|keo dai|mat|khoang)\s+(\d+)\s*(?:h|gio|tieng)", t)
    if m:
        return int(m.group(1)) * 60

    # "X tieng" (khong phai 'Xh') -> duration
    m = re.search(r"(\d+)\s*tieng", t)
    if m:
        return int(m.group(1)) * 60

    return None


def _parse_distance(text: str) -> Optional[float]:
    t = _normalize(text)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*km\b", t)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m\b", t)
    if m:
        return float(m.group(1).replace(",", ".")) / 1000.0
    return None


def _detect_activity(text: str) -> str:
    t = _normalize(text)
    for activity, patterns in ACTIVITY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, t):
                return activity
    return "task"


def _extract_title(text: str) -> str:
    t = text.strip()
    if len(t) > 100:
        t = t[:100] + "..."
    return t


class ParsedEvent:
    """Ket qua parse."""
    _FIELDS = ("title", "event_type", "start_time", "end_time",
               "duration_min", "distance_km", "location", "raw")

    def __init__(self, **kw):
        for k in self._FIELDS:
            setattr(self, k, kw.get(k))
        self._source = kw.get("_source")

    def to_dict(self):
        d = {k: getattr(self, k) for k in self._FIELDS}
        d["_source"] = self._source
        if self.start_time:
            d["start_time"] = self.start_time.isoformat()
        if self.end_time:
            d["end_time"] = self.end_time.isoformat()
        return d

    def __repr__(self):
        return (f"ParsedEvent(type={self.event_type}, title={self.title!r}, "
                f"start={self.start_time}, dur={self.duration_min}min, "
                f"dist={self.distance_km}km)")


def _parse_relative_time(text: str, now: datetime):
    """Parse 'X phut nua', 'X gio nua', 'X tieng nua', 'X ngay nua'.
    Return datetime hoac None.
    """
    t = _normalize(text)

    # "X phut nua" / "X phut"
    m = re.search(r"(\d+)\s*phut\s*(?:nua)?", t)
    if m and "nua" in t:
        return now + timedelta(minutes=int(m.group(1)))

    # "X gio nua" / "X tieng nua"
    m = re.search(r"(\d+)\s*(?:gio|tieng|h)\s*nua", t)
    if m:
        return now + timedelta(hours=int(m.group(1)))

    # "X ngay nua"
    m = re.search(r"(\d+)\s*ngay\s*nua", t)
    if m:
        return now + timedelta(days=int(m.group(1)))

    return None


def parse_event(text: str, now: datetime = None) -> ParsedEvent:
    if now is None:
        now = datetime.now(TZ)

    event_type = _detect_activity(text)
    distance = _parse_distance(text)

    # UU TIEN 1: relative time ("15 phut nua")
    rel_dt = _parse_relative_time(text, now)
    if rel_dt is not None:
        duration = _parse_duration(text) or 60
        return ParsedEvent(
            title=_extract_title(text),
            event_type=event_type,
            start_time=rel_dt,
            end_time=rel_dt + timedelta(minutes=duration),
            duration_min=duration,
            distance_km=distance,
            location=None,
            raw=text,
            _source="regex_relative",
        )

    # UU TIEN 2: absolute time nhu cu
    date = _parse_date(text, now)
    t = _parse_time(text)
    duration = _parse_duration(text)

    if duration is None:
        duration = {"gym": 60, "run": 30, "bike": 45, "swim": 45, "yoga": 60,
                    "class": 90, "exam": 120, "meeting": 60,
                    "study": 60, "task": 60}.get(event_type, 60)

    if t is None:
        t = {"gym": time(19, 0), "run": time(6, 0), "bike": time(6, 30),
             "swim": time(7, 0), "yoga": time(6, 30),
             "class": time(8, 0), "exam": time(8, 0),
             "meeting": time(20, 0), "study": time(20, 0),
             "task": time(9, 0)}.get(event_type, time(9, 0))

    start_dt = TZ.localize(datetime.combine(date, t))
    end_dt = start_dt + timedelta(minutes=duration)

    return ParsedEvent(
        title=_extract_title(text),
        event_type=event_type,
        start_time=start_dt,
        end_time=end_dt,
        duration_min=duration,
        distance_km=distance,
        location=None,
        raw=text,
        _source="regex",
    )


if __name__ == "__main__":
    tests = [
        "mai 6h sang chay bo 5km",
        "toi nay gym 7h",
        "3h chieu thu 4 hop nhom",
        "30 phut nua hoc calculus",
        "sang mai 6h30 dap xe 10km",
        "chu nhat 8h thi toan roi rac",
    ]
    print("=" * 70)
    print("NL PARSER TEST")
    print("=" * 70)
    for txt in tests:
        ev = parse_event(txt)
        print(f"\n📝 {txt}")
        print(f"   -> type={ev.event_type} | title={ev.title!r}")
        print(f"   -> start={ev.start_time.strftime('%a %d/%m %H:%M')}")
        print(f"   -> dur={ev.duration_min}min | dist={ev.distance_km}km")