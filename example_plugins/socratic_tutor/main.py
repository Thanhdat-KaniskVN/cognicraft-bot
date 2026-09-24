# main.py
"""
Socratic Tutor Plugin
"""
import json
import os
from pathlib import Path


class SocraticTutorPlugin:
    """Socratic Tutor Plugin"""

    def __init__(self, manifest, config, core_api):
        self.manifest = manifest
        self.config = config
        self.core_api = core_api
        self.core_api.plugin_id = manifest.id

        # Session storage
        self.sessions = {}

    def on_load(self):
        """Called when plugin loaded"""
        print(f"[{self.manifest.name}] Loaded v{self.manifest.version}")

    def on_unload(self):
        """Called when plugin unloaded"""
        print(f"[{self.manifest.name}] Unloaded")

    async def start_socratic(self, ctx, topic):
        """Start Socratic session"""
        user_id = ctx.author.id
        member = ctx.author.display_name

        # Call AI
        prompt = f"""Bạn là Socratic Tutor. Sinh 1 câu hỏi đầu tiên về topic: {topic}

**Yêu cầu:**
- KHÔNG đưa đáp án
- Câu hỏi ngắn gọn, dẫn dắt
- Có gợi ý

Trả về JSON:
{{"question": "...", "hint": "..."}}"""

        try:
            result = await self.core_api.call_ai(prompt, task_type="socratic")
            question = result.get("question", "Bạn nghĩ gì về topic này?")
            hint = result.get("hint", "")
        except Exception as e:
            question = f"Hãy giải thích {topic} theo cách hiểu của bạn?"
            hint = "Nghĩ về ví dụ cụ thể."

        # Save session
        self.sessions[user_id] = {
            "member": member,
            "topic": topic,
            "turn": 1,
            "max_turns": self.config.get("max_turns", 5),
            "history": [],
        }

        # Send message
        msg = f"""# 🎓 SOCRATIC TUTOR – {topic.upper()}

**Câu 1/{self.sessions[user_id]['max_turns']}**

❓ {question}

💡 Gợi ý: {hint}

---
Gõ `!answer <câu trả lời>` để tiếp tục."""

        await ctx.send(msg)

    async def answer_question(self, ctx, answer):
        """Answer question"""
        user_id = ctx.author.id

        if user_id not in self.sessions:
            await ctx.send("❌ Chưa có session. Gõ `!socratic <topic>` để bắt đầu.")
            return

        session = self.sessions[user_id]

        # Evaluate
        prompt = f"""Đánh giá câu trả lời Socratic:

**Topic:** {session['topic']}
**Câu trả lời:** {answer}

Trả về JSON:
{{"feedback": "...", "score": 0-5}}"""

        try:
            result = await self.core_api.call_ai(prompt, task_type="socratic")
            feedback = result.get("feedback", "Cảm ơn câu trả lời.")
            score = result.get("score", 3)
        except Exception as e:
            feedback = "Cảm ơn câu trả lời."
            score = 3

        session["history"].append({"answer": answer, "score": score})
        session["turn"] += 1

        # Check complete
        if session["turn"] > session["max_turns"]:
            await self._complete_session(ctx, session)
            del self.sessions[user_id]
            return

        # Next question
        prompt = f"""Sinh câu hỏi Socratic tiếp theo:

**Topic:** {session['topic']}
**Câu số:** {session['turn']}/{session['max_turns']}
**Lịch sử:** {json.dumps(session['history'], ensure_ascii=False)}

Trả về JSON:
{{"question": "...", "hint": "..."}}"""

        try:
            result = await self.core_api.call_ai(prompt, task_type="socratic")
            next_q = result.get("question", "Bạn nghĩ gì thêm?")
        except Exception as e:
            next_q = "Bạn có thể mở rộng thêm không?"

        msg = f"""📝 **Đánh giá:** {feedback}
**Điểm:** {score}/5

---

**Câu {session['turn']}/{session['max_turns']}**

❓ {next_q}

Gõ `!answer <câu trả lời>` để tiếp tục."""

        await ctx.send(msg)

    async def _complete_session(self, ctx, session):
        """Complete session"""
        total = sum(h["score"] for h in session["history"])
        avg = total / len(session["history"]) if session["history"] else 0

        msg = f"""# 🎉 HOÀN THÀNH SOCRATIC – {session['topic'].upper()}

**Điểm TB:** {avg:.2f}/5
**Số câu:** {len(session['history'])}/{session['max_turns']}

Cảm ơn bạn đã tham gia!"""

        await ctx.send(msg)

        # Save insights
        try:
            await self.core_api.save_scores(
                await self.core_api.get_current_week(),
                session["member"],
                {"socratic_score": avg},
            )
        except Exception as e:
            print(f"[Socratic] Save error: {e}")

    async def auto_recommend(self, member, score, **kwargs):
        """Hook: on_score_complete"""
        if score < 3.5:
            # Gợi ý Socratic
            print(f"[Socratic] Auto-recommend for {member} (score={score})")

    async def add_summary(self, week, report, **kwargs):
        """Hook: on_weekly_report"""
        print(f"[Socratic] Add summary to week {week} report")
        return "Socratic summary added"