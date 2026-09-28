# jarvis/ai_advisor.py
"""AI Advisor - Gemini powered advice. Cache + fallback."""
import hashlib
import json
from datetime import datetime

from ai_provider import call_ai_json


# Cache in-memory (rate limit friendly)
_ADVICE_CACHE = {}


def _cache_key(context_type, severity, event_types):
    key = f"{context_type}|{severity}|{','.join(sorted(event_types))}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def _format_event_summary(actions):
    lines = []
    for a in actions:
        ev = a["event"]
        start = ev.get("start_time")
        time_str = ""
        if start:
            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start)
                except Exception:
                    pass
            if hasattr(start, "strftime"):
                time_str = start.strftime("%a %H:%M")
        lines.append(
            f"- [{a['action'].upper()}] {ev['title']} ({ev['event_type']}) "
            f"@ {time_str} | score={a['score']}"
        )
    return "\n".join(lines)


def generate_advice_ai(context_type, severity, actions, user_context_text=""):
    """Goi Gemini de tao advice ca nhan hoa.
    Fallback None neu fail (caller dung hardcoded).
    """
    if not actions:
        return None

    event_types = [a["event"]["event_type"] for a in actions]
    key = _cache_key(context_type, severity, event_types)

    if key in _ADVICE_CACHE:
        print(f"[AIAdvisor] cache HIT {key}")
        return _ADVICE_CACHE[key]

    summary = _format_event_summary(actions)
    n_keep = sum(1 for a in actions if a["action"] == "keep")
    n_move = sum(1 for a in actions if a["action"] == "reschedule")
    n_cancel = sum(1 for a in actions if a["action"] == "cancel")

    prompt = f"""Ban la coach ca nhan cho sinh vien. User vua noi: "{user_context_text}"

Tinh trang: {context_type} (severity: {severity})

Danh sach events sap toi va quyet dinh so bo:
{summary}

Tom tat: {n_keep} giu, {n_move} doi, {n_cancel} huy.

Hay viet loi khuyen NGAN GON (2-4 cau, < 80 tu) bang tieng Viet KHONG DAU:
1. Xac nhan tinh trang user (dong cam ngan)
2. Cai gi PHAI HUY va TAI SAO (1 cau)
3. Cai gi CO THE DOI + GOI Y thoi diem moi (1 cau, cu the gio)
4. Cai gi GIU va LY DO (1 cau)
5. Loi dong vien cuoi (1 cau)

Tra ve JSON:
{{
  "advice": "<loi khuyen day du>",
  "tip": "<1 meo cu the de hoi phuc/on dinh>",
  "reschedule_suggestion": "<gio moi goi y cho cac event MOVE, vd: chieu mai 15h>"
}}

Chi tra ve JSON."""

    try:
        result = call_ai_json(prompt, task_type="jarvis_advice")
        advice = result.get("advice", "").strip()
        tip = result.get("tip", "").strip()
        resch = result.get("reschedule_suggestion", "").strip()

        if not advice:
            print("[AIAdvisor] empty advice from AI")
            return None

        out = {
            "advice": advice,
            "tip": tip,
            "reschedule_suggestion": resch,
            "_source": "ai",
        }
        _ADVICE_CACHE[key] = out
        print(f"[AIAdvisor] cached {key}")
        return out

    except Exception as e:
        print(f"[AIAdvisor] AI error: {e}")
        return None


async def generate_advice_ai_async(*args, **kwargs):
    import asyncio
    return await asyncio.to_thread(generate_advice_ai, *args, **kwargs)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from datetime import datetime, timedelta
    import pytz
    TZ = pytz.timezone("Asia/Ho_Chi_Minh")
    now = datetime.now(TZ)

    fake_actions = [
        {"event": {"title": "Chay bo 5km", "event_type": "run", "start_time": now + timedelta(hours=2)}, "score": 4, "action": "cancel"},
        {"event": {"title": "Gym", "event_type": "gym", "start_time": now + timedelta(hours=6)}, "score": 4, "action": "reschedule"},
        {"event": {"title": "Thi giua ki Toan", "event_type": "exam", "start_time": now + timedelta(hours=8)}, "score": 15, "action": "keep"},
        {"event": {"title": "Hop nhom quan trong", "event_type": "meeting", "start_time": now + timedelta(hours=3)}, "score": 14, "action": "keep"},
    ]

    print("=" * 70)
    print("AI ADVISOR TEST")
    print("=" * 70)
    r = generate_advice_ai("sick", "high", fake_actions, "toi om roi")
    print(json.dumps(r, ensure_ascii=False, indent=2))

    print("\n--- Cache test (2nd call should hit) ---")
    r2 = generate_advice_ai("sick", "high", fake_actions, "toi om roi")
    print(f"Same object: {r is r2}")