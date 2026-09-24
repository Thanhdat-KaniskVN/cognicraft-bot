# plugins/socratic_tutor/main.py
"""
Socratic Tutor Plugin - Demo plugin
"""
import json


class SocraticTutorPlugin:
    """Socratic Tutor Plugin"""

    def __init__(self, manifest, config, core_api):
        self.manifest = manifest
        self.config = config
        self.core_api = core_api
        self.core_api.plugin_id = manifest.id
        self.sessions = {}

    def on_load(self):
        """Called when plugin loaded"""
        print(f"[{self.manifest.name}] Loaded v{self.manifest.version}")

    def on_unload(self):
        """Called when plugin unloaded"""
        print(f"[{self.manifest.name}] Unloaded")

    async def start_socratic(self, ctx, topic: str = "unknown"):
        """Start Socratic session"""
        user_id = ctx.author.id
        member = ctx.author.display_name

        prompt = f"""Bạn là Socratic Tutor. Sinh 1 câu hỏi đầu tiên về topic: {topic}

Trả về JSON:
{{"question": "...", "hint": "..."}}"""

        try:
            result = await self.core_api.call_ai(prompt, task_type="socratic")
            question = result.get("question", f"Bạn nghĩ gì về {topic}?")
            hint = result.get("hint", "Nghĩ về ví dụ cụ thể.")
        except Exception as e:
            question = f"Hãy giải thích {topic}?"
            hint = "Nghĩ về ví dụ."

        self.sessions[user_id] = {
            "member": member,
            "topic": topic,
            "turn": 1,
            "max_turns": self.config.get("max_turns", 5),
            "history": [],
        }

        msg = f"""# 🎓 SOCRATIC TUTOR – {topic.upper()}

**Câu 1/{self.sessions[user_id]['max_turns']}**

❓ {question}

💡 Gợi ý: {hint}

---
Gõ `!answer <câu trả lời>` để tiếp tục."""

        await ctx.send(msg)

    async def answer_question(self, ctx, answer: str = ""):
        """Answer question"""
        user_id = ctx.author.id

        if user_id not in self.sessions:
            await ctx.send("❌ Chưa có session. Gõ `!socratic <topic>` để bắt đầu.")
            return

        session = self.sessions[user_id]

        prompt = f"""Đánh giá câu trả lời:

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

        if session["turn"] > session["max_turns"]:
            total = sum(h["score"] for h in session["history"])
            avg = total / len(session["history"])
            await ctx.send(f"# 🎉 HOÀN THÀNH\n\n**Điểm TB:** {avg:.2f}/5")
            del self.sessions[user_id]
            return

        msg = f"""📝 **Đánh giá:** {feedback}
**Điểm:** {score}/5

---

**Câu {session['turn']}/{session['max_turns']}**

Gõ `!answer <câu trả lời>` để tiếp tục."""

        await ctx.send(msg)