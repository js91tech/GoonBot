"""Drug trade — grow product in a lab and deal it on the street or black market."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.drug_ui import send_drug_lab_panel, send_drug_market_panel
from utils.helpers import guild_only_message

logger = logging.getLogger(__name__)


class Drugs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    drugs_group = app_commands.Group(
        name="drugs",
        description="Grow, harvest, and deal contraband for high-risk profit.",
        guild_only=True,
    )

    @drugs_group.command(name="lab", description="Open your grow lab: plant, harvest, and sell.")
    async def lab(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        await send_drug_lab_panel(interaction, self)

    @drugs_group.command(name="market", description="Browse and trade on the black market.")
    async def market(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        await send_drug_market_panel(interaction, self)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Drugs(bot))
