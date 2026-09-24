# plugin_commands.py
"""
Plugin Commands - Commands để manage plugins
"""
import discord
from discord.ext import commands


def setup_plugin_commands(bot, plugin_loader, is_admin):
    """Setup plugin management commands"""

    @bot.command(name="plugins")
    async def plugins_cmd(ctx):
        """List all loaded plugins"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return

        loaded = plugin_loader.list_loaded()

        if not loaded:
            await ctx.send("📦 Chưa có plugin nào được load.")
            return

        msg = "# 📦 LOADED PLUGINS\n\n"
        for p in loaded:
            msg += f"**{p['name']}** v{p['version']}\n"
            msg += f"  _{p['author']}_\n"
            msg += f"  ID: `{p['id']}`\n\n"

        await ctx.send(msg)

    @bot.command(name="plugin_info")
    async def plugin_info_cmd(ctx, plugin_id: str):
        """Get plugin info"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return

        info = plugin_loader.get_plugin_info(plugin_id)

        if not info:
            await ctx.send(f"❌ Plugin `{plugin_id}` không tìm thấy.")
            return

        m = info["manifest"]
        msg = f"# 📦 {m['name']}\n\n"
        msg += f"**ID:** `{m['id']}`\n"
        msg += f"**Version:** {m['version']}\n"
        msg += f"**Author:** {m['author']}\n"
        msg += f"**Category:** {m['category']}\n"
        msg += f"**License:** {m['license']}\n\n"
        msg += f"**Description:**\n{m['description']}\n\n"
        msg += f"**Permissions:**\n"
        for p in m['permissions']:
            msg += f"- `{p}`\n"

        await ctx.send(msg)

    @bot.command(name="plugin_load")
    async def plugin_load_cmd(ctx, plugin_id: str):
        """Load a plugin"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return

        success, message = plugin_loader.load_plugin(plugin_id)

        if success:
            await ctx.send(f"✅ {message}")
        else:
            await ctx.send(f"❌ {message}")

    @bot.command(name="plugin_unload")
    async def plugin_unload_cmd(ctx, plugin_id: str):
        """Unload a plugin"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return

        success, message = plugin_loader.unload_plugin(plugin_id)

        if success:
            await ctx.send(f"✅ {message}")
        else:
            await ctx.send(f"❌ {message}")

    @bot.command(name="plugin_discover")
    async def plugin_discover_cmd(ctx):
        """Discover all available plugins"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return

        plugins = plugin_loader.discover_plugins()

        if not plugins:
            await ctx.send("📦 Không có plugin nào trong `plugins/`.")
            return

        msg = "# 🔍 DISCOVERED PLUGINS\n\n"
        for p in plugins:
            loaded = "✅" if p.id in plugin_loader.loaded_plugins else "⚪"
            msg += f"{loaded} **{p.name}** v{p.version}\n"
            msg += f"  ID: `{p.id}` | Category: {p.category}\n\n"

        await ctx.send(msg)