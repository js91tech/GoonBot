"""Goon session hub — /goon edge, finish, ruin, tease, dare + group calls."""
from __future__ import annotations

import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.achievements import evaluate_unlocks, format_unlock_message
from utils.bot_players import pvp_target_error, skip_gameplay_bot
from utils.bot_room import resolve_lore_channel, send_channel_message
from utils.goon_group import (
    GroupCallState,
    GroupGoonCallView,
    GroupGoonRoundView,
    call_body,
    edit_call_message,
    find_gooners_role,
    group_call_skip_reason,
    group_goon_call_media,
    group_goon_favor_media,
    pick_velvet_favor,
    prune_chatter_stamps,
    recent_channel_author_stamps,
    resolve_round_copy,
    round_body,
    velvet_favor_claim_copy,
)
from utils.cards import format_card_drop
from utils.goon_session import (
    format_session_block,
    is_group_goon_chat_claim,
    next_group_goon_call_minutes,
    persona_edge_mult,
    persona_ruin_cost_mult,
    pick_dare,
    pick_group_goon_prompt,
    roll_edge_gain,
    roll_group_goon_reward,
    roll_tease_gain,
    tease_cost_for,
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
        self.active_calls: dict[int, GroupCallState] = {}
        self.recent_chatters: dict[int, dict[int, float]] = {}
        self._call_due_at: dict[int, float] = {}
        self._call_locks: dict[int, asyncio.Lock] = {}
        self.call_view = GroupGoonCallView()
        self.round_view = GroupGoonRoundView()
        self.group_goon_call_tick.start()
        self.group_goon_expire_tick.start()

    def cog_unload(self) -> None:
        self.group_goon_call_tick.cancel()
        self.group_goon_expire_tick.cancel()

    def _schedule_next_group_call(
        self, guild_id: int, *, now: float | None = None, startup: bool = False,
    ) -> None:
        ts = time.time() if now is None else now
        if startup:
            delay = float(config.GOON_CALL_STARTUP_DELAY_MINUTES) * 60.0
        else:
            delay = float(next_group_goon_call_minutes()) * 60.0
        self._call_due_at[guild_id] = ts + delay

    def _note_chatter(self, guild_id: int, user_id: int, *, now: float | None = None) -> None:
        ts = time.time() if now is None else now
        self.recent_chatters.setdefault(guild_id, {})[user_id] = ts

    def _live_chatters(self, guild_id: int, now: float) -> set[int]:
        window = float(config.GOON_CALL_CHAT_WINDOW_MINUTES) * 60.0
        stamps = prune_chatter_stamps(self.recent_chatters.get(guild_id, {}), now, window)
        self.recent_chatters[guild_id] = stamps
        return set(stamps)

    def _lock_for(self, channel_id: int) -> asyncio.Lock:
        return self._call_locks.setdefault(channel_id, asyncio.Lock())

    async def _persist(self, state: GroupCallState) -> None:
        try:
            await self.bot.db.upsert_goon_group_call(state.to_payload())
        except Exception:
            logging.exception("Group goon: persist failed channel %s", state.channel_id)

    async def _drop_call(self, channel_id: int) -> None:
        self.active_calls.pop(channel_id, None)
        try:
            await self.bot.db.delete_goon_group_call(channel_id)
        except Exception:
            logging.debug("Group goon: delete persist failed channel %s", channel_id)

    async def _restore_calls(self) -> None:
        try:
            rows = await self.bot.db.list_goon_group_calls()
        except Exception:
            logging.exception("Group goon: restore failed")
            return
        now = time.time()
        for payload in rows:
            state = GroupCallState.from_payload(payload)
            if state.phase == "call" and now >= state.call_expires_at:
                await self.bot.db.delete_goon_group_call(state.channel_id)
                continue
            if state.phase == "round" and now >= state.round_ends_at:
                await self.bot.db.delete_goon_group_call(state.channel_id)
                continue
            guild = self.bot.get_guild(state.guild_id)
            if guild is None:
                continue
            channel = guild.get_channel(state.channel_id)
            if channel is None or state.message_id <= 0:
                self.active_calls[state.channel_id] = state
                continue
            try:
                state.message = await channel.fetch_message(state.message_id)
            except (discord.HTTPException, discord.NotFound):
                state.message = None
            self.active_calls[state.channel_id] = state

    def _note_round(self, channel_id: int | None, user_id: int, *, kind: str) -> None:
        if channel_id is None:
            return
        state = self.active_calls.get(channel_id)
        if state is None or state.phase != "round" or user_id not in state.joiners:
            return
        now = time.time()
        if kind == "edge":
            state.edges[user_id] = now
        elif kind == "leaked":
            state.leaked.setdefault(user_id, now)
        elif kind == "finished":
            state.finished.setdefault(user_id, now)
        self.bot.loop.create_task(self._persist(state))

    async def _maybe_unlock(self, member: discord.Member, guild_id: int) -> str:
        try:
            unlocked = await evaluate_unlocks(self.bot.db, guild_id, member.id)
        except Exception:
            logging.exception("Group goon: achievement eval failed")
            return ""
        return format_unlock_message(unlocked)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if self.bot.user and message.author.id == self.bot.user.id:
            return
        if message.guild is None or skip_gameplay_bot(message.author):
            return
        if not isinstance(message.author, discord.Member):
            return
        self._note_chatter(message.guild.id, message.author.id)
        state = self.active_calls.get(message.channel.id)
        if state is None:
            return
        replied = bool(
            message.reference
            and message.reference.message_id
            and state.message_id
            and message.reference.message_id == state.message_id
        )
        if not is_group_goon_chat_claim(message.content, replied_to_prompt=replied):
            return
        if state.phase == "call":
            err = await self._claim_first(message.author, state)
            if err is None:
                try:
                    await message.add_reaction("💋")
                except discord.HTTPException:
                    logging.debug("Group goon call: could not react to %s", message.id)
            return
        if state.phase == "round":
            late = time.time() > state.free_join_until
            err = await self._join_round(message.author, state, late=late)
            if err is None:
                try:
                    await message.add_reaction("💋")
                except discord.HTTPException:
                    logging.debug("Group goon round: could not react to %s", message.id)

    @tasks.loop(seconds=config.GOON_CALL_POLL_SECONDS)
    async def group_goon_call_tick(self) -> None:
        now = time.time()
        for guild in self.bot.guilds:
            try:
                await self._maybe_post_group_goon_call(guild, now=now)
            except Exception:
                logging.exception("Group goon call tick failed guild %s", guild.id)

    @group_goon_call_tick.before_loop
    async def before_group_goon_call_tick(self) -> None:
        await self.bot.wait_until_ready()
        await self._restore_calls()
        now = time.time()
        for guild in self.bot.guilds:
            if guild.id not in self._call_due_at:
                self._schedule_next_group_call(guild.id, now=now, startup=True)

    @tasks.loop(seconds=20)
    async def group_goon_expire_tick(self) -> None:
        now = time.time()
        for state in list(self.active_calls.values()):
            if state.phase == "call" and now >= state.call_expires_at:
                await self._expire_call(state)
            elif state.phase == "round" and now >= state.round_ends_at:
                await self._resolve_round(state)

    @group_goon_expire_tick.before_loop
    async def before_group_goon_expire_tick(self) -> None:
        await self.bot.wait_until_ready()

    async def _maybe_post_group_goon_call(self, guild: discord.Guild, *, now: float) -> None:
        if guild.id not in self._call_due_at:
            self._schedule_next_group_call(guild.id, now=now, startup=True)
        due = now >= self._call_due_at[guild.id]
        channel = await resolve_lore_channel(guild, self.bot.db)
        existing = self.active_calls.get(channel.id) if channel is not None else None
        chatters = self._live_chatters(guild.id, now)
        if channel is not None and due:
            window = float(config.GOON_CALL_CHAT_WINDOW_MINUTES) * 60.0
            history = await recent_channel_author_stamps(
                channel,
                after_ts=now - window,
                limit=int(config.GOON_CALL_HISTORY_LIMIT),
            )
            if history:
                bucket = self.recent_chatters.setdefault(guild.id, {})
                for uid, ts in history.items():
                    bucket[uid] = max(bucket.get(uid, 0.0), ts)
                chatters = self._live_chatters(guild.id, now)
        reason = group_call_skip_reason(
            channel_ok=channel is not None,
            active=existing is not None,
            due=due,
            chatter_count=len(chatters),
            min_chatters=int(config.GOON_CALL_MIN_CHATTERS),
        )
        if reason is not None:
            logging.debug("Group goon call skip guild %s: %s", guild.id, reason)
            return
        assert channel is not None
        await self._post_group_goon_call(guild, channel, now=now)

    async def _post_group_goon_call(
        self, guild: discord.Guild, channel: discord.TextChannel, *, now: float,
    ) -> None:
        desired = roll_group_goon_reward()
        taken = await self.bot.db.debit_house_pot(guild.id, desired)
        if taken < config.GOON_CALL_MIN_POT:
            if taken > 0:
                await self.bot.db.credit_house_pot(guild.id, taken)
            amount = 0.0
        else:
            amount = taken
        condoms = 0
        state = GroupCallState(
            guild_id=guild.id,
            channel_id=channel.id,
            amount=amount,
            condoms=condoms,
            prompt=pick_group_goon_prompt(),
            call_expires_at=now + float(config.GOON_CALL_CLAIM_SECONDS),
        )
        role = find_gooners_role(guild)
        body = call_body(state, role=role)
        embed, art = group_goon_call_media()
        send_kwargs: dict[str, object] = {
            "embed": embed,
            "view": self.call_view,
            "allowed_mentions": discord.AllowedMentions(
                roles=[role] if role is not None else False,
                users=False,
            ),
        }
        if art is not None:
            send_kwargs["file"] = art
        posted = await send_channel_message(
            self.bot,
            channel,
            body,
            **send_kwargs,
        )
        if posted is None:
            if amount > 0:
                await self.bot.db.credit_house_pot(guild.id, amount)
            logging.warning("Group goon call: send failed guild %s channel %s", guild.id, channel.id)
            return
        state.message = posted
        state.message_id = posted.id
        self.active_calls[channel.id] = state
        self._schedule_next_group_call(guild.id, now=now)
        await self._persist(state)
        logging.info(
            "Group goon call posted guild %s channel %s prize %s chatters %s",
            guild.id,
            channel.id,
            amount,
            len(self.recent_chatters.get(guild.id, {})),
        )

    async def handle_group_ready(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        state = self.active_calls.get(interaction.channel_id)
        if state is None or state.phase != "call":
            await interaction.response.send_message("That call is closed.", ephemeral=True)
            return
        if state.guild_id != interaction.guild_id:
            await interaction.response.send_message("Wrong server.", ephemeral=True)
            return
        err = await self._claim_first(interaction.user, state)
        if err == "taken":
            await interaction.response.send_message("Someone already answered.", ephemeral=True)
            return
        if err == "restricted":
            await interaction.response.send_message("You cannot claim rewards right now.", ephemeral=True)
            return
        if err == "bot":
            await interaction.response.send_message("You cannot claim this.", ephemeral=True)
            return
        extra = f"**{fmt_amount(state.amount)}** hit your pocket. " if state.amount > 0 else ""
        await interaction.response.send_message(
            f"You're in. {extra}Velvet's coming to you first. Floor's open — others can join.",
            ephemeral=True,
        )

    async def handle_group_join(
        self, interaction: discord.Interaction, *, late: bool,
    ) -> None:
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        state = self.active_calls.get(interaction.channel_id)
        if state is None or state.phase != "round":
            await interaction.response.send_message("No live round.", ephemeral=True)
            return
        err = await self._join_round(interaction.user, state, late=late)
        if err == "in":
            await interaction.response.send_message("You're already in.", ephemeral=True)
            return
        if err == "free":
            await interaction.response.send_message(
                "Free join is still open — press **Join** (no condom).",
                ephemeral=True,
            )
            return
        if err == "late":
            await interaction.response.send_message(
                "Free join closed. Press **Join late (condom)** or spend one from inventory.",
                ephemeral=True,
            )
            return
        if err == "condom":
            await interaction.response.send_message(
                "Need 1 condom in inventory to join late.",
                ephemeral=True,
            )
            return
        if err == "restricted":
            await interaction.response.send_message("You cannot join right now.", ephemeral=True)
            return
        await interaction.response.send_message("You're on the floor. `/goon edge`.", ephemeral=True)

    async def _claim_first(self, member: discord.Member, state: GroupCallState) -> str | None:
        async with self._lock_for(state.channel_id):
            return await self._claim_first_unlocked(member, state)

    async def _claim_first_unlocked(self, member: discord.Member, state: GroupCallState) -> str | None:
        if member.bot and not config.ALLOW_BOT_PLAYERS:
            return "bot"
        if state.phase != "call":
            return "taken"
        if await self.bot.db.is_restricted(member.id, state.guild_id):
            return "restricted"
        if state.host_id:
            return "taken"
        state.host_id = member.id
        state.phase = "round"
        now = time.time()
        state.round_ends_at = now + float(config.GOON_ROUND_SECONDS)
        state.free_join_until = now + float(config.GOON_ROUND_FREE_JOIN_SECONDS)
        state.joiners.add(member.id)
        await self.bot.db.credit_wallet(member.id, state.guild_id, state.amount)
        await self.bot.db.tick_goon_passive(
            member.id,
            state.guild_id,
            gain=config.GOON_CALL_METER_GAIN,
            now=now,
            cooldown=0.0,
        )
        await self.bot.db.bump_group_rounds(member.id, state.guild_id)
        await record_quest_event(
            self.bot.db, state.guild_id, member.id, "group_goon",
        )
        await self._persist(state)
        await edit_call_message(state, content=round_body(state), view=self.round_view)
        await self._send_velvet_favor(member, state)
        await self._maybe_grant_session_card(member, state)
        return None

    async def _send_velvet_favor(self, member: discord.Member, state: GroupCallState) -> None:
        kind = pick_velvet_favor()
        embed, art = group_goon_favor_media(kind)
        content = velvet_favor_claim_copy(kind, member.id, state.amount)
        channel = None
        if state.message is not None:
            channel = state.message.channel
        if channel is None:
            guild = getattr(member, "guild", None)
            getter = getattr(guild, "get_channel", None) if guild is not None else None
            channel = getter(state.channel_id) if getter is not None else None
        send_kwargs: dict[str, object] = {
            "embed": embed,
            "allowed_mentions": discord.AllowedMentions(users=True, roles=False),
        }
        if art is not None:
            send_kwargs["file"] = art
        posted = await send_channel_message(self.bot, channel, content, **send_kwargs)
        if posted is None:
            logging.warning(
                "Group goon favor: send failed guild %s channel %s",
                state.guild_id,
                state.channel_id,
            )

    def _session_channel(self, member: discord.Member, state: GroupCallState):
        if state.message is not None:
            return state.message.channel
        guild = getattr(member, "guild", None)
        getter = getattr(guild, "get_channel", None) if guild is not None else None
        return getter(state.channel_id) if getter is not None else None

    async def _maybe_grant_session_card(
        self, member: discord.Member, state: GroupCallState,
    ) -> None:
        slots = int(await self.bot.db.get_config_value(
            state.guild_id, "card_session_join_slots",
        ))
        if slots <= 0 or len(state.joiners) > slots:
            return
        granted = await self.bot.db.grant_engagement_card(member.id, state.guild_id)
        if not granted:
            return
        line = format_card_drop(granted, prefix="Session GoonCard")
        content = f"{member.mention} {line} — first **{slots}** on the floor."
        channel = self._session_channel(member, state)
        await send_channel_message(
            self.bot,
            channel,
            content,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False),
        )

    async def _join_round(
        self, member: discord.Member, state: GroupCallState, *, late: bool,
    ) -> str | None:
        async with self._lock_for(state.channel_id):
            return await self._join_round_unlocked(member, state, late=late)

    async def _join_round_unlocked(
        self, member: discord.Member, state: GroupCallState, *, late: bool,
    ) -> str | None:
        if member.bot and not config.ALLOW_BOT_PLAYERS:
            return "bot"
        if state.phase != "round":
            return "taken"
        if member.id in state.joiners:
            return "in"
        if await self.bot.db.is_restricted(member.id, state.guild_id):
            return "restricted"
        now = time.time()
        free = now <= state.free_join_until
        if late and free:
            return "free"
        if not late and not free:
            return "late"
        if not free:
            qty = await self.bot.db.get_inventory_quantity(
                member.id, state.guild_id, "condoms",
            )
            if qty <= 0:
                return "condom"
            if not await self.bot.db.consume_inventory_item(
                member.id, state.guild_id, "condoms",
            ):
                return "condom"
        state.joiners.add(member.id)
        await self.bot.db.tick_goon_passive(
            member.id,
            state.guild_id,
            gain=config.GOON_ROUND_METER_GAIN,
            now=now,
            cooldown=0.0,
        )
        await self.bot.db.bump_group_rounds(member.id, state.guild_id)
        await record_quest_event(
            self.bot.db, state.guild_id, member.id, "group_goon",
        )
        await self._persist(state)
        await edit_call_message(state, content=round_body(state), view=self.round_view)
        await self._maybe_grant_session_card(member, state)
        return None

    async def _expire_call(self, state: GroupCallState) -> None:
        if state.phase != "call":
            return
        await self.bot.db.credit_house_pot(state.guild_id, state.amount)
        await edit_call_message(
            state,
            content=f"**{state.prompt}**\n_Nobody answered. Session's cold._",
            view=None,
        )
        await self._drop_call(state.channel_id)

    async def _resolve_round(self, state: GroupCallState) -> None:
        if state.phase != "round":
            return
        guild = self.bot.get_guild(state.guild_id)
        dare = pick_dare()
        now = time.time()
        vc_ids: list[int] = []
        last_id: int | None = None
        for uid in state.joiners:
            await self.bot.db.start_goon_dare(
                uid, state.guild_id, now=now, seconds=config.GOON_DARE_SECONDS,
            )
            if guild is not None:
                member = guild.get_member(uid)
                if member is not None and getattr(member, "voice", None) and member.voice.channel:
                    vc_ids.append(uid)
        never = [uid for uid in state.joiners if uid not in state.edges]
        if never:
            last_id = never[0]
        elif state.edges:
            last_id = max(state.edges, key=state.edges.get)
        vc_bonus = 0.0
        if len(vc_ids) >= config.GOON_ROUND_VC_MIN:
            desired = float(config.GOON_ROUND_VC_BONUS) * len(vc_ids)
            taken = await self.bot.db.debit_house_pot(state.guild_id, desired)
            if taken > 0:
                share = taken / max(1, len(vc_ids))
                vc_bonus = share
                for uid in vc_ids:
                    await self.bot.db.credit_wallet(uid, state.guild_id, share)
        tax = 0.0
        if last_id is not None and len(state.joiners) >= 2:
            tax = float(config.GOON_ROUND_LATE_TAX)
            paid = await self.bot.db.debit_wallet(last_id, state.guild_id, tax)
            if paid:
                await self.bot.db.credit_house_pot(state.guild_id, tax)
            else:
                tax = 0.0
        first_break_id = None
        first_break_kind = None
        first_at = 1e18
        for kind, bucket in (("leaked", state.leaked), ("finished", state.finished)):
            for uid, ts in bucket.items():
                if ts < first_at:
                    first_at = ts
                    first_break_id = uid
                    first_break_kind = kind
        copy = resolve_round_copy(
            state,
            dare=dare,
            vc_count=len(vc_ids),
            vc_bonus=vc_bonus,
            last_id=last_id,
            tax=tax,
            first_break_id=first_break_id,
            first_break_kind=first_break_kind,
        )
        await edit_call_message(state, content=copy, view=None)
        await self._drop_call(state.channel_id)

    goon = app_commands.Group(
        name="goon",
        description="Edge, finish, ruin, tease — the session loop.",
        guild_only=True,
    )

    async def _status_embed(self, member: discord.Member, guild_id: int) -> discord.Embed:
        state = await self.bot.db.get_goon_session(member.id, guild_id)
        embed = session_embed(member, format_session_block(state))
        class_id = await self.bot.db.get_class_id(member.id, guild_id)
        tease = tease_cost_for(class_id)
        embed.add_field(
            name="Moves",
            value=(
                "`/goon edge` — keep going\n"
                "`/goon finish` — cash the streak (condom keeps half)\n"
                "`/goon ruin @user` — ruin them (or yourself)\n"
                f"`/goon tease @user` — **{fmt_amount(tease)}** to push their meter\n"
                "`/goon dare` — timed floor dare"
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
        class_id = await self.bot.db.get_class_id(member.id, interaction.guild_id)
        result = await self.bot.db.apply_goon_edge(
            member.id,
            interaction.guild_id,
            gain=roll_edge_gain() * persona_edge_mult(class_id),
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
        self._note_round(interaction.channel_id, member.id, kind="edge")
        if result.leaked:
            self._note_round(interaction.channel_id, member.id, kind="leaked")
        extra = ""
        if result.held:
            extra = " Condom held the leak. You're still at 100."
        elif result.leaked:
            extra = f" You leaked. Consolation **{fmt_amount(result.payout)}**."
        if result.dare_paid > 0:
            extra += f" Dare cashed **{fmt_amount(result.dare_paid)}**."
        watch = (
            f" **{result.watchers}** watching in VC — meter hits harder."
            if result.watchers
            else ""
        )
        title = "Leaked" if result.leaked else "Still edged"
        embed = session_embed(
            member,
            format_session_block(result.state),
            title=title,
        )
        embed.description = (
            f"+**{int(result.gained)}** meter · streak **{result.state.streak}**.{watch}{extra}\n\n"
            + (embed.description or "")
        )
        unlock = await self._maybe_unlock(member, interaction.guild_id)
        if unlock:
            embed.add_field(name="Achievement", value=unlock, inline=False)
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
        self._note_round(interaction.channel_id, member.id, kind="finished")
        kept = ""
        if result.streak_kept:
            kept = f" Condom kept streak **{result.streak_kept}**."
        embed = session_embed(
            member,
            format_session_block(result.state),
            title="Finished",
        )
        embed.description = (
            f"You broke. Paid **{fmt_amount(result.payout)}**.{kept}\n\n"
            + (embed.description or "")
        )
        unlock = await self._maybe_unlock(member, interaction.guild_id)
        if unlock:
            embed.add_field(name="Achievement", value=unlock, inline=False)
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
        class_id = await self.bot.db.get_class_id(actor.id, interaction.guild_id)
        if target.id != actor.id:
            err = pvp_target_error(target, actor.id)
            if err:
                await interaction.response.send_message(err, ephemeral=True)
                return
            result = await self.bot.db.apply_goon_ruin_other(
                actor.id,
                target.id,
                interaction.guild_id,
                now=time.time(),
                cost_mult=persona_ruin_cost_mult(class_id),
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
            if result.error == "shielded":
                await interaction.response.send_message(
                    f"{target.mention} was wrapped. Charge blocked. You got your goonbux back.",
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
        self._note_round(interaction.channel_id, target.id, kind="leaked")
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
        unlock = await self._maybe_unlock(actor, interaction.guild_id)
        if unlock:
            embed.add_field(name="Achievement", value=unlock, inline=False)
        await interaction.response.send_message(embed=embed)

    @goon.command(name="ruin", description="Ruin your session — or pay to ruin someone else's.")
    @app_commands.describe(user="Leave empty to ruin yourself.")
    async def ruin(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        await self.run_ruin(interaction, user)

    async def run_tease(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        err = pvp_target_error(user, interaction.user.id)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        class_id = await self.bot.db.get_class_id(interaction.user.id, interaction.guild_id)
        cost = tease_cost_for(class_id)
        result = await self.bot.db.apply_goon_tease(
            interaction.user.id,
            user.id,
            interaction.guild_id,
            gain=roll_tease_gain(),
            now=time.time(),
            cost=cost,
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
                    f"Need **{fmt_amount(cost)}** in pocket.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message("You can't tease yourself.", ephemeral=True)
            return
        leak = ""
        if result.held:
            leak = " They wrapped. Leak held."
        elif result.leaked:
            leak = " They leaked."
            self._note_round(interaction.channel_id, user.id, kind="leaked")
        embed = branded_embed(
            panel_title("Teased", member_name=user.display_name),
            description=(
                f"{interaction.user.mention} pushed {user.mention}'s meter "
                f"+**{int(result.gained)}** for **{fmt_amount(result.cost)}**.{leak}\n\n"
                + format_session_block(result.state)
            ),
        )
        await interaction.response.send_message(embed=embed)

    @goon.command(name="tease", description="Pay to push someone else's meter.")
    @app_commands.describe(user="Who you're working up.")
    async def tease(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.run_tease(interaction, user)

    async def run_dare(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        dare = pick_dare()
        await self.bot.db.start_goon_dare(
            member.id,
            interaction.guild_id,
            now=time.time(),
        )
        await self.bot.db.tick_goon_passive(
            member.id,
            interaction.guild_id,
            gain=config.GOON_CHAT_GAIN,
            now=time.time(),
            cooldown=0.0,
        )
        embed = branded_embed(
            panel_title("Floor dare", member_name=member.display_name),
            description=(
                f"{member.mention} dropped a dare:\n\n**{dare}**\n\n"
                f"`/goon edge` within **{int(config.GOON_DARE_SECONDS)}s** "
                f"cashes **{fmt_amount(config.GOON_DARE_PAYOUT)}**."
            ),
        )
        await interaction.response.send_message(embed=embed)

    @goon.command(name="dare", description="Drop a floor dare in the channel.")
    async def dare(self, interaction: discord.Interaction) -> None:
        await self.run_dare(interaction)


async def setup(bot: commands.Bot) -> None:
    cog = Goon(bot)
    await bot.add_cog(cog)
    bot.add_view(cog.call_view)
    bot.add_view(cog.round_view)
