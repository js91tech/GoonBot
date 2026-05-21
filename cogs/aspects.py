from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.aspects import (
    ASPECT_DEFINITIONS,
    format_aspect_effect,
    format_aspect_line,
    instance_from_row,
)
from utils.helpers import fmt_amount, guild_only_message


class Aspects(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def aspect_instance_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        rows = await self.bot.db.list_aspect_instances(
            interaction.user.id,
            interaction.guild_id,
        )
        equipped_id = await self.bot.db.get_equipped_aspect_instance_id(
            interaction.user.id,
            interaction.guild_id,
        )
        current_lower = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for row in rows:
            inst = instance_from_row(row)
            label = f"{inst.name} {inst.roll_pct:g}% (#{inst.instance_id})"
            if current_lower and current_lower not in label.lower():
                if current_lower not in str(inst.instance_id):
                    continue
            if equipped_id == inst.instance_id:
                label += " [equipped]"
            choices.append(
                app_commands.Choice(name=label[:100], value=str(inst.instance_id)),
            )
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(
        name="aspects",
        description="View your collected aspects (Diablo-style combat modifiers).",
    )
    @app_commands.describe(user="Player to inspect. Defaults to you.")
    @app_commands.guild_only()
    async def aspects(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        target = user or interaction.user
        rows = await self.bot.db.list_aspect_instances(target.id, interaction.guild_id)
        equipped_id = await self.bot.db.get_equipped_aspect_instance_id(
            target.id,
            interaction.guild_id,
        )
        if not rows:
            await interaction.response.send_message(
                f"{target.display_name} has no aspects yet. "
                f"Boss kills can drop them, or buy one for **{fmt_amount(config.ASPECT_SHOP_PRICE)}** with `/buy-aspect`.",
                ephemeral=True,
            )
            return
        lines = [
            format_aspect_line(
                instance_from_row(row),
                equipped=equipped_id == int(row["instance_id"]),
            )
            for row in rows
        ]
        embed = discord.Embed(
            title=f"{target.display_name}'s Aspects",
            description="\n".join(lines[:15]),
            color=discord.Color.purple(),
        )
        if len(lines) > 15:
            embed.set_footer(text=f"+{len(lines) - 15} more aspects")
        else:
            embed.set_footer(text="Use /equip-aspect with the instance id · /aspect-shop for catalog")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="aspect-shop",
        description="Browse aspect types and shop pricing.",
    )
    @app_commands.guild_only()
    async def aspect_shop(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        catalog = "\n".join(
            f"**{a.name}** — {a.description}" for a in ASPECT_DEFINITIONS
        )
        embed = discord.Embed(
            title="Aspect Shop",
            description=(
                f"Buy a random rolled aspect for **{fmt_amount(config.ASPECT_SHOP_PRICE)}** with `/buy-aspect`.\n"
                "Shop rolls land between **4%** and **14%**. Boss drops scale with threat tier "
                "(harder bosses = higher rolls, up to **40%** on mythic-tier raids).\n"
                "Utility aspects affect duels/hr, work income (up to **3×**), energy regen, "
                "duel loot, daily/passive gold, and more.\n\n"
                f"{catalog}"
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_footer(text="Equip one aspect at a time with /equip-aspect")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="buy-aspect",
        description=f"Buy a random aspect roll for {config.ASPECT_SHOP_PRICE:,.0f} nuggets.",
    )
    @app_commands.guild_only()
    async def buy_aspect(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        price = config.ASPECT_SHOP_PRICE
        instance_id = await self.bot.db.buy_aspect_from_shop(
            interaction.user.id,
            interaction.guild_id,
            price,
        )
        if instance_id is None:
            await interaction.response.send_message(
                f"You need **{fmt_amount(price)}** to buy an aspect.",
                ephemeral=True,
            )
            return
        row = await self.bot.db.get_aspect_instance(
            interaction.user.id,
            interaction.guild_id,
            instance_id,
        )
        if row is None:
            await interaction.response.send_message(
                "Purchase succeeded but aspect could not be loaded.",
                ephemeral=True,
            )
            return
        inst = instance_from_row(row)
        await interaction.response.send_message(
            f"You bought **{inst.name}** — {format_aspect_effect(inst)} (`aspect#{inst.instance_id}`). "
            f"Use `/equip-aspect {inst.instance_id}`.",
            ephemeral=True,
        )

    @app_commands.command(
        name="equip-aspect",
        description="Equip one aspect to boost combat (boss raids and duels).",
    )
    @app_commands.describe(instance_id="Aspect instance id from /aspects")
    @app_commands.autocomplete(instance_id=aspect_instance_autocomplete)
    @app_commands.guild_only()
    async def equip_aspect(
        self,
        interaction: discord.Interaction,
        instance_id: str,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        raw = instance_id.strip().lower().removeprefix("aspect#")
        try:
            iid = int(raw)
        except ValueError:
            await interaction.response.send_message(
                "Use the numeric id from `/aspects` (e.g. `42`).",
                ephemeral=True,
            )
            return
        ok = await self.bot.db.equip_aspect_instance(
            interaction.user.id,
            interaction.guild_id,
            iid,
        )
        if not ok:
            await interaction.response.send_message(
                "You do not own that aspect instance.",
                ephemeral=True,
            )
            return
        row = await self.bot.db.get_aspect_instance(
            interaction.user.id,
            interaction.guild_id,
            iid,
        )
        inst = instance_from_row(row)
        await interaction.response.send_message(
            f"Equipped **{inst.name}** — {format_aspect_effect(inst)}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Aspects(bot))
