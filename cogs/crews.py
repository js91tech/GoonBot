from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import fmt_amount, guild_only_message, valid_amount


class Crews(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def crew_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        names = await self.bot.db.list_joinable_crew_names(interaction.guild_id)
        needle = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for name in names:
            if needle and needle not in name.lower():
                continue
            choices.append(app_commands.Choice(name=name[:100], value=name))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="crew", description="Crew 2.0: join, treasury, leaderboard.")
    @app_commands.describe(
        action="What to do",
        name="Crew name — pick an existing crew or type a new one",
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
    @app_commands.autocomplete(name=crew_name_autocomplete)
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
                for i, row in enumerate(rows, 1)
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
                    "Pick an existing crew from autocomplete or type a **new crew name** (2–32 chars).",
                    ephemeral=True,
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
            joined_name = await self.bot.db.resolve_crew_name(guild_id, name) or name.strip()[:32]
            await interaction.response.send_message(
                f"You joined crew **{joined_name}**!", ephemeral=True,
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
            if not valid_amount(amount):
                await interaction.response.send_message(
                    "Enter a positive amount (at least 0.01 nuggets).", ephemeral=True,
                )
                return
            deposit = float(amount)
            err = await self.bot.db.deposit_crew_treasury(uid, guild_id, deposit)
            if err:
                msgs = {
                    "not_in_crew": "Join a crew first.",
                    "insufficient_funds": "Not enough nuggets.",
                    "invalid_amount": "Enter a positive amount.",
                    "treasury_error": "Could not update crew treasury. Try again.",
                }
                await interaction.response.send_message(
                    msgs.get(err, err), ephemeral=True,
                )
                return
            membership = await self.bot.db.get_crew_membership(uid, guild_id)
            stats = (
                await self.bot.db.get_crew_stats(guild_id, membership)
                if membership is not None
                else None
            )
            treasury = float(stats["treasury"]) if stats is not None else deposit
            await interaction.response.send_message(
                f"Deposited **{fmt_amount(deposit)}** into your crew treasury "
                f"(total **{fmt_amount(treasury)}**).",
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
