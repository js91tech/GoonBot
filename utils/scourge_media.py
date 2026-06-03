"""Scourge event warning embed media."""
from __future__ import annotations

from pathlib import Path

import discord

import config


def scourge_warning_embed(*, seconds_until_active: int) -> discord.Embed:
    embed = discord.Embed(
        title="⚠️ SCOURGE VIRUS INCOMING",
        description=(
            f"**{config.SCOURGE_VIRUS_NAME}** is breaking containment in "
            f"**{seconds_until_active}s**.\n\n"
            f"For **{config.SCOURGE_ACTIVE_SECONDS // 60} minutes**, the top "
            f"**{config.SCOURGE_TOP_TARGETS}** raiders will be at risk — "
            f"**{config.SCOURGE_INFECTIONS_PER_EVENT}** infections, one per minute.\n\n"
            f"Infected players have **{config.SCOURGE_PASS_SECONDS}s** to "
            f"**`/scourge-pass`** the virus or lose "
            f"**{int(config.SCOURGE_BANK_PENALTY_MIN):,}–{int(config.SCOURGE_BANK_PENALTY_MAX):,}** "
            f"from their **bank**."
        ),
        color=discord.Color.dark_purple(),
    )
    embed.set_footer(text="Prepare your vaults · /scourge-pass to pass the infection")
    url = config.SCOURGE_WARNING_GIF_URL
    if url:
        embed.set_image(url=url)
    return embed


def scourge_warning_files() -> list[discord.File]:
    path = Path(config.SCOURGE_WARNING_GIF_PATH)
    if not path.is_file():
        return []
    if config.SCOURGE_WARNING_GIF_URL:
        return []
    return [discord.File(path, filename="scourge_warning.gif")]


def attach_local_warning_gif(embed: discord.Embed) -> str | None:
    """If using a local GIF, set embed image attachment URL. Returns filename or None."""
    files = scourge_warning_files()
    if not files:
        return None
    embed.set_image(url="attachment://scourge_warning.gif")
    return "scourge_warning.gif"
