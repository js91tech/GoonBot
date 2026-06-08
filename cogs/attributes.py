from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.attributes_ui import send_attributes_panel
from utils.character_attributes import (
    STAT_EMOJI,
    STAT_KEYS,
    STAT_LABELS,
    CharacterAttributes,
    format_attributes_block,
    normalize_stat_name,
    stat_cap_for_prestige,
    total_point_pool_cap,
    unspent_attribute_points,
)
from utils.helpers import guild_only_message


class Attributes(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="attributes",
        description="View or allocate STR/DEX/AGI/DEF/VIT (reduces boss debuffs, boosts combat).",
    )
    @app_commands.describe(
        user="Player to inspect (defaults to you).",
        stat="Stat to raise: strength, dexterity, agility, defense, or vitality.",
        points="How many points to allocate (omit to open the panel).",
    )
    @app_commands.guild_only()
    async def attributes(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        stat: str | None = None,
        points: app_commands.Range[int, 1, 25] | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        target = user or interaction.user
        if not isinstance(target, discord.Member):
            await interaction.response.send_message("Member not found.", ephemeral=True)
            return

        if stat is not None and points is not None:
            if target.id != interaction.user.id:
                await interaction.response.send_message(
                    "You can only allocate your own attributes.",
                    ephemeral=True,
                )
                return
            ok, message = await self.bot.db.allocate_attribute_points(
                interaction.user.id,
                interaction.guild_id,
                stat,
                points,
            )
            if not ok:
                await interaction.response.send_message(message, ephemeral=True)
                return
            await send_attributes_panel(interaction, self, target=interaction.user)
            return

        if stat is not None or points is not None:
            await interaction.response.send_message(
                "Provide both **stat** and **points** to allocate via command, or omit both for the panel.",
                ephemeral=True,
            )
            return

        await send_attributes_panel(interaction, self, target=target)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Attributes(bot))
