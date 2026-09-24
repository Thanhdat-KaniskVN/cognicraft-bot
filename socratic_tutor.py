# socratic_tutor.py
"""
Socratic Tutor - Dạy bằng câu hỏi
- Bot hỏi, không đưa đáp án
- User trả lời → Bot đánh giá + hỏi sâu hơn
- 5 câu → Kết luận + Insights
"""
import json
import hashlib
import os
from datetime import datetime
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class SocraticSession:
    """Session của 1 user"""

    def __init__(self, user_id, member, topic):
        self.user_id = user_id
        self.member = member
        self.topic = topic
        self.turn = 0
        self.max_turns = 5
        self.history = []  # List of {question, answer, evaluation}
        self.started_at = datetime.now()
        self.status = "active"  # active | completed | cancelled

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "member": self.member,
            "topic": self.topic,
            "turn": self.turn,
            "max_turns": self.max_turns,
            "history": self.history,
            "started_at": self.started_at.isoformat(),
            "status": self.status,
        }


class SocraticTutor:
    """Socratic Tutor - Dạy bằng câu hỏi"""

    MAX_INSIGHT_LEN = 80
    MAX_SESSION_MINUTES = 30

    def __init__(self):
        self.cache_dir = os.path.join(CACHE_DIR, "socratic")
        os.makedirs(self.cache_dir, exist_ok=True)
        # Active sessions: {user_id: SocraticSession}
        self.sessions = {}

    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================

    def start_session(self, user_id, member, topic):
        """
        Bắt đầu session mới.

        Returns:
            dict: {question, turn, topic}
        """
        # Hủy session cũ nếu có
        if user_id in self.sessions:
            self.sessions[user_id].status = "cancelled"

        # Tạo session mới
        session = SocraticSession(user_id, member, topic)
        self.sessions[user_id] = session

        # Sinh câu hỏi đầu tiên
        question_data = self._generate_question(
            topic=topic,
            turn=0,
            history=[],
        )

        session.history.append({
            "question": question_data["question"],
            "hint": question_data.get("hint", ""),
            "focus": question_data.get("focus", ""),
            "answer": None,
            "evaluation": None,
        })
        session.turn = 1

        return {
            "question": question_data["question"],
            "hint": question_data.get("hint", ""),
            "turn": 1,
            "max_turns": session.max_turns,
            "topic": topic,
        }

    def answer_question(self, user_id, answer):
        """
        User trả lời câu hỏi.

        Returns:
            dict: {
                "evaluation": str,
                "score": int,
                "next_question": str,
                "turn": int,
                "is_completed": bool,
                "final_report": dict (nếu completed),
            }
        """
        if user_id not in self.sessions:
            return {"error": "Chưa có session. Gõ `!socratic <topic>` để bắt đầu."}

        session = self.sessions[user_id]
        if session.status != "active":
            return {"error": "Session đã kết thúc. Gõ `!socratic <topic>` để bắt đầu mới."}

        # Cập nhật câu trả lời vào history
        current = session.history[-1]
        current["answer"] = answer

        # Đánh giá câu trả lời
        evaluation = self._evaluate_answer(
            topic=session.topic,
            question=current["question"],
            answer=answer,
            turn=session.turn,
            history=session.history[:-1],
        )
        current["evaluation"] = evaluation

        # Kiểm tra đã hết turn chưa
        if session.turn >= session.max_turns:
            session.status = "completed"
            final_report = self._generate_final_report(session)
            return {
                "evaluation": evaluation["feedback"],
                "score": evaluation["score"],
                "is_completed": True,
                "final_report": final_report,
            }

        # Sinh câu hỏi tiếp theo
        next_data = self._generate_question(
            topic=session.topic,
            turn=session.turn,
            history=session.history,
        )

        session.history.append({
            "question": next_data["question"],
            "hint": next_data.get("hint", ""),
            "focus": next_data.get("focus", ""),
            "answer": None,
            "evaluation": None,
        })
        session.turn += 1

        return {
            "evaluation": evaluation["feedback"],
            "score": evaluation["score"],
            "next_question": next_data["question"],
            "turn": session.turn,
            "max_turns": session.max_turns,
            "is_completed": False,
        }

    def get_hint(self, user_id):
        """Lấy hint cho câu hỏi hiện tại"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        if session.status != "active":
            return None

        current = session.history[-1]
        return current.get("hint", "Không có gợi ý cho câu này.")

    def skip_question(self, user_id):
        """Bỏ qua câu hỏi hiện tại"""
        if user_id not in self.sessions:
            return {"error": "Chưa có session."}

        session = self.sessions[user_id]
        if session.status != "active":
            return {"error": "Session đã kết thúc."}

        current = session.history[-1]
        current["answer"] = "(Bỏ qua)"
        current["evaluation"] = {
            "feedback": "Bỏ qua câu hỏi.",
            "score": 0,
        }

        # Nếu còn turn → sinh câu hỏi mới
        if session.turn >= session.max_turns:
            session.status = "completed"
            final_report = self._generate_final_report(session)
            return {
                "is_completed": True,
                "final_report": final_report,
            }

        next_data = self._generate_question(
            topic=session.topic,
            turn=session.turn,
            history=session.history,
        )

        session.history.append({
            "question": next_data["question"],
            "hint": next_data.get("hint", ""),
            "focus": next_data.get("focus", ""),
            "answer": None,
            "evaluation": None,
        })
        session.turn += 1

        return {
            "next_question": next_data["question"],
            "turn": session.turn,
            "max_turns": session.max_turns,
            "is_completed": False,
        }

    def end_session(self, user_id):
        """Kết thúc session sớm"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        session.status = "completed"

        final_report = self._generate_final_report(session)
        return final_report

    def get_status(self, user_id):
        """Lấy trạng thái session"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        return {
            "topic": session.topic,
            "turn": session.turn,
            "max_turns": session.max_turns,
            "status": session.status,
            "started_at": session.started_at.strftime("%H:%M"),
            "history_count": len(session.history),
        }

    # ============================================================
    # AI GENERATION
    # ============================================================

    def _generate_question(self, topic, turn, history):
        """Sinh câu hỏi Socratic"""
        # Build context từ history
        history_text = ""
        if history:
            history_text = "**Lịch sử hỏi-đáp:**\n"
            for i, h in enumerate(history, 1):
                history_text += f"\nCâu {i}: {h['question']}\n"
                if h.get("answer"):
                    history_text += f"Trả lời: {h['answer'][:200]}\n"
                if h.get("evaluation"):
                    history_text += f"Đánh giá: {h['evaluation'].get('feedback', '')[:100]}\n"

        prompt = f"""Bạn là Socratic Tutor - dạy bằng CÂU HỎI, KHÔNG đưa đáp án.

**Topic:** {topic}
**Câu hỏi số:** {turn + 1}/{5}
{history_text}

**Yêu cầu:**
- Sinh 1 câu hỏi dẫn dắt để user TỰ KHÁM PHÁ
- KHÔNG đưa đáp án
- Nếu là câu đầu: hỏi khái niệm cơ bản
- Nếu câu sau: hỏi sâu hơn, đào sâu vào câu trả lời trước
- Có thể hỏi "tại sao", "nếu...thì sao", "so sánh với..."
- Câu hỏi phải ngắn gọn, dễ hiểu

**Trả về JSON:**
{{
  "question": "<câu hỏi>",
  "hint": "<gợi ý ngắn để user tự tìm ra>",
  "focus": "<khái niệm đang tập trung>"
}}

Chỉ trả về JSON."""

        try:
            result = call_ai_json(prompt, task_type="socratic")
            return {
                "question": result.get("question", "Bạn nghĩ gì về khái niệm này?"),
                "hint": result.get("hint", ""),
                "focus": result.get("focus", topic),
            }
        except Exception as e:
            print(f"[SocraticTutor] Generate question error: {e}")
            return {
                "question": f"Hãy giải thích {topic} theo cách hiểu của bạn?",
                "hint": "Nghĩ về ví dụ cụ thể.",
                "focus": topic,
            }

    def _evaluate_answer(self, topic, question, answer, turn, history):
        """Đánh giá câu trả lời của user"""
        prompt = f"""Bạn là Socratic Tutor - đánh giá câu trả lời.

**Topic:** {topic}
**Câu hỏi:** {question}
**User trả lời:** {answer}
**Câu số:** {turn}/5

**Yêu cầu:**
- Đánh giá câu trả lời (KHÔNG đưa đáp án đúng)
- Khen ngợi điểm đúng, chỉ ra điểm cần suy nghĩ thêm
- Nếu user trả lời tốt: công nhận + hỏi sâu hơn
- Nếu user trả lời kém: gợi ý hướng suy nghĩ (không đưa đáp án)
- KHÔNG nói "đáp án là...", chỉ dẫn dắt

**Trả về JSON:**
{{
  "feedback": "<nhận xét + dẫn dắt>",
  "score": <0-5>,
  "follow_up": "<câu hỏi gợi mở nếu cần>"
}}

Chỉ trả về JSON."""

        try:
            result = call_ai_json(prompt, task_type="socratic")
            return {
                "feedback": result.get("feedback", "Cảm ơn câu trả lời của bạn."),
                "score": max(0, min(5, float(result.get("score", 3)))),
                "follow_up": result.get("follow_up", ""),
            }
        except Exception as e:
            print(f"[SocraticTutor] Evaluate error: {e}")
            return {
                "feedback": "Cảm ơn câu trả lời. Hãy tiếp tục suy nghĩ.",
                "score": 3,
                "follow_up": "",
            }

    def _generate_final_report(self, session):
        """Tạo báo cáo cuối session"""
        # Tính điểm trung bình
        scores = [
            h["evaluation"]["score"]
            for h in session.history
            if h.get("evaluation") and h["evaluation"].get("score") is not None
        ]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Đếm số câu trả lời
        answered = sum(1 for h in session.history if h.get("answer") and h["answer"] != "(Bỏ qua)")
        skipped = sum(1 for h in session.history if h.get("answer") == "(Bỏ qua)")

        # Tạo tổng kết bằng AI
        summary = self._generate_summary(session, avg_score)

        return {
            "member": session.member,
            "topic": session.topic,
            "total_questions": len(session.history),
            "answered": answered,
            "skipped": skipped,
            "avg_score": round(avg_score, 2),
            "summary": summary.get("summary", ""),
            "strengths": summary.get("strengths", []),
            "weaknesses": summary.get("weaknesses", []),
            "recommendations": summary.get("recommendations", []),
            "duration_minutes": round(
                (datetime.now() - session.started_at).total_seconds() / 60, 1
            ),
        }

    def _generate_summary(self, session, avg_score):
        """Tạo summary bằng AI"""
        history_text = ""
        for i, h in enumerate(session.history, 1):
            history_text += f"\nCâu {i}: {h['question']}\n"
            if h.get("answer"):
                history_text += f"Trả lời: {h['answer'][:200]}\n"
            if h.get("evaluation"):
                history_text += f"Điểm: {h['evaluation'].get('score', 0)}/5\n"

        prompt = f"""Tổng kết session Socratic:

**Member:** {session.member}
**Topic:** {session.topic}
**Điểm trung bình:** {avg_score}/5

**Lịch sử:**
{history_text}

**Trả về JSON:**
{{
  "summary": "<tổng kết 2-3 câu về session>",
  "strengths": ["<điểm mạnh 1>", "<điểm mạnh 2>"],
  "weaknesses": ["<điểm yếu 1>", "<điểm yếu 2>"],
  "recommendations": ["<gợi ý 1>", "<gợi ý 2>"]
}}

Chỉ trả về JSON."""

        try:
            return call_ai_json(prompt, task_type="socratic")
        except Exception as e:
            print(f"[SocraticTutor] Summary error: {e}")
            return {
                "summary": "Session hoàn thành.",
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
            }

    # ============================================================
    # UTILS
    # ============================================================

    def get_active_sessions_count(self):
        """Đếm số session đang active"""
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