"""Random girl portraits attached to `/goon dare` and group-round dares."""
from __future__ import annotations

import random
from pathlib import Path

import discord

DARE_ROOT = Path(__file__).resolve().parent.parent / "assets" / "dares"
_IMAGE_SUFFIXES = frozenset({".png", ".gif", ".webp", ".jpg", ".jpeg"})


def dare_art_paths() -> list[Path]:
    if not DARE_ROOT.is_dir():
        return []
    return sorted(
        path
        for path in DARE_ROOT.iterdir()
        if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES
    )


def pick_dare_art() -> Path | None:
    paths = dare_art_paths()
    if not paths:
        return None
    return random.choice(paths)


def _attachment_filename(path: Path) -> str:
    """Discord embed attachment:// names — avoid underscores (image won't render)."""
    return path.name.replace("_", "-")


def attach_dare_art(embed: discord.Embed, *, path: Path | None = None) -> discord.File | None:
    art_path = path if path is not None else pick_dare_art()
    if art_path is None or not art_path.is_file():
        return None
    filename = _attachment_filename(art_path)
    art = discord.File(str(art_path), filename=filename)
    embed.set_image(url=art.uri)
    return art
