# hub_ui.py
"""
Hub UI - Discord UI Components cho Plugin Hub
"""
import discord
from discord import ui


# ============================================================
# PLUGIN LIST VIEW (có pagination)
# ============================================================

class PluginListView(ui.View):
    """View hiển thị danh sách plugins với pagination"""

    def __init__(self, plugins, hub, title="📦 Plugin Hub", per_page=3, timeout=120):
        super().__init__(timeout=timeout)
        self.plugins = plugins
        self.hub = hub
        self.title = title
        self.per_page = per_page
        self.page = 0
        self.total_pages = max(1, (len(plugins) + per_page - 1) // per_page)

        # Disable buttons if only 1 page
        if self.total_pages <= 1:
            self.prev_btn.disabled = True
            self.next_btn.disabled = True

    def build_embed(self) -> discord.Embed:
        """Build embed cho trang hiện tại"""
        start = self.page * self.per_page
        end = start + self.per_page
        page_plugins = self.plugins[start:end]

        embed = discord.Embed(
            title=self.title,
            description=f"**{len(self.plugins)} plugins** · Trang {self.page + 1}/{self.total_pages}",
            color=discord.Color.blue(),
        )

        for p in page_plugins:
            status_icon = "✅" if p.get("installed") else "📥"
            rating_stars = "⭐" * int(p.get("rating", 4))
            size_kb = p.get("size_kb", 0)

            value = (
                f"*{p['description'][:100]}*\n"
                f"**Category:** {p['category']} · **Author:** {p['author']}\n"
                f"{rating_stars} {p.get('rating', '?')} ({p.get('reviews', 0)} reviews) · "
                f"📥 {p.get('downloads', 0)} · `{size_kb} KB`\n"
                f"**Status:** {'✅ Đã cài' if p.get('installed') else '⚪ Chưa cài'}"
            )

            embed.add_field(
                name=f"{status_icon} {p['name']} v{p['version']}",
                value=value,
                inline=False,
            )

        embed.set_footer(text="Dùng các nút bên dưới để điều hướng")
        return embed

    @ui.button(label="◀ Trước", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: ui.Button):
        if self.page > 0:
            self.page -= 1

        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.total_pages - 1

        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Sau ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1

        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.total_pages - 1

        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔍 Tìm kiếm", style=discord.ButtonStyle.primary, row=1)
    async def search_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = SearchModal(self.hub, interaction.message)
        await interaction.response.send_modal(modal)

    @ui.button(label="📁 Danh mục", style=discord.ButtonStyle.secondary, row=1)
    async def categories_btn(self, interaction: discord.Interaction, button: ui.Button):
        plugins = self.hub.list_plugins()
        categories = {}
        for p in plugins:
            cat = p["category"]
            categories[cat] = categories.get(cat, 0) + 1

        msg = "# 📁 DANH MỤC\n\n"
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            msg += f"**{cat}** – {count} plugins\n"

        await interaction.response.send_message(msg, ephemeral=True)

    @ui.button(label="🔄 Refresh", style=discord.ButtonStyle.success, row=1)
    async def refresh_btn(self, interaction: discord.Interaction, button: ui.Button):
        self.hub.refresh_registry()
        self.plugins = self.hub.list_plugins()
        self.page = 0
        self.total_pages = max(1, (len(self.plugins) + self.per_page - 1) // self.per_page)

        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)


# ============================================================
# PLUGIN DETAIL VIEW
# ============================================================

class PluginDetailView(ui.View):
    """View chi tiết 1 plugin"""

    def __init__(self, plugin: dict, hub, timeout=120):
        super().__init__(timeout=timeout)
        self.plugin = plugin
        self.hub = hub

        # Update button based on install status
        if plugin.get("installed"):
            self.install_btn.label = "🗑️ Gỡ cài đặt"
            self.install_btn.style = discord.ButtonStyle.danger
        else:
            self.install_btn.label = "📥 Cài đặt"
            self.install_btn.style = discord.ButtonStyle.success

    def build_embed(self) -> discord.Embed:
        """Build embed chi tiết"""
        p = self.plugin
        rating_stars = "⭐" * int(p.get("rating", 4))

        embed = discord.Embed(
            title=f"📦 {p['name']}",
            description=p.get("description", ""),
            color=discord.Color.green() if p.get("installed") else discord.Color.blue(),
        )

        # Row 1: Basic info
        embed.add_field(name="Version", value=f"`{p['version']}`", inline=True)
        embed.add_field(name="Author", value=p["author"], inline=True)
        embed.add_field(name="Category", value=p["category"], inline=True)

        # Row 2: Extra info
        embed.add_field(name="License", value=p.get("license", "MIT"), inline=True)
        embed.add_field(name="Size", value=f"{p.get('size_kb', 0)} KB", inline=True)
        embed.add_field(
            name="Status",
            value="✅ Đã cài" if p.get("installed") else "⚪ Chưa cài",
            inline=True,
        )

        # Rating
        embed.add_field(
            name="Rating",
            value=f"{rating_stars} {p.get('rating', '?')} ({p.get('reviews', 0)} reviews)",
            inline=False,
        )

        # Downloads
        embed.add_field(
            name="Downloads",
            value=f"📥 {p.get('downloads', 0):,}",
            inline=False,
        )

        # Tags
        tags = p.get("tags", [])
        if tags:
            embed.add_field(
                name="Tags",
                value=" ".join(f"`{t}`" for t in tags),
                inline=False,
            )

        # Verified
        if p.get("verified"):
            embed.add_field(
                name="✅ Verified",
                value="Plugin đã được kiểm duyệt",
                inline=False,
            )

        # Homepage
        if p.get("homepage"):
            embed.add_field(
                name="🔗 Homepage",
                value=p["homepage"],
                inline=False,
            )

        return embed

    @ui.button(label="📥 Cài đặt", style=discord.ButtonStyle.success, row=0)
    async def install_btn(self, interaction: discord.Interaction, button: ui.Button):
        plugin_id = self.plugin["id"]

        if self.plugin.get("installed"):
            # Uninstall
            result = self.hub.uninstall(plugin_id)

            if result["success"]:
                await interaction.response.send_message(
                    f"✅ {result['message']}\n🔄 Restart bot để áp dụng.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"❌ {result['message']}",
                    ephemeral=True,
                )
        else:
            # Install
            result = self.hub.install(plugin_id)

            if result["success"]:
                await interaction.response.send_message(
                    f"✅ **CÀI ĐẶT THÀNH CÔNG**\n\n"
                    f"{result['message']}\n\n"
                    f"🔄 **Restart bot để load plugin:**\n"
                    f"```\npython bot.py\n```",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"❌ {result['message']}",
                    ephemeral=True,
                )

    @ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_btn(self, interaction: discord.Interaction, button: ui.Button):
        # Refresh plugin data
        updated = self.hub.get_plugin(self.plugin["id"])
        if updated:
            self.plugin = updated

        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="⬅️ Quay lại", style=discord.ButtonStyle.secondary, row=0)
    async def back_btn(self, interaction: discord.Interaction, button: ui.Button):
        plugins = self.hub.list_plugins()
        view = PluginListView(plugins, self.hub, "📦 Plugin Hub")
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ============================================================
# SEARCH MODAL
# ============================================================

class SearchModal(ui.Modal, title="🔍 Tìm kiếm Plugin"):
    """Modal nhập query search"""

    query = ui.TextInput(
        label="Từ khóa",
        placeholder="VD: quiz, socratic, ai...",
        min_length=1,
        max_length=50,
        required=True,
    )

    def __init__(self, hub, original_message=None):
        super().__init__()
        self.hub = hub
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        """Xử lý khi submit"""
        results = self.hub.search(self.query.value)

        if not results:
            await interaction.response.send_message(
                f"❌ Không tìm thấy plugin nào cho `{self.query.value}`.",
                ephemeral=True,
            )
            return

        view = PluginListView(
            results,
            self.hub,
            f"🔍 Kết quả: {self.query.value}",
        )
        embed = view.build_embed()

        await interaction.response.send_message(embed=embed, view=view)