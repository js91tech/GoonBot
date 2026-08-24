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
            f"GoonBot only runs in {bot_room.mention} "
            f"(the NuggetIvitesBot / bot room). Use that channel."
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
