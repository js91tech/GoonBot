from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "avatars"
CUSTOM_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "custom"
DEFAULT_AVATAR_ID = "nugget_raider"
CUSTOM_AVATAR_PREFIX = "custom_"


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


def custom_avatar_id(user_id: int) -> str:
    return f"{CUSTOM_AVATAR_PREFIX}{user_id}"


def is_custom_avatar_id(avatar_id: str) -> bool:
    return avatar_id.startswith(CUSTOM_AVATAR_PREFIX)


def custom_avatar_dir(guild_id: int, user_id: int) -> Path:
    return CUSTOM_ASSETS_ROOT / str(guild_id) / str(user_id)


def get_avatar(avatar_id: str | None) -> AvatarDef | None:
    if not avatar_id:
        return AVATAR_MAP.get(DEFAULT_AVATAR_ID)
    if is_custom_avatar_id(avatar_id):
        return AvatarDef(avatar_id, "Custom Avatar", "Your uploaded victory art.", 0.0, "🎨")
    return AVATAR_MAP.get(avatar_id.strip().lower())


def portrait_path(avatar_id: str, *, guild_id: int | None = None, user_id: int | None = None) -> Path:
    if is_custom_avatar_id(avatar_id) and guild_id is not None and user_id is not None:
        folder = custom_avatar_dir(guild_id, user_id)
        for name in ("portrait.png", "portrait.gif", "portrait.jpg"):
            path = folder / name
            if path.is_file():
                return path
    return ASSETS_ROOT / avatar_id / "portrait.png"


def victory_path(
    avatar_id: str,
    *,
    guild_id: int | None = None,
    user_id: int | None = None,
) -> Path:
    if is_custom_avatar_id(avatar_id) and guild_id is not None and user_id is not None:
        folder = custom_avatar_dir(guild_id, user_id)
        for name in ("victory.gif", "victory.png", "victory.jpg"):
            path = folder / name
            if path.is_file():
                return path
    gif = ASSETS_ROOT / avatar_id / "victory.gif"
    if gif.is_file():
        return gif
    return ASSETS_ROOT / avatar_id / "victory.png"


def victory_attachment_name(avatar_id: str) -> str:
    path = victory_path(avatar_id)
    return f"victory_{avatar_id}{path.suffix}"


def resolve_equipped_avatar_id(stored: str | None) -> str:
    if stored and (stored in AVATAR_MAP or is_custom_avatar_id(stored)):
        return stored
    return DEFAULT_AVATAR_ID


def build_victory_attachment(
    avatar_id: str | None,
    *,
    guild_id: int | None = None,
    user_id: int | None = None,
) -> tuple[list[discord.File], str | None]:
    """Return Discord files and attachment:// filename for embed.set_image."""
    import discord

    aid = resolve_equipped_avatar_id(avatar_id)
    uid = user_id
    if is_custom_avatar_id(aid):
        try:
            uid = int(aid.removeprefix(CUSTOM_AVATAR_PREFIX))
        except ValueError:
            uid = user_id
    path = victory_path(aid, guild_id=guild_id, user_id=uid)
    if not path.is_file():
        return [], None
    filename = f"victory_{aid}{path.suffix}"
    return [discord.File(str(path), filename=filename)], filename


def build_portrait_attachment(
    avatar_id: str | None,
    *,
    guild_id: int | None = None,
    user_id: int | None = None,
) -> tuple[list[discord.File], str | None]:
    import discord

    aid = resolve_equipped_avatar_id(avatar_id)
    uid = user_id
    if is_custom_avatar_id(aid):
        try:
            uid = int(aid.removeprefix(CUSTOM_AVATAR_PREFIX))
        except ValueError:
            uid = user_id
    path = portrait_path(aid, guild_id=guild_id, user_id=uid)
    if not path.is_file():
        return [], None
    filename = f"portrait_{aid}{path.suffix}"
    return [discord.File(str(path), filename=filename)], filename
