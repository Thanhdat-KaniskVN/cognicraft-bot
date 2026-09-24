# hub_commands.py
"""
Hub Commands - Discord commands cho Plugin Hub
"""
import discord
from hub_ui import PluginListView, PluginDetailView, SearchModal


def setup_hub_commands(bot, hub, is_admin):
    """Setup hub commands"""

    @bot.command(name="hub")
    async def hub_cmd(ctx):
        """Mở Plugin Hub"""
        plugins = hub.list_plugins()

        if not plugins:
            await ctx.send("📦 Hub đang trống. Thử `!hub_refresh` để cập nhật.")
            return

        view = PluginListView(plugins, hub, "📦 Plugin Hub")
        embed = view.build_embed()
        await ctx.send(embed=embed, view=view)

    @bot.command(name="hub_featured")
    async def hub_featured_cmd(ctx):
        """Xem plugins nổi bật"""
        plugins = hub.get_featured()

        if not plugins:
            await ctx.send("⭐ Chưa có plugin nổi bật.")
            return

        view = PluginListView(plugins, hub, "⭐ Featured Plugins")
        embed = view.build_embed()
        await ctx.send(embed=embed, view=view)

    @bot.command(name="hub_search")
    async def hub_search_cmd(ctx, *, query: str = None):
        """Tìm kiếm plugin. Nếu không có query → mở modal."""
        if query is None:
            # Mở modal search
            modal = SearchModal(hub, None)
            await ctx.send("🔍 Nhấn nút bên dưới để tìm kiếm.", view=SearchButtonView(hub))
            return

        results = hub.search(query)

        if not results:
            await ctx.send(f"❌ Không tìm thấy plugin nào cho `{query}`.")
            return

        view = PluginListView(results, hub, f"🔍 Kết quả: {query}")
        embed = view.build_embed()
        await ctx.send(embed=embed, view=view)

    @bot.command(name="hub_info")
    async def hub_info_cmd(ctx, plugin_id: str):
        """Xem chi tiết plugin"""
        plugin = None
        for p in hub.registry.get("plugins", []):
            if p["id"] == plugin_id:
                plugin = p
                break

        if not plugin:
            await ctx.send(f"❌ Plugin `{plugin_id}` không tìm thấy.")
            return

        view = PluginDetailView(plugin, hub)
        embed = view.build_embed()
        await ctx.send(embed=embed, view=view)

    @bot.command(name="hub_install")
    async def hub_install_cmd(ctx, plugin_id: str):
        """Cài đặt plugin"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return

        await ctx.send(f"📥 Đang cài `{plugin_id}`...")

        result = hub.install(plugin_id)

        if result["success"]:
            embed = discord.Embed(
                title="✅ CÀI ĐẶT THÀNH CÔNG",
                description=result["message"],
                color=discord.Color.green(),
            )
            embed.add_field(
                name="🚀 Restart bot",
                value="`python bot.py`",
                inline=False,
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {result['message']}")

    @bot.command(name="hub_uninstall")
    async def hub_uninstall_cmd(ctx, plugin_id: str):
        """Gỡ cài đặt plugin"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return

        result = hub.uninstall(plugin_id)

        if result["success"]:
            await ctx.send(f"✅ {result['message']}")
        else:
            await ctx.send(f"❌ {result['message']}")

    @bot.command(name="hub_refresh")
    async def hub_refresh_cmd(ctx):
        """Refresh registry"""
        await ctx.send("🔄 Đang refresh registry...")

        try:
            # Force rebuild từ example_plugins/
            plugins = hub.list_plugins()
            stats = hub.get_stats()

            embed = discord.Embed(
                title="✅ REFRESH THÀNH CÔNG",
                description=f"Đã cập nhật registry ({len(plugins)} plugins)",
                color=discord.Color.green(),
            )
            embed.add_field(name="Total plugins", value=stats["total_plugins"], inline=True)
            embed.add_field(name="Installed", value=stats["installed"], inline=True)
            embed.add_field(name="Categories", value=stats["categories"], inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Refresh thất bại: {e}")
            print(f"[Hub] Refresh error: {e}")

    @bot.command(name="hub_updates")
    async def hub_updates_cmd(ctx):
        """Check for updates"""
        updates = hub.check_updates()

        if not updates:
            await ctx.send("✅ Tất cả plugins đã cập nhật mới nhất.")
            return

        msg = "# 🔄 CÓ BẢN CẬP NHẬT\n\n"
        for u in updates:
            msg += f"**{u['name']}**\n"
            msg += f"  `{u['installed']}` → `{u['available']}`\n\n"

        msg += "Dùng `!hub_install <id>` để cập nhật."

        await ctx.send(msg)

    @bot.command(name="hub_stats")
    async def hub_stats_cmd(ctx):
        """Hub statistics"""
        stats = hub.get_stats()

        embed = discord.Embed(
            title="📊 HUB STATS",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Total Plugins", value=stats["total_plugins"], inline=True)
        embed.add_field(name="Installed", value=stats["installed"], inline=True)
        embed.add_field(name="Available", value=stats["available"], inline=True)
        embed.add_field(name="Categories", value=stats["categories"], inline=True)

        await ctx.send(embed=embed)
 # ============================================================
# SEARCH BUTTON VIEW
# ============================================================

from discord import ui as discord_ui


class SearchButtonView(discord_ui.View):
    """View chỉ có 1 nút mở modal search"""

    def __init__(self, hub, timeout=60):
        super().__init__(timeout=timeout)
        self.hub = hub

    @discord_ui.button(label="🔍 Tìm kiếm", style=discord.ButtonStyle.primary)
    async def search_button(self, interaction: discord.Interaction, button: discord_ui.Button):
        modal = SearchModal(self.hub, None)
        await interaction.response.send_modal(modal)       