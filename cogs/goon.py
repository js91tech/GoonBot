"""Goon session hub — /goon edge, finish, ruin, tease, dare."""
from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.bot_players import pvp_target_error
from utils.goon_session import (
    format_session_block,
    pick_dare,
    roll_edge_gain,
    roll_tease_gain,
    voice_watchers,
    watch_multiplier,
)
from utils.goon_theme import branded_embed, danger_color, panel_title
from utils.helpers import fmt_amount, guild_only_message
from utils.quests import record_quest_event


def session_embed(member: discord.Member, block: str, *, title: str = "Goon session") -> discord.Embed:
    embed = branded_embed(
        panel_title(title, member_name=member.display_name),
        description=block,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


class Goon(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    goon = app_commands.Group(
        name="goon",
        description="Edge, finish, ruin, tease — the session loop.",
        guild_only=True,
    )

    async def _status_embed(self, member: discord.Member, guild_id: int) -> discord.Embed:
        state = await self.bot.db.get_goon_session(member.id, guild_id)
        embed = session_embed(member, format_session_block(state))
        embed.add_field(
            name="Moves",
            value=(
                "`/goon edge` — keep going\n"
                "`/goon finish` — cash the streak\n"
                "`/goon ruin @user` — ruin them (or yourself)\n"
                f"`/goon tease @user` — **{fmt_amount(config.GOON_TEASE_COST)}** to push their meter\n"
                "`/goon dare` — drop a floor dare"
            ),
            inline=False,
        )
        return embed

    @goon.command(name="status", description="Check your (or their) goon session.")
    @app_commands.describe(user="Whose session to peek. Defaults to you.")
    async def status(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        target = user or interaction.user
        if not isinstance(target, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        embed = await self._status_embed(target, interaction.guild_id)
        await interaction.response.send_message(embed=embed, ephemeral=target.id == interaction.user.id)

    async def run_edge(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        watchers = voice_watchers(member)
        result = await self.bot.db.apply_goon_edge(
            member.id,
            interaction.guild_id,
            gain=roll_edge_gain(),
            now=time.time(),
            watch_mult=watch_multiplier(watchers),
            watchers=watchers,
        )
        if not result.ok:
            wait = int(result.cooldown) + 1
            await interaction.response.send_message(
                f"Too soon. Edge again in **{wait}s** — hold it.",
                ephemeral=True,
            )
            return
        await record_quest_event(
            self.bot.db, interaction.guild_id, member.id, "goon_edge",
        )
        leak = " You're leaking. Finish or get ruined." if result.leaked else ""
        watch = (
            f" **{result.watchers}** watching in VC — meter hits harder."
            if result.watchers
            else ""
        )
        embed = session_embed(
            member,
            format_session_block(result.state),
            title="Still edged",
        )
        embed.description = (
            f"+**{int(result.gained)}** meter · streak **{result.state.streak}**.{watch}{leak}\n\n"
            + (embed.description or "")
        )
        await interaction.response.send_message(embed=embed)

    @goon.command(name="edge", description="Keep the session going. Don't finish.")
    async def edge(self, interaction: discord.Interaction) -> None:
        await self.run_edge(interaction)

    async def run_finish(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        result = await self.bot.db.apply_goon_finish(
            member.id, interaction.guild_id, now=time.time(),
        )
        if not result.ok:
            await interaction.response.send_message(
                "You're not even edged. `/goon edge` first.",
                ephemeral=True,
            )
            return
        await record_quest_event(
            self.bot.db, interaction.guild_id, member.id, "goon_finish",
        )
        embed = session_embed(
            member,
            format_session_block(result.state),
            title="Finished",
        )
        embed.description = (
            f"You broke. Paid **{fmt_amount(result.payout)}**. Streak's gone.\n\n"
            + (embed.description or "")
        )
        await interaction.response.send_message(embed=embed)

    @goon.command(name="finish", description="Cash the streak. Session resets.")
    async def finish(self, interaction: discord.Interaction) -> None:
        await self.run_finish(interaction)

    async def run_ruin(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        target = user or actor
        if target.id != actor.id:
            err = pvp_target_error(target, actor.id)
            if err:
                await interaction.response.send_message(err, ephemeral=True)
                return
            result = await self.bot.db.apply_goon_ruin_other(
                actor.id, target.id, interaction.guild_id, now=time.time(),
            )
        else:
            result = await self.bot.db.apply_goon_ruin_self(
                actor.id, interaction.guild_id, now=time.time(),
            )
        if not result.ok:
            if result.error == "funds":
                await interaction.response.send_message(
                    f"Need **{fmt_amount(result.cost)}** in pocket to ruin them.",
                    ephemeral=True,
                )
                return
            if result.error == "target_dry":
                await interaction.response.send_message(
                    "They're not edged. Nothing to ruin.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                "Nothing to ruin. `/goon edge` first.",
                ephemeral=True,
            )
            return
        await record_quest_event(
            self.bot.db, interaction.guild_id, actor.id, "goon_ruin",
        )
        if target.id == actor.id:
            embed = branded_embed(
                panel_title("Ruined yourself", member_name=actor.display_name),
                description=(
                    f"You dumped it. Consolation **{fmt_amount(result.payout)}**.\n\n"
                    + format_session_block(result.state)
                ),
                color=danger_color(),
            )
        else:
            embed = branded_embed(
                panel_title("Ruined", member_name=target.display_name),
                description=(
                    f"{actor.mention} ruined {target.mention}. "
                    f"Paid **{fmt_amount(result.cost)}**, stole **{fmt_amount(result.stolen)}**. "
                    "Streak's dead.\n\n"
                    + format_session_block(result.state)
                ),
                color=danger_color(),
            )
        await interaction.response.send_message(embed=embed)

    @goon.command(name="ruin", description="Ruin your session — or pay to ruin someone else's.")
    @app_commands.describe(user="Leave empty to ruin yourself.")
    async def ruin(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        await self.run_ruin(interaction, user)

    @goon.command(name="tease", description="Pay to push someone else's meter.")
    @app_commands.describe(user="Who you're working up.")
    async def tease(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        err = pvp_target_error(user, interaction.user.id)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        result = await self.bot.db.apply_goon_tease(
            interaction.user.id,
            user.id,
            interaction.guild_id,
            gain=roll_tease_gain(),
            now=time.time(),
        )
        if not result.ok:
            if result.error == "cooldown":
                await interaction.response.send_message(
                    f"Easy. Tease again in **{int(result.cooldown) + 1}s**.",
                    ephemeral=True,
                )
                return
            if result.error == "funds":
                await interaction.response.send_message(
                    f"Need **{fmt_amount(config.GOON_TEASE_COST)}** in pocket.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message("You can't tease yourself.", ephemeral=True)
            return
        leak = " They're leaking." if result.leaked else ""
        embed = branded_embed(
            panel_title("Teased", member_name=user.display_name),
            description=(
                f"{interaction.user.mention} pushed {user.mention}'s meter "
                f"+**{int(result.gained)}** for **{fmt_amount(result.cost)}**.{leak}\n\n"
                + format_session_block(result.state)
            ),
        )
        await interaction.response.send_message(embed=embed)

    @goon.command(name="dare", description="Drop a floor dare in the channel.")
    async def dare(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        dare = pick_dare()
        await self.bot.db.tick_goon_passive(
            member.id,
            interaction.guild_id,
            gain=config.GOON_CHAT_GAIN,
            now=time.time(),
            cooldown=0.0,
        )
        embed = branded_embed(
            panel_title("Floor dare", member_name=member.display_name),
            description=f"{member.mention} dropped a dare:\n\n**{dare}**",
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Goon(bot))
