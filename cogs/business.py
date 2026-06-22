"""Business Empire — own a business, earn passive income, upgrade, and grow."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.business_ui import build_business_payload
from utils.businesses import tier_def
from utils.helpers import fmt_amount, guild_only_message
from utils.quests import record_quest_event

logger = logging.getLogger(__name__)


class Business(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.business_income_tick.start()

    def cog_unload(self) -> None:
        self.business_income_tick.cancel()

    business_group = app_commands.Group(
        name="business",
        description="Build and manage your business empire.",
        guild_only=True,
    )

    async def _send_panel(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        member = interaction.user
        if guild_id is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        payload = await build_business_payload(self, member, guild_id, member.id)
        if payload is None:
            await interaction.response.send_message(
                "You don't own a business yet. Use **/business create** to start "
                f"with a Lemon Stand ({fmt_amount(tier_def(1).purchase_cost)}).",
                ephemeral=True,
            )
            return
        embed, files, view = payload
        await interaction.response.send_message(embed=embed, files=files, view=view)

    @business_group.command(name="create", description="Open your first business (a Lemon Stand).")
    async def create(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        member = interaction.user
        if guild_id is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        await interaction.response.defer()
        err = await self.bot.db.create_business(member.id, guild_id)
        defn = tier_def(1)
        if err == "already_owns":
            await interaction.followup.send(
                "You already own a business. Use **/business info** to manage it.",
                ephemeral=True,
            )
            return
        if err == "insufficient_funds":
            await interaction.followup.send(
                f"You need **{fmt_amount(defn.purchase_cost)}** in your pocket to "
                "open a Lemon Stand.",
                ephemeral=True,
            )
            return
        if err:
            await interaction.followup.send("Could not create a business right now.", ephemeral=True)
            return
        await record_quest_event(self.bot.db, guild_id, member.id, "business_create")
        payload = await build_business_payload(self, member, guild_id, member.id)
        if payload is None:
            await interaction.followup.send("Business created!", ephemeral=True)
            return
        embed, files, view = payload
        embed.description = (
            f"🎉 You opened a **{defn.name}**! It earns "
            f"{fmt_amount(defn.base_income_per_hour)}/hr. Collect revenue with the "
            "button below and reinvest to grow your empire."
        )
        await interaction.followup.send(embed=embed, files=files, view=view)

    @business_group.command(name="info", description="View and manage your business.")
    async def info(self, interaction: discord.Interaction) -> None:
        await self._send_panel(interaction)

    @business_group.command(name="collect", description="Collect stored revenue from your business.")
    async def collect(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        amount, err = await self.bot.db.collect_business_income(interaction.user.id, guild_id)
        if err == "no_business":
            await interaction.followup.send(
                "You don't own a business. Use **/business create**.", ephemeral=True,
            )
            return
        if err == "empty":
            await interaction.followup.send(
                "No revenue stored yet — let it build up.", ephemeral=True,
            )
            return
        if err:
            await interaction.followup.send("Could not collect right now.", ephemeral=True)
            return
        await record_quest_event(self.bot.db, guild_id, interaction.user.id, "business_collect")
        await interaction.followup.send(
            f"💰 Collected **{fmt_amount(amount)}** to your pocket!", ephemeral=True,
        )

    @business_group.command(name="upgrade", description="Open the upgrade panel for your business.")
    async def upgrade(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        from utils.business_ui import UpgradeBranchView, build_upgrade_embed

        row = await self.bot.db.get_business(interaction.user.id, guild_id)
        if row is None:
            await interaction.response.send_message(
                "You don't own a business. Use **/business create**.", ephemeral=True,
            )
            return
        view = UpgradeBranchView(self, guild_id, interaction.user.id)
        await interaction.response.send_message(
            embed=build_upgrade_embed(row), view=view, ephemeral=True,
        )

    @business_group.command(name="prestige", description="Business prestige (coming soon).")
    async def prestige(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Business prestige unlocks once you reach the Corporation tier. "
            "This endgame reset is coming in a future update.",
            ephemeral=True,
        )

    @tasks.loop(seconds=config.BUSINESS_INCOME_TICK_SECONDS)
    async def business_income_tick(self) -> None:
        for guild in self.bot.guilds:
            try:
                await self.bot.db.process_business_income(guild.id)
            except Exception:
                logger.exception("business income tick failed guild=%s", guild.id)

    @business_income_tick.before_loop
    async def before_business_income_tick(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Business(bot))
