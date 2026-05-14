from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.helpers import fmt_amount, guild_only_message, valid_amount


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_chatters: set[tuple[int, int]] = set()
        self.passive_active_tick.start()
        self.vc_earning_tick.start()

    def cog_unload(self) -> None:
        self.passive_active_tick.cancel()
        self.vc_earning_tick.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        if await self.bot.db.is_restricted(message.author.id, message.guild.id):
            return

        await self.bot.db.record_message_reward(
            message.author.id,
            message.guild.id,
            config.PASSIVE_CHAT_REWARD,
        )
        self.active_chatters.add((message.guild.id, message.author.id))

    @tasks.loop(hours=1)
    async def passive_active_tick(self) -> None:
        chatters = self.active_chatters
        self.active_chatters = set()
        for guild_id, user_id in chatters:
            if not await self.bot.db.is_restricted(user_id, guild_id):
                await self.bot.db.credit_wallet(user_id, guild_id, config.PASSIVE_ACTIVE_BONUS)
                await self.bot.db.set_last_active(user_id, guild_id, time.time())

    @passive_active_tick.before_loop
    async def before_passive_active_tick(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=60)
    async def vc_earning_tick(self) -> None:
        for guild in self.bot.guilds:
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if member.bot or await self.bot.db.is_restricted(member.id, guild.id):
                        continue
                    await self.bot.db.credit_wallet(member.id, guild.id, config.VOICE_CHAT_REWARD)

    @vc_earning_tick.before_loop
    async def before_vc_earning_tick(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="daily", description="Claim your daily nuggets.")
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        current = time.time()
        remaining = await self.bot.db.claim_daily(
            interaction.user.id,
            interaction.guild_id,
            config.DAILY_REWARD,
            config.DAILY_COOLDOWN_SECONDS,
            current,
        )
        if remaining is not None:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await interaction.response.send_message(
                f"You already claimed daily. Try again in {hours}h {minutes}m.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"You claimed {fmt_amount(config.DAILY_REWARD)}.",
            ephemeral=True,
        )

    @app_commands.command(name="balance", description="Check a wallet balance.")
    @app_commands.describe(user="User to check. Defaults to you.")
    @app_commands.guild_only()
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        target = user or interaction.user
        balance = await self.bot.db.get_balance(target.id, interaction.guild_id)
        await interaction.response.send_message(
            f"{target.mention} has {fmt_amount(balance)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="leaderboard", description="Show the richest users.")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        rows = await self.bot.db.leaderboard(interaction.guild.id)
        if not rows:
            await interaction.response.send_message("No wallets yet.")
            return

        lines = []
        for index, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(int(row["user_id"]))
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"**{index}.** {name}: {fmt_amount(float(row['wallet']))}")

        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="pay", description="Send nuggets to another user.")
    @app_commands.describe(user="User to pay", amount="Amount to send")
    @app_commands.guild_only()
    async def pay(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: float,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        if user.bot or user.id == interaction.user.id:
            await interaction.response.send_message("Choose another non-bot user.", ephemeral=True)
            return
        if not valid_amount(amount):
            await interaction.response.send_message("Enter a positive amount.", ephemeral=True)
            return

        paid = await self.bot.db.transfer_wallet(
            interaction.user.id,
            user.id,
            interaction.guild_id,
            amount,
        )
        if not paid:
            await interaction.response.send_message("You do not have enough nuggets.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"{interaction.user.mention} paid {user.mention} {fmt_amount(amount)}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
