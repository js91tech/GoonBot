"""Boss elemental counter procs and hazard descriptions."""
from __future__ import annotations

import random
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class ElementProcRoll:
    """Outcome of rolling an elemental proc on a boss counter."""

    note: str = ""
    frost_slow_until: float | None = None
    verdant_root_until: float | None = None
    fire_burn: tuple[float, int, float] | None = None
    storm_stun_seconds: float | None = None
    void_mana_drain: int | None = None





def _element_hazards() -> dict[str, str]:
    return {
        "frost": (
            f"❄️ **Frost** — counters may **slow** you (+{config.BOSS_FROST_EXTRA_ATTACK_COOLDOWN}s between attacks for {config.BOSS_FROST_SLOW_SECONDS}s)."
        ),
        "fire": (
            f"🔥 **Fire** — counters may **burn** you ({config.BOSS_FIRE_BURN_PROC_CHANCE:.0%} chance, "
            f"{config.BOSS_FIRE_BURN_TICKS} ticks every {config.BOSS_FIRE_BURN_INTERVAL_SECONDS}s)."
        ),
        "storm": (
            f"⚡ **Storm** — counters may **stun** you for **{config.BOSS_STORM_STUN_SECONDS[0]}–{config.BOSS_STORM_STUN_SECONDS[1]}s**."
        ),
        "void": (
            f"🌑 **Void** — counters may **drain mana** ({config.BOSS_VOID_DRAIN_PROC_CHANCE:.0%} chance)."
        ),
        "verdant": (
            f"🌿 **Verdant** — counters may **root** you (+{config.BOSS_VERDANT_EXTRA_ATTACK_COOLDOWN}s between attacks for {config.BOSS_VERDANT_ROOT_SECONDS}s)."
        ),
    }


def element_hazard_text(element: str | None) -> str | None:
    if not element:
        return None
    return _element_hazards().get(str(element).lower())


def roll_element_proc(element: str | None, *, now: float) -> ElementProcRoll:
    """Roll whether a boss counter applies an elemental rider effect."""
    if not element:
        return ElementProcRoll()
    elem = str(element).lower()

    if elem == "frost" and random.random() < config.BOSS_FROST_PROC_CHANCE:
        until = now + config.BOSS_FROST_SLOW_SECONDS
        return ElementProcRoll(
            note=(
                f" ❄️ **Chilled!** +{config.BOSS_FROST_EXTRA_ATTACK_COOLDOWN}s "
                f"between attacks for **{config.BOSS_FROST_SLOW_SECONDS}s**."
            ),
            frost_slow_until=until,
        )

    if elem == "fire" and random.random() < config.BOSS_FIRE_BURN_PROC_CHANCE:
        tick_damage = float(
            random.randint(config.BOSS_FIRE_BURN_DAMAGE[0], config.BOSS_FIRE_BURN_DAMAGE[1]),
        )
        ticks = config.BOSS_FIRE_BURN_TICKS
        first_tick = now + config.BOSS_FIRE_BURN_INTERVAL_SECONDS
        return ElementProcRoll(
            note=f" 🔥 **Burning!** **{int(tick_damage)}** damage/tick × **{ticks}** ticks.",
            fire_burn=(tick_damage, ticks, first_tick),
        )

    if elem == "storm" and random.random() < config.BOSS_STORM_STUN_PROC_CHANCE:
        lo, hi = config.BOSS_STORM_STUN_SECONDS
        stun_seconds = float(random.randint(lo, hi))
        return ElementProcRoll(
            note=f" ⚡ **Stunned!** Down for **{int(stun_seconds)}s**.",
            storm_stun_seconds=stun_seconds,
        )

    if elem == "void" and random.random() < config.BOSS_VOID_DRAIN_PROC_CHANCE:
        lo, hi = config.BOSS_VOID_MANA_DRAIN
        drain = random.randint(lo, hi)
        return ElementProcRoll(
            note=f" 🌑 **Void tear!** **{drain}** mana drained.",
            void_mana_drain=drain,
        )

    if elem == "verdant" and random.random() < config.BOSS_VERDANT_ROOT_PROC_CHANCE:
        until = now + config.BOSS_VERDANT_ROOT_SECONDS
        return ElementProcRoll(
            note=(
                f" 🌿 **Rooted!** +{config.BOSS_VERDANT_EXTRA_ATTACK_COOLDOWN}s "
                f"between attacks for **{config.BOSS_VERDANT_ROOT_SECONDS}s**."
            ),
            verdant_root_until=until,
        )

    return ElementProcRoll()


def extra_attack_cooldown_for_status(
    attack_slow_until: float,
    verdant_root_until: float,
    *,
    now: float,
) -> int:
    """Extra seconds added to the base boss attack cooldown while debuffed."""
    extra = 0
    if attack_slow_until > now:
        extra += config.BOSS_FROST_EXTRA_ATTACK_COOLDOWN
    if verdant_root_until > now:
        extra += config.BOSS_VERDANT_EXTRA_ATTACK_COOLDOWN
    return extra
