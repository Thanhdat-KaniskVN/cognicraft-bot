# jarvis/test_advisor.py
"""20 test cases cho JARVIS Advisor."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pytz
from jarvis.context_analyzer import detect_context
from jarvis.priority_scorer import score_event, classify
from jarvis.advisor import analyze
from jarvis import event_manager as em

TZ = pytz.timezone("Asia/Ho_Chi_Minh")
TEST_USER = "test_advisor_999"


def setup_events():
    for ev in em.list_events(user_id=TEST_USER, days_ahead=365, status=None):
        em.delete_event(ev["id"])
    now = datetime.now(TZ)
    events = [
        ("Chay bo 5km", "run", now + timedelta(hours=2)),
        ("Gym buoi toi", "gym", now + timedelta(hours=6)),
        ("Hoc mon ADP", "class", now + timedelta(hours=4)),
        ("Hop nhom quan trong", "meeting", now + timedelta(hours=3)),
        ("Thi giua ki Toan", "exam", now + timedelta(hours=8)),
        ("On bai induction", "study", now + timedelta(hours=10)),
        ("Dap xe 10km", "bike", now + timedelta(hours=24)),
        ("Boi 30 phut", "swim", now + timedelta(hours=30)),
    ]
    created = []
    for title, etype, start in events:
        eid = em.create_event(TEST_USER, "TestUser", title, etype, start)
        if eid:
            created.append(eid)
    return created


TEST_CASES = [
    ("toi om roi", "sick", "high"),
    ("em bi sot cao qua", "sick_heavy", "high"),
    ("te xe roi dau qua", "accident", "critical"),
    ("met moi qua khong lam gi duoc", "tired", "medium"),
    ("co viec gap dot xuat", "urgent", "high"),
    ("gia dinh co chuyen", "family", "high"),
    ("toi bi benh", "sick", "high"),
    ("nhap vien roi", "sick_heavy", "high"),
    ("tai nan giao thong", "accident", "critical"),
    ("kiet suc roi", "tired", "medium"),
    ("viec gap", "urgent", "high"),
    ("me om", "family", "high"),
    ("dau dau qua", "sick", "high"),
    ("cap cuu", "sick_heavy", "high"),
    ("gay tay roi", "accident", "critical"),
    ("buon ngu qua", "tired", "medium"),
    ("khan cap", "urgent", "high"),
    ("nguoi than om", "family", "high"),
    ("ho va sot", "sick", "high"),
    ("met", "tired", "medium"),
]


def test_context_detection():
    print("=" * 70)
    print("TEST 1-20: Context detection")
    print("=" * 70)
    passed = 0
    for i, (text, exp_ctx, exp_sev) in enumerate(TEST_CASES, 1):
        ctx = detect_context(text)
        ok = ctx and ctx.context_type == exp_ctx and ctx.severity == exp_sev
        mark = "PASS" if ok else "FAIL"
        got = f"{ctx.context_type}/{ctx.severity}" if ctx else "None"
        print(f"  [{i:2d}] [{mark}] {text[:40]:42s} -> {got:20s} (exp {exp_ctx}/{exp_sev})")
        if ok:
            passed += 1
    print(f"\n  Result: {passed}/{len(TEST_CASES)} passed")
    return passed


def test_priority_scoring():
    print("\n" + "=" * 70)
    print("BONUS: Priority scoring")
    print("=" * 70)
    now = datetime.now(TZ)
    fake_events = [
        {"title": "Thi giua ki", "event_type": "exam", "start_time": now + timedelta(hours=1)},
        {"title": "Gym", "event_type": "gym", "start_time": now + timedelta(hours=5)},
        {"title": "Hop nhom quan trong", "event_type": "meeting", "start_time": now + timedelta(hours=3)},
        {"title": "Chay bo", "event_type": "run", "start_time": now + timedelta(hours=20)},
    ]
    for ev in fake_events:
        s, r = score_event(ev, now)
        print(f"  {ev['title']:25s} ({ev['event_type']:8s}) -> score={s:2d} | {r}")


def test_full_analysis():
    print("\n" + "=" * 70)
    print("BONUS: Full analysis 'toi om roi'")
    print("=" * 70)
    result = analyze(TEST_USER, "toi om roi")
    if not result:
        print("  [FAIL] analyze() returned None")
        return
    print(f"  Context: {result['context']}")
    print(f"  Severity: {result['severity']}")
    print(f"  Advice: {result['advice']}")
    print(f"  Stats: {result.get('stats')}")
    print(f"\n  Actions:")
    for a in result["actions"]:
        ev = a["event"]
        icon = {"keep": "OK", "reschedule": "MOVE", "cancel": "DEL"}[a["action"]]
        print(f"    [{icon:5s}] score={a['score']:2d} | {ev['title']:30s} ({ev['event_type']})")


if __name__ == "__main__":
    print("JARVIS ADVISOR TEST SUITE\n")
    ids = setup_events()
    print(f"[Setup] Created {len(ids)} test events for user {TEST_USER}\n")
    p = test_context_detection()
    test_priority_scoring()
    test_full_analysis()
    print(f"\n{'=' * 70}")
    print(f"FINAL: {p}/20 context tests passed")
    print("=" * 70)
    print(f"\n[Cleanup] Keeping test events for next run (delete manually if needed)")