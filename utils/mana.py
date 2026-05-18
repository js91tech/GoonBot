from __future__ import annotations

import time
from dataclasses import dataclass

import config
from utils.classes import get_class, is_healer_class


@dataclass(frozen=True)
class ManaSnapshot:
    current: int
    cap: int
    is_healer: bool
    regen_per_tick: int
    tick_seconds: int
    seconds_until_tick: int


def _regen_params(is_healer: bool) -> tuple[int, float]:
    if is_healer:
        return config.MANA_HEALER_REGEN_PER_TICK, float(config.MANA_HEALER_REGEN_INTERVAL_SECONDS)
    return config.MANA_REGEN_PER_TICK, float(config.MANA_REGEN_INTERVAL_SECONDS)


def apply_mana_time_regen(
    current: int,
    cap: int,
    last_tick_at: float,
    *,
    is_healer: bool,
    now: float | None = None,
) -> tuple[int, float]:
    per_tick, interval = _regen_params(is_healer)
    ts = time.time() if now is None else now
    if interval <= 0 or per_tick <= 0:
        return min(current, cap), last_tick_at
    elapsed = max(0.0, ts - last_tick_at)
    ticks = int(elapsed // interval)
    if ticks <= 0:
        return min(current, cap), last_tick_at
    refreshed = min(cap, current + ticks * per_tick)
    advanced_at = last_tick_at + ticks * interval
    return refreshed, advanced_at


def mana_from_damage(damage: int, *, is_healer: bool) -> int:
    if damage <= 0:
        return 0
    pct = config.MANA_HEALER_ON_DAMAGE_PCT if is_healer else config.MANA_ON_DAMAGE_PCT
    return max(1, int(damage * pct))


def mana_snapshot(
    current: int,
    cap: int,
    last_tick_at: float,
    *,
    is_healer: bool,
    now: float | None = None,
) -> ManaSnapshot:
    per_tick, interval = _regen_params(is_healer)
    ts = time.time() if now is None else now
    refreshed, advanced_at = apply_mana_time_regen(
        current,
        cap,
        last_tick_at,
        is_healer=is_healer,
        now=ts,
    )
    if refreshed >= cap:
        until = 0
    else:
        elapsed = max(0.0, ts - advanced_at)
        into_tick = elapsed % interval if interval > 0 else 0.0
        until = max(0, int(interval - into_tick)) if interval > 0 else 0
    return ManaSnapshot(
        current=refreshed,
        cap=cap,
        is_healer=is_healer,
        regen_per_tick=per_tick,
        tick_seconds=int(interval),
        seconds_until_tick=until,
    )


def mana_cap_for_class(class_id: str | None) -> int:
    cls = get_class(class_id)
    if cls is None:
        return config.MANA_BASE_CAP
    bonus = 0
    if cls.tier == "master":
        bonus = 25
    elif cls.tier == "evolved":
        bonus = 12
    elif cls.tier in ("hybrid", "special"):
        bonus = 30
    return config.MANA_BASE_CAP + bonus


def is_healer_for_class(class_id: str | None) -> bool:
    return is_healer_class(class_id)


def mana_bar(current: int, cap: int, *, length: int = 10) -> str:
    if cap <= 0:
        return "░" * length
    filled = int(round((current / cap) * length))
    filled = max(0, min(length, filled))
    return "▰" * filled + "▱" * (length - filled)
