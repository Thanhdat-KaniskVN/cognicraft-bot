# jarvis/multi_parser.py
"""Multi-event parser v5 - normalize-first, pure ASCII."""
import re
import os
from datetime import datetime, timedelta, time
import pytz
from jarvis.nl_parser import parse_event, _normalize, TZ

DEBUG = os.getenv("JARVIS_DEBUG", "").strip() == "1"


def _dbg(msg):
    if DEBUG:
        print(f"[MultiParser] {msg}")


SPLIT_PATTERNS = [
    r"\s*,\s*(?:roi)\s+",
    r"\s*,\s*(?:va)\s+",
    r"\s+(?:roi)\s+",
    r"\s+(?:va)\s+",
    r"\s+(?:sau khi|sau do)\s+",
    r"\s+(?:tiep theo)\s+",
    r"\s+xong\s+(?:thi\s+)?",
    r"\s+(?:cung)\s+",
]

COMMA_SPLIT = re.compile(
    r",\s*(?=\d|\b(?:hoc|di|tap|chay|an|lam|ngu|toi|sang|chieu|trua|dem)\b)"
)

RANGE_PATTERN = re.compile(
    r"(\d{1,2})(?:[h:](\d{1,2})?)?\s*(?:-|->|den|toi)\s*(\d{1,2})(?:[h:](\d{1,2})?)?",
    re.IGNORECASE,
)
MAX_EVENT_HOURS = 12

DAY_KW = ["sang mai", "chieu mai", "toi mai", "trua mai", "ngay mai",
          "thu 2", "thu 3", "thu 4", "thu 5", "thu 6", "thu 7", "chu nhat",
          "hom nay"]
PERIOD_KW = ["sang", "chieu", "toi", "trua", "dem"]


def _kw(txt, kw):
    return bool(re.search(rf"\b{re.escape(kw)}\b", txt))


def _extract_global_context(norm):
    day = None
    period = None
    for kw in ["sang mai", "chieu mai", "toi mai", "trua mai", "ngay mai"]:
        if _kw(norm, kw):
            day = "mai"
            break
    if not day:
        for kw in ["thu 2", "thu 3", "thu 4", "thu 5", "thu 6", "thu 7", "chu nhat"]:
            if _kw(norm, kw):
                day = kw
                break
    if not day:
        if _kw(norm, "hom nay"):
            day = "hom nay"
        elif re.search(r"\bmai\b", norm):
            day = "mai"
    for kw in PERIOD_KW:
        if _kw(norm, kw):
            period = kw
            break
    _dbg(f"context: day={day!r} period={period!r}")
    return day, period


def _has_day(norm):
    for kw in DAY_KW + ["ngay"]:
        if _kw(norm, kw):
            return True
    if re.search(r"\bmai\b", norm):
        return True
    return False


def _has_period(norm):
    for kw in PERIOD_KW:
        if _kw(norm, kw):
            return True
    return False


def _has_ambiguous_hour(norm):
    return bool(re.search(r"\b([1-9]|1[0-2])\s*(?:[h:]|gio|h)\b", norm))


def _split_events(norm):
    parts = [norm]
    for pat in SPLIT_PATTERNS:
        new_parts = []
        for p in parts:
            sub = re.split(pat, p)
            new_parts.extend([s.strip() for s in sub if s and s.strip()])
        parts = new_parts
    new_parts = []
    for p in parts:
        sub = COMMA_SPLIT.split(p)
        new_parts.extend([s.strip() for s in sub if s and s.strip()])
    parts = new_parts
    _dbg(f"split -> {len(parts)} parts")
    return parts


def _apply_context(norm_parts):
    if not norm_parts:
        return norm_parts
    gday, gperiod = _extract_global_context(norm_parts[0])
    result = []
    for i, p in enumerate(norm_parts):
        prefix = []
        if not _has_day(p) and gday:
            prefix.append(gday)
        if not _has_period(p) and gperiod and _has_ambiguous_hour(p):
            prefix.append(gperiod)
        if prefix:
            new_p = " ".join(prefix) + " " + p
            _dbg(f"  part[{i}]: {p!r} -> {new_p!r}")
            p = new_p
        result.append(p)
    return result


def parse_time_range(text: str):
    t = _normalize(text)
    m = RANGE_PATTERN.search(t)
    if not m:
        return None

    h1 = int(m.group(1))
    m1 = int(m.group(2)) if m.group(2) else 0
    h2_raw = int(m.group(3))
    m2 = int(m.group(4)) if m.group(4) else 0

    period = None
    if re.search(r"\b(chieu|pm|afternoon)\b", t):
        period = "pm"
    elif re.search(r"\b(toi|dem|evening|night)\b", t):
        period = "pm"
    elif re.search(r"\b(sang|am|morning)\b", t):
        period = "am"

    # Cross-midnight chi khi h1 >= 20 (buoi toi muon -> qua ngay)
    cross_midnight = (h1 > h2_raw) and (h1 >= 20)

    # Apply period cho h2
    h2 = h2_raw
    if not cross_midnight:
        if period == "pm" and h2 < 12:
            h2 += 12
        elif period == "am" and h2 == 12:
            h2 = 0

    # Neu period=pm va duration > 12h -> thu adjust h1 += 12 (vd "3h-5h chieu")
    if period == "pm" and h1 < 12 and not cross_midnight:
        dur_test = h2 - h1
        if dur_test < 0:
            dur_test += 24
        if dur_test > MAX_EVENT_HOURS:
            h1_alt = h1 + 12
            dur_alt = h2 - h1_alt
            if dur_alt < 0:
                dur_alt += 24
            if 0 <= dur_alt <= MAX_EVENT_HOURS:
                h1 = h1_alt

    if not (0 <= h1 <= 23 and 0 <= h2 <= 23):
        return None

    dur_h = h2 - h1
    if dur_h < 0:
        dur_h += 24
    if dur_h > MAX_EVENT_HOURS:
        return None

    return time(h1, m1), time(h2, m2)


def _clean_title(norm):
    t = norm.strip()
    for _ in range(4):
        before = t
        t = re.sub(r"^(?:sang|chieu|toi|trua|dem)\s+", "", t)
        t = re.sub(r"^(?:hom nay|ngay mai)\s+", "", t)
        t = re.sub(r"^(?:mai|nay)\s+", "", t)
        t = re.sub(r"^(?:thu\s+\d|chu nhat)\s+", "", t)
        t = t.strip().lstrip(",.;:")
        if t == before:
            break
    return t.strip().rstrip(",.;:").strip()


def parse_multi_events(text, now=None):
    if now is None:
        now = datetime.now(TZ)
    if not text or not text.strip():
        return []
    norm = _normalize(text)
    _dbg(f"\n>>> PARSE: {text!r}")
    _dbg(f"    norm: {norm!r}")
    parts_norm = _split_events(norm)
    parts_norm = _apply_context(parts_norm)
    events = []
    for pn in parts_norm:
        ev = parse_event(pn, now)
        if ev is None or ev.start_time is None:
            _dbg(f"  SKIP: {pn!r}")
            continue
        rng = parse_time_range(pn)
        if rng:
            st, et = rng
            date = ev.start_time.date()
            start_dt = TZ.localize(datetime.combine(date, st))
            end_dt = TZ.localize(datetime.combine(date, et))
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            ev.start_time = start_dt
            ev.end_time = end_dt
            ev.duration_min = int((end_dt - start_dt).total_seconds() / 60)
        ev.title = _clean_title(ev.title) or pn
        ev._source = "multi"
        events.append(ev)
    return events


if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    tests = [
        "s\u00e1ng mai ch\u1ea1y b\u1ed9 5h s\u00e1ng r\u1ed3i h\u1ecdc m\u00f4n adp 7h30-1h chi\u1ec1u, v\u00e0 t\u1eadp gym 5h chi\u1ec1u",
        "t\u1ed1i nay gym 7h v\u00e0 h\u1ecdc b\u00e0i 9h",
        "th\u1ee9 4 h\u1ecdp nh\u00f3m 3h chi\u1ec1u, sau \u0111\u00f3 h\u1ecdc calculus 7h t\u1ed1i",
        "mai 6h ch\u1ea1y b\u1ed9 5km",
        "s\u00e1ng mai 6h ch\u1ea1y b\u1ed9, 8h \u0111i h\u1ecdc, 5h chi\u1ec1u gym",
        "chi\u1ec1u nay 3h h\u1ecdc python, 5h ch\u1ea1y b\u1ed9, t\u1ed1i 8h \u00f4n b\u00e0i",
    ]
    print("=" * 70)
    print("MULTI-PARSER TEST v5")
    print("=" * 70)
    for txt in tests:
        print(f"\n>>> {txt}")
        events = parse_multi_events(txt)
        print(f"    -> {len(events)} events")
        for i, ev in enumerate(events, 1):
            print(f"      [{i}] {ev.event_type:8s} | {ev.title[:55]!r}")
            print(f"          {ev.start_time.strftime('%a %d/%m %H:%M')} -> {ev.end_time.strftime('%H:%M')} ({ev.duration_min}min)")