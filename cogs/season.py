from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.helpers import guild_only_message


class Season(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="season", description="Duel ELO season status or admin reset.")
    @app_commands.describe(action="Status or reset (admin)")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Status", value="status"),
            app_commands.Choice(name="Reset ELO (admin)", value="reset"),
        ],
    )
    @app_commands.guild_only()
    async def season(self, interaction: discord.Interaction, action: str) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        guild_id = interaction.guild_id

        if action == "reset":
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Admin only.", ephemeral=True)
                return
            new_season = await self.bot.db.reset_elo_season(guild_id)
            await interaction.response.send_message(
                f"**Season {new_season}** started. All duel ELO ratings reset to "
                f"**{config.DUEL_ELO_START}**.",
                ephemeral=True,
            )
            return

        season_num, last_reset = await self.bot.db.get_elo_season(guild_id)
        rating, wins, losses = await self.bot.db.get_duel_elo(
            interaction.user.id, guild_id,
        )
        reset_text = (
            "Never"
            if last_reset <= 0
            else f"<t:{int(last_reset)}:R>"
        )
        await interaction.response.send_message(
            f"**Season {season_num}** · Last reset: {reset_text}\n"
            f"Your ELO: **{rating}** ({wins}W / {losses}L)\n"
            f"Admins can run `/season` → **Reset ELO** to start a new ranked season.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Season(bot))
