"""Generate and persist unique per-player default avatar assets."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from utils.avatar_portrait import portrait_spec_for_user, write_portrait_assets

DEFAULT_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "defaults"
UNIQUE_DEFAULT_PREFIX = "raider_"
GENERATION_VERSION = 2

logger = logging.getLogger(__name__)


def unique_default_avatar_id(user_id: int, guild_id: int) -> str:
    digest = hashlib.sha256(f"{user_id}:{guild_id}".encode()).hexdigest()[:10]
    return f"{UNIQUE_DEFAULT_PREFIX}{digest}"


def unique_default_avatar_dir(guild_id: int, user_id: int) -> Path:
    return DEFAULT_ASSETS_ROOT / str(guild_id) / str(user_id)


def default_assets_ready(guild_id: int, user_id: int) -> bool:
    folder = unique_default_avatar_dir(guild_id, user_id)
    version_file = folder / ".generation"
    if version_file.is_file():
        try:
            if int(version_file.read_text().strip()) < GENERATION_VERSION:
                return False
        except ValueError:
            return False
    elif (folder / "portrait.png").is_file():
        return False
    if not (folder / "portrait.png").is_file():
        return False
    return (folder / "victory.gif").is_file() or (folder / "victory.png").is_file()


def _mark_generation(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".generation").write_text(str(GENERATION_VERSION))


def _generate_procedural_assets(user_id: int, guild_id: int, folder: Path) -> None:
    spec = portrait_spec_for_user(user_id, guild_id)
    write_portrait_assets(spec, folder)
    _mark_generation(folder)
    logger.info(
        "Generated procedural default avatar for user %s guild %s (%s / %s)",
        user_id,
        guild_id,
        spec.archetype,
        spec.hair_style,
    )


def ensure_default_avatar_assets(user_id: int, guild_id: int) -> Path:
    """Sync entry point — rich procedural portraits."""
    folder = unique_default_avatar_dir(guild_id, user_id)
    if default_assets_ready(guild_id, user_id):
        return folder
    _generate_procedural_assets(user_id, guild_id, folder)
    return folder


async def ensure_default_avatar_assets_async(user_id: int, guild_id: int) -> Path:
    """Generate unique portrait art; tries AI image API first when configured."""
    folder = unique_default_avatar_dir(guild_id, user_id)
    if default_assets_ready(guild_id, user_id):
        return folder

    import config

    if config.AI_API_KEY and config.AVATAR_AI_GENERATION:
        from utils.avatar_ai import try_generate_ai_avatar

        if await try_generate_ai_avatar(user_id, guild_id, folder):
            _mark_generation(folder)
            logger.info("Generated AI default avatar for user %s guild %s", user_id, guild_id)
            return folder

    await asyncio.to_thread(_generate_procedural_assets, user_id, guild_id, folder)
    return folder
