# jarvis/advisor.py
"""JARVIS Advisor - analyze context + decide actions with AI advice."""
from datetime import datetime, timedelta
import pytz

from jarvis.context_analyzer import detect_context
from jarvis.priority_scorer import score_event, classify
from jarvis import event_manager as em
from jarvis.ai_advisor import generate_advice_ai

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

ADVICE = {
    "accident": "Uu tien suc khoe! Di cap cuu ngay. Huy toan bo event hom nay.",
    "sick_heavy": "Om nang! Nghi ngoi hoan toan. Doi het events 1-2 ngay.",
    "sick": "Om nhe. Nghi tap luyen, giu lai hoc/hop quan trong. Uong thuoc + ngu du.",
    "tired": "Met moi. Bo hoat dong the chat, giu viec quan trong. Nghi 1-2h.",
    "urgent": "Co viec gap. Doi hoat dong linh hoat, giu nguyen lich co dinh.",
    "family": "Viec gia dinh. Uu tien gia dinh, doi cac event khong quan trong.",
}

PHYSICAL_TYPES = {"run", "gym", "bike", "swim", "yoga"}
REST_REQUIRED = {"sick", "sick_heavy", "accident", "tired"}
CRITICAL_REST = {"sick_heavy", "accident"}

ACTION_ICON = {"keep": "OK", "reschedule": "MOVE", "cancel": "DEL", "skip": "SKIP"}


def _ai_advice(ctx_type, severity, actions, text):
    """Wrapper - tra ve (advice, tip, resch, source)."""
    try:
        r = generate_advice_ai(ctx_type, severity, actions, user_context_text=text)
        if r:
            return (
                r.get("advice", ""),
                r.get("tip", ""),
                r.get("reschedule_suggestion", ""),
                "ai",
            )
    except Exception as e:
        print(f"[Advisor] AI advice err: {e}")
    return (ADVICE.get(ctx_type, ""), "", "", "rule")


def analyze(user_id, text, now=None):
    """Main entry. Return dict {context, actions, advice, tip} or None."""
    if now is None:
        now = datetime.now(TZ)

    ctx = detect_context(text)
    if not ctx:
        return None

    severity = ctx.severity
    events = em.list_events(user_id=user_id, days_ahead=3)

    if not events:
        advice, tip, resch, src = _ai_advice(ctx.context_type, severity, [], text)
        return {
            "context": ctx.to_dict(),
            "severity": severity,
            "actions": [],
            "advice": advice,
            "tip": tip,
            "reschedule_suggestion": resch,
            "advice_source": src,
            "note": "Khong co event nao sap toi",
            "stats": {"total": 0, "keep": 0, "reschedule": 0, "cancel": 0},
        }

    actions = []
    for ev in events:
        score, reasons = score_event(ev, now)
        action = classify(score, severity)

        # FIX: Physical activity khi om/met -> force cancel/reschedule
        if ctx.context_type in REST_REQUIRED and ev["event_type"] in PHYSICAL_TYPES:
            if ctx.context_type in CRITICAL_REST:
                action = "cancel"
                reasons.append(f"physical + {ctx.context_type} -> FORCE CANCEL")
            else:
                action = "reschedule"
                reasons.append(f"physical + {ctx.context_type} -> FORCE RESCHEDULE")

        # Exam/class/meeting khong duoc cancel
        if action == "cancel" and ev["event_type"] in ("exam", "class", "meeting"):
            action = "reschedule"
            reasons.append("exam/class/meeting -> downgrade to reschedule")

        actions.append({
            "event": ev,
            "score": score,
            "reasons": reasons,
            "action": action,
        })

    order = {"cancel": 0, "reschedule": 1, "keep": 2}
    actions.sort(key=lambda a: (order[a["action"]], a["score"]))

    advice, tip, resch, src = _ai_advice(ctx.context_type, severity, actions, text)

    return {
        "context": ctx.to_dict(),
        "severity": severity,
        "actions": actions,
        "advice": advice,
        "tip": tip,
        "reschedule_suggestion": resch,
        "advice_source": src,
        "stats": {
            "total": len(actions),
            "keep": sum(1 for a in actions if a["action"] == "keep"),
            "reschedule": sum(1 for a in actions if a["action"] == "reschedule"),
            "cancel": sum(1 for a in actions if a["action"] == "cancel"),
        },
    }


def apply_actions(user_id, actions, dry_run=True):
    """Apply cancel actions. dry_run=True: chi tra ve plan."""
    applied = []
    for a in actions:
        ev_id = a["event"]["id"]
        if a["action"] == "cancel":
            if not dry_run:
                em.cancel_event(ev_id)
            applied.append((ev_id, "cancelled"))
    return applied


if __name__ == "__main__":
    import sys, os, json
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    TEST_UID = "test_advisor_999"
    # Setup fake events
    for ev in em.list_events(user_id=TEST_UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])
    now = datetime.now(TZ)
    for title, etype, dt in [
        ("Chay bo 5km", "run", now + timedelta(hours=2)),
        ("Gym", "gym", now + timedelta(hours=6)),
        ("Thi giua ki Toan", "exam", now + timedelta(hours=8)),
        ("Hop nhom quan trong", "meeting", now + timedelta(hours=3)),
    ]:
        em.create_event(TEST_UID, "TestUser", title, etype, dt)
    print("=" * 70)
    print("ADVISOR TEST (with AI advice)")
    print("=" * 70)
    r = analyze(TEST_UID, "toi om roi")
    if not r:
        print("FAIL: analyze returned None")
    else:
        print(f"Context:    {r['context']['context_type']} / {r['severity']}")
        print(f"Source:     {r['advice_source']}")
        print(f"Advice:     {r['advice'][:150]}...")
        print(f"Tip:        {r['tip'][:100]}")
        print(f"Reschedule: {r['reschedule_suggestion']}")
        print(f"Stats:      {r['stats']}")
        print("\nActions:")
        for a in r["actions"]:
            print(f"  [{a['action']:10s}] score={a['score']:2d} | {a['event']['title']}")