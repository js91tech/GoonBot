"""Goon session hub — /goon edge, finish, ruin, tease, dare."""
from __future__ import annotations

import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.bot_players import pvp_target_error, skip_gameplay_bot
from utils.bot_room import resolve_lore_channel, send_channel_message
from utils.goon_session import (
    GROUP_GOON_PROMPT,
    format_session_block,
    is_group_goon_chat_claim,
    next_group_goon_call_minutes,
    pick_dare,
    roll_edge_gain,
    roll_group_goon_reward,
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


class GroupGoonCallView(discord.ui.View):
    """First click or yes-in-chat wins goonbux + condoms."""

    def __init__(
        self,
        cog: Goon,
        guild_id: int,
        channel_id: int,
        amount: float,
        condoms: int,
    ) -> None:
        super().__init__(timeout=float(config.GOON_CALL_CLAIM_SECONDS))
        self.cog = cog
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.amount = amount
        self.condoms = condoms
        self._claimed = False
        self._claim_lock = asyncio.Lock()
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        self.cog.active_calls.pop(self.channel_id, None)
        for item in self.children:
            item.disabled = True
        if self.message is None or self._claimed:
            return
        try:
            await self.message.edit(
                content=(
                    f"**{GROUP_GOON_PROMPT}**\n"
                    "_Nobody answered. Session's cold._"
                ),
                view=self,
            )
        except (discord.HTTPException, discord.NotFound):
            logging.debug("Group goon call: timeout edit failed channel %s", self.channel_id)

    async def try_claim(self, member: discord.Member) -> str | None:
        """Award the first valid answer. Returns None on success, else an error key."""
        if member.bot and not config.ALLOW_BOT_PLAYERS:
            return "bot"
        async with self._claim_lock:
            if self._claimed:
                return "taken"
            if await self.cog.bot.db.is_restricted(member.id, self.guild_id):
                return "restricted"
            await self.cog.bot.db.credit_wallet(member.id, self.guild_id, self.amount)
            for _ in range(self.condoms):
                await self.cog.bot.db.grant_item(member.id, self.guild_id, "condoms")
            await self.cog.bot.db.tick_goon_passive(
                member.id,
                self.guild_id,
                gain=config.GOON_CALL_METER_GAIN,
                now=time.time(),
                cooldown=0.0,
            )
            self._claimed = True
            self.cog.active_calls.pop(self.channel_id, None)
            for item in self.children:
                item.disabled = True
            self.stop()
        if self.message is not None:
            body = (
                f"**{GROUP_GOON_PROMPT}**\n"
                f"{member.mention} said yes first — "
                f"**{fmt_amount(self.amount)}** + **{self.condoms}× Condoms**."
            )
            try:
                await self.message.edit(
                    content=body,
                    allowed_mentions=discord.AllowedMentions(users=[member]),
                    view=self,
                )
            except (discord.HTTPException, discord.NotFound):
                logging.debug("Group goon call: claim edit failed channel %s", self.channel_id)
        return None

    @discord.ui.button(label="I'm ready", style=discord.ButtonStyle.success)
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("Wrong server.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        err = await self.try_claim(interaction.user)
        if err == "taken":
            await interaction.response.send_message("Someone already answered.", ephemeral=True)
            return
        if err == "restricted":
            await interaction.response.send_message("You cannot claim rewards right now.", ephemeral=True)
            return
        if err == "bot":
            await interaction.response.send_message("You cannot claim this.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"You're in. **{fmt_amount(self.amount)}** + **{self.condoms}× Condoms**.",
            ephemeral=True,
        )


class Goon(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_calls: dict[int, GroupGoonCallView] = {}
        self.group_goon_call_tick.start()

    def cog_unload(self) -> None:
        self.group_goon_call_tick.cancel()

    def _roll_group_call_interval(self) -> None:
        self.group_goon_call_tick.change_interval(minutes=next_group_goon_call_minutes())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if self.bot.user and message.author.id == self.bot.user.id:
            return
        if message.guild is None or skip_gameplay_bot(message.author):
            return
        if not isinstance(message.author, discord.Member):
            return
        view = self.active_calls.get(message.channel.id)
        if view is None:
            return
        replied = bool(
            message.reference
            and message.reference.message_id
            and view.message is not None
            and message.reference.message_id == view.message.id
        )
        if not is_group_goon_chat_claim(message.content, replied_to_prompt=replied):
            return
        err = await view.try_claim(message.author)
        if err is None:
            try:
                await message.add_reaction("💋")
            except discord.HTTPException:
                logging.debug("Group goon call: could not react to %s", message.id)

    @tasks.loop(minutes=config.GOON_CALL_INTERVAL_MINUTES)
    async def group_goon_call_tick(self) -> None:
        try:
            for guild in self.bot.guilds:
                await self._post_group_goon_call(guild)
        finally:
            self._roll_group_call_interval()

    @group_goon_call_tick.before_loop
    async def before_group_goon_call_tick(self) -> None:
        await self.bot.wait_until_ready()
        self._roll_group_call_interval()

    async def _post_group_goon_call(self, guild: discord.Guild) -> None:
        channel = await resolve_lore_channel(guild, self.bot.db)
        if channel is None:
            return
        existing = self.active_calls.get(channel.id)
        if existing is not None and not existing._claimed:
            return
        amount = roll_group_goon_reward()
        condoms = int(config.GOON_CALL_CONDOMS)
        view = GroupGoonCallView(self, guild.id, channel.id, amount, condoms)
        body = (
            f"**{GROUP_GOON_PROMPT}**\n"
            f"First to answer (**I'm ready** or type **yes**) gets "
            f"**{fmt_amount(amount)}** + **{condoms}× Condoms**."
        )
        posted = await send_channel_message(
            self.bot,
            channel,
            body,
            view=view,
        )
        if posted is None:
            return
        view.message = posted
        self.active_calls[channel.id] = view

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
