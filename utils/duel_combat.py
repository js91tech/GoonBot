from __future__ import annotations

import random
from dataclasses import dataclass, field

import config
from items import ShopItem, get_item
from utils.gear_sets import SetBonus, detect_set_bonus


@dataclass
class DuelFighter:
    user_id: int
    display_name: str
    weapon: ShopItem | None
    armor: ShopItem | None
    set_bonus: SetBonus | None
    prestige_level: int
    max_hp: int
    hp: int


@dataclass(frozen=True)
class DuelStrike:
    attacker_id: int
    defender_id: int
    damage: int
    mitigated: int
    critical: bool
    verb: str
    defender_hp_after: int


@dataclass(frozen=True)
class DuelResult:
    winner_id: int
    loser_id: int
    strikes: list[DuelStrike] = field(default_factory=list)


def fighter_from_equipment(
    user_id: int,
    display_name: str,
    equipment: dict[str, str],
    *,
    prestige_level: int,
) -> DuelFighter:
    weapon = get_item(equipment["weapon"]) if equipment.get("weapon") else None
    armor = get_item(equipment["armor"]) if equipment.get("armor") else None
    set_bonus = detect_set_bonus(weapon, armor)
    max_hp = config.PLAYER_BASE_HP + (armor.hp_bonus if armor is not None else 0)
    return DuelFighter(
        user_id=user_id,
        display_name=display_name,
        weapon=weapon,
        armor=armor,
        set_bonus=set_bonus,
        prestige_level=prestige_level,
        max_hp=max_hp,
        hp=max_hp,
    )


def _attack_roll(
    attacker: DuelFighter,
    *,
    damage_mult: float = 1.0,
) -> tuple[int, bool, str]:
    extra_crit = attacker.prestige_level * config.PRESTIGE_CRIT_BONUS_PER_LEVEL
    weapon = attacker.weapon
    if weapon is None:
        low = int(config.BOSS_UNARMED_MIN * damage_mult)
        high = int(config.BOSS_UNARMED_MAX * damage_mult)
        damage = random.randint(low, max(low, high))
        crit_chance = config.PLAYER_BASE_CRIT_CHANCE + extra_crit
        verb = "hits"
    else:
        low = int((weapon.power + config.BOSS_ATTACK_BONUS_MIN) * damage_mult)
        high = int((weapon.power + config.BOSS_ATTACK_BONUS_MAX) * damage_mult)
        damage = random.randint(low, max(low, high))
        crit_chance = config.PLAYER_BASE_CRIT_CHANCE + weapon.crit_chance + extra_crit
        verb = random.choice(weapon.verbs or ("strikes",))
    critical = random.random() < crit_chance
    if critical:
        damage = int(damage * config.PLAYER_ATTACK_CRIT_MULTIPLIER)
    return damage, critical, verb


def _apply_mitigation(
    raw_damage: int,
    defender: DuelFighter,
) -> tuple[int, int]:
    armor = defender.armor
    if armor is None:
        return raw_damage, 0
    mitigated = int(raw_damage * armor.power / (armor.power + 100))
    if defender.set_bonus is not None:
        mitigated += int(raw_damage * defender.set_bonus.mitigation_bonus)
    mitigated = min(raw_damage - 1, mitigated)
    return max(1, raw_damage - mitigated), mitigated


def _one_strike(attacker: DuelFighter, defender: DuelFighter) -> DuelStrike:
    damage_mult = attacker.set_bonus.damage_mult if attacker.set_bonus is not None else 1.0
    raw, critical, verb = _attack_roll(attacker, damage_mult=damage_mult)
    damage, mitigated = _apply_mitigation(raw, defender)
    defender.hp = max(0, defender.hp - damage)
    return DuelStrike(
        attacker_id=attacker.user_id,
        defender_id=defender.user_id,
        damage=damage,
        mitigated=mitigated,
        critical=critical,
        verb=verb,
        defender_hp_after=defender.hp,
    )


def simulate_duel(attacker: DuelFighter, defender: DuelFighter) -> DuelResult:
    """Turn-based fight; challenger (attacker) strikes first."""
    strikes: list[DuelStrike] = []
    max_turns = config.DUEL_MAX_COMBAT_ROUNDS * 2
    for turn in range(max_turns):
        if attacker.hp <= 0 or defender.hp <= 0:
            break
        if turn % 2 == 0:
            strikes.append(_one_strike(attacker, defender))
        else:
            strikes.append(_one_strike(defender, attacker))

    if attacker.hp > defender.hp:
        winner_id = attacker.user_id
    elif defender.hp > attacker.hp:
        winner_id = defender.user_id
    elif attacker.max_hp >= defender.max_hp:
        winner_id = attacker.user_id
    else:
        winner_id = defender.user_id

    loser_id = defender.user_id if winner_id == attacker.user_id else attacker.user_id
    return DuelResult(winner_id=winner_id, loser_id=loser_id, strikes=strikes)


def format_strike_line(strike: DuelStrike, fighters: dict[int, DuelFighter]) -> str:
    attacker = fighters[strike.attacker_id]
    defender = fighters[strike.defender_id]
    crit = " **CRIT**" if strike.critical else ""
    mit = f" ({strike.mitigated} blocked)" if strike.mitigated else ""
    return (
        f"**{attacker.display_name}** {strike.verb} **{defender.display_name}** "
        f"for **{strike.damage}**{mit}{crit} → {strike.defender_hp_after}/{defender.max_hp} HP"
    )
