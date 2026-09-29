# jarvis/personality.py
"""JARVIS personality templates - Iron Man vibe."""

STYLE = "ironman"  # default


IRONMAN = {
    # === Greetings ===
    "greeting_morning": "Good morning, sir. Ready when you are.",
    "greeting_evening": "Good evening, sir. How may I assist?",
    "greeting_general": "At your service, sir.",

    # === Event add ===
    "add_confirmed": "Yes, sir. I have logged {n} event{s}.",
    "add_gcal": "Synced to your Google Calendar, sir.",
    "add_local": "Logged locally, sir. No calendar sync as requested.",

    # === Cancel ===
    "cancel_done": "Cancelled, sir. Event #{id} has been removed.",
    "delete_done": "Erased permanently, sir. Event #{id} is no more.",

    # === Conflict ===
    "conflict_title": "A scheduling conflict, sir.",
    "conflict_intro": "I've detected an overlap. Shall I resolve it?",
    "chain_applied": "Very good, sir. Schedule adjusted. {n} event{s} relocated.",

    # === Reminder ===
    "reminder_intro": "A reminder, sir.",
    "reminder_urgent": "Immediate attention required, sir.",

    # === Context (sick/tired/etc) ===
    "context_sick": "I'm sorry to hear that, sir. Adjusting your schedule accordingly.",
    "context_accident": "This is serious, sir. Please seek medical attention immediately.",
    "context_tired": "You've been working hard, sir. Perhaps a brief respite?",
    "context_urgent": "Understood, sir. Reprioritizing your commitments.",

    # === Errors ===
    "error_parse": "My apologies, sir. I couldn't parse that.",
    "error_general": "My apologies, sir. Something went awry.",
    "error_empty": "I'm afraid I didn't catch that, sir.",

    # === Info ===
    "empty_today": "Nothing on the agenda today, sir. A rare pleasure.",
    "stats_intro": "Your calendar at a glance, sir.",
    "list_intro": "Your schedule, sir.",

    # === Misc ===
    "help_intro": "At your service, sir. Here's what I can do:",
    "processing": "One moment, sir.",
    "thanks": "Always a pleasure, sir.",
    "unknown": "I'm afraid I don't follow, sir. Try `!j help`.",
}


CASUAL = {
    "greeting_morning": "Chao buoi sang!",
    "add_confirmed": "Da them {n} event{s}.",
    "conflict_title": "Phat hien xung dot!",
    "reminder_intro": "Nhac nho:",
    "error_parse": "Khong parse duoc.",
    "error_general": "Co loi xay ra.",
    "thanks": "Khong co gi!",
}


STYLES = {
    "ironman": IRONMAN,
    "casual": CASUAL,
}


def set_style(style: str):
    global STYLE
    if style in STYLES:
        STYLE = style
        return True
    return False


def get(key: str, **kwargs) -> str:
    """Get template + interpolate.

    Fallback: IRONMAN -> raw key neu khong tim thay.
    """
    tpl_map = STYLES.get(STYLE, IRONMAN)
    tpl = tpl_map.get(key) or IRONMAN.get(key) or key

    # Interpolate {n}, {s}, {id}, ...
    try:
        return tpl.format(**kwargs)
    except (KeyError, IndexError):
        return tpl


def sir_suffix(text: str) -> str:
    """Add ", sir." if not present (ironman style)."""
    if STYLE != "ironman":
        return text
    if text.rstrip().endswith(("sir.", "sir", "Sir.", "Sir")):
        return text
    return text.rstrip(". ") + ", sir."


def format_plural(n: int) -> dict:
    return {"n": n, "s": "" if n == 1 else "s"}


if __name__ == "__main__":
    print("=" * 60)
    print("PERSONALITY TEST")
    print("=" * 60)

    print(f"\n[Style] {STYLE}")
    tests = [
        ("greeting_morning", {}),
        ("add_confirmed", {"n": 3, "s": "s"}),
        ("add_confirmed", {"n": 1, "s": ""}),
        ("conflict_title", {}),
        ("context_sick", {}),
        ("error_parse", {}),
        ("unknown_key_xyz", {}),
    ]
    for key, kw in tests:
        print(f"  {key:25s} -> {get(key, **kw)!r}")

    print("\n[Style: casual]")
    set_style("casual")
    for key, kw in tests:
        print(f"  {key:25s} -> {get(key, **kw)!r}")

    set_style("ironman")
    print(f"\n[sir_suffix] {sir_suffix('Task completed')!r}")
    print(f"[sir_suffix] {sir_suffix('Cancelled, sir.')!r}")