from __future__ import annotations

from typing import TYPE_CHECKING

import discord

import config
from utils.bodyguards import format_bodyguard_roster
from utils.helpers import fmt_amount

if TYPE_CHECKING:
    from discord.ext import commands


def build_bodyguard_embed(
    member: discord.Member,
    *,
    guards: dict[int, int],
    wallet: float,
) -> discord.Embed:
    total = sum(guards.values())
    embed = discord.Embed(
        title=f"{member.display_name}'s bodyguards",
        description=(
            "Hired guards defend your **bank** against `/bank-heist`.\n"
            f"Roster: {format_bodyguard_roster(guards)}\n"
            f"Slots: **{total}/{config.BODYGUARD_MAX_TOTAL}**"
        ),
        color=discord.Color.dark_blue(),
    )
    for tier, spec in sorted(config.BODYGUARD_TIERS.items()):
        qty = guards.get(tier, 0)
        embed.add_field(
            name=f"T{tier} — {spec['name']}",
            value=(
                f"**{fmt_amount(float(spec['cost']))}** each · "
                f"Defense **{int(float(spec['defense']) * 100)}%** · "
                f"Owned: **{qty}**"
            ),
            inline=False,
        )
    embed.set_footer(text=f"Pocket: {fmt_amount(wallet)} · Hire from wallet")
    return embed


class BodyguardView(discord.ui.View):
    def __init__(self, cog: commands.Cog, guild_id: int, user_id: int) -> None:
        super().__init__(timeout=180.0)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your bodyguard panel.", ephemeral=True,
            )
            return False
        return True

    async def _hire(self, interaction: discord.Interaction, tier: int) -> None:
        err = await self.cog.bot.db.hire_bodyguard(self.user_id, self.guild_id, tier)
        if err == "max_guards":
            await interaction.response.send_message(
                f"You already have **{config.BODYGUARD_MAX_TOTAL}** bodyguards.",
                ephemeral=True,
            )
            return
        if err == "insufficient_funds":
            cost = float(config.BODYGUARD_TIERS[tier]["cost"])
            await interaction.response.send_message(
                f"You need **{fmt_amount(cost)}** in your pocket.",
                ephemeral=True,
            )
            return
        if err:
            await interaction.response.send_message("Could not hire guard.", ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Hired guard.", ephemeral=True)
            return
        guards = await self.cog.bot.db.get_bodyguards(self.user_id, self.guild_id)
        wallet = await self.cog.bot.db.get_balance(self.user_id, self.guild_id)
        name = str(config.BODYGUARD_TIERS[tier]["name"])
        embed = build_bodyguard_embed(member, guards=guards, wallet=wallet)
        await interaction.response.edit_message(
            content=f"Hired **1× {name}** (T{tier}).",
            embed=embed,
            view=self,
        )

    @discord.ui.button(label="+1 Rookie (T1)", style=discord.ButtonStyle.secondary, row=0)
    async def hire_t1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._hire(interaction, 1)

    @discord.ui.button(label="+1 Veteran (T2)", style=discord.ButtonStyle.primary, row=0)
    async def hire_t2(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._hire(interaction, 2)

    @discord.ui.button(label="+1 Elite (T3)", style=discord.ButtonStyle.danger, row=0)
    async def hire_t3(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._hire(interaction, 3)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Refreshed.", ephemeral=True)
            return
        guards = await self.cog.bot.db.get_bodyguards(self.user_id, self.guild_id)
        wallet = await self.cog.bot.db.get_balance(self.user_id, self.guild_id)
        embed = build_bodyguard_embed(member, guards=guards, wallet=wallet)
        await interaction.response.edit_message(embed=embed, view=self)


async def send_bodyguard_panel(
    interaction: discord.Interaction,
    cog: commands.Cog,
) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("Guild only.", ephemeral=True)
        return
    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message("Members only.", ephemeral=True)
        return
    guards = await cog.bot.db.get_bodyguards(member.id, interaction.guild_id)
    wallet = await cog.bot.db.get_balance(member.id, interaction.guild_id)
    embed = build_bodyguard_embed(member, guards=guards, wallet=wallet)
    view = BodyguardView(cog, interaction.guild_id, member.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
