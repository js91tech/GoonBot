from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.bot_players import skip_gameplay_bot
from utils.bot_room import (
    message_allowed_for_trivia,
    resolve_lore_channel,
    send_channel_message,
)
from utils.drugs import DRUGS, drug_by_id
from utils.helpers import fmt_amount, guild_only_message

_TRIVIA_PUNCT = ".,!?;:()[]{}\"'"


def normalize_trivia_guess(text: str) -> str:
    return text.strip().strip(_TRIVIA_PUNCT).lower()


def trivia_speed_fraction(remaining_seconds: float, total_seconds: float = config.TRIVIA_SECONDS) -> float:
    """1.0 = answered instantly, 0.0 = answered at the deadline."""
    if total_seconds <= 0:
        return 0.0
    return max(0.0, min(1.0, remaining_seconds / total_seconds))


def trivia_speed_multiplier(remaining_seconds: float) -> float:
    frac = trivia_speed_fraction(remaining_seconds)
    return config.TRIVIA_SPEED_MIN_MULT + (
        config.TRIVIA_SPEED_MAX_MULT - config.TRIVIA_SPEED_MIN_MULT
    ) * frac


def trivia_drug_chance(remaining_seconds: float) -> float:
    frac = trivia_speed_fraction(remaining_seconds)
    return min(1.0, config.TRIVIA_DRUG_CHANCE + config.TRIVIA_DRUG_FAST_BONUS * frac)


def roll_trivia_drug() -> str | None:
    """Pick a random drug, weighted toward cheaper catalog entries."""
    if not DRUGS:
        return None
    weights = [1.0 / max(defn.seed_cost, 1.0) for defn in DRUGS]
    return random.choices(DRUGS, weights=weights, k=1)[0].drug_id


def format_trivia_window(seconds: int = config.TRIVIA_SECONDS) -> str:
    if seconds % 60 == 0 and seconds >= 60:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{seconds} seconds"


@dataclass
class TriviaRound:
    round_id: str
    answer: str
    expires_at: float
    started_at: float
    view: TriviaAnswerView | None = None
    message: discord.Message | None = None
    end_task: asyncio.Task | None = field(default=None, repr=False)


class TriviaAnswerModal(discord.ui.Modal, title="Answer the trivia"):
    guess = discord.ui.TextInput(
        label="Missing word",
        placeholder="Type your guess…",
        required=True,
        max_length=100,
    )

    def __init__(self, cog: Trivia, channel_id: int, round_id: str) -> None:
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id
        self.round_id = round_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.submit_answer(
            interaction, self.channel_id, str(self.guess.value), self.round_id,
        )


class TriviaAnswerView(discord.ui.View):
    """Attached to trivia round announcements so answers can be typed privately."""

    def __init__(self, cog: Trivia, channel_id: int, round_id: str) -> None:
        super().__init__(timeout=config.TRIVIA_SECONDS + 30)
        self.cog = cog
        self.channel_id = channel_id
        self.round_id = round_id
        self.message: discord.Message | None = None

    @discord.ui.button(label="✍️ Answer", style=discord.ButtonStyle.primary)
    async def answer_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        if not self.cog._round_is_active(self.channel_id, self.round_id):
            await interaction.response.send_message(
                "That round already ended.", ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            TriviaAnswerModal(self.cog, self.channel_id, self.round_id),
        )

    async def on_timeout(self) -> None:
        await self.cog._expire_round(self.channel_id, self.round_id, announce=True)

    async def disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logging.debug("Trivia: could not disable Answer button on message edit")


class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_rounds: dict[int, TriviaRound] = {}
        self.trivia_event_tick.start()

    def cog_unload(self) -> None:
        self.trivia_event_tick.cancel()
        for round_state in list(self.active_rounds.values()):
            if round_state.end_task is not None and not round_state.end_task.done():
                round_state.end_task.cancel()

    @app_commands.command(name="trivia", description="Start a Lore Roulette trivia round.")
    @app_commands.guild_only()
    async def trivia(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.channel_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        target = await resolve_lore_channel(interaction.guild, self.bot.db, interaction.channel)
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message(
                "I could not find the main channel (yappinmain) for Lore Roulette.",
                ephemeral=True,
            )
            return

        if self._channel_has_active_round(target.id):
            await interaction.response.send_message(
                f"A trivia round is already active in {target.mention}.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        started = await self._start_round(interaction.guild, target)
        if not started:
            await interaction.followup.send(
                "I could not find a suitable recent message for trivia.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            f"Lore Roulette is live in {target.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="chaos", description="Open the chaos hub (trivia, virus).")
    @app_commands.guild_only()
    async def chaos(self, interaction: discord.Interaction) -> None:
        from utils.meta_hub_ui import send_chaos_hub

        await send_chaos_hub(interaction, self)

    @tasks.loop(hours=config.TRIVIA_EVENT_INTERVAL_HOURS)
    async def trivia_event_tick(self) -> None:
        for guild in self.bot.guilds:
            channel = await resolve_lore_channel(guild, self.bot.db)
            if channel is None:
                logging.warning("Trivia event: no channel to announce in guild %s", guild.id)
                continue
            if self._channel_has_active_round(channel.id):
                continue
            try:
                await self._start_round(guild, channel, announce_prefix=True)
            except discord.HTTPException:
                logging.exception("Trivia event: failed to start in guild %s", guild.id)

    @trivia_event_tick.before_loop
    async def before_trivia_event_tick(self) -> None:
        await self.bot.wait_until_ready()

    def _channel_has_active_round(self, channel_id: int) -> bool:
        active = self.active_rounds.get(channel_id)
        return active is not None and active.expires_at > time.time()

    def _round_is_active(self, channel_id: int, round_id: str) -> bool:
        active = self.active_rounds.get(channel_id)
        return (
            active is not None
            and active.round_id == round_id
            and active.expires_at > time.time()
        )

    async def _disable_round_view(self, round_state: TriviaRound) -> None:
        if round_state.view is not None:
            await round_state.view.disable_buttons()

    async def _expire_round(
        self,
        channel_id: int,
        round_id: str,
        *,
        announce: bool,
    ) -> None:
        active = self.active_rounds.get(channel_id)
        if active is None or active.round_id != round_id:
            return
        self.active_rounds.pop(channel_id, None)
        if active.end_task is not None and not active.end_task.done():
            active.end_task.cancel()
        await self._disable_round_view(active)
        if not announce or active.message is None:
            return
        await send_channel_message(
            self.bot,
            active.message.channel,
            content=f"⏰ Trivia timed out — the answer was `{active.answer}`.",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _start_round(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        *,
        announce_prefix: bool = False,
    ) -> bool:
        resolved = await resolve_lore_channel(guild, self.bot.db, channel)
        if not isinstance(resolved, discord.TextChannel):
            logging.warning("Trivia: no lore channel to start in guild %s", guild.id)
            return False
        channel = resolved

        puzzle = await self._make_puzzle(guild)
        if puzzle is None:
            return False

        prompt, answer = puzzle
        started_at = time.time()
        round_id = uuid.uuid4().hex
        view = TriviaAnswerView(self, channel.id, round_id)
        round_state = TriviaRound(
            round_id=round_id,
            answer=normalize_trivia_guess(answer),
            expires_at=started_at + config.TRIVIA_SECONDS,
            started_at=started_at,
            view=view,
        )
        self.active_rounds[channel.id] = round_state
        header = "**Random Lore Roulette!** " if announce_prefix else ""
        message = await send_channel_message(
            self.bot,
            channel,
            content=(
                f"{header}Fill the blank — **faster answers pay more**, winners can snag a **stash drop**:\n\n"
                f"> {prompt}\n\n"
                "_Type in chat, or tap **Answer**. Gooner lore fills in when the floor's been quiet._"
            ),
            view=view,
        )
        if message is None:
            self.active_rounds.pop(channel.id, None)
            if round_state.end_task is not None and not round_state.end_task.done():
                round_state.end_task.cancel()
            return False
        view.message = message
        round_state.message = message
        delay = max(0.5, round_state.expires_at - time.time())
        round_state.end_task = asyncio.create_task(
            self._round_timer(channel.id, round_id, delay),
            name=f"trivia-end-{channel.id}-{round_id[:8]}",
        )
        return True

    async def _round_timer(self, channel_id: int, round_id: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        await self._expire_round(channel_id, round_id, announce=True)

    async def start_via_hub(self, interaction: discord.Interaction) -> None:
        """Entry point for ChaosHubView's "Start trivia" button."""
        if interaction.guild is None or interaction.channel_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        target = await resolve_lore_channel(interaction.guild, self.bot.db, interaction.channel)
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message(
                "I could not find the main channel (yappinmain) for Lore Roulette.",
                ephemeral=True,
            )
            return

        if self._channel_has_active_round(target.id):
            await interaction.response.send_message(
                f"A trivia round is already active in {target.mention}.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Starting a Lore Roulette round in {target.mention}…",
            ephemeral=True,
        )
        started = await self._start_round(interaction.guild, target)
        if not started:
            await interaction.followup.send(
                "I could not find a suitable recent message for trivia.", ephemeral=True,
            )

    async def _make_puzzle(self, guild: discord.Guild) -> tuple[str, str] | None:
        if guild.me is None:
            return None

        after = datetime.now(UTC) - timedelta(days=config.TRIVIA_HISTORY_DAYS)
        candidates: list[str] = []
        channels = list(guild.text_channels)
        random.shuffle(channels)

        for channel in channels[: config.TRIVIA_MAX_CHANNELS]:
            permissions = channel.permissions_for(guild.me)
            if not (permissions.read_message_history and permissions.view_channel):
                continue
            try:
                async for message in channel.history(
                    limit=config.TRIVIA_MESSAGES_PER_CHANNEL,
                    after=after,
                    oldest_first=False,
                ):
                    if message.author.bot or not message.content:
                        continue
                    if "http://" in message.content or "https://" in message.content:
                        continue
                    if "@" in message.content or "#" in message.content:
                        continue
                    if len(message.content.split()) >= 4:
                        candidates.append(message.content)
            except discord.HTTPException:
                continue

        if not candidates:
            from utils.goon_session import blank_lore_line

            return blank_lore_line()

        for content in random.sample(candidates, k=len(candidates)):
            words = content.split()
            choices = [
                index
                for index, word in enumerate(words)
                if len(word.strip(_TRIVIA_PUNCT)) >= 3 and word.strip(_TRIVIA_PUNCT).isalnum()
            ]
            if not choices:
                continue
            index = random.choice(choices)
            answer = words[index].strip(_TRIVIA_PUNCT)
            words[index] = "_____"
            return " ".join(words), answer

        return None

    async def _trivia_event_mult(self, guild_id: int) -> float:
        event = await self.bot.db.get_active_guild_event(guild_id)
        if event is not None and str(event["event_type"]) == "trivia_fiesta":
            return float(event["multiplier"])
        return 1.0

    async def _reward_correct_answer(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        answer: str,
        expires_at: float,
        started_at: float,
    ) -> str:
        """Pay out a correct guess and return the public announcement text."""
        now = time.time()
        remaining = max(0.0, expires_at - now)
        speed_mult = trivia_speed_multiplier(remaining)

        base_reward = await self.bot.db.get_config_value(guild.id, "trivia_reward")
        house_pot = await self.bot.db.get_house_pot(guild.id)
        pool_share = house_pot * config.TRIVIA_HOUSE_POOL_SHARE
        taken = await self.bot.db.debit_house_pot(guild.id, pool_share)
        reward = (base_reward + taken) * speed_mult
        income_mult = await self.bot.db.get_income_multiplier(user.id, guild.id)
        fiesta_mult = await self._trivia_event_mult(guild.id)
        paid = reward * income_mult * fiesta_mult
        await self.bot.db.credit_wallet(
            user.id,
            guild.id,
            reward * fiesta_mult,
            apply_bonuses=True,
        )

        drug_note = ""
        if random.random() < trivia_drug_chance(remaining):
            drug_id = roll_trivia_drug()
            defn = drug_by_id(drug_id) if drug_id else None
            if defn is not None:
                await self.bot.db.grant_drug_units(user.id, guild.id, defn.drug_id, 1)
                drug_note = f" Bonus stash drop: {defn.emoji} **1× {defn.name}**!"

        elapsed = max(0.0, now - started_at)
        return (
            f"{user.mention} got it in **{elapsed:.1f}s**! "
            f"The answer was `{answer}`. "
            f"Prize: {fmt_amount(paid)} ({speed_mult:.2f}× speed bonus).{drug_note}"
        )

    async def _claim_round(
        self,
        channel_id: int,
        round_id: str | None,
    ) -> TriviaRound | None:
        active = self.active_rounds.get(channel_id)
        if active is None or active.expires_at <= time.time():
            if active is not None:
                self.active_rounds.pop(channel_id, None)
            return None
        if round_id is not None and active.round_id != round_id:
            return None
        self.active_rounds.pop(channel_id, None)
        if active.end_task is not None and not active.end_task.done():
            active.end_task.cancel()
        await self._disable_round_view(active)
        return active

    async def submit_answer(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        guess: str,
        round_id: str,
    ) -> None:
        """Handle a guess submitted through :class:`TriviaAnswerModal`."""
        if interaction.guild is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        active = self.active_rounds.get(channel_id)
        if active is None or active.expires_at <= time.time():
            self.active_rounds.pop(channel_id, None)
            await interaction.response.send_message("That round already ended.", ephemeral=True)
            return
        if active.round_id != round_id:
            await interaction.response.send_message(
                "That Answer button is for an older round.", ephemeral=True,
            )
            return

        if normalize_trivia_guess(guess) != active.answer:
            await interaction.response.send_message("Not quite — try again!", ephemeral=True)
            return

        # Defer before payout so Discord's 3s modal window cannot expire mid-DB.
        await interaction.response.defer(ephemeral=True)
        claimed = await self._claim_round(channel_id, round_id)
        if claimed is None:
            await interaction.followup.send("That round already ended.", ephemeral=True)
            return

        text = await self._reward_correct_answer(
            interaction.guild,
            interaction.user,
            claimed.answer,
            claimed.expires_at,
            claimed.started_at,
        )
        await interaction.followup.send(f"✅ Correct! {text}", ephemeral=True)

        channel = interaction.guild.get_channel(channel_id) or self.bot.get_channel(channel_id)
        if isinstance(channel, discord.abc.Messageable):
            await send_channel_message(
                self.bot,
                channel,
                content=text,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if skip_gameplay_bot(message.author) or message.guild is None:
            return
        if not await message_allowed_for_trivia(message, self.bot.db):
            return

        active = self.active_rounds.get(message.channel.id)
        if active is None:
            return

        if active.expires_at <= time.time():
            await self._expire_round(message.channel.id, active.round_id, announce=True)
            return

        if normalize_trivia_guess(message.content) != active.answer:
            return

        claimed = await self._claim_round(message.channel.id, active.round_id)
        if claimed is None:
            return
        text = await self._reward_correct_answer(
            message.guild, message.author, claimed.answer, claimed.expires_at, claimed.started_at,
        )
        await send_channel_message(
            self.bot,
            message.channel,
            content=text,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Trivia(bot))
