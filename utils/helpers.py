from __future__ import annotations

import math
import re
import time
from collections.abc import Iterable

import discord

import config

WORD_RE = re.compile(r"[A-Za-z0-9_']+")


def now() -> float:
    return time.time()


def fmt_amount(amount: float) -> str:
    value = f"{int(amount):,}" if amount == int(amount) else f"{amount:,.1f}"
    return f"{value} {config.CURRENCY_EMOJI}"


def valid_amount(amount: float, *, minimum: float = 0.01) -> bool:
    return math.isfinite(amount) and amount >= minimum


def normalize_trigger_word(word: str) -> str | None:
    cleaned = word.strip().lower()
    if not cleaned or len(cleaned) > config.BOUNTY_TRIGGER_MAX_LENGTH:
        return None
    if not re.fullmatch(r"[a-z0-9_'-]+", cleaned):
        return None
    return cleaned


def message_words(content: str) -> list[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(content)]


def contains_word(content: str, word: str) -> bool:
    return word.lower() in message_words(content)


def member_display(member: discord.abc.User) -> str:
    return getattr(member, "display_name", member.name)


def is_admin(interaction: discord.Interaction) -> bool:
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


def unique_member_ids(members: Iterable[discord.Member]) -> set[int]:
    return {member.id for member in members}


async def send_error(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


def guild_only_message() -> str:
    return "This command can only be used inside a server."
