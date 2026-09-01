"""Profile / chaos buttons into the goon session loop."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.goon_session import format_session_block
from utils.goon_theme import branded_embed, panel_title
from utils.helpers import fmt_amount

if TYPE_CHECKING:
    from discord.ext import commands

    from database import Database


async def build_goon_session_embed(db: Database, member: discord.Member, guild_id: int) -> discord.Embed:
    import config

    state = await db.get_goon_session(member.id, guild_id)
    embed = branded_embed(
        panel_title("Goon session", member_name=member.display_name),
        description=format_session_block(state),
    )
    embed.add_field(
        name="Commands",
        value=(
            "`/goon edge` · `/goon finish` · `/goon ruin` · `/goon tease` · `/goon dare`\n"
            f"Tease costs **{fmt_amount(config.GOON_TEASE_COST)}** (Hosts cheaper). "
            "Chat, VC, jobs, and `/daily` also fill the meter. "
            "Every 145 minutes the main chat asks if you're ready (Velvet art attached) — first yes wins house-pot goonbux + condoms, then a group round."
        ),
        inline=False,
    )
    return embed


class GoonSessionHubView(discord.ui.View):
    def __init__(self, cog: commands.Cog, guild_id: int, user_id: int) -> None:
        super().__init__(timeout=180.0)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your session.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Edge", style=discord.ButtonStyle.primary, row=0)
    async def edge_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        goon = self.cog.bot.get_cog("Goon")
        if goon is None:
            await interaction.response.send_message("Use `/goon edge`.", ephemeral=True)
            return
        await goon.run_edge(interaction)

    @discord.ui.button(label="Finish", style=discord.ButtonStyle.success, row=0)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        goon = self.cog.bot.get_cog("Goon")
        if goon is None:
            await interaction.response.send_message("Use `/goon finish`.", ephemeral=True)
            return
        await goon.run_finish(interaction)

    @discord.ui.button(label="Ruin me", style=discord.ButtonStyle.danger, row=0)
    async def ruin_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        goon = self.cog.bot.get_cog("Goon")
        if goon is None:
            await interaction.response.send_message("Use `/goon ruin`.", ephemeral=True)
            return
        await goon.run_ruin(interaction, user=None)

    @discord.ui.button(label="Dare", style=discord.ButtonStyle.secondary, row=0)
    async def dare_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        goon = self.cog.bot.get_cog("Goon")
        if goon is None:
            await interaction.response.send_message("Use `/goon dare`.", ephemeral=True)
            return
        await goon.run_dare(interaction)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Tease someone…",
        min_values=1,
        max_values=1,
        row=1,
    )
    async def tease_select(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect,
    ) -> None:
        goon = self.cog.bot.get_cog("Goon")
        if goon is None:
            await interaction.response.send_message("Use `/goon tease`.", ephemeral=True)
            return
        picked = select.values[0]
        if not isinstance(picked, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        await goon.run_tease(interaction, picked)
