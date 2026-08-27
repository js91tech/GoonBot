"""Boss elemental counter procs and hazard descriptions."""
from __future__ import annotations

import random
from dataclasses import dataclass

import config
from utils.character_attributes import DebuffResistance


@dataclass(frozen=True)
class ElementProcRoll:
    """Outcome of rolling an elemental proc on a boss counter."""

    note: str = ""
    fire_burn: tuple[float, int, float] | None = None
    void_mana_drain: int | None = None


def roll_debuff_attack_cooldown() -> float:
    lo, hi = config.BOSS_DEBUFF_ATTACK_COOLDOWN_SECONDS
    return float(random.randint(lo, hi))


def roll_debuff_duration_for_threat(threat: int) -> float:
    """Legacy duration helper (knockdown still uses BOSS_DEBUFF_MAX_SECONDS)."""
    lo, hi = config.BOSS_DEBUFF_DURATION_BASE_SECONDS
    base = random.randint(lo, hi)
    tier_lo, tier_hi = config.BOSS_DEBUFF_DURATION_PER_TIER_SECONDS
    tier_bonus = max(0, threat - 1) * random.randint(tier_lo, tier_hi)
    return min(config.BOSS_DEBUFF_MAX_SECONDS, float(base + tier_bonus))


def debuff_duration_range_for_threat(threat: int) -> tuple[int, int]:
    """Approximate min/max duration for leftover duration-helper tests."""
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
    """Crowd-control hazards (chill/stun/root) are disabled. Fire/void remain."""
    return {
        "fire": (
            f"🔥 **Fire** — counters may **burn** you ({config.BOSS_FIRE_BURN_PROC_CHANCE:.0%} chance, "
            f"{config.BOSS_FIRE_BURN_TICKS} ticks every {config.BOSS_FIRE_BURN_INTERVAL_SECONDS}s)."
        ),
        "void": (
            f"🌑 **Void** — counters may **drain mana** ({config.BOSS_VOID_DRAIN_PROC_CHANCE:.0%} chance)."
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
    """Roll whether a boss counter applies an elemental rider effect.

    Frost chill, storm stun, and verdant root are not applied.
    """
    if not element:
        return ElementProcRoll()
    resist = resistance or DebuffResistance()
    elem = str(element).lower()

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

    if elem == "void" and random.random() < config.BOSS_VOID_DRAIN_PROC_CHANCE * resist.cc_proc_mult:
        lo, hi = config.BOSS_VOID_MANA_DRAIN
        drain = max(1, int(random.randint(lo, hi) * resist.void_drain_mult))
        return ElementProcRoll(
            note=f" 🌑 **Void tear!** **{drain}** mana drained.",
            void_mana_drain=drain,
        )

    return ElementProcRoll()


def attack_cooldown_while_debuffed(
    attack_slow_until: float,
    verdant_root_until: float,
    debuff_attack_cooldown: float,
    *,
    now: float,
) -> float | None:
    """Boss chill/root no longer changes attack pacing; leftover columns are ignored."""
    del attack_slow_until, verdant_root_until, debuff_attack_cooldown, now
    return None
