# plugins/practice_quiz/main.py
"""
Practice Quiz Plugin - Demo
"""
import json


class PracticeQuizPlugin:
    def __init__(self, manifest, config, core_api):
        self.manifest = manifest
        self.config = config
        self.core_api = core_api
        self.core_api.plugin_id = manifest.id
        self.sessions = {}

    def on_load(self):
        print(f"[{self.manifest.name}] Loaded v{self.manifest.version}")

    def on_unload(self):
        print(f"[{self.manifest.name}] Unloaded")

    async def start_quiz(self, ctx, topic: str = "unknown", num: int = 5):
        """Start quiz session"""
        user_id = ctx.author.id

        prompt = f"""Sinh {num} câu hỏi trắc nghiệm về topic: {topic}

Trả về JSON:
{{
  "questions": [
    {{"question": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct": "A"}}
  ]
}}"""

        try:
            result = await self.core_api.call_ai(prompt, task_type="quiz")
            questions = result.get("questions", [])
        except Exception as e:
            await ctx.send(f"❌ Lỗi: {e}")
            return

        if not questions:
            await ctx.send("❌ Không sinh được câu hỏi.")
            return

        self.sessions[user_id] = {
            "topic": topic,
            "questions": questions,
            "current": 0,
            "correct": 0,
        }

        q = questions[0]
        msg = f"# 📝 QUIZ – {topic.upper()}\n\n"
        msg += f"**Câu 1/{len(questions)}**\n\n"
        msg += f"{q['question']}\n\n"
        for k, v in q['options'].items():
            msg += f"**{k}.** {v}\n"

        await ctx.send(msg)