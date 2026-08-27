"""GoonBot bot-room gate — public typing stays in one channel (NuggetIvitesBot room)."""
from __future__ import annotations

import logging
import re
from typing import Any

import discord

import config

_logger = logging.getLogger(__name__)

_NAME_STRIP = re.compile(r"[^a-z0-9]+")


def _norm_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    return _NAME_STRIP.sub("", name.lower())


def channel_matches_bot_room_name(channel: discord.abc.GuildChannel) -> bool:
    norm = _norm_name(getattr(channel, "name", "") or "")
    if not norm:
        return False
    for hint in config.BOT_ROOM_NAME_HINTS:
        if _norm_name(hint) in norm or norm in _norm_name(hint):
            return True
    return False


async def bot_room_only_enabled(db: object, guild_id: int) -> bool:
    get_config = getattr(db, "get_config_value", None)
    if get_config is None:
        return bool(config.BOT_ROOM_ONLY)
    try:
        value = await get_config(guild_id, "bot_room_only")
    except KeyError:
        return bool(config.BOT_ROOM_ONLY)
    return float(value) >= 1.0


def _can_send(guild: discord.Guild, channel: discord.abc.GuildChannel) -> bool:
    me = guild.me
    if me is None:
        return True
    return bool(channel.permissions_for(me).send_messages)


async def _resolve_id(
    guild: discord.Guild,
    channel_id: int | None,
) -> discord.TextChannel | None:
    if channel_id is None:
        return None
    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel) and _can_send(guild, channel):
        return channel
    return None


def find_bot_room_by_name(guild: discord.Guild) -> discord.TextChannel | None:
    """Prefer channels named like NuggetIvitesBot / goonbot-room."""
    matches = [
        ch
        for ch in guild.text_channels
        if channel_matches_bot_room_name(ch) and _can_send(guild, ch)
    ]
    if not matches:
        return None
    # Prefer exact-ish nuggetivitesbot names first
    matches.sort(
        key=lambda ch: (
            0 if "nuggetivit" in _norm_name(ch.name) else 1,
            0 if "goonbot" in _norm_name(ch.name) else 1,
            len(ch.name),
        ),
    )
    return matches[0]


def channel_matches_main_channel_name(channel: discord.abc.GuildChannel) -> bool:
    """True for social main chat names like yappinmain / yappin-main."""
    norm = _norm_name(getattr(channel, "name", "") or "")
    if not norm:
        return False
    for hint in config.MAIN_CHANNEL_NAME_HINTS:
        hint_n = _norm_name(hint)
        if hint_n and (norm == hint_n or hint_n in norm):
            return True
    return False


def find_main_channel_by_name(guild: discord.Guild) -> discord.TextChannel | None:
    matches = [
        ch
        for ch in guild.text_channels
        if channel_matches_main_channel_name(ch) and _can_send(guild, ch)
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda ch: (
            0 if _norm_name(ch.name) == "yappinmain" else 1,
            len(ch.name),
        ),
    )
    return matches[0]


def _distinct_from(channel: discord.TextChannel | None, other: discord.abc.GuildChannel | None) -> bool:
    if channel is None:
        return False
    if other is None:
        return True
    return int(channel.id) != int(other.id)


async def resolve_bot_room(
    guild: discord.Guild,
    db: object,
) -> discord.TextChannel | None:
    """The single channel GoonBot is allowed to type in."""
    # 1) Env pin
    pinned = await _resolve_id(guild, config.BOT_CHANNEL_ID)
    if pinned is not None:
        return pinned

    # 2) Designated
    get_designated = getattr(db, "get_designated_channel_id", None)
    if get_designated is not None:
        channel = await _resolve_id(guild, await get_designated(guild.id))
        if channel is not None:
            return channel

    # 3) Main
    get_main = getattr(db, "get_main_channel_id", None)
    if get_main is not None:
        channel = await _resolve_id(guild, await get_main(guild.id))
        if channel is not None:
            return channel

    # 4) Name match (NuggetIvitesBot room, etc.)
    named = find_bot_room_by_name(guild)
    if named is not None:
        return named

    return None


async def resolve_lore_channel(
    guild: discord.Guild,
    db: object,
    preferred: discord.abc.Messageable | None = None,
) -> discord.TextChannel | None:
    """Where Lore Roulette posts: social main chat (yappinmain), not the bot room.

    Falls back to the bot room only when no distinct main channel exists.
    """
    bot_room = await resolve_bot_room(guild, db)

    pinned = await _resolve_id(guild, config.MAIN_CHANNEL_ID)
    if pinned is not None and _distinct_from(pinned, bot_room):
        return pinned

    get_main = getattr(db, "get_main_channel_id", None)
    if get_main is not None:
        stored = await _resolve_id(guild, await get_main(guild.id))
        if stored is not None and _distinct_from(stored, bot_room):
            return stored

    named = find_main_channel_by_name(guild)
    if named is not None and _distinct_from(named, bot_room):
        return named

    if (
        isinstance(preferred, discord.TextChannel)
        and _can_send(guild, preferred)
        and _distinct_from(preferred, bot_room)
    ):
        return preferred

    if bot_room is not None:
        return bot_room

    if isinstance(preferred, discord.TextChannel) and _can_send(guild, preferred):
        return preferred
    return None


async def channel_is_allowed_lore(
    guild: discord.Guild,
    db: object,
    channel: Any,
) -> bool:
    lore = await resolve_lore_channel(guild, db)
    if lore is None:
        return False
    return is_bot_room_channel(channel, lore)


def is_bot_room_channel(
    channel: Any,
    bot_room: discord.abc.GuildChannel | None,
) -> bool:
    if bot_room is None or channel is None:
        return False
    channel_id = getattr(channel, "id", None)
    if channel_id is not None and int(channel_id) == int(bot_room.id):
        return True
    parent = getattr(channel, "parent", None)
    if parent is not None and getattr(parent, "id", None) == bot_room.id:
        return True
    return False


async def channel_is_allowed_bot_room(
    guild: discord.Guild,
    db: object,
    channel: Any,
) -> bool:
    if not await bot_room_only_enabled(db, guild.id):
        return True
    bot_room = await resolve_bot_room(guild, db)
    if bot_room is None:
        # Not configured yet — allow admins to set it up; block players.
        return False
    return is_bot_room_channel(channel, bot_room)


def bot_room_required_message(bot_room: discord.abc.GuildChannel | None) -> str:
    if bot_room is not None:
        return (
            f"GoonBot only runs in {bot_room.mention}. Use that channel. "
            f"Lore Roulette (`/trivia`) also runs in #yappinmain."
        )
    return (
        "GoonBot is locked to a single bot room, but none is set yet. "
        "Ask an admin to run `/admin set-designated-channel` on the "
        "**nuggetivitesbot** room (or set `BOT_CHANNEL_ID`)."
    )


async def guard_public_send(
    guild: discord.Guild,
    db: object,
    channel: discord.abc.Messageable,
) -> discord.abc.Messageable | None:
    """If bot-room-only, rewrite sends to the bot room (or drop if unset)."""
    if not await bot_room_only_enabled(db, guild.id):
        return channel
    bot_room = await resolve_bot_room(guild, db)
    if bot_room is None:
        _logger.warning(
            "bot_room_only on but no bot room configured in guild %s — dropping send",
            guild.id,
        )
        return None
    channel_id = getattr(channel, "id", None)
    if channel_id is not None and int(channel_id) == int(bot_room.id):
        return channel
    return bot_room


async def resolve_public_channel(
    guild: discord.Guild,
    db: object,
    preferred: discord.abc.Messageable | None = None,
) -> discord.abc.Messageable | None:
    """Pick where a public bot post should land (bot room when locked)."""
    if preferred is not None:
        guarded = await guard_public_send(guild, db, preferred)
        if guarded is not None:
            return guarded
    if await bot_room_only_enabled(db, guild.id):
        return await resolve_bot_room(guild, db)
    return preferred


async def bot_room_channel_id(guild: discord.Guild, db: object) -> int | None:
    channel = await resolve_bot_room(guild, db)
    if channel is None:
        return None
    return int(channel.id)


async def message_allowed_for_gameplay(message: discord.Message, db: object) -> bool:
    """When bot-room-only, gameplay listeners only run in the bot room."""
    if message.guild is None:
        return False
    if not await bot_room_only_enabled(db, message.guild.id):
        return True
    return await channel_is_allowed_bot_room(message.guild, db, message.channel)


async def message_allowed_for_trivia(message: discord.Message, db: object) -> bool:
    """Lore Roulette may be answered in the bot room or the main (yappinmain) channel."""
    if message.guild is None:
        return False
    if not await bot_room_only_enabled(db, message.guild.id):
        return True
    if await channel_is_allowed_bot_room(message.guild, db, message.channel):
        return True
    return await channel_is_allowed_lore(message.guild, db, message.channel)


async def send_channel_message(
    bot: discord.Client,
    channel: discord.abc.Messageable | None,
    *args: object,
    **kwargs: object,
) -> discord.Message | None:
    """Send to a specific channel with no bot-room rewrite (Lore Roulette)."""
    from utils.discord_api import safe_channel_send

    if channel is None:
        return None
    gate = getattr(bot, "outbound_gate", None)
    return await safe_channel_send(channel, *args, gate=gate, **kwargs)  # type: ignore[arg-type]


async def send_bot_room_message(
    bot: discord.Client,
    guild: discord.Guild,
    db: object,
    preferred: discord.abc.Messageable | None,
    *args: object,
    **kwargs: object,
) -> discord.Message | None:
    """Send a public message, redirecting to the bot room when locked."""
    from utils.discord_api import safe_channel_send

    channel = await resolve_public_channel(guild, db, preferred)
    if channel is None:
        return None
    gate = getattr(bot, "outbound_gate", None)
    return await safe_channel_send(channel, *args, gate=gate, **kwargs)  # type: ignore[arg-type]
