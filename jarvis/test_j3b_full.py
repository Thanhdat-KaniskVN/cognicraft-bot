# jarvis/test_j3b_full.py
"""40 test cases - chaotic data + edge cases + integration."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pytz

from jarvis import event_manager as em
from jarvis.multi_parser import parse_multi_events
from jarvis.conflict_detector import (
    detect_conflicts, suggest_slots, EXCLUSIVE_TYPES, _parse_dt, TZ
)
from jarvis.chain_rescheduler import build_chain, apply_chain

UID = "test_j3b_chaos"
now = datetime.now(TZ)

PASS = 0
FAIL = 0
FAILED_TESTS = []


def reset():
    for ev in em.list_events(user_id=UID, days_ahead=365, status=None):
        em.delete_event(ev["id"])


def check(name, condition, details=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILED_TESTS.append((name, details))
        print(f"  [FAIL] {name} | {details}")


# ============================================================
# PART 1: PARSE CHAOTIC INPUT (10 tests)
# ============================================================
print("\n" + "=" * 70)
print("PART 1: PARSE CHAOTIC INPUT (1-10)")
print("=" * 70)

reset()

# T1: 1 event đơn giản
events = parse_multi_events("mai 6h chay bo 5km", now=now)
check("T1: single event", len(events) == 1 and events[0].event_type == "run",
      f"got {len(events)} events")

# T2: 3 events chaotic
text2 = "sang mai chay bo 5h sang roi hoc adp 7h30-1h chieu, va tap gym 5h chieu"
events2 = parse_multi_events(text2, now=now)
check("T2: chaotic 3 events", len(events2) == 3, f"got {len(events2)}")

# T3: comma split
events3 = parse_multi_events("sang mai 6h chay bo, 8h di hoc, 5h chieu gym", now=now)
check("T3: comma split 3 events", len(events3) == 3, f"got {len(events3)}")

# T4: relative time
events4 = parse_multi_events("20 phut nua hoc python", now=now)
check("T4: relative time +20p", len(events4) == 1 and abs((events4[0].start_time - now).total_seconds() / 60 - 20) < 2,
      f"delta={((events4[0].start_time - now).total_seconds()/60 if events4 else 0):.0f}")

# T5: relative hours
events5 = parse_multi_events("2 tieng nua hop nhom", now=now)
check("T5: relative +2h", len(events5) == 1 and abs((events5[0].start_time - now).total_seconds() / 3600 - 2) < 0.1,
      f"delta_h={((events5[0].start_time - now).total_seconds()/3600 if events5 else 0):.1f}")

# T6: time range 7h30-1h chieu
events6 = parse_multi_events("mai 7h30-1h chieu hoc adp", now=now)
ok6 = len(events6) == 1 and events6[0].duration_min > 300
check("T6: time range duration > 5h", ok6, f"dur={events6[0].duration_min if events6 else 0}")

# T7: context inheritance (period)
events7 = parse_multi_events("toi nay gym 7h va hoc bai 9h", now=now)
ok7 = len(events7) == 2 and events7[1].start_time.hour >= 20
check("T7: period inherit -> 21h study", ok7,
      f"hr={events7[1].start_time.hour if len(events7)>1 else '?'}")

# T8: context inheritance (day)
events8 = parse_multi_events("thu 4 hop nhom 3h chieu, sau do hoc calculus 7h toi", now=now)
ok8 = len(events8) == 2 and events8[0].start_time.date() == events8[1].start_time.date()
check("T8: day inherit same date", ok8, f"dates differ")

# T9: study type detection
events9 = parse_multi_events("mai 8h hoc bai", now=now)
check("T9: study type", len(events9) == 1 and events9[0].event_type == "study",
      f"got {events9[0].event_type if events9 else '?'}")

# T10: empty text
events10 = parse_multi_events("", now=now)
check("T10: empty -> []", len(events10) == 0, f"got {len(events10)}")


# ============================================================
# PART 2: CONFLICT DETECTION (10 tests)
# ============================================================
print("\n" + "=" * 70)
print("PART 2: CONFLICT DETECTION (11-20)")
print("=" * 70)

reset()

# Setup common events
base = (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
em.create_event(UID, "T", "Hop nhom", "meeting", base, base + timedelta(hours=1))
em.create_event(UID, "T", "Doc sach", "study", base + timedelta(hours=2), base + timedelta(hours=3))
em.create_event(UID, "T", "Gym", "gym", base + timedelta(hours=4), base + timedelta(hours=5))

# T11: exact overlap meeting
c11 = detect_conflicts(UID, base, base + timedelta(hours=1), event_type="class")
check("T11: exact overlap class vs meeting", len(c11) == 1, f"got {len(c11)}")

# T12: partial overlap
c12 = detect_conflicts(UID, base + timedelta(minutes=30), base + timedelta(hours=2), event_type="class")
check("T12: partial overlap", len(c12) >= 1, f"got {len(c12)}")

# T13: task type skip check
c13 = detect_conflicts(UID, base, base + timedelta(hours=1), event_type="task")
check("T13: task skip conflict", len(c13) == 0, f"got {len(c13)}")

# T14: study type skip check
c14 = detect_conflicts(UID, base, base + timedelta(hours=1), event_type="study")
check("T14: study skip conflict", len(c14) == 0, f"got {len(c14)}")

# T15: gym type check conflict
c15 = detect_conflicts(UID, base + timedelta(hours=4), base + timedelta(hours=5), event_type="gym")
check("T15: gym conflict", len(c15) == 1, f"got {len(c15)}")

# T16: no overlap
c16 = detect_conflicts(UID, base + timedelta(hours=10), base + timedelta(hours=11), event_type="class")
check("T16: no overlap -> 0", len(c16) == 0, f"got {len(c16)}")

# T17: exclusive types set has all expected
expected = {"class", "exam", "meeting", "gym", "run", "bike", "swim", "yoga"}
check("T17: EXCLUSIVE_TYPES complete", expected.issubset(EXCLUSIVE_TYPES),
      f"missing {expected - EXCLUSIVE_TYPES}")

# T18: _parse_dt converts UTC -> TZ
from datetime import timezone
utc_dt = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)  # 08:00 UTC = 15:00 VN
converted = _parse_dt(utc_dt)
check("T18: _parse_dt UTC->TZ", converted.hour == 15, f"got {converted.hour}")

# T19: suggest slots returns 3
sug = suggest_slots(base + timedelta(hours=1), 60, UID, n=3)
check("T19: suggest 3 slots", len(sug) == 3, f"got {len(sug)}")

# T20: suggest slots avoid conflicts
ok20 = all(not any(
    s["start"] < (_parse_dt(e["start_time"]) + timedelta(hours=1)) and
    s["end"] > _parse_dt(e["start_time"])
    for e in em.list_events(user_id=UID, days_ahead=3)
    if e.get("event_type") in EXCLUSIVE_TYPES
) for s in sug)
check("T20: suggestions no conflict", ok20, "overlap detected")


# ============================================================
# PART 3: CHAIN RESCHEDULE (10 tests)
# ============================================================
print("\n" + "=" * 70)
print("PART 3: CHAIN RESCHEDULE (21-30)")
print("=" * 70)

reset()

# Setup 3 chained meetings
chain_base = (now + timedelta(days=2)).replace(hour=15, minute=0, second=0, microsecond=0)
em.create_event(UID, "T", "M1", "meeting", chain_base, chain_base + timedelta(hours=1))
em.create_event(UID, "T", "M2", "meeting", chain_base + timedelta(hours=1, minutes=30),
                chain_base + timedelta(hours=2, minutes=30))
em.create_event(UID, "T", "M3", "meeting", chain_base + timedelta(hours=3, minutes=0),
                chain_base + timedelta(hours=4, minutes=0))

# T21: build chain with overlap
new_start = chain_base + timedelta(minutes=30)
new_end = new_start + timedelta(hours=1)
plan21 = build_chain(UID, new_start, new_end, new_event_type="meeting")
check("T21: chain detects 1+", len(plan21["chain"]) >= 1, f"got {len(plan21['chain'])}")

# T22: chain has_conflicts
check("T22: has_conflicts True", plan21["has_conflicts"] is True, f"got {plan21['has_conflicts']}")

# T23: flexible type -> no chain
plan23 = build_chain(UID, new_start, new_end, new_event_type="task")
check("T23: task -> no chain", len(plan23["chain"]) == 0, f"got {len(plan23['chain'])}")

# T24: chain exclusive flag
check("T24: exclusive=True for meeting", plan23.get("exclusive") is False and plan21.get("exclusive") is True,
      "flags wrong")

# T25: first chain item reason=conflict
first_reason = plan21["chain"][0]["reason"] if plan21["chain"] else None
check("T25: first reason=conflict", first_reason == "conflict", f"got {first_reason}")

# T26: chain item new_start after original conflict end
ok26 = all(item["new_start"] > item["old_start"] for item in plan21["chain"])
check("T26: new_start > old_start", ok26, "some shifted back")

# T27: chain gaps respected (>= 5 min)
ok27 = True
for i in range(len(plan21["chain"]) - 1):
    gap = (plan21["chain"][i+1]["new_start"] - plan21["chain"][i]["new_end"]).total_seconds() / 60
    if gap < 4:
        ok27 = False
check("T27: chain gap >= 5p", ok27, "gap too small")

# T28: apply_chain returns applied list
applied = apply_chain(UID, plan21["chain"])
check("T28: apply_chain returns list", isinstance(applied, list) and len(applied) == len(plan21["chain"]),
      f"got {len(applied)}/{len(plan21['chain'])}")

# T29: after apply, event start changed
if applied:
    ev_check = em.get_event(applied[0][0])
    new_start_db = _parse_dt(ev_check["start_time"])
    check("T29: DB updated", new_start_db == _parse_dt(applied[0][1]), "start not updated")
else:
    check("T29: DB updated", False, "no applied")

# T30: max_chain limit respected
reset()
big_base = (now + timedelta(days=3)).replace(hour=8, minute=0, second=0, microsecond=0)
for i in range(10):
    em.create_event(UID, "T", f"M{i}", "meeting",
                    big_base + timedelta(hours=i),
                    big_base + timedelta(hours=i, minutes=30))
plan30 = build_chain(UID, big_base, big_base + timedelta(minutes=45), max_chain=5,
                     new_event_type="meeting")
check("T30: max_chain=5 enforced", len(plan30["chain"]) <= 5, f"got {len(plan30['chain'])}")


# ============================================================
# PART 4: INTEGRATION + EDGE CASES (10 tests)
# ============================================================
print("\n" + "=" * 70)
print("PART 4: INTEGRATION + EDGE CASES (31-40)")
print("=" * 70)

reset()

# T31: dedupe window - same event 2x
now_plus = now + timedelta(hours=2)
id1 = em.create_event(UID, "T", "Test", "meeting", now_plus)
id2 = em.create_event(UID, "T", "Test", "meeting", now_plus)
check("T31: dedupe same time", id1 == id2, f"{id1} != {id2}")

# T32: dedupe window - +3p still dedupe
id3 = em.create_event(UID, "T", "Test", "meeting", now_plus + timedelta(minutes=3))
check("T32: dedupe +3p", id3 == id1, f"{id3} != {id1}")

# T33: dedupe window - +10p different
id4 = em.create_event(UID, "T", "Test", "meeting", now_plus + timedelta(minutes=10))
check("T33: +10p NOT dedupe", id4 != id1, f"{id4} == {id1}")

# T34: cross-midnight time range
events34 = parse_multi_events("toi mai 23h-1h sang", now=now)
ok34 = len(events34) == 1 and events34[0].duration_min > 100
check("T34: cross-midnight range", ok34,
      f"dur={events34[0].duration_min if events34 else 0}")

# T35: empty chain apply
empty_applied = apply_chain(UID, [])
check("T35: apply empty chain", empty_applied == [], f"got {empty_applied}")

# T36: conflict check with exclude_id
reset()
ex_base = (now + timedelta(days=4)).replace(hour=10, minute=0, second=0, microsecond=0)
ex_id = em.create_event(UID, "T", "Me", "meeting", ex_base, ex_base + timedelta(hours=1))
c36 = detect_conflicts(UID, ex_base, ex_base + timedelta(hours=1), exclude_id=ex_id, event_type="class")
check("T36: exclude_id works", len(c36) == 0, f"got {len(c36)}")

# T37: chain with flexible interleave (task between meetings)
reset()
flex_base = (now + timedelta(days=5)).replace(hour=14, minute=0, second=0, microsecond=0)
em.create_event(UID, "T", "M1", "meeting", flex_base, flex_base + timedelta(hours=1))
em.create_event(UID, "T", "Break", "task", flex_base + timedelta(hours=1), flex_base + timedelta(hours=2))
em.create_event(UID, "T", "M2", "meeting", flex_base + timedelta(hours=2),
                flex_base + timedelta(hours=3))
plan37 = build_chain(UID, flex_base + timedelta(minutes=30), flex_base + timedelta(hours=1, minutes=30),
                     new_event_type="meeting")
ids = [item["event"]["id"] for item in plan37["chain"]]
check("T37: task not in chain", len(ids) == 2, f"chain={len(ids)} (expect 2 meetings)")

# T38: duplicate add via parser (same text 2x)
reset()
e1 = parse_multi_events("mai 7h hoc bai", now=now)
e2 = parse_multi_events("mai 7h hoc bai", now=now)
ok38 = len(e1) == len(e2) == 1 and e1[0].start_time == e2[0].start_time
check("T38: parser deterministic", ok38, f"{len(e1)} vs {len(e2)}")

# T39: suggestion within 7 days
sug39 = suggest_slots(now + timedelta(hours=2), 60, UID, n=3, day_window=7)
ok39 = len(sug39) > 0 and all(s["start"] > now for s in sug39)
check("T39: suggestions in future", ok39, f"got {len(sug39)}")

# T40: chain preserves duration
reset()
dur_base = (now + timedelta(days=6)).replace(hour=9, minute=0, second=0, microsecond=0)
em.create_event(UID, "T", "C1", "class", dur_base, dur_base + timedelta(minutes=90))
em.create_event(UID, "T", "C2", "class", dur_base + timedelta(minutes=90),
                dur_base + timedelta(minutes=180))
plan40 = build_chain(UID, dur_base, dur_base + timedelta(minutes=60), new_event_type="class")
ok40 = all(
    (item["new_end"] - item["new_start"]) == (item["old_end"] - item["old_start"])
    for item in plan40["chain"]
)
check("T40: duration preserved", ok40, "durations differ")


# ============================================================
# FINAL
# ============================================================
reset()

print("\n" + "=" * 70)
print(f"FINAL: {PASS}/{PASS + FAIL} passed")
print("=" * 70)

if FAILED_TESTS:
    print("\nFailed tests:")
    for name, details in FAILED_TESTS:
        print(f"  [FAIL] {name} | {details}")
else:
    print("ALL PASS! J3B FULL READY!")