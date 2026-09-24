# core_api.py
"""
Core API - Bridge cho plugins gọi core services
- Data access (scores, insights, ...)
- AI service
- Discord API
- Config
- Events
"""
import asyncio
from typing import Any, Dict, List, Optional


class CoreAPI:
    """API cho plugins"""

    def __init__(self, modules):
        """
        Args:
            modules: Dict chứa các core modules
        """
        self.modules = modules
        self.plugin_id = None  # Set khi plugin gọi

    # ============================================================
    # DATA ACCESS
    # ============================================================

    async def get_scores(self, week=None, member=None) -> List[Dict]:
        """Lấy scores"""
        self._check_permission("read:scores")

        get_week_scores = self.modules["get_week_scores"]
        get_pending_score = self.modules["get_pending_score"]

        if member and week:
            return [get_pending_score(week, member)]
        elif week:
            return get_week_scores(week)

        return []

    async def save_scores(self, week, member, scores) -> bool:
        """Lưu scores"""
        self._check_permission("write:scores")

        save_score = self.modules["save_score"]
        save_score(week, member, scores, source="plugin")
        return True

    async def get_insights(self, topic=None, limit=10) -> List[Dict]:
        """Lấy insights"""
        self._check_permission("read:insights")

        sheets = self.modules.get("sheets")
        if not sheets:
            return []

        return await asyncio.to_thread(sheets.load_insights, topic)

    async def get_members(self) -> List[str]:
        """Lấy danh sách members"""
        return self.modules["ALL_MEMBERS"]

    async def get_current_week(self) -> int:
        """Lấy tuần hiện tại"""
        get_current_week = self.modules["get_current_week"]
        return get_current_week()

    async def get_time_info(self) -> Dict:
        """Lấy thông tin thời gian"""
        time_tracker = self.modules["time_tracker"]
        return time_tracker.get_current_info()

    # ============================================================
    # AI SERVICE
    # ============================================================

    async def call_ai(self, prompt, task_type="default", max_tokens=None) -> Dict:
        """Gọi AI"""
        self._check_permission("call:ai")

        from ai_provider import call_ai_json
        return await asyncio.to_thread(
            call_ai_json, prompt, max_tokens, 3, task_type
        )

    # ============================================================
    # DISCORD API
    # ============================================================

    async def send_message(self, channel_id, content=None, embed=None):
        """Gửi message đến channel"""
        self._check_permission("send:messages")

        bot = self.modules["bot"]
        channel = bot.get_channel(channel_id)

        if not channel:
            return False

        await channel.send(content=content, embed=embed)
        return True

    async def send_dm(self, user_id, content=None, embed=None):
        """Gửi DM cho user"""
        self._check_permission("send:dm")

        bot = self.modules["bot"]
        user = await bot.fetch_user(user_id)

        if not user:
            return False

        await user.send(content=content, embed=embed)
        return True

    # ============================================================
    # CONFIG
    # ============================================================

    def get_config(self, key, default=None):
        """Lấy config"""
        self._check_permission("read:config")

        from config import __dict__ as config_dict
        return config_dict.get(key, default)

    # ============================================================
    # EVENTS
    # ============================================================

    async def emit_event(self, event_name, **kwargs):
        """Emit event"""
        event_bus = self.modules.get("event_bus")
        if event_bus:
            await event_bus.emit(event_name, **kwargs)

    # ============================================================
    # PERMISSIONS
    # ============================================================

    def _check_permission(self, permission):
        """Check permission của plugin"""
        if not self.plugin_id:
            return  # Core call

        loader = self.modules.get("plugin_loader")
        if not loader:
            return

        plugin = loader.loaded_plugins.get(self.plugin_id)
        if not plugin:
            raise PermissionError(f"Plugin {self.plugin_id} not loaded")

        manifest = plugin["manifest"]
        if permission not in manifest.permissions:
            raise PermissionError(
                f"Plugin {self.plugin_id} lacks permission: {permission}"
            )