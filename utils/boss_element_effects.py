"""Boss elemental counter procs and hazard descriptions."""
from __future__ import annotations

import random
from dataclasses import dataclass

import config
from utils.character_attributes import (
    DebuffResistance,
    apply_cc_duration,
    apply_debuff_attack_cooldown,
)


@dataclass(frozen=True)
class ElementProcRoll:
    """Outcome of rolling an elemental proc on a boss counter."""

    note: str = ""
    frost_slow_until: float | None = None
    verdant_root_until: float | None = None
    fire_burn: tuple[float, int, float] | None = None
    storm_stun_seconds: float | None = None
    void_mana_drain: int | None = None
    debuff_attack_cooldown: float | None = None


def roll_debuff_attack_cooldown() -> float:
    lo, hi = config.BOSS_DEBUFF_ATTACK_COOLDOWN_SECONDS
    return float(random.randint(lo, hi))


def roll_debuff_duration_for_threat(threat: int) -> float:
    """Stun/freeze/root duration: short base, small tier bonus, hard-capped at 30s."""
    lo, hi = config.BOSS_DEBUFF_DURATION_BASE_SECONDS
    base = random.randint(lo, hi)
    tier_lo, tier_hi = config.BOSS_DEBUFF_DURATION_PER_TIER_SECONDS
    tier_bonus = max(0, threat - 1) * random.randint(tier_lo, tier_hi)
    return min(config.BOSS_DEBUFF_MAX_SECONDS, float(base + tier_bonus))


def debuff_duration_range_for_threat(threat: int) -> tuple[int, int]:
    """Approximate min/max stun/freeze duration for hazard text."""
    base_lo, base_hi = config.BOSS_DEBUFF_DURATION_BASE_SECONDS
    tier_lo, tier_hi = config.BOSS_DEBUFF_DURATION_PER_TIER_SECONDS
    tier_bonus_min = max(0, threat - 1) * tier_lo
    tier_bonus_max = max(0, threat - 1) * tier_hi
    cap = int(config.BOSS_DEBUFF_MAX_SECONDS)
    return (
        min(cap, base_lo + tier_bonus_min),
        min(cap, base_hi + tier_bonus_max),
    )


def _element_hazards() -> dict[str, str]:
    lo, hi = config.BOSS_DEBUFF_DURATION_BASE_SECONDS
    tier_lo, tier_hi = config.BOSS_DEBUFF_DURATION_PER_TIER_SECONDS
    cap = int(config.BOSS_DEBUFF_MAX_SECONDS)
    tier_note = f", +{tier_lo}–{tier_hi}s per threat tier (max **{cap}s**; AGI reduces further)"
    debuff_lo, debuff_hi = config.BOSS_DEBUFF_ATTACK_COOLDOWN_SECONDS
    return {
        "frost": (
            f"❄️ **Frost** — counters may **chill** you "
            f"({debuff_lo}–{debuff_hi}s between attacks for **{lo}–{hi}s**{tier_note})."
        ),
        "fire": (
            f"🔥 **Fire** — counters may **burn** you ({config.BOSS_FIRE_BURN_PROC_CHANCE:.0%} chance, "
            f"{config.BOSS_FIRE_BURN_TICKS} ticks every {config.BOSS_FIRE_BURN_INTERVAL_SECONDS}s)."
        ),
        "storm": (
            f"⚡ **Storm** — counters may **stun** you for **{lo}–{hi}s**{tier_note}."
        ),
        "void": (
            f"🌑 **Void** — counters may **drain mana** ({config.BOSS_VOID_DRAIN_PROC_CHANCE:.0%} chance)."
        ),
        "verdant": (
            f"🌿 **Verdant** — counters may **root** you "
            f"({debuff_lo}–{debuff_hi}s between attacks for **{lo}–{hi}s**{tier_note})."
        ),
    }


def element_hazard_text(element: str | None) -> str | None:
    if not element:
        return None
    return _element_hazards().get(str(element).lower())


def roll_element_proc(
    element: str | None,
    *,
    now: float,
    threat: int = 1,
    resistance: DebuffResistance | None = None,
) -> ElementProcRoll:
    """Roll whether a boss counter applies an elemental rider effect."""
    if not element:
        return ElementProcRoll()
    resist = resistance or DebuffResistance()
    elem = str(element).lower()
    debuff_cd = apply_debuff_attack_cooldown(roll_debuff_attack_cooldown(), resist)

    if elem == "frost" and random.random() < config.BOSS_FROST_PROC_CHANCE * resist.cc_proc_mult:
        duration = apply_cc_duration(roll_debuff_duration_for_threat(threat), resist)
        until = now + duration
        return ElementProcRoll(
            note=(
                f" ❄️ **Chilled!** **{int(debuff_cd)}s** between attacks "
                f"for **{int(duration)}s**."
            ),
            frost_slow_until=until,
            debuff_attack_cooldown=debuff_cd,
        )

    if elem == "fire" and random.random() < config.BOSS_FIRE_BURN_PROC_CHANCE * resist.cc_proc_mult:
        tick_damage = float(
            random.randint(config.BOSS_FIRE_BURN_DAMAGE[0], config.BOSS_FIRE_BURN_DAMAGE[1]),
        )
        tick_damage = max(1.0, tick_damage * resist.dot_damage_mult)
        ticks = config.BOSS_FIRE_BURN_TICKS
        first_tick = now + config.BOSS_FIRE_BURN_INTERVAL_SECONDS
        return ElementProcRoll(
            note=f" 🔥 **Burning!** **{int(tick_damage)}** damage/tick × **{ticks}** ticks.",
            fire_burn=(tick_damage, ticks, first_tick),
        )

    if elem == "storm" and random.random() < config.BOSS_STORM_STUN_PROC_CHANCE * resist.cc_proc_mult:
        stun_seconds = apply_cc_duration(roll_debuff_duration_for_threat(threat), resist)
        return ElementProcRoll(
            note=f" ⚡ **Stunned!** Down for **{int(stun_seconds)}s**.",
            storm_stun_seconds=stun_seconds,
        )

    if elem == "void" and random.random() < config.BOSS_VOID_DRAIN_PROC_CHANCE * resist.cc_proc_mult:
        lo, hi = config.BOSS_VOID_MANA_DRAIN
        drain = max(1, int(random.randint(lo, hi) * resist.void_drain_mult))
        return ElementProcRoll(
            note=f" 🌑 **Void tear!** **{drain}** mana drained.",
            void_mana_drain=drain,
        )

    if elem == "verdant" and random.random() < config.BOSS_VERDANT_ROOT_PROC_CHANCE * resist.cc_proc_mult:
        duration = apply_cc_duration(roll_debuff_duration_for_threat(threat), resist)
        until = now + duration
        return ElementProcRoll(
            note=(
                f" 🌿 **Rooted!** **{int(debuff_cd)}s** between attacks "
                f"for **{int(duration)}s**."
            ),
            verdant_root_until=until,
            debuff_attack_cooldown=debuff_cd,
        )

    return ElementProcRoll()


def attack_cooldown_while_debuffed(
    attack_slow_until: float,
    verdant_root_until: float,
    debuff_attack_cooldown: float,
    *,
    now: float,
) -> float | None:
    """Seconds between boss attacks while chilled or rooted, if a debuff is active."""
    if attack_slow_until <= now and verdant_root_until <= now:
        return None
    if debuff_attack_cooldown > 0:
        return debuff_attack_cooldown
    return roll_debuff_attack_cooldown()
