# main.py
import json
from pathlib import Path
from datetime import datetime


class FlashcardPlugin:
    def __init__(self, manifest, config, core_api):
        self.manifest = manifest
        self.config = config
        self.core_api = core_api
        self.core_api.plugin_id = manifest.id
        
        self.data_dir = Path("cache") / "flashcard"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cards_file = self.data_dir / "cards.json"
        self.cards = self._load_cards()

    def _load_cards(self):
        if self.cards_file.exists():
            try:
                with open(self.cards_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cards(self):
        with open(self.cards_file, "w", encoding="utf-8") as f:
            json.dump(self.cards, f, ensure_ascii=False, indent=2)

    def on_load(self):
        print(f"[{self.manifest.name}] Loaded v{self.manifest.version}")

    def on_unload(self):
        print(f"[{self.manifest.name}] Unloaded")

    async def create_flashcard(self, ctx, topic: str, count: int = 5):
        member = ctx.author.display_name
        user_id = str(ctx.author.id)
        
        await ctx.send(f"Dang tao {count} flashcard cho topic {topic}...")
        
        prompt = f"Tao {count} flashcard ve {topic}. JSON: {{\"cards\":[{{\"front\":\"...\",\"back\":\"...\"}}]}}"
        
        try:
            result = await self.core_api.call_ai(prompt, task_type="flashcard")
            cards = result.get("cards", [])
        except Exception as e:
            await ctx.send(f"Loi AI: {e}")
            return
        
        if not cards:
            await ctx.send("Khong tao duoc flashcard.")
            return
        
        if user_id not in self.cards:
            self.cards[user_id] = []
        
        for card in cards:
            self.cards[user_id].append({
                "front": card.get("front", ""),
                "back": card.get("back", ""),
                "topic": topic,
                "created_at": datetime.now().isoformat(),
                "review_count": 0,
            })
        
        self._save_cards()
        
        msg = f"# FLASHCARD - {topic.upper()}\n\n"
        msg += f"Da tao: {len(cards)} the\n"
        msg += f"Tong the: {len(self.cards[user_id])}\n\n"
        
        for i, card in enumerate(cards, 1):
            msg += f"**{i}. {card.get('front', '?')}**\n"
            msg += f"||{card.get('back', '?')}||\n\n"
        
        await ctx.send(msg)

    async def review_flashcard(self, ctx, topic: str = None):
        import random
        user_id = str(ctx.author.id)
        
        if user_id not in self.cards or not self.cards[user_id]:
            await ctx.send("Ban chua co flashcard. Go !flashcard <topic> de tao.")
            return
        
        user_cards = self.cards[user_id]
        if topic:
            user_cards = [c for c in user_cards if c.get("topic", "").lower() == topic.lower()]
        
        if not user_cards:
            await ctx.send(f"Khong co flashcard cho topic {topic}.")
            return
        
        card = random.choice(user_cards)
        
        msg = f"# ON TAP FLASHCARD\n\n"
        msg += f"**Topic:** {card.get('topic', '?')}\n"
        msg += f"**Cau hoi:** {card.get('front', '?')}\n\n"
        msg += f"**Dap an:** ||{card.get('back', '?')}||\n"
        
        card["review_count"] = card.get("review_count", 0) + 1
        self._save_cards()
        
        await ctx.send(msg)

    async def auto_create_cards(self, member, topic, score, **kwargs):
        if score < 3.5:
            print(f"[Flashcard] Recommend for {member} (score={score})")
        return None