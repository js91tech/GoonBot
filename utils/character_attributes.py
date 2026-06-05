"""Character attributes (STR/DEX/AGI/DEF/VIT) earned from class XP."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import config

AttributeName = Literal["strength", "dexterity", "agility", "defense", "vitality"]
STAT_KEYS: tuple[AttributeName, ...] = (
    "strength",
    "dexterity",
    "agility",
    "defense",
    "vitality",
)
STAT_COLUMNS: dict[AttributeName, str] = {
    "strength": "stat_str",
    "dexterity": "stat_dex",
    "agility": "stat_agi",
    "defense": "stat_def",
    "vitality": "stat_vit",
}
STAT_LABELS: dict[AttributeName, str] = {
    "strength": "STR",
    "dexterity": "DEX",
    "agility": "AGI",
    "defense": "DEF",
    "vitality": "VIT",
}
STAT_EMOJI: dict[AttributeName, str] = {
    "strength": "💪",
    "dexterity": "🎯",
    "agility": "💨",
    "defense": "🛡️",
    "vitality": "❤️",
}


@dataclass(frozen=True)
class CharacterAttributes:
    strength: int = config.ATTR_BASE_VALUE
    dexterity: int = config.ATTR_BASE_VALUE
    agility: int = config.ATTR_BASE_VALUE
    defense: int = config.ATTR_BASE_VALUE
    vitality: int = config.ATTR_BASE_VALUE

    def value(self, name: AttributeName) -> int:
        return getattr(self, name)

    def points_spent(self) -> int:
        base = config.ATTR_BASE_VALUE
        return sum(max(0, self.value(name) - base) for name in STAT_KEYS)

    @classmethod
    def from_row(cls, row) -> CharacterAttributes:
        def _get(col: str) -> int:
            try:
                raw = row[col]
            except (KeyError, IndexError, TypeError):
                return config.ATTR_BASE_VALUE
            if raw is None:
                return config.ATTR_BASE_VALUE
            return int(raw)

        return cls(
            strength=_get("stat_str"),
            dexterity=_get("stat_dex"),
            agility=_get("stat_agi"),
            defense=_get("stat_def"),
            vitality=_get("stat_vit"),
        )


def total_attribute_points_earned(class_xp: int) -> int:
    earned = class_xp // config.ATTR_XP_PER_POINT
    return min(config.ATTR_MAX_TOTAL_POINTS, earned)


def unspent_attribute_points(attrs: CharacterAttributes, class_xp: int) -> int:
    return max(0, total_attribute_points_earned(class_xp) - attrs.points_spent())


def _bonus_points(value: int) -> int:
    return max(0, value - config.ATTR_BASE_VALUE)


@dataclass(frozen=True)
class AttributeCombatBonuses:
    """Combat modifiers derived from allocated attributes."""

    damage_mult: float = 1.0
    extra_crit: float = 0.0
    mitigation_bonus: float = 0.0
    hp_bonus: int = 0


@dataclass(frozen=True)
class DebuffResistance:
    """Multipliers applied to boss elemental debuffs (lower = less effect)."""

    cc_duration_mult: float = 1.0
    cc_proc_mult: float = 1.0
    debuff_attack_cd_mult: float = 1.0
    dot_damage_mult: float = 1.0
    void_drain_mult: float = 1.0


def combat_bonuses_from_attributes(attrs: CharacterAttributes) -> AttributeCombatBonuses:
    str_bonus = _bonus_points(attrs.strength)
    dex_bonus = _bonus_points(attrs.dexterity)
    def_bonus = _bonus_points(attrs.defense)
    vit_bonus = _bonus_points(attrs.vitality)

    damage_mult = 1.0 + str_bonus * config.ATTR_STR_DAMAGE_PCT
    extra_crit = min(
        config.ATTR_MAX_DEX_CRIT_BONUS,
        dex_bonus * config.ATTR_DEX_CRIT_PCT,
    )
    mitigation_bonus = min(
        config.ATTR_MAX_DEF_MITIGATION_BONUS,
        def_bonus * config.ATTR_DEF_MITIGATION_PCT,
    )
    hp_bonus = vit_bonus * config.ATTR_VIT_HP_PER_POINT
    return AttributeCombatBonuses(
        damage_mult=damage_mult,
        extra_crit=extra_crit,
        mitigation_bonus=mitigation_bonus,
        hp_bonus=hp_bonus,
    )


def debuff_resistance_from_attributes(attrs: CharacterAttributes) -> DebuffResistance:
    agi_bonus = _bonus_points(attrs.agility)
    def_bonus = _bonus_points(attrs.defense)

    cc_duration_reduction = min(
        config.ATTR_MAX_CC_DURATION_REDUCTION,
        agi_bonus * config.ATTR_AGI_CC_DURATION_PCT,
    )
    cc_proc_resist = min(
        config.ATTR_MAX_CC_PROC_RESIST,
        agi_bonus * config.ATTR_AGI_CC_PROC_RESIST_PCT,
    )
    attack_cd_reduction = min(0.35, agi_bonus * config.ATTR_AGI_ATTACK_CD_PCT)
    dot_resist = min(
        config.ATTR_MAX_DOT_RESIST,
        def_bonus * config.ATTR_DEF_DOT_RESIST_PCT,
    )

    return DebuffResistance(
        cc_duration_mult=max(0.25, 1.0 - cc_duration_reduction),
        cc_proc_mult=max(0.35, 1.0 - cc_proc_resist),
        debuff_attack_cd_mult=max(0.65, 1.0 - attack_cd_reduction),
        dot_damage_mult=max(0.50, 1.0 - dot_resist),
        void_drain_mult=max(0.50, 1.0 - dot_resist),
    )


def apply_cc_duration(duration: float, resistance: DebuffResistance) -> float:
    reduced = duration * resistance.cc_duration_mult
    return max(config.ATTR_MIN_DEBUFF_SECONDS, reduced)


def apply_debuff_attack_cooldown(cooldown: float, resistance: DebuffResistance) -> float:
    return max(2.0, cooldown * resistance.debuff_attack_cd_mult)


def format_attributes_block(attrs: CharacterAttributes, *, class_xp: int) -> str:
    unspent = unspent_attribute_points(attrs, class_xp)
    earned = total_attribute_points_earned(class_xp)
    lines = [
        f"**{STAT_EMOJI[name]} {STAT_LABELS[name]}** **{attrs.value(name)}**"
        for name in STAT_KEYS
    ]
    lines.append(
        f"Points: **{attrs.points_spent()}/{earned}** spent"
        + (f" · **{unspent}** unspent" if unspent else "")
    )
    combat = combat_bonuses_from_attributes(attrs)
    resist = debuff_resistance_from_attributes(attrs)
    effect_lines = []
    if combat.damage_mult > 1.0:
        effect_lines.append(f"+{int(round((combat.damage_mult - 1) * 100))}% damage (STR)")
    if combat.extra_crit > 0:
        effect_lines.append(f"+{int(round(combat.extra_crit * 100))}% crit (DEX)")
    if combat.mitigation_bonus > 0:
        effect_lines.append(f"+{int(round(combat.mitigation_bonus * 100))}% mitigation (DEF)")
    if combat.hp_bonus > 0:
        effect_lines.append(f"+{combat.hp_bonus} HP (VIT)")
    cc_red = int(round((1.0 - resist.cc_duration_mult) * 100))
    if cc_red > 0:
        effect_lines.append(f"-{cc_red}% stun/root/chill duration (AGI)")
    proc_red = int(round((1.0 - resist.cc_proc_mult) * 100))
    if proc_red > 0:
        effect_lines.append(f"-{proc_red}% debuff proc chance (AGI)")
    dot_red = int(round((1.0 - resist.dot_damage_mult) * 100))
    if dot_red > 0:
        effect_lines.append(f"-{dot_red}% burn/void drain (DEF)")
    if effect_lines:
        lines.append("**Effects** — " + " · ".join(effect_lines))
    return "\n".join(lines)


def normalize_stat_name(raw: str) -> AttributeName | None:
    key = raw.strip().lower()
    aliases: dict[str, AttributeName] = {
        "str": "strength",
        "strength": "strength",
        "dex": "dexterity",
        "dexterity": "dexterity",
        "agi": "agility",
        "agility": "agility",
        "def": "defense",
        "defense": "defense",
        "vit": "vitality",
        "vitality": "vitality",
        "health": "vitality",
        "hp": "vitality",
    }
    return aliases.get(key)
