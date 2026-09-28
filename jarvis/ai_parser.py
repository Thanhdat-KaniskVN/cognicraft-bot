# jarvis/ai_parser.py
"""Hybrid parser: Regex -> AI fallback. Tich hop san token optimization."""
import json
from datetime import datetime, timedelta
import pytz

from jarvis.nl_parser import parse_event, ParsedEvent, TZ
from ai_provider import call_ai_json

REGEX_MIN_LEN = 8


def _regex_looks_good(ev, text: str) -> bool:
    """Tra True neu regex ket qua dang tin."""
    if ev is None or ev.start_time is None:
        return False
    if len(text.strip()) < REGEX_MIN_LEN:
        return False

    norm = text.lower()

    # --- Force AI khi cau co pattern phuc tap ---
    force_ai_patterns = [
        r"\bsau khi\b",       # "sau khi an trua..."
        r"\bkhi nao\b",       # "khi nao ranh..."
        r"\bneu\b",           # dieu kien
        r"\bco the\b",
        r"\bco le\b",
        r"\bhen\b",           # "hen ban..."
        r"\bcafe\b",          # activity khong ro type
        r"\bdi choi\b",
        r"\bdi an\b",
        r"\bgap\b",           # "gap ban"
    ]
    import re
    for pat in force_ai_patterns:
        if re.search(pat, norm):
            return False

    # --- Duration bat thuong (> 3h) -> suspect ---
    if ev.duration_min and ev.duration_min > 180:
        # 6h30 co the la 6h30p hoac 6h30' (sai) -> suspect
        return False

    # --- Hour default 9h nhung cau co so > 12 -> co the miss PM ---
    if ev.start_time.hour == 9 and re.search(r"\b(1[3-9]|2[0-3])\b", norm):
        return False

    # --- Cau co 'sang' nhung start = 7h cho swim (default) -> suspect ---
    if ev.event_type == "swim" and ev.start_time.hour == 7:
        if re.search(r"\b(chieu|toi|trua|sau)\b", norm):
            return False

    if len(norm.split()) < 2:
        return False
    return True


def _ai_parse(text: str, now: datetime = None) -> ParsedEvent:
    if now is None:
        now = datetime.now(TZ)
    today_str = now.strftime("%A, %d/%m/%Y")

    prompt = f"""Ban la AI parse lich tieng Viet. Doc cau tieng Viet tu nhien, tra ve JSON.

**Bay gio:** {today_str}, {now.strftime('%H:%M')}
**Cau:** "{text}"

**Tra ve JSON** (KHONG markdown):
{{
  "event_type": "gym|run|bike|swim|yoga|class|exam|meeting|study|task|other",
  "title": "tieu de ngan (khong qua 60 ky tu)",
  "date_offset": <so ngay tu hom nay>,
  "hour": <0-23>,
  "minute": <0-59>,
  "duration_min": <so phut, mac dinh 60>,
  "distance_km": <so km hoac null>,
  "location": "dia diem hoac null"
}}

Chi tra ve JSON."""

    try:
        result = call_ai_json(prompt, task_type="jarvis_parse")

        offset = int(result.get("date_offset", 0))
        hour = max(0, min(23, int(result.get("hour", 9))))
        minute = max(0, min(59, int(result.get("minute", 0))))
        duration = max(5, min(600, int(result.get("duration_min", 60))))

        date = (now + timedelta(days=offset)).date()
        start_dt = TZ.localize(
            datetime.combine(date, datetime.min.time().replace(hour=hour, minute=minute))
        )
        end_dt = start_dt + timedelta(minutes=duration)

        return ParsedEvent(
            title=(result.get("title") or text)[:100],
            event_type=result.get("event_type", "task"),
            start_time=start_dt,
            end_time=end_dt,
            duration_min=duration,
            distance_km=result.get("distance_km"),
            location=result.get("location"),
            raw=text,
            _source="ai",
        )
    except Exception as e:
        print(f"[AIParser] AI error: {e}")
        return None


def parse_event_smart(text: str, now: datetime = None,
                      force_ai: bool = False) -> ParsedEvent:
    """Hybrid: regex (fast) -> AI fallback."""
    if not text or not text.strip():
        return None

    if not force_ai:
        try:
            ev = parse_event(text, now)
            if _regex_looks_good(ev, text):
                ev._source = "regex"
                return ev
            print(f"[AIParser] Regex low-conf -> AI: {text!r}")
        except Exception as e:
            print(f"[AIParser] Regex exc: {e}")

    ev = _ai_parse(text, now)
    if ev is not None:
        return ev

    print("[AIParser] AI failed -> regex last resort")
    try:
        ev = parse_event(text, now)
        ev._source = "regex_fallback"
        return ev
    except Exception as e:
        print(f"[AIParser] Total fail: {e}")
        return None


async def parse_event_smart_async(text: str, now: datetime = None,
                                   force_ai: bool = False) -> ParsedEvent:
    import asyncio
    return await asyncio.to_thread(parse_event_smart, text, now, force_ai)


if __name__ == "__main__":
    tests = [
        "mai 6h sang chay bo 5km",
        "toi nay gym 7h",
        "3h chieu thu 4 hop nhom",
        "sang mai 6h30 dap xe 10km",
        "sau khi an trua xong di boi 30 phut",
        "khi nao ranh thi on lai bai induction",
        "hen ban 3h chieu mai cafe o quan quen",
    ]
    print("=" * 70)
    print("AI PARSER TEST (hybrid)")
    print("=" * 70)
    for txt in tests:
        ev = parse_event_smart(txt)
        if ev is None:
            print(f"\n📝 {txt}\n   FAILED")
            continue
        src = getattr(ev, "_source", "?")
        print(f"\n📝 {txt}")
        print(f"   [{src}] type={ev.event_type} | {ev.title!r}")
        print(f"   start={ev.start_time.strftime('%a %d/%m %H:%M')} | dur={ev.duration_min}min | dist={ev.distance_km}km")

    print("\n" + "=" * 70)
    print("TOKEN STATS")
    print("=" * 70)
    try:
        from ai_provider import get_token_stats
        s = get_token_stats()
        print(f"  Requests: {s['requests_used']}")
        print(f"  Tokens: {s['tokens_used']:,}")
        print(f"  By task: {s.get('requests_by_task', {})}")
    except Exception as e:
        print(f"  [skip] {e}")