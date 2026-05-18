from __future__ import annotations

import random
from dataclasses import dataclass, field

import config
from items import ShopItem
from utils.combat_engine import (
    AttackContext,
    apply_armor_mitigation,
    max_hp_from_armor,
    roll_jester_reflect,
    roll_player_damage,
)
from utils.spell_effects import CombatSpellState
from utils.gear_sets import SetBonus, detect_set_bonus
from utils.loadout import parse_loadout


@dataclass
class DuelFighter:
    user_id: int
    display_name: str
    weapon: ShopItem | None
    off_hand: ShopItem | None
    armor: ShopItem | None
    set_bonus: SetBonus | None
    prestige_level: int
    max_hp: int
    hp: int
    class_id: str | None = None
    spell_state: CombatSpellState | None = None
    spell_offense_used: bool = False
    spell_defense_used: bool = False


@dataclass(frozen=True)
class DuelStrike:
    attacker_id: int
    defender_id: int
    damage: int
    mitigated: int
    critical: bool
    verb: str
    defender_hp_after: int
    jester_reflect: bool = False


@dataclass(frozen=True)
class DuelResult:
    winner_id: int
    loser_id: int
    strikes: list[DuelStrike] = field(default_factory=list)
    jester_steals: list[tuple[int, int, float]] = field(default_factory=list)


def fighter_from_equipment(
    user_id: int,
    display_name: str,
    equipment: dict[str, str],
    *,
    prestige_level: int,
    class_id: str | None = None,
    class_modifiers=None,
) -> DuelFighter:
    from utils.classes import get_modifiers

    loadout = parse_loadout(equipment)
    set_bonus = detect_set_bonus(loadout.primary, loadout.armor)
    mods = class_modifiers if class_modifiers is not None else get_modifiers(class_id)
    max_hp = max_hp_from_armor(loadout.armor, class_modifiers=mods)
    return DuelFighter(
        user_id=user_id,
        display_name=display_name,
        weapon=loadout.primary,
        off_hand=loadout.off_hand,
        armor=loadout.armor,
        set_bonus=set_bonus,
        prestige_level=prestige_level,
        class_id=class_id,
        max_hp=max_hp,
        hp=max_hp,
    )


def _attack_context(
    attacker: DuelFighter,
    defender: DuelFighter,
) -> AttackContext:
    from utils.combat_engine import attack_context_for_class

    return attack_context_for_class(
        attacker.class_id,
        prestige_level=attacker.prestige_level,
        defender_class_id=defender.class_id,
    )


def _one_strike(attacker: DuelFighter, defender: DuelFighter) -> DuelStrike:
    reflect = roll_jester_reflect(defender.class_id)
    if reflect.proc:
        attacker.hp = 0
        return DuelStrike(
            attacker_id=attacker.user_id,
            defender_id=defender.user_id,
            damage=0,
            mitigated=0,
            critical=False,
            verb="fumbles",
            defender_hp_after=defender.hp,
            jester_reflect=True,
        )

    ctx = _attack_context(attacker, defender)
    damage_mult = ctx.damage_mult
    extra_crit = ctx.extra_crit
    if attacker.spell_state is not None and not attacker.spell_offense_used:
        st = attacker.spell_state
        if st.damage_mult > 1.0:
            damage_mult *= st.damage_mult
            attacker.spell_offense_used = True
        if st.extra_crit > 0:
            extra_crit += st.extra_crit
            attacker.spell_offense_used = True
    ctx = AttackContext(
        prestige_level=ctx.prestige_level,
        class_modifiers=ctx.class_modifiers,
        damage_mult=damage_mult,
        extra_crit=extra_crit,
        pvp_matchup_mult=ctx.pvp_matchup_mult,
        boss_element_mult=ctx.boss_element_mult,
    )
    raw, critical, verb = roll_player_damage(
        attacker.weapon,
        off_hand=attacker.off_hand,
        ctx=ctx,
        set_bonus=attacker.set_bonus,
    )
    from utils.classes import get_modifiers

    fortify_mult = 1.0
    if defender.spell_state is not None and not defender.spell_defense_used:
        if defender.spell_state.fortify_mult < 1.0:
            fortify_mult = defender.spell_state.fortify_mult
            defender.spell_defense_used = True
    mitigated_raw = max(1, int(raw * fortify_mult)) if fortify_mult < 1.0 else raw
    damage, mitigated = apply_armor_mitigation(
        mitigated_raw,
        defender.armor,
        set_bonus=defender.set_bonus,
        class_modifiers=get_modifiers(defender.class_id),
    )
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
    jester_steals: list[tuple[int, int, float]] = []
    max_turns = config.DUEL_MAX_COMBAT_ROUNDS * 2
    for turn in range(max_turns):
        if attacker.hp <= 0 or defender.hp <= 0:
            break
        if turn % 2 == 0:
            strike = _one_strike(attacker, defender)
        else:
            strike = _one_strike(defender, attacker)
        strikes.append(strike)
        if strike.jester_reflect:
            jester_id = strike.defender_id
            victim_id = strike.attacker_id
            jester_steals.append((jester_id, victim_id, 0.0))

    if attacker.hp > defender.hp:
        winner_id = attacker.user_id
    elif defender.hp > attacker.hp:
        winner_id = defender.user_id
    elif attacker.max_hp >= defender.max_hp:
        winner_id = attacker.user_id
    else:
        winner_id = defender.user_id

    loser_id = defender.user_id if winner_id == attacker.user_id else attacker.user_id
    return DuelResult(winner_id=winner_id, loser_id=loser_id, strikes=strikes, jester_steals=jester_steals)


def format_strike_line(strike: DuelStrike, fighters: dict[int, DuelFighter]) -> str:
    attacker = fighters[strike.attacker_id]
    defender = fighters[strike.defender_id]
    if strike.jester_reflect:
        return (
            f"**{attacker.display_name}** attacks **{defender.display_name}** — "
            f"**who me?** The strike fails and **{attacker.display_name}** is instantly downed!"
        )
    crit = " **CRIT**" if strike.critical else ""
    mit = f" ({strike.mitigated} blocked)" if strike.mitigated else ""
    return (
        f"**{attacker.display_name}** {strike.verb} **{defender.display_name}** "
        f"for **{strike.damage}**{mit}{crit} → {strike.defender_hp_after}/{defender.max_hp} HP"
    )
