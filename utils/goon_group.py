"""Group goon call — persistent buttons, round state, main-chat ping."""
from __future__ import annotations

import datetime
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import discord

import config
from utils.goon_session import GROUP_GOON_PROMPT
from utils.helpers import fmt_amount

if TYPE_CHECKING:
    from cogs.goon import Goon

CALL_READY_ID = "goon:group:ready"
ROUND_JOIN_ID = "goon:group:join"
ROUND_LATE_ID = "goon:group:late"


@dataclass
class GroupCallState:
    guild_id: int
    channel_id: int
    amount: float
    condoms: int
    prompt: str = GROUP_GOON_PROMPT
    message_id: int = 0
    phase: str = "call"
    host_id: int = 0
    call_expires_at: float = 0.0
    round_ends_at: float = 0.0
    free_join_until: float = 0.0
    joiners: set[int] = field(default_factory=set)
    edges: dict[int, float] = field(default_factory=dict)
    leaked: dict[int, float] = field(default_factory=dict)
    finished: dict[int, float] = field(default_factory=dict)
    message: discord.Message | None = None

    def to_payload(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "message_id": self.message_id,
            "phase": self.phase,
            "amount": self.amount,
            "condoms": self.condoms,
            "host_id": self.host_id,
            "call_expires_at": self.call_expires_at,
            "round_ends_at": self.round_ends_at,
            "free_join_until": self.free_join_until,
            "prompt": self.prompt,
            "joiners": sorted(self.joiners),
            "edges": {str(k): v for k, v in self.edges.items()},
            "leaked": {str(k): v for k, v in self.leaked.items()},
            "finished": {str(k): v for k, v in self.finished.items()},
        }

    @classmethod
    def from_payload(cls, payload: dict) -> GroupCallState:
        return cls(
            guild_id=int(payload["guild_id"]),
            channel_id=int(payload["channel_id"]),
            amount=float(payload.get("amount") or 0),
            condoms=int(payload.get("condoms") or 0),
            prompt=str(payload.get("prompt") or GROUP_GOON_PROMPT),
            message_id=int(payload.get("message_id") or 0),
            phase=str(payload.get("phase") or "call"),
            host_id=int(payload.get("host_id") or 0),
            call_expires_at=float(payload.get("call_expires_at") or 0),
            round_ends_at=float(payload.get("round_ends_at") or 0),
            free_join_until=float(payload.get("free_join_until") or 0),
            joiners=set(int(x) for x in (payload.get("joiners") or [])),
            edges={int(k): float(v) for k, v in (payload.get("edges") or {}).items()},
            leaked={int(k): float(v) for k, v in (payload.get("leaked") or {}).items()},
            finished={int(k): float(v) for k, v in (payload.get("finished") or {}).items()},
        )


def prune_chatter_stamps(
    stamps: dict[int, float],
    now: float,
    window_seconds: float,
) -> dict[int, float]:
    """Drop typer timestamps outside the live-chat window."""
    if window_seconds <= 0:
        return dict(stamps)
    cutoff = now - window_seconds
    return {uid: ts for uid, ts in stamps.items() if ts >= cutoff}


def group_call_skip_reason(
    *,
    channel_ok: bool,
    active: bool,
    due: bool,
    chatter_count: int,
    min_chatters: int,
) -> str | None:
    """Why a poll should not post. None means post. Quiet/no-channel must not reschedule."""
    if not channel_ok:
        return "no_channel"
    if active:
        return "active_call"
    if not due:
        return "not_due"
    if chatter_count < min_chatters:
        return "quiet"
    return None


async def recent_channel_author_stamps(
    channel: object,
    *,
    after_ts: float,
    limit: int = 40,
) -> dict[int, float]:
    """Unique human authors from recent channel history (survives bot restarts)."""
    history = getattr(channel, "history", None)
    if history is None:
        return {}
    after = datetime.datetime.fromtimestamp(after_ts, tz=datetime.timezone.utc)
    found: dict[int, float] = {}
    try:
        async for msg in history(limit=limit, after=after):
            author = getattr(msg, "author", None)
            if author is None or getattr(author, "bot", False):
                continue
            uid = getattr(author, "id", None)
            if uid is None:
                continue
            created = getattr(msg, "created_at", None)
            if created is None:
                ts = after_ts
            elif getattr(created, "timestamp", None) is not None:
                ts = float(created.timestamp())
            else:
                ts = after_ts
            uid_i = int(uid)
            found[uid_i] = max(found.get(uid_i, 0.0), ts)
    except Exception:
        logging.debug("Group goon: history scan failed", exc_info=True)
    return found


def find_gooners_role(guild: discord.Guild) -> discord.Role | None:
    hints = tuple(h.lower() for h in config.GOON_CALL_ROLE_HINTS)
    for role in guild.roles:
        name = (role.name or "").lower().replace(" ", "")
        if any(hint.replace(" ", "") in name or name in hint.replace(" ", "") for hint in hints):
            if role.is_default():
                continue
            return role
    return None


def _velvet_call_art_paths() -> list[Path]:
    """Velvet portraits and any matching GIF/WebP drops for group-session calls."""
    from utils.boss_art import ARMORED_ROOT, ASSETS_ROOT, GLAM_ROOT

    found: list[Path] = []
    for root in (GLAM_ROOT, ARMORED_ROOT, ASSETS_ROOT):
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".gif", ".png", ".webp"}:
                continue
            if "velvet" in path.name.lower():
                found.append(path)
    return found


def group_goon_call_media() -> tuple[discord.Embed, discord.File | None]:
    """Embed + Velvet image (or GIF when present) sent with the group-goon prompt."""
    from utils.boss_art import VELVET_VARIANTS, attach_boss_art
    from utils.goon_theme import branded_embed, panel_title

    embed = branded_embed(
        panel_title("Group goon"),
        description="Velvet walked in. First yes opens the floor.",
    )
    candidates = _velvet_call_art_paths()
    gifs = [path for path in candidates if path.suffix.lower() == ".gif"]
    pool = gifs or candidates
    if pool:
        path = random.choice(pool)
        parent = path.parent.name
        filename = f"{parent}-{path.name}" if parent in {"glam", "armored"} else path.name
        filename = filename.replace("_", "-")
        art = discord.File(str(path), filename=filename)
        embed.set_image(url=f"attachment://{filename}")
        return embed, art
    art = attach_boss_art(embed, random.choice(tuple(VELVET_VARIANTS)))
    return embed, art


def call_body(state: GroupCallState, *, role: discord.Role | None = None) -> str:
    mention = f"{role.mention} " if role is not None else ""
    if state.amount > 0:
        prize = f"**{fmt_amount(state.amount)}** + **{state.condoms}× Condoms** from the house"
    else:
        prize = f"**{state.condoms}× Condoms** from the house"
    return (
        f"{mention}**{state.prompt}**\n"
        f"First to answer (**I'm ready** or type **yes**) gets {prize}.\n"
        "_Then the floor stays open for a group round._"
    )


def round_body(state: GroupCallState) -> str:
    names = " ".join(f"<@{uid}>" for uid in list(state.joiners)[:12])
    left = max(0, int(state.round_ends_at - time.time()))
    free_left = max(0, int(state.free_join_until - time.time()))
    late = (
        f"Free join **{free_left}s**. After that, **Join late** spends 1 condom."
        if free_left > 0
        else "Free join closed. **Join late** spends 1 condom."
    )
    return (
        f"**{state.prompt}**\n"
        f"<@{state.host_id}> opened the floor — "
        f"**{fmt_amount(state.amount)}** + **{state.condoms}× Condoms**.\n"
        f"In: {names or '_nobody_'}\n"
        f"{late} Round ends in **{left}s**. `/goon edge` now. Don't finish first."
    )


def resolve_round_copy(
    state: GroupCallState,
    *,
    dare: str,
    vc_count: int,
    vc_bonus: float,
    last_id: int | None,
    tax: float,
    first_break_id: int | None,
    first_break_kind: str | None,
) -> str:
    n = len(state.joiners)
    lines = [
        f"**Group session closed.** {n} on the floor.",
        f"Dare: **{dare}** — `/goon edge` in **{int(config.GOON_DARE_SECONDS)}s** to cash it.",
    ]
    if vc_count >= config.GOON_ROUND_VC_MIN and vc_bonus > 0:
        lines.append(
            f"**{vc_count}** in VC — house kicked in **{fmt_amount(vc_bonus)}** each."
        )
    if last_id is not None and tax > 0:
        lines.append(
            f"<@{last_id}> edged last (or never). Tax **{fmt_amount(tax)}** to the house."
        )
    if first_break_id is not None:
        verb = "leaked" if first_break_kind == "leaked" else "finished"
        lines.append(f"<@{first_break_id}> {verb} first. Get roasted.")
    return "\n".join(lines)


def _cog_from(interaction: discord.Interaction) -> Goon | None:
    return interaction.client.get_cog("Goon")  # type: ignore[return-value]


class GroupGoonCallView(discord.ui.View):
    """Persistent first-answer button."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="I'm ready",
        style=discord.ButtonStyle.success,
        custom_id=CALL_READY_ID,
    )
    async def ready_button(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        del button
        cog = _cog_from(interaction)
        if cog is None:
            await interaction.response.send_message("Session cog is down.", ephemeral=True)
            return
        await cog.handle_group_ready(interaction)


class GroupGoonRoundView(discord.ui.View):
    """Persistent join / late-join buttons for the group round."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Join",
        style=discord.ButtonStyle.primary,
        custom_id=ROUND_JOIN_ID,
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        del button
        cog = _cog_from(interaction)
        if cog is None:
            await interaction.response.send_message("Session cog is down.", ephemeral=True)
            return
        await cog.handle_group_join(interaction, late=False)

    @discord.ui.button(
        label="Join late (condom)",
        style=discord.ButtonStyle.secondary,
        custom_id=ROUND_LATE_ID,
    )
    async def late_button(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        del button
        cog = _cog_from(interaction)
        if cog is None:
            await interaction.response.send_message("Session cog is down.", ephemeral=True)
            return
        await cog.handle_group_join(interaction, late=True)


async def edit_call_message(state: GroupCallState, *, content: str, view: discord.ui.View | None) -> None:
    if state.message is None:
        return
    try:
        await state.message.edit(
            content=content,
            view=view,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False),
        )
    except (discord.HTTPException, discord.NotFound):
        logging.debug("Group goon: edit failed channel %s", state.channel_id)
