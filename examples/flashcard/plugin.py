# examples/flashcard/plugin.py
"""Flashcard — Tạo thẻ ghi nhớ"""

def create(topic: str, num: int = 10) -> list:
    return [{"front": f"Q{i}: {topic}?", "back": f"A{i}"} for i in range(1, num + 1)]

def run(command: str, args: list = None) -> str:
    args = args or []
    if command == "create":
        topic = args[0] if args else "chủ đề"
        return f"🃏 Đã tạo 10 flashcard về {topic}"
    return f"❌ Unknown: {command}"


if __name__ == "__main__":
    print(run("create", ["lịch sử"]))