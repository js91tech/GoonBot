from __future__ import annotations

import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import fmt_amount, guild_only_message


class Hacker(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.timers: dict[int, asyncio.Task[None]] = {}

    def cog_unload(self) -> None:
        for task in self.timers.values():
            task.cancel()

    async def _penalty(self, guild_id: int, pass_count: int) -> float:
        base = await self.bot.db.get_config_value(guild_id, "hack_base_penalty")
        increment = await self.bot.db.get_config_value(guild_id, "hack_penalty_increment")
        return base + pass_count * increment

    def _replace_timer(self, guild_id: int, channel_id: int) -> None:
        old_task = self.timers.pop(guild_id, None)
        if old_task is not None:
            old_task.cancel()
        self.timers[guild_id] = asyncio.create_task(self._virus_timer(guild_id, channel_id))

    async def _virus_timer(self, guild_id: int, channel_id: int) -> None:
        try:
            pot = await self.bot.db.get_hacker_pot(guild_id)
            if pot is None:
                return
            await asyncio.sleep(max(0.0, float(pot["expires_at"]) - time.time()))
            await self._detonate(guild_id, channel_id)
        except asyncio.CancelledError:
            raise
        finally:
            if self.timers.get(guild_id) is asyncio.current_task():
                self.timers.pop(guild_id, None)

    async def _detonate(self, guild_id: int, channel_id: int) -> None:
        pot = await self.bot.db.get_hacker_pot(guild_id)
        if pot is None:
            return
        penalty = await self._penalty(guild_id, int(pot["pass_count"]))
        removed = await self.bot.db.remove_up_to_balance(int(pot["holder_id"]), guild_id, penalty)
        await self.bot.db.clear_hacker_pot(guild_id)

        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, discord.abc.Messageable):
            await channel.send(
                f"The virus flatlined <@{int(pot['holder_id'])}> for {fmt_amount(removed)}.",
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @app_commands.command(name="hack", description="Start a hot-potato virus.")
    @app_commands.describe(target="Initial virus holder")
    @app_commands.guild_only()
    async def hack(self, interaction: discord.Interaction, target: discord.Member) -> None:
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        if target.bot or target.id == interaction.user.id:
            await interaction.response.send_message("Choose another non-bot user.", ephemeral=True)
            return

        existing = await self.bot.db.get_hacker_pot(interaction.guild_id)
        if existing is not None and float(existing["expires_at"]) > time.time():
            await interaction.response.send_message("A virus is already active in this server.", ephemeral=True)
            return
        if existing is not None:
            await self.bot.db.clear_hacker_pot(interaction.guild_id)

        current = time.time()
        cooldown_seconds = await self.bot.db.get_config_value(interaction.guild_id, "hack_cooldown_seconds")
        cooldown_remaining = await self.bot.db.claim_hack_start(
            interaction.guild_id,
            interaction.user.id,
            cooldown_seconds,
            current,
        )
        if cooldown_remaining is not None:
            await interaction.response.send_message(
                f"You can use `/hack` again in {int(cooldown_remaining // 60) + 1} minute(s).",
                ephemeral=True,
            )
            return

        timer_seconds = await self.bot.db.get_config_value(interaction.guild_id, "hack_timer_seconds")
        await self.bot.db.set_hacker_pot(
            interaction.guild_id,
            target.id,
            0,
            current,
            current + timer_seconds,
        )
        self._replace_timer(interaction.guild_id, interaction.channel_id)
        await interaction.response.send_message(
            f"{target.mention} has the virus! They have {int(timer_seconds)} seconds to "
            "`/transfer` it to someone else before the penalty hits.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="transfer", description="Pass the virus to someone else.")
    @app_commands.describe(target="New virus holder")
    @app_commands.guild_only()
    async def transfer(self, interaction: discord.Interaction, target: discord.Member) -> None:
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        if target.bot or target.id == interaction.user.id:
            await interaction.response.send_message("Choose another non-bot user.", ephemeral=True)
            return

        pot = await self.bot.db.get_hacker_pot(interaction.guild_id)
        current = time.time()
        if pot is None or float(pot["expires_at"]) <= current:
            if pot is not None:
                await self._detonate(interaction.guild_id, interaction.channel_id)
            await interaction.response.send_message("No active virus is transferable.", ephemeral=True)
            return
        if int(pot["holder_id"]) != interaction.user.id:
            await interaction.response.send_message("Only the current holder can transfer the virus.", ephemeral=True)
            return

        next_pass_count = int(pot["pass_count"]) + 1
        timer_seconds = await self.bot.db.get_config_value(interaction.guild_id, "hack_timer_seconds")
        await self.bot.db.set_hacker_pot(
            interaction.guild_id,
            target.id,
            next_pass_count,
            current,
            current + timer_seconds,
        )
        self._replace_timer(interaction.guild_id, interaction.channel_id)
        penalty = await self._penalty(interaction.guild_id, next_pass_count)
        await interaction.response.send_message(
            f"{interaction.user.mention} passed the virus to {target.mention}. "
            f"They have {int(timer_seconds)} seconds to `/transfer` it before "
            f"the {fmt_amount(penalty)} penalty hits.",
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Hacker(bot))
