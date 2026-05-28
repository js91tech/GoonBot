from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import fmt_amount, guild_only_message, valid_amount


class Crews(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="crew", description="Crew 2.0: join, treasury, leaderboard.")
    @app_commands.describe(
        action="What to do",
        name="Crew name (2–32 chars)",
        amount="Nuggets to deposit into crew treasury",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Status", value="status"),
            app_commands.Choice(name="Join crew", value="join"),
            app_commands.Choice(name="Leave crew", value="leave"),
            app_commands.Choice(name="Deposit", value="deposit"),
            app_commands.Choice(name="Leaderboard", value="leaderboard"),
        ],
    )
    @app_commands.guild_only()
    async def crew(
        self,
        interaction: discord.Interaction,
        action: str,
        name: str | None = None,
        amount: float | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        guild_id = interaction.guild_id
        uid = interaction.user.id

        if action == "leaderboard":
            rows = await self.bot.db.crew_leaderboard(guild_id, limit=10)
            if not rows:
                await interaction.response.send_message(
                    "No crews yet. **Join crew** to found one.", ephemeral=True,
                )
                return
            lines = [
                f"**{i}. {row['crew_name']}** — Lv{int(row['level'])} · "
                f"{fmt_amount(float(row['score']))} treasury · {int(row['xp'])} XP"
                for i, row in enumerate(rows, start=1)
            ]
            embed = discord.Embed(
                title="Crew leaderboard",
                description="\n".join(lines),
                color=discord.Color.dark_gold(),
            )
            await interaction.response.send_message(embed=embed)
            return

        if action == "join":
            if not name:
                await interaction.response.send_message(
                    "Provide a **name** for your crew.", ephemeral=True,
                )
                return
            err = await self.bot.db.join_crew(uid, guild_id, name)
            messages = {
                "invalid_name": "Crew name must be 2–32 characters.",
                "already_in_crew": "Leave your current crew first.",
                "crew_full": "That crew already has 8 members.",
            }
            if err:
                await interaction.response.send_message(messages.get(err, err), ephemeral=True)
                return
            await interaction.response.send_message(
                f"You joined crew **{name.strip()[:32]}**!", ephemeral=True,
            )
            return

        if action == "leave":
            if await self.bot.db.leave_crew(uid, guild_id):
                await interaction.response.send_message("You left your crew.", ephemeral=True)
            else:
                await interaction.response.send_message(
                    "You are not in a crew.", ephemeral=True,
                )
            return

        if action == "deposit":
            if amount is None:
                await interaction.response.send_message(
                    "Set an **amount** to deposit.", ephemeral=True,
                )
                return
            try:
                deposit = valid_amount(amount)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            err = await self.bot.db.deposit_crew_treasury(uid, guild_id, deposit)
            if err:
                msgs = {
                    "not_in_crew": "Join a crew first.",
                    "insufficient_funds": "Not enough nuggets.",
                }
                await interaction.response.send_message(
                    msgs.get(err, err), ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"Deposited **{fmt_amount(deposit)}** into your crew treasury.",
                ephemeral=True,
            )
            return

        membership = await self.bot.db.get_crew_membership(uid, guild_id)
        if membership is None:
            await interaction.response.send_message(
                "You are not in a crew. Use **Join crew** to create or join one.",
                ephemeral=True,
            )
            return
        stats = await self.bot.db.get_crew_stats(guild_id, membership)
        members = await self.bot.db.list_crew_members(guild_id, membership)
        member_names = []
        if interaction.guild:
            for row in members[:8]:
                m = interaction.guild.get_member(int(row["user_id"]))
                member_names.append(m.display_name if m else f"User {row['user_id']}")
        treasury = float(stats["treasury"]) if stats else 0.0
        level = int(stats["level"]) if stats else 1
        xp = int(stats["xp"]) if stats else 0
        embed = discord.Embed(
            title=f"Crew {membership}",
            description="\n".join(member_names) or "_No members_",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Treasury", value=fmt_amount(treasury), inline=True)
        embed.add_field(name="Level / XP", value=f"{level} / {xp}", inline=True)
        embed.set_footer(text="Heists with crewmates get +10% success per member (existing rule)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Crews(bot))
