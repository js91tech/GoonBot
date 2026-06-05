from __future__ import annotations

import config
from utils.loadout import off_hand_power_bonus


def loadout_combat_power(
    weapon_power: int,
    *,
    off_hand_power: int = 0,
    armor_power: int = 0,
) -> int:
    return weapon_power + off_hand_power + armor_power


def power_from_loadout(loadout) -> int:
    """Total gear power for bodyguard defeat scaling."""
    weapon_p = loadout.primary.power if loadout.primary is not None else 0
    off_p = off_hand_power_bonus(loadout.off_hand)
    armor_p = loadout.armor.power if loadout.armor is not None else 0
    return loadout_combat_power(weapon_p, off_hand_power=off_p, armor_power=armor_p)


def bodyguard_defeat_chance(
    thief_power: int,
    heist_tier: int,
    guards: dict[int, int],
) -> float:
    """Chance the thief gets past bodyguards before the tier loot roll."""
    if not guards or sum(guards.values()) <= 0:
        return 1.0

    defense = sum(
        float(config.BODYGUARD_TIERS[tier]["defense"]) * qty
        for tier, qty in guards.items()
        if tier in config.BODYGUARD_TIERS
    )
    max_defense = config.BODYGUARD_MAX_TOTAL * float(config.BODYGUARD_TIERS[3]["defense"])
    defense_ratio = min(1.0, defense / max_defense) if max_defense > 0 else 0.0

    target = config.BODYGUARD_HEIST_TIER_TARGET.get(heist_tier, 0.60)
    base_no_guards = config.BODYGUARD_MAX_GEAR_NO_GUARDS
    chance_at_max_gear = base_no_guards - (base_no_guards - target) * defense_ratio

    gear_ratio = min(1.0, thief_power / config.BODYGUARD_REFERENCE_POWER)
    floor = config.BODYGUARD_NO_GEAR_FLOOR
    chance = floor + (chance_at_max_gear - floor) * gear_ratio
    return max(floor, min(0.95, chance))


def format_bodyguard_roster(guards: dict[int, int]) -> str:
    if not guards or sum(guards.values()) <= 0:
        return "_No bodyguards hired_"
    parts: list[str] = []
    for tier in sorted(guards):
        qty = guards[tier]
        if qty <= 0:
            continue
        name = str(config.BODYGUARD_TIERS[tier]["name"])
        parts.append(f"**{qty}×** {name} (T{tier})")
    return " · ".join(parts) if parts else "_No bodyguards hired_"
