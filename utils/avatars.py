from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "avatars"
DEFAULT_AVATAR_ID = "nugget_raider"


@dataclass(frozen=True)
class AvatarDef:
    id: str
    name: str
    description: str
    price: float
    emoji: str = "🍘"


AVATARS: tuple[AvatarDef, ...] = (
    AvatarDef(
        "nugget_raider",
        "Nugget Raider",
        "Default raid mascot — unlocked for everyone.",
        0.0,
        "⚔️",
    ),
    AvatarDef(
        "duel_champion",
        "Duel Champion",
        "Flex after PvP wins.",
        2_500.0,
        "🥊",
    ),
    AvatarDef(
        "raid_medic",
        "Raid Medic",
        "For healers and field medics.",
        2_500.0,
        "💊",
    ),
    AvatarDef(
        "vault_mogul",
        "Vault Mogul",
        "Economy grinder aesthetic.",
        5_000.0,
        "💰",
    ),
    AvatarDef(
        "boss_slayer",
        "Boss Slayer",
        "Trophy hunter victory pose.",
        10_000.0,
        "🏆",
    ),
)

AVATAR_MAP: dict[str, AvatarDef] = {a.id: a for a in AVATARS}


def get_avatar(avatar_id: str | None) -> AvatarDef | None:
    if not avatar_id:
        return AVATAR_MAP.get(DEFAULT_AVATAR_ID)
    return AVATAR_MAP.get(avatar_id.strip().lower())


def portrait_path(avatar_id: str) -> Path:
    return ASSETS_ROOT / avatar_id / "portrait.png"


def victory_path(avatar_id: str) -> Path:
    """Prefer animated victory GIF when present."""
    gif = ASSETS_ROOT / avatar_id / "victory.gif"
    if gif.is_file():
        return gif
    return ASSETS_ROOT / avatar_id / "victory.png"


def victory_attachment_name(avatar_id: str) -> str:
    path = victory_path(avatar_id)
    return f"victory_{avatar_id}{path.suffix}"


def resolve_equipped_avatar_id(stored: str | None) -> str:
    if stored and stored in AVATAR_MAP:
        return stored
    return DEFAULT_AVATAR_ID


def build_victory_attachment(avatar_id: str | None) -> tuple[list[discord.File], str | None]:
    """Return Discord files and attachment:// filename for embed.set_image."""
    import discord

    aid = resolve_equipped_avatar_id(avatar_id)
    path = victory_path(aid)
    if not path.is_file():
        return [], None
    filename = victory_attachment_name(aid)
    return [discord.File(str(path), filename=filename)], filename


def build_portrait_attachment(avatar_id: str | None) -> tuple[list[discord.File], str | None]:
    import discord

    aid = resolve_equipped_avatar_id(avatar_id)
    path = portrait_path(aid)
    if not path.is_file():
        return [], None
    filename = f"portrait_{aid}.png"
    return [discord.File(str(path), filename=filename)], filename
