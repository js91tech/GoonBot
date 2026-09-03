"""GoonCards slash command — collect, buy packs, sell, and market."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.cards_hub_ui import send_cards_hub
from utils.helpers import guild_only_message


class Cards(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="cards", description="Open GoonCards — binder, packs, market, collection.")
    @app_commands.guild_only()
    async def cards(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        await send_cards_hub(self, interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Cards(bot))
