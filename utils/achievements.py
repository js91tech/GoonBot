from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database import Database


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    emoji: str = "🏅"


ACHIEVEMENTS: dict[str, Achievement] = {
    "first_blood": Achievement("first_blood", "First Blood", "Help defeat your first boss.", "🩸"),
    "raid_veteran": Achievement("raid_veteran", "Raid Veteran", "Help defeat 25 bosses.", "⚔️"),
    "mythic_slayer": Achievement("mythic_slayer", "Mythic Slayer", "Help defeat a mythic Hannah.", "🌌"),
    "heist_king": Achievement("heist_king", "Heist King", "Succeed at 10 heists.", "🎭"),
    "field_medic": Achievement("field_medic", "Field Medic", "Revive 25 downed raiders.", "💊"),
    "wealthy": Achievement("wealthy", "Nugget Baron", "Hold 200,000 nuggets at once.", "💰"),
    "excalibur_owner": Achievement(
        "excalibur_owner",
        "Excalibur Bearer",
        "Own a Nugget Excalibur.",
        "👑",
    ),
    "master_crafter": Achievement("master_crafter", "Master Crafter", "Upgrade battle-worn gear once.", "🔨"),
    "prestige_1": Achievement("prestige_1", "Reborn", "Prestige once.", "♻️"),
    "prestige_5": Achievement("prestige_5", "Ascendant", "Reach prestige 5.", "✨"),
    "hundred_raids": Achievement("hundred_raids", "Raid Legend", "Help defeat 100 bosses.", "🏆"),
}


async def evaluate_unlocks(
    db: Database,
    guild_id: int,
    user_id: int,
    *,
    wallet: float | None = None,
) -> list[Achievement]:
    progress = await db.get_user_progress(user_id, guild_id)
    unlocked = await db.list_achievements(user_id, guild_id)
    newly: list[Achievement] = []

    async def grant(achievement_id: str) -> None:
        if achievement_id in unlocked:
            return
        if await db.unlock_achievement(user_id, guild_id, achievement_id):
            achievement = ACHIEVEMENTS[achievement_id]
            newly.append(achievement)
            unlocked.add(achievement_id)

    bosses = int(progress["bosses_killed"])
    if bosses >= 1:
        await grant("first_blood")
    if bosses >= 25:
        await grant("raid_veteran")
    if bosses >= 100:
        await grant("hundred_raids")
    if int(progress["mythic_kills"]) >= 1:
        await grant("mythic_slayer")
    if int(progress["heists_won"]) >= 10:
        await grant("heist_king")
    if int(progress["heals_given"]) >= 25:
        await grant("field_medic")
    if int(progress["crafts_done"]) >= 1:
        await grant("master_crafter")
    prestige = int(progress["prestige_level"])
    if prestige >= 1:
        await grant("prestige_1")
    if prestige >= 5:
        await grant("prestige_5")

    if wallet is None:
        wallet = await db.get_balance(user_id, guild_id)
    if wallet >= 200_000:
        await grant("wealthy")

    rows = await db.get_inventory(user_id, guild_id)
    for row in rows:
        if str(row["item_id"]) == "nugget_excalibur" and int(row["quantity"]) > 0:
            await grant("excalibur_owner")
            break

    return newly


def format_unlock_message(achievements: list[Achievement]) -> str:
    if not achievements:
        return ""
    parts = [f"{a.emoji} **{a.name}** — {a.description}" for a in achievements]
    return "Achievement unlocked!\n" + "\n".join(parts)
