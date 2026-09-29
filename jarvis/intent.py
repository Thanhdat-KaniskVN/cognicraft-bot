# jarvis/intent.py
"""Intent classifier - phan loai tin nhan user (regex + AI fallback)."""
import re
import unicodedata
from typing import Optional
import json


def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("\u0111", "d").replace("\u0110", "D").lower().strip()


# Schedule keywords (co the la lenh add event)
SCHEDULE_VERBS = [
    r"\b(them|dat|len lich|schedule|book|tao)\b",
    r"\b(nhac|remind|bao|thong bao)\b",
]

TIME_HINTS = [
    r"\b\d{1,2}\s*(?:h|gio|:)\d{0,2}\b",           # 6h, 6h30, 6:30
    r"\b\d{1,2}\s*phut\s*(?:nua)?\b",                # 15 phut nua
    r"\b\d{1,2}\s*(?:tieng|gio)\s*nua\b",            # 2 tieng nua
    r"\b(hom nay|mai|ngay mai|toi nay|sang mai|chieu mai|toi mai|trua mai)\b",
    r"\b(thu\s*[2-7]|chu nhat)\b",
]

ACTIVITY_HINTS = [
    r"\b(chay bo|tap gym|gym|dap xe|boi|yoga|di hoc|hoc|hop|thi|on bai|lam bai|doc sach|ca phe|cafe|hop nhom|hop team)\b",
]

CONTEXT_HINTS = [
    r"\b(om|benh|sot|dau|met|met moi|kiet suc)\b",
    r"\b(te xe|tai nan|gay tay|gay chan)\b",
    r"\b(co viec|viec gap|dot xuat|khan cap)\b",
    r"\b(gia dinh|me om|bo om|nguoi than)\b",
]

CHAT_HINTS = [
    r"\b(la gi|nhu the nao|tai sao|the nao)\b",   # cau hoi kien thuc
    r"^\s*(xin chao|chao|hello|hi|hey)\b",
    r"^\s*(cam on|thank|thanks|cam on ban|cam on em)\b",
    r"^\s*(ban la ai|bot la gi|help giup)\b",
    r"\b(ban nghi sao|the nao|lam gi bay gio|co nen)\b",
]

QUERY_HINTS = [
    r"\b(hom nay|mai|tuan nay|chieu nay|toi nay|sang nay|trua nay)\b.*\b(co gi|lam gi|nen lam|the nao|co khong)\b",
    r"\b(xem|list|liet ke|check)\b.*\b(lich|schedule|event)\b",
    r"\b(con bao nhieu|co may)\s+(?:task|event|viec)\b",
]


def _match_any(text_norm: str, patterns: list) -> bool:
    for p in patterns:
        if re.search(p, text_norm):
            return True
    return False


AI_INTENTS = ["schedule", "context", "chat", "query", "ignore"]

_AI_CACHE = {}  # simple in-memory cache


def _ai_classify(text: str) -> dict:
    """Fallback - goi Gemini khi regex khong chac chan."""
    cache_key = text.strip().lower()
    if cache_key in _AI_CACHE:
        return _AI_CACHE[cache_key]

    try:
        from ai_provider import call_ai_json
    except ImportError:
        return {"intent": "ignore", "confidence": 0.0, "reason": "no_ai"}

    prompt = f"""Ban la AI classify tin nhan Discord cua user cho app lich JARVIS.

**Tin nhan:** "{text}"

**Tra ve JSON** (KHONG markdown):
{{
  "intent": "schedule|context|chat|query|ignore",
  "confidence": 0.0-1.0
}}

**Dinh nghia:**
- schedule: them event vao lich (co gio/activity cu the). VD: "mai 6h chay bo", "2h nua hop nhom"
- context: user bao tinh trang (om, met, te xe, co viec). VD: "toi om roi", "met qua"
- query: hoi thong tin lich. VD: "hom nay co gi", "mai lam gi", "xem lich"
- chat: chao hoi / cam on / cau hoi kien thuc. VD: "xin chao", "cam on", "python la gi"
- ignore: khong lien quan. VD: "ok", "lol", "haha"

Chi tra ve JSON."""

    try:
        result = call_ai_json(prompt, task_type="jarvis_intent")
        intent = result.get("intent", "ignore")
        if intent not in AI_INTENTS:
            intent = "ignore"
        conf = float(result.get("confidence", 0.7))
        out = {"intent": intent, "confidence": conf, "reason": "ai_fallback"}
        _AI_CACHE[cache_key] = out
        return out
    except Exception as e:
        print(f"[Intent] AI fallback err: {e}")
        return {"intent": "ignore", "confidence": 0.5, "reason": "ai_error"}


def classify(text: str) -> dict:
    """Classify intent.

    Returns:
        {
            "intent": "schedule" | "context" | "chat" | "query" | "ignore",
            "confidence": 0.0-1.0,
            "reason": str,
        }
    """
    if not text or len(text.strip()) < 3:
        return {"intent": "ignore", "confidence": 1.0, "reason": "too_short"}

    n = _norm(text)

    # Query check TRUOC (tranh "hom nay co gi" -> schedule)
    if _match_any(n, QUERY_HINTS):
        return {"intent": "query", "confidence": 0.85, "reason": "query_hint"}

    # Schedule verbs -> high confidence
    if _match_any(n, SCHEDULE_VERBS):
        return {"intent": "schedule", "confidence": 0.95, "reason": "schedule_verb"}

    # Context + time/activity
    has_context = _match_any(n, CONTEXT_HINTS)
    has_time = _match_any(n, TIME_HINTS)
    has_activity = _match_any(n, ACTIVITY_HINTS)

    # Context alone -> context (vd: "toi om roi")
    if has_context:
        return {"intent": "context", "confidence": 0.9, "reason": "context_match"}

    if has_time and has_activity:
        return {"intent": "schedule", "confidence": 0.85, "reason": "time+activity"}

    if has_time and len(n.split()) >= 3:
        return {"intent": "schedule", "confidence": 0.7, "reason": "time_only"}

    # Chat
    if _match_any(n, CHAT_HINTS):
        return {"intent": "chat", "confidence": 0.75, "reason": "chat_hint"}

    # LOW CONFIDENCE -> AI fallback
    # Truong hop khong co hint nao -> thu AI
    try:
        from ai_provider import call_ai_json  # noqa
        return _ai_classify(text)
    except ImportError:
        pass

    # Fallback cuoi
    return {"intent": "ignore", "confidence": 0.5, "reason": "no_match"}


if __name__ == "__main__":
    tests = [
        "mai 6h chay bo",
        "toi nay gym 7h va hoc bai 9h",
        "them su kien hop nhom 3h chieu",
        "nhac toi 15 phut nua uong nuoc",
        "toi om roi",
        "met moi qua",
        "te xe roi",
        "co viec gap",
        "xin chao",
        "cam on em",
        "hom nay co gi",
        "xem lich tuan nay",
        "ban nghi sao ve python",
        "ok",
        "lol",
        "hello world",
        "python la gi",
        "3h chieu hop nhom",
    ]
    print("=" * 70)
    print("INTENT CLASSIFIER TEST")
    print("=" * 70)
    for t in tests:
        r = classify(t)
        print(f"  {t!r:45s} -> {r['intent']:10s} ({r['confidence']:.2f}) [{r['reason']}]")