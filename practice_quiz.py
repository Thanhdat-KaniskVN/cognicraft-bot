# practice_quiz.py
"""
Practice Quiz - Kiểm tra trắc nghiệm
- Multiple choice, True/False, Fill in blank
- Bot chấm + giải thích
- Lưu kết quả vào Sheets
"""
import json
import hashlib
import os
from datetime import datetime
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class QuizSession:
    """Session quiz của 1 user"""

    def __init__(self, user_id, member, topic, num_questions=5):
        self.user_id = user_id
        self.member = member
        self.topic = topic
        self.num_questions = num_questions
        self.current_index = 0
        self.questions = []  # List of questions
        self.answers = []     # List of {question_id, user_answer, correct, explanation}
        self.started_at = datetime.now()
        self.status = "active"

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "member": self.member,
            "topic": self.topic,
            "current_index": self.current_index,
            "questions": self.questions,
            "answers": self.answers,
            "started_at": self.started_at.isoformat(),
            "status": self.status,
        }


class PracticeQuiz:
    """Practice Quiz - Kiểm tra trắc nghiệm"""

    def __init__(self):
        self.cache_dir = os.path.join(CACHE_DIR, "quiz")
        os.makedirs(self.cache_dir, exist_ok=True)
        # Active sessions: {user_id: QuizSession}
        self.sessions = {}

    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================

    def start_quiz(self, user_id, member, topic, num_questions=5):
        """
        Bắt đầu quiz mới.

        Returns:
            dict: {question, index, total}
        """
        # Hủy session cũ
        if user_id in self.sessions:
            self.sessions[user_id].status = "cancelled"

        # Validate num_questions
        num_questions = max(3, min(10, num_questions))

        # Tạo session
        session = QuizSession(user_id, member, topic, num_questions)

        # Sinh câu hỏi
        questions = self._generate_questions(topic, num_questions)
        if not questions:
            return {"error": "Không thể sinh câu hỏi. Thử lại sau."}

        session.questions = questions
        self.sessions[user_id] = session

        return self._format_question(session)

    def answer_question(self, user_id, user_answer):
        """
        User trả lời câu hỏi.

        Returns:
            dict: {
                "is_correct": bool,
                "correct_answer": str,
                "explanation": str,
                "next_question": dict (nếu còn),
                "is_completed": bool,
                "result": dict (nếu completed),
            }
        """
        if user_id not in self.sessions:
            return {"error": "Chưa có quiz. Gõ `!quiz <topic>` để bắt đầu."}

        session = self.sessions[user_id]
        if session.status != "active":
            return {"error": "Quiz đã kết thúc. Gõ `!quiz <topic>` để bắt đầu mới."}

        current_q = session.questions[session.current_index]
        user_answer_clean = user_answer.strip().upper()

        # Chấm điểm
        correct = self._check_answer(current_q, user_answer_clean)

        session.answers.append({
            "question_id": current_q["id"],
            "question": current_q["question"],
            "user_answer": user_answer_clean,
            "correct_answer": current_q["correct"],
            "is_correct": correct,
            "explanation": current_q.get("explanation", ""),
        })

        # Tăng index
        session.current_index += 1

        # Kiểm tra hoàn thành
        if session.current_index >= len(session.questions):
            session.status = "completed"
            result = self._generate_result(session)
            return {
                "is_correct": correct,
                "correct_answer": current_q["correct"],
                "explanation": current_q.get("explanation", ""),
                "is_completed": True,
                "result": result,
            }

        return {
            "is_correct": correct,
            "correct_answer": current_q["correct"],
            "explanation": current_q.get("explanation", ""),
            "next_question": self._format_question(session),
            "is_completed": False,
        }

    def skip_question(self, user_id):
        """Bỏ qua câu hiện tại"""
        if user_id not in self.sessions:
            return {"error": "Chưa có quiz."}

        session = self.sessions[user_id]
        if session.status != "active":
            return {"error": "Quiz đã kết thúc."}

        current_q = session.questions[session.current_index]
        session.answers.append({
            "question_id": current_q["id"],
            "question": current_q["question"],
            "user_answer": "(Bỏ qua)",
            "correct_answer": current_q["correct"],
            "is_correct": False,
            "explanation": current_q.get("explanation", ""),
        })

        session.current_index += 1

        if session.current_index >= len(session.questions):
            session.status = "completed"
            return {
                "is_completed": True,
                "result": self._generate_result(session),
            }

        return {
            "next_question": self._format_question(session),
            "is_completed": False,
        }

    def get_hint(self, user_id):
        """Lấy hint cho câu hiện tại"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        if session.status != "active":
            return None

        current_q = session.questions[session.current_index]
        return current_q.get("hint", "Không có gợi ý.")

    def end_quiz(self, user_id):
        """Kết thúc quiz sớm"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        session.status = "completed"
        return self._generate_result(session)

    def get_status(self, user_id):
        """Lấy trạng thái quiz"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        return {
            "topic": session.topic,
            "current": session.current_index + 1,
            "total": len(session.questions),
            "correct": sum(1 for a in session.answers if a.get("is_correct")),
            "status": session.status,
            "started_at": session.started_at.strftime("%H:%M"),
        }

    # ============================================================
    # AI GENERATION
    # ============================================================

    def _generate_questions(self, topic, num_questions):
        """Sinh câu hỏi bằng AI"""
        # Cache key
        cache_key = hashlib.md5(
            f"{PROMPT_VERSION}|quiz|{topic}|{num_questions}".encode()
        ).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        prompt = f"""Sinh {num_questions} câu hỏi trắc nghiệm về topic: **{topic}**

**Yêu cầu:**
- Mỗi câu có 4 đáp án A, B, C, D
- Chỉ 1 đáp án đúng
- Có giải thích ngắn cho đáp án đúng
- Có gợi ý (hint) ngắn
- Độ khó tăng dần
- Nội dung phù hợp với sinh viên năm 1-2 CS

**Trả về JSON:**
{{
  "questions": [
    {{
      "id": 1,
      "question": "<câu hỏi>",
      "options": {{
        "A": "<đáp án A>",
        "B": "<đáp án B>",
        "C": "<đáp án C>",
        "D": "<đáp án D>"
      }},
      "correct": "A",
      "explanation": "<giải thích tại sao A đúng>",
      "hint": "<gợi ý ngắn>",
      "difficulty": "Easy|Medium|Hard"
    }}
  ]
}}

Chỉ trả về JSON."""

        try:
            result = call_ai_json(prompt, task_type="quiz")
            questions = result.get("questions", [])

            # Validate
            valid_questions = []
            for q in questions:
                if all(k in q for k in ["id", "question", "options", "correct"]):
                    if q["correct"] in q["options"]:
                        valid_questions.append(q)

            # Save cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(valid_questions, f, ensure_ascii=False, indent=2)

            return valid_questions
        except Exception as e:
            print(f"[PracticeQuiz] Generate error: {e}")
            return []

    def _check_answer(self, question, user_answer):
        """Check đáp án"""
        # Normalize
        correct = question["correct"].strip().upper()
        return user_answer == correct

    def _format_question(self, session):
        """Format câu hỏi để gửi Discord"""
        current_q = session.questions[session.current_index]

        # Format options
        options_text = ""
        for key, value in current_q["options"].items():
            options_text += f"**{key}.** {value}\n"

        return {
            "question": current_q["question"],
            "options": options_text,
            "difficulty": current_q.get("difficulty", "Medium"),
            "index": session.current_index + 1,
            "total": len(session.questions),
            "topic": session.topic,
        }

    def _generate_result(self, session):
        """Tạo kết quả cuối"""
        total = len(session.questions)
        answered = len([a for a in session.answers if a.get("user_answer") != "(Bỏ qua)"])
        skipped = total - answered
        correct = sum(1 for a in session.answers if a.get("is_correct"))
        wrong = answered - correct
        score = round(correct / total * 5, 2) if total > 0 else 0

        # Phân tích điểm yếu
        weak_questions = [
            a for a in session.answers if not a.get("is_correct")
        ]

        # Gợi ý dựa trên kết quả
        if score >= 4.5:
            level = "Xuất sắc"
            icon = "🏆"
        elif score >= 3.5:
            level = "Tốt"
            icon = "🟢"
        elif score >= 2.5:
            level = "Trung bình"
            icon = "🟡"
        else:
            level = "Cần cải thiện"
            icon = "🔴"

        # Tạo summary bằng AI
        summary = self._generate_summary(session, score, correct, total)

        return {
            "member": session.member,
            "topic": session.topic,
            "total": total,
            "answered": answered,
            "skipped": skipped,
            "correct": correct,
            "wrong": wrong,
            "score": score,
            "level": level,
            "icon": icon,
            "weak_questions": weak_questions[:3],
            "summary": summary.get("summary", ""),
            "recommendations": summary.get("recommendations", []),
            "duration_minutes": round(
                (datetime.now() - session.started_at).total_seconds() / 60, 1
            ),
        }

    def _generate_summary(self, session, score, correct, total):
        """Tạo summary bằng AI"""
        history_text = ""
        for i, a in enumerate(session.answers, 1):
            icon = "✅" if a["is_correct"] else "❌"
            history_text += f"\n{icon} Câu {i}: {a['question'][:100]}\n"
            history_text += f"   User: {a['user_answer']} | Đúng: {a['correct_answer']}\n"

        prompt = f"""Tổng kết quiz:

**Member:** {session.member}
**Topic:** {session.topic}
**Điểm:** {correct}/{total} câu đúng → {score}/5

**Lịch sử:**
{history_text}

**Trả về JSON:**
{{
  "summary": "<tổng kết 2-3 câu>",
  "recommendations": ["<gợi ý 1>", "<gợi ý 2>"]
}}

Chỉ trả về JSON."""

        try:
            return call_ai_json(prompt, task_type="quiz")
        except Exception as e:
            print(f"[PracticeQuiz] Summary error: {e}")
            return {
                "summary": f"Hoàn thành {total} câu, đúng {correct} câu.",
                "recommendations": [],
            }

    # ============================================================
    # UTILS
    # ============================================================

    def get_active_count(self):
        """Đếm session active"""
        return sum(
            1 for s in self.sessions.values()
            if s.status == "active"
        )

    def cleanup_old_sessions(self, max_age_minutes=60):
        """Xóa session cũ"""
        now = datetime.now()
        to_remove = []

        for user_id, session in self.sessions.items():
            age = (now - session.started_at).total_seconds() / 60
            if age > max_age_minutes:
                to_remove.append(user_id)

        for user_id in to_remove:
            del self.sessions[user_id]

        return len(to_remove)