# jarvis/interactive.py
"""Discord Views cho conflict resolution (buttons)."""
import asyncio
import discord
from datetime import datetime, timedelta

from jarvis.chain_rescheduler import build_chain, apply_chain, format_chain_preview
from jarvis.conflict_detector import detect_conflicts, suggest_slots, _parse_dt


ICONS = {
    "gym": "GYM", "run": "RUN", "bike": "BIKE", "swim": "SWIM", "yoga": "YOGA",
    "class": "CLASS", "exam": "EXAM", "meeting": "MEET",
    "study": "STUDY", "task": "TASK", "other": "OTHER",
}


def _fmt(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%H:%M %a %d/%m")


class ChainConfirmView(discord.ui.View):
    """View hien thi chain preview + [Apply] [Change] [Cancel]."""

    def __init__(self, user_id, member, new_event, plan, timeout=120):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.member = member
        self.new_event = new_event
        self.plan = plan
        self.applied = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "Chi nguoi tao lenh moi duoc doi lich!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Ap dung", emoji="✅", style=discord.ButtonStyle.success)
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.applied:
            await interaction.response.send_message("Da apply roi!", ephemeral=True)
            return

        await interaction.response.defer()
        applied = await asyncio.to_thread(apply_chain, self.user_id, self.plan["chain"])
        self.applied = True

        # Update GCal cho tung event
        try:
            from jarvis.gcal_sync import push_event_async
            for item in self.plan["chain"]:
                ev = item["event"]
                gcal_id = ev.get("gcal_event_id")
                if gcal_id:
                    # TODO: update GCal event time
                    pass
        except Exception as e:
            print(f"[ChainView] GCal update: {e}")

        # Add new event vao DB
        try:
            from jarvis import event_manager as em
            from jarvis.gcal_sync import push_event_async
            new_id = await asyncio.to_thread(
                em.create_event,
                self.user_id, self.member,
                self.new_event.title, self.new_event.event_type,
                self.new_event.start_time, self.new_event.end_time,
                self.new_event.location,
            )
            # Push GCal cho event moi
            gcal = await push_event_async(
                title=self.new_event.title,
                start_dt=self.new_event.start_time,
                end_dt=self.new_event.end_time,
                description=f"JARVIS {self.new_event.event_type}",
            )
            if gcal and gcal.get("id"):
                await asyncio.to_thread(
                    em.update_event, new_id,
                    gcal_event_id=gcal["id"],
                    gcal_html_link=gcal.get("htmlLink"),
                )
        except Exception as e:
            print(f"[ChainView] New event fail: {e}")

        embed = discord.Embed(
            title="DA AP DUNG CHAIN RESCHEDULE",
            description=f"Da doi {len(applied)} events + them 1 event moi",
            color=discord.Color.green(),
        )
        lines = []
        for item in self.plan["chain"]:
            ev = item["event"]
            lines.append(f"`#{ev['id']}` {ev['title']}: {item['old_start'].strftime('%H:%M')} -> **{item['new_start'].strftime('%H:%M')}**")
        embed.add_field(name="Events da doi", value="\n".join(lines[:10]) or "None", inline=False)
        embed.add_field(name="Event moi", value=f"**{self.new_event.title}** @ {_fmt(self.new_event.start_time)}", inline=False)
        embed.set_footer(text="!j de xem lich")

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Doi gio khac", emoji="🔄", style=discord.ButtonStyle.primary)
    async def change_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        suggestions = self.plan.get("suggestions", [])
        sug_txt = ""
        if suggestions:
            sug_txt = "\n**Khung gio trong goi y:**\n"
            for i, s in enumerate(suggestions[:3], 1):
                sug_txt += f"  {i}. `{s['start'].strftime('%H:%M %a %d/%m')}`\n"
        await interaction.response.send_message(
            f"Go lai lenh voi gio moi:\n"
            f"```\n!j {self.new_event.title} 16:30\n```{sug_txt}",
            ephemeral=True,
        )

    @discord.ui.button(label="Huy", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Da huy",
            description=f"Khong thay doi lich. Event moi **{self.new_event.title}** khong duoc them.",
            color=discord.Color.greyple(),
        )
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)
        self.stop()


class ConflictView(discord.ui.View):
    """View hien thi khi co conflict - [Xem chain] [Doi gio] [Huy]."""

    def __init__(self, user_id, member, new_event, conflicts, suggestions, timeout=120):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.member = member
        self.new_event = new_event
        self.conflicts = conflicts
        self.suggestions = suggestions

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("Chi nguoi tao lenh moi duoc tuong tac!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Xem chain reschedule", emoji="📅", style=discord.ButtonStyle.primary)
    async def chain_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        # Build chain
        plan = await asyncio.to_thread(
            build_chain,
            self.user_id,
            self.new_event.start_time,
            self.new_event.end_time,
            self.new_event.event_type,
        )
        plan["suggestions"] = self.suggestions

        if not plan["chain"]:
            await interaction.followup.send("Khong co chain nao can doi.", ephemeral=True)
            return

        # Show chain preview + buttons
        preview = format_chain_preview(plan["chain"])

        embed = discord.Embed(
            title="CHAIN RESCHEDULE - PREVIEW",
            description=preview[:2000],
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="Event moi se them",
            value=f"**{self.new_event.title}** @ {_fmt(self.new_event.start_time)} -> {self.new_event.end_time.strftime('%H:%M')}",
            inline=False,
        )
        embed.set_footer(text=f"{len(plan['chain'])} events se bi doi | Chain se chay tuan tu, giu khoang nghi 5 phut")

        view = ChainConfirmView(self.user_id, self.member, self.new_event, plan)
        await interaction.message.edit(embed=embed, view=view)

    @discord.ui.button(label="Doi gio khac", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def change_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        sug_txt = "\n**Khung gio trong goi y:**\n"
        for i, s in enumerate(self.suggestions[:3], 1):
            sug_txt += f"  {i}. `{s['start'].strftime('%H:%M %a %d/%m')}`\n"
        await interaction.response.send_message(
            f"Go lai lenh voi gio moi:\n"
            f"```\n!j {self.new_event.title} <HH:MM>\n```{sug_txt}",
            ephemeral=True,
        )

    @discord.ui.button(label="Huy", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Da huy",
            description=f"Event moi **{self.new_event.title}** khong duoc them.",
            color=discord.Color.greyple(),
        )
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)
        self.stop()


def build_conflict_embed(user_member, new_event, conflicts, suggestions):
    """Build embed cho ConflictView."""
    icon = ICONS.get(new_event.event_type, "TASK")
    embed = discord.Embed(
        title="PHAT HIEN XUNG DOT",
        description=f"Event moi **{icon} {new_event.title}** bi trung voi {len(conflicts)} event khac.",
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Event moi",
        value=f"`{_fmt(new_event.start_time)} -> {new_event.end_time.strftime('%H:%M')}`",
        inline=False,
    )

    conf_lines = []
    for c in conflicts[:5]:
        c_start = _parse_dt(c["start_time"])
        c_end = _parse_dt(c["end_time"]) if c.get("end_time") else c_start + timedelta(hours=1)
        icon_c = ICONS.get(c.get("event_type", "task"), "TASK")
        conf_lines.append(f"`#{c['id']}` {icon_c} **{c['title']}** @ {c_start.strftime('%H:%M')}-{c_end.strftime('%H:%M')}")
    embed.add_field(name="Trung voi", value="\n".join(conf_lines), inline=False)

    if suggestions:
        sug_lines = [f"{i}. `{s['start'].strftime('%H:%M %a %d/%m')}`" for i, s in enumerate(suggestions[:3], 1)]
        embed.add_field(name="Khung gio trong goi y", value="\n".join(sug_lines), inline=False)

    embed.set_footer(text="Chon hanh dong ben duoi hoac doi gio khac")
    return embed


if __name__ == "__main__":
    print("[OK] interactive.py loaded")
    print(f"  ChainConfirmView: {ChainConfirmView}")
    print(f"  ConflictView:     {ConflictView}")