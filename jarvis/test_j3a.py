# jarvis/test_j3a.py
"""20 test cases cho J3A parser + commands."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.multi_parser import parse_multi_events

TESTS = [
    # === BASIC (5) ===
    ("mai 6h chay bo 5km", 1, "run", None),
    ("toi nay gym 7h", 1, "gym", None),
    ("3h chieu thu 4 hop nhom", 1, "meeting", None),
    ("sang mai 6h30 dap xe 10km", 1, "bike", None),
    ("chu nhat 8h thi toan roi rac", 1, "exam", None),
    # === MULTI (5) ===
    ("mai 6h chay, 8h hoc, 5h chieu gym", 3, None, None),
    ("toi nay gym 7h va hoc bai 9h", 2, None, None),
    ("thu 4 hop nhom 3h chieu, sau do hoc calculus 7h toi", 2, None, None),
    ("sang mai chay bo 5h sang roi hoc adp 7h30-1h chieu, va tap gym 5h chieu", 3, None, None),
    ("chieu nay 3h hoc python, 5h chay bo, toi 8h on bai", 3, None, None),
    # === TIME RANGE (3) ===
    ("mai hoc adp 7h30-1h chieu", 1, "class", 330),  # 5.5h
    ("thu 3 thi 8h-10h sang", 1, None, 120),
    ("toi nay gym 7h-8h30", 1, "gym", 90),
    # === EDGE (4) ===
    ("hen ban 3h chieu mai cafe o quan quen", 1, None, None),
    ("khi nao ranh thi on lai bai induction", 1, "study", None),
    ("sau khi an trua xong di boi 30 phut", 1, "swim", 30),
    ("toi nay 8h hoc bai 2 tieng", 1, "study", 120),
    # === MIXED (3) ===
    ("sang mai 6h chay bo, 8h di hoc, 5h chieu gym", 3, None, None),
    ("toi mai 8h hop nhom keo dai 2 tieng", 1, "meeting", 120),
    ("thu 6 9h thi cuoi ki, chieu 3h gym, toi 7h on bai", 3, None, None),
]


def run():
    print("=" * 72)
    print("J3A TEST SUITE - 20 cases")
    print("=" * 72)

    passed = 0
    failed = []

    for i, (txt, exp_count, exp_type, exp_dur) in enumerate(TESTS, 1):
        events = parse_multi_events(txt)
        n = len(events)
        ok_count = (n == exp_count)

        # Check type cua event dau tien
        ok_type = True
        if exp_type and n > 0:
            ok_type = (events[0].event_type == exp_type)

        # Check duration
        ok_dur = True
        if exp_dur and n > 0:
            ok_dur = (abs(events[0].duration_min - exp_dur) <= 5)

        status = "PASS" if (ok_count and ok_type and ok_dur) else "FAIL"

        if status == "PASS":
            passed += 1
            print(f"[{i:02d}] {status} | {n}ev | {txt[:55]}")
        else:
            print(f"[{i:02d}] {status} | {n}ev (exp {exp_count}) | {txt[:55]}")
            for j, ev in enumerate(events, 1):
                print(f"        [{j}] {ev.event_type:8s} {ev.start_time.strftime('%a %H:%M')} dur={ev.duration_min}p {ev.title[:40]!r}")
            if not ok_type:
                print(f"        TYPE: {events[0].event_type} != {exp_type}")
            if not ok_dur:
                print(f"        DUR: {events[0].duration_min} != {exp_dur}")
            failed.append((i, txt))

    print("=" * 72)
    print(f"RESULT: {passed}/{len(TESTS)} pass")
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
    print("=" * 72)


if __name__ == "__main__":
    run()