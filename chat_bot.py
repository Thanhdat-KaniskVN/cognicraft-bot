# chat_bot.py
"""
Chat Bot - Chat tự do + Auto-detect insights
- Context-aware (nhớ 5 tin nhắn gần nhất)
- Auto-detect insights (question, difficulty, suggestion, insight)
- Lưu vào tab Chat Insights trong Sheets
"""
import json
import hashlib
import os
from datetime import datetime
from ai_provider import call_ai_json
from config import CACHE_DIR, PROMPT_VERSION


class ChatSession:
    """Session chat của 1 user"""

    def __init__(self, user_id, member, role="member_g1"):
        self.user_id = user_id
        self.member = member
        self.role = role
        self.messages = []  # List of {role: "user"|"bot", content, timestamp}
        self.started_at = datetime.now()
        self.max_context = 10  # Giữ 10 tin nhắn gần nhất

    def add_message(self, role, content):
        """Thêm tin nhắn vào history"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # Trim nếu quá dài
        if len(self.messages) > self.max_context * 2:
            self.messages = self.messages[-self.max_context * 2:]

    def get_context(self, limit=5):
        """Lấy N tin nhắn gần nhất để làm context"""
        return self.messages[-limit * 2:]


class ChatBot:
    """Chat Bot - Chat tự do + Auto-detect insights"""

    # Max message length để tránh spam
    MAX_MESSAGE_LENGTH = 1000

    # Insights types
    INSIGHT_TYPES = {
        "question": "❓ Câu hỏi hay",
        "difficulty": "⚠️ Khó khăn",
        "suggestion": "💡 Gợi ý",
        "insight": "🧠 Hiểu biết mới",
        "bug": "🐛 Báo lỗi",
    }

    def __init__(self):
        self.cache_dir = os.path.join(CACHE_DIR, "chat")
        os.makedirs(self.cache_dir, exist_ok=True)
        # Active sessions: {user_id: ChatSession}
        self.sessions = {}

    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================

    def get_or_create_session(self, user_id, member, role="member_g1"):
        """Lấy session cũ hoặc tạo mới"""
        if user_id not in self.sessions:
            self.sessions[user_id] = ChatSession(user_id, member, role)
        return self.sessions[user_id]

    def clear_session(self, user_id):
        """Xóa session"""
        if user_id in self.sessions:
            del self.sessions[user_id]
            return True
        return False

    def get_history(self, user_id, limit=10):
        """Lấy lịch sử chat"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        return session.messages[-limit * 2:]

    # ============================================================
    # MAIN CHAT
    # ============================================================

    def chat(self, user_id, member, message, role="member_g1"):
        """
        Chat với bot.

        Args:
            user_id: Discord user ID
            member: Tên member
            message: Tin nhắn user
            role: Role của user

        Returns:
            dict: {
                "reply": str,
                "insights": list (nếu phát hiện),
                "tokens_used": int,
            }
        """
        # Validate
        if not message or not message.strip():
            return {"error": "Tin nhắn rỗng."}

        if len(message) > self.MAX_MESSAGE_LENGTH:
            message = message[:self.MAX_MESSAGE_LENGTH] + "..."

        # Get session
        session = self.get_or_create_session(user_id, member, role)

        # Add user message
        session.add_message("user", message)

        # Generate bot reply
        reply = self._generate_reply(session, message, role)

        # Add bot reply
        session.add_message("bot", reply)

        # Detect insights
              # Detect insights (không block chat nếu fail)
        try:
            insights = self._detect_insights(session, message, reply)
        except Exception as e:
            print(f"[ChatBot] Insights detection failed (OK): {e}")
            insights = []

        return {
            "reply": reply,
            "insights": insights,
            "member": member,
            "role": role,
            "session_message_count": len(session.messages),
        }

    # ============================================================
    # AI GENERATION
    # ============================================================

    def _generate_reply(self, session, message, role):
        """Sinh reply bằng AI"""
        # Build context
        context = session.get_context(limit=5)

        context_text = ""
        if len(context) > 1:  # Không phải tin nhắn đầu
            context_text = "**Lịch sử chat gần đây:**\n"
            for msg in context[:-1]:  # Bỏ tin nhắn cuối (vừa gửi)
                role_label = "User" if msg["role"] == "user" else "Bot"
                context_text += f"{role_label}: {msg['content'][:200]}\n"

        # System prompt theo role
        role_prompts = {
            "admin": "Bạn là trợ lý AI cho Admin của CogniCraft - hệ thống học tập. Admin có thể hỏi về data, insights, và quản lý hệ thống.",
            "leader": "Bạn là trợ lý AI cho Leader tuần của CogniCraft. Leader có thể hỏi về cách điều hành nhóm, lập kế hoạch, hỗ trợ members.",
            "member_g1": "Bạn là trợ lý AI học tập cho member G1 của CogniCraft. Bạn giúp member học tốt hơn: giải thích concepts, gợi ý tài liệu, định hướng học tập.",
            "guest": "Bạn là trợ lý AI của CogniCraft. Trả lời thân thiện về hệ thống học tập.",
        }

        system_prompt = role_prompts.get(role, role_prompts["guest"])

        prompt = f"""{system_prompt}

**Tên user:** {session.member}
**Role:** {role}

{context_text}

**Tin nhắn mới của user:**
{message}

**Yêu cầu:**
- Trả lời ngắn gọn, đi thẳng vào vấn đề (tối đa 300 từ)
- Giọng thân thiện, khích lệ
- Nếu user hỏi về học tập → hướng dẫn cụ thể
- Nếu user hỏi về hệ thống → giải thích rõ
- Nếu không biết → nói thật, không bịa
- KHÔNG dùng markdown table phức tạp
- Có thể dùng bullet points ngắn gọn

**Trả về JSON:**
{{
  "reply": "<câu trả lời>",
  "follow_up": "<câu hỏi gợi mở nếu phù hợp, có thể rỗng>"
}}

Chỉ trả về JSON."""

        try:
            result = call_ai_json(prompt, task_type="chat")
            reply = result.get("reply", "Xin lỗi, mình không hiểu. Bạn có thể nói rõ hơn?")

            # Thêm follow-up nếu có
            follow_up = result.get("follow_up", "")
            if follow_up:
                reply += f"\n\n💬 _{follow_up}_"

            return reply
        except Exception as e:
            err = str(e)

            if "503" in err or "UNAVAILABLE" in err:
                print(f"[ChatBot] Gemini 503 (high traffic)")
                return (
                    "⏳ **Gemini đang quá tải** (giờ cao điểm).\n\n"
                    "Thử lại sau **5-10 phút** nhé!\n"
                    "Hoặc gõ `!ping` để kiểm tra AI provider."
                )
            elif "timeout" in err.lower():
                print(f"[ChatBot] Gemini timeout")
                return (
                    "⏱️ **AI provider bị timeout**.\n\n"
                    "Thử lại sau 1-2 phút nhé!"
                )
            else:
                print(f"[ChatBot] Reply error: {err[:200]}")
                return f"❌ Lỗi: `{err[:150]}`\n\nThử lại sau nhé!"
    # ============================================================
    # INSIGHTS DETECTION
    # ============================================================

    def _detect_insights(self, session, message, reply):
        """Detect insights từ cuộc chat."""
        # Chỉ detect nếu message đủ dài.
        if len(message) < 20:
            return []

        prompt = f"""Phân tích cuộc chat sau để phát hiện INSIGHTS có giá trị:

**User:** {session.member} ({session.role})
**Tin nhắn:** {message}
**Bot reply:** {reply[:500]}

**Các loại insight cần phát hiện:**
1. **question** – Câu hỏi hay, có giá trị học tập
2. **difficulty** – Khó khăn, vướng mắc của member
3. **suggestion** – Gợi ý, đề xuất cải thiện hệ thống
4. **insight** – Hiểu biết mới, khám phá hay
5. **bug** – Báo lỗi, vấn đề kỹ thuật

**Yêu cầu:**
- CHỈ trả về insight nếu THỰC SỰ có giá trị (không spam)
- Nếu không có gì đặc biệt → trả về mảng rỗng
- Mỗi insight có: type, content, topic

**Trả về JSON:**
{{
  "insights": [
    {{
      "type": "question|difficulty|suggestion|insight|bug",
      "content": "<mô tả ngắn gọn 1 câu>",
      "topic": "<topic liên quan hoặc 'general'>"
    }}
  ]
}}

Chỉ trả về JSON. Nếu không có insight nào, trả về {{"insights": []}}."""

        try:
            result = call_ai_json(prompt, task_type="chat")
            insights = result.get("insights", [])

            # Validate
            valid_insights = []
            for ins in insights:
                if ins.get("type") in self.INSIGHT_TYPES:
                    if ins.get("content"):
                        valid_insights.append({
                            "type": ins["type"],
                            "content": ins["content"][:200],
                            "topic": ins.get("topic", "general")[:50],
                        })

            return valid_insights[:3]  # Max 3 insights/message
        except Exception as e:
            print(f"[ChatBot] Detect insights error: {e}")
            return []

    # ============================================================
    # UTILS
    # ============================================================

    def get_active_count(self):
        """Đếm session active"""
        return len(self.sessions)

    def get_session_info(self, user_id):
        """Lấy info session"""
        if user_id not in self.sessions:
            return None

        session = self.sessions[user_id]
        return {
            "member": session.member,
            "role": session.role,
            "message_count": len(session.messages),
            "started_at": session.started_at.strftime("%H:%M"),
        }

    def cleanup_old_sessions(self, max_age_minutes=120):
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