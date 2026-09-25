# examples/socratic_tutor/plugin.py
"""
Socratic Tutor — Dạy bằng câu hỏi, không đưa đáp án
"""

PROMPTS = [
    "Câu hỏi này cho em biết điều gì?",
    "Em có thể giải thích lại bằng lời của em không?",
    "Điều gì sẽ xảy ra nếu ta thay đổi điều kiện này?",
    "Em có thể so sánh với ví dụ khác không?",
    "Tại sao em nghĩ vậy? Cho anh ví dụ?",
]

def ask(topic: str, level: int = 1) -> dict:
    """Sinh câu hỏi Socratic về topic"""
    return {
        "topic": topic,
        "level": level,
        "questions": [f"{topic}: {p}" for p in PROMPTS[:level + 1]],
    }

def run(command: str, args: list = None) -> str:
    args = args or []
    if command == "ask":
        topic = args[0] if args else "chủ đề"
        return f"🎓 Câu hỏi Socratic về {topic}: {PROMPTS[0]}"
    return f"❌ Unknown command: {command}"


if __name__ == "__main__":
    print(run("ask", ["induction"]))