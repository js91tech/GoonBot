from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.character_attributes import (
    STAT_EMOJI,
    STAT_KEYS,
    STAT_LABELS,
    CharacterAttributes,
    format_attributes_block,
    normalize_stat_name,
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
        points="How many points to allocate (omit to view only).",
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
        guild_id = interaction.guild_id
        row = await self.bot.db.get_user_character(target.id, guild_id)
        progress = await self.bot.db.get_user_progress(target.id, guild_id)
        prestige_level = int(progress["prestige_level"])
        attrs = CharacterAttributes.from_row(row)
        class_xp = int(row["class_xp"])

        if stat is not None and points is not None:
            if target.id != interaction.user.id:
                await interaction.response.send_message(
                    "You can only allocate your own attributes.",
                    ephemeral=True,
                )
                return
            ok, message = await self.bot.db.allocate_attribute_points(
                interaction.user.id,
                guild_id,
                stat,
                points,
            )
            if not ok:
                await interaction.response.send_message(message, ephemeral=True)
                return
            row = await self.bot.db.get_user_character(interaction.user.id, guild_id)
            progress = await self.bot.db.get_user_progress(interaction.user.id, guild_id)
            prestige_level = int(progress["prestige_level"])
            attrs = CharacterAttributes.from_row(row)
            class_xp = int(row["class_xp"])
            embed = discord.Embed(
                title="Attributes updated",
                description=f"{message}\n\n{format_attributes_block(attrs, class_xp=class_xp, prestige_level=prestige_level)}",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if stat is not None or points is not None:
            await interaction.response.send_message(
                "Provide both **stat** and **points** to allocate, or omit both to view.",
                ephemeral=True,
            )
            return

        unspent = unspent_attribute_points(attrs, class_xp, prestige_level)
        help_line = ""
        if target.id == interaction.user.id and unspent > 0:
            help_line = (
                f"\n\nAllocate with `/attributes stat:agility points:{min(unspent, 5)}` "
                f"(AGI reduces stun/root/chill)."
            )
        from utils.character_attributes import stat_cap_for_prestige

        stat_cap = stat_cap_for_prestige(prestige_level)
        stat_guide = (
            "**STR** — damage · **DEX** — crit · **AGI** — debuff resist "
            "· **DEF** — mitigation & burn/void resist · **VIT** — max HP\n"
            f"All stats start at **0**. Per-stat cap **{stat_cap}** "
            f"(**15** base + **1** per prestige, **25** at prestige 10). "
            f"First **20** earned points come quickly from class XP; later points cost more."
        )
        embed = discord.Embed(
            title=f"{target.display_name}'s Attributes",
            description=format_attributes_block(
                attrs, class_xp=class_xp, prestige_level=prestige_level,
            )
            + help_line,
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="What each stat does",
            value=stat_guide,
            inline=False,
        )
        embed.add_field(
            name="Stats",
            value=" · ".join(
                f"{STAT_EMOJI[name]} {STAT_LABELS[name]}" for name in STAT_KEYS
            ),
            inline=False,
        )
        if normalize_stat_name(stat or "") is None and stat:
            embed.set_footer(text=f"Unknown stat '{stat}'. Try agility, defense, vitality, etc.")
        await interaction.response.send_message(
            embed=embed,
            ephemeral=target.id != interaction.user.id,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Attributes(bot))
