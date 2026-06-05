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
            return min(config.ATTR_MAX_VALUE, int(raw))

        return cls(
            strength=_get("stat_str"),
            dexterity=_get("stat_dex"),
            agility=_get("stat_agi"),
            defense=_get("stat_def"),
            vitality=_get("stat_vit"),
        )


def attribute_point_cap(prestige_level: int) -> int:
    """Total allocatable points; prestige 0 = 50, prestige 10 = 100."""
    return config.ATTR_BASE_TOTAL_POINTS + prestige_level * config.ATTR_POINTS_PER_PRESTIGE


def xp_required_for_attribute_points(point_count: int) -> int:
    """Cumulative class XP to earn N attribute points (first 20 are cheaper)."""
    if point_count <= 0:
        return 0
    fast = min(point_count, config.ATTR_FAST_POINT_COUNT)
    slow = max(0, point_count - config.ATTR_FAST_POINT_COUNT)
    return (
        fast * config.ATTR_XP_PER_FAST_POINT
        + slow * config.ATTR_XP_PER_SLOW_POINT
    )


def attribute_points_from_class_xp(class_xp: int) -> int:
    """How many points class XP has earned (ignores prestige cap)."""
    max_points = attribute_point_cap(config.PRESTIGE_MAX_LEVEL)
    lo, hi = 0, max_points
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if xp_required_for_attribute_points(mid) <= class_xp:
            lo = mid
        else:
            hi = mid - 1
    return lo


def total_attribute_points_available(class_xp: int, prestige_level: int) -> int:
    """Earned points limited by current prestige pool cap."""
    earned = attribute_points_from_class_xp(class_xp)
    return min(earned, attribute_point_cap(prestige_level))


def unspent_attribute_points(
    attrs: CharacterAttributes,
    class_xp: int,
    prestige_level: int,
) -> int:
    return max(
        0,
        total_attribute_points_available(class_xp, prestige_level) - attrs.points_spent(),
    )


def xp_until_next_attribute_point(
    class_xp: int,
    prestige_level: int,
    attrs: CharacterAttributes,
) -> int | None:
    """Class XP still needed for the next point, or None if capped."""
    cap = attribute_point_cap(prestige_level)
    earned = attribute_points_from_class_xp(class_xp)
    if attrs.points_spent() >= cap:
        return None
    if earned > attrs.points_spent() and total_attribute_points_available(class_xp, prestige_level) > attrs.points_spent():
        return 0
    next_point = earned + 1
    if next_point > cap:
        return None
    return max(0, xp_required_for_attribute_points(next_point) - class_xp)


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


def format_attributes_block(
    attrs: CharacterAttributes,
    *,
    class_xp: int,
    prestige_level: int = 0,
) -> str:
    cap = attribute_point_cap(prestige_level)
    available = total_attribute_points_available(class_xp, prestige_level)
    unspent = unspent_attribute_points(attrs, class_xp, prestige_level)
    lines = [
        f"**{STAT_EMOJI[name]} {STAT_LABELS[name]}** **{attrs.value(name)}** / **{config.ATTR_MAX_VALUE}**"
        for name in STAT_KEYS
    ]
    lines.append(
        f"Pool: **{attrs.points_spent()}/{available}** allocated"
        f" (prestige cap **{cap}**)"
        + (f" · **{unspent}** unspent" if unspent else "")
    )
    xp_left = xp_until_next_attribute_point(class_xp, prestige_level, attrs)
    if xp_left is not None and xp_left > 0:
        lines.append(f"Next point in **{xp_left}** class XP")
    elif available >= cap and attribute_points_from_class_xp(class_xp) >= cap:
        lines.append("Prestige up to raise your attribute point cap (+5 per level).")
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
