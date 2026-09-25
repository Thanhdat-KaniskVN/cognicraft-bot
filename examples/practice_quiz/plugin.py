# examples/practice_quiz/plugin.py
"""Practice Quiz — Tạo quiz trắc nghiệm"""

def generate(topic: str, num: int = 5) -> list:
    return [{
        "q": f"Câu {i}: {topic}?",
        "options": ["A", "B", "C", "D"],
        "answer": "A",
    } for i in range(1, num + 1)]

def run(command: str, args: list = None) -> str:
    args = args or []
    if command == "quiz":
        topic = args[0] if args else "chủ đề"
        return f"📝 Quiz về {topic}: 5 câu hỏi"
    return f"❌ Unknown: {command}"


if __name__ == "__main__":
    print(run("quiz", ["toán"]))