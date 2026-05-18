from __future__ import annotations

from dataclasses import dataclass

from utils.skills import SpellBuff


@dataclass
class CombatSpellState:
    buff: SpellBuff | None = None
    damage_mult: float = 1.0
    fortify_mult: float = 1.0
    extra_crit: float = 0.0
    heal_self_fraction: float = 0.0
    heal_ally_fraction: float = 0.0
    income_bonus: float = 0.0
    heist_bonus: float = 0.0


def combat_state_from_spell(spell: SpellBuff | None) -> CombatSpellState:
    if spell is None:
        return CombatSpellState()
    effect = spell.effect
    mag = spell.magnitude
    if effect in ("damage_boost", "heavy_strike", "chaos_card"):
        return CombatSpellState(buff=spell, damage_mult=mag)
    if effect == "crit_surge":
        return CombatSpellState(buff=spell, extra_crit=mag)
    if effect == "fortify":
        return CombatSpellState(buff=spell, fortify_mult=mag)
    if effect == "heal_self":
        return CombatSpellState(buff=spell, heal_self_fraction=mag)
    if effect == "heal_ally":
        return CombatSpellState(buff=spell, heal_ally_fraction=mag)
    if effect == "income_spark":
        return CombatSpellState(buff=spell, income_bonus=mag)
    if effect == "heist_smoke":
        return CombatSpellState(buff=spell, heist_bonus=mag)
    return CombatSpellState(buff=spell)
