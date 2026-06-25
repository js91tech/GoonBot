"""DM notification eligibility and effective preference resolution."""
from __future__ import annotations

from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from database import Database

NOTIFY_CATEGORY_MASK = (
    config.NOTIFY_CROPS
    | config.NOTIFY_BOSS
    | config.NOTIFY_BUSINESS
    | config.NOTIFY_DEFENSE
)


def notify_opt_out_footer(guild_name: str) -> str:
    return (
        f"\n\n_To stop these DMs: run `/notify` in **{guild_name}** and uncheck "
        "categories (or clear all toggles to opt out)._"
    )


async def is_notify_eligible(db: Database, user_id: int, guild_id: int) -> bool:
    """Active players or anyone who has participated in a boss raid."""
    if await db.get_activity_xp(user_id, guild_id) >= config.NOTIFY_ACTIVE_MIN_XP:
        return True
    if await db.get_boss_damage(user_id, guild_id) > 0:
        return True
    progress = await db.get_user_progress(user_id, guild_id)
    if int(progress["bosses_killed"]) > 0:
        return True
    return False


async def effective_notify_flags(db: Database, user_id: int, guild_id: int) -> int:
    raw = await db.get_notify_flags(user_id, guild_id)
    if raw & config.NOTIFY_USER_CONFIGURED:
        return raw & NOTIFY_CATEGORY_MASK
    if await is_notify_eligible(db, user_id, guild_id):
        return config.NOTIFY_ELIGIBLE_DEFAULT_FLAGS
    return 0


async def panel_notify_flags(db: Database, user_id: int, guild_id: int) -> tuple[int, bool, bool]:
    """Return (display_flags, user_configured, eligible) for the /notify panel."""
    raw = await db.get_notify_flags(user_id, guild_id)
    configured = bool(raw & config.NOTIFY_USER_CONFIGURED)
    eligible = await is_notify_eligible(db, user_id, guild_id)
    if configured:
        display = raw & NOTIFY_CATEGORY_MASK
    elif eligible:
        display = config.NOTIFY_ELIGIBLE_DEFAULT_FLAGS
    else:
        display = 0
    return display, configured, eligible
