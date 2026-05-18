from __future__ import annotations

import time
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class EnergySnapshot:
    current: int
    cap: int
    cap_upgrades: int
    regen_per_tick: int
    tick_seconds: int
    seconds_until_tick: int


def energy_cap_for_upgrades(cap_upgrades: int) -> int:
    return config.ENERGY_BASE_CAP + cap_upgrades * config.ENERGY_CAP_PER_UPGRADE


def apply_energy_regen(
    current: int,
    cap: int,
    last_tick_at: float,
    *,
    now: float | None = None,
    regen_per_tick: int | None = None,
    tick_seconds: float | None = None,
) -> tuple[int, float]:
    """Apply passive regen in whole ticks. Returns (energy, updated_last_tick_at)."""
    ts = time.time() if now is None else now
    per_tick = config.ENERGY_REGEN_PER_TICK if regen_per_tick is None else regen_per_tick
    interval = (
        config.ENERGY_REGEN_INTERVAL_SECONDS if tick_seconds is None else tick_seconds
    )
    if interval <= 0 or per_tick <= 0:
        return min(current, cap), last_tick_at

    elapsed = max(0.0, ts - last_tick_at)
    ticks = int(elapsed // interval)
    if ticks <= 0:
        return min(current, cap), last_tick_at

    refreshed = min(cap, current + ticks * per_tick)
    advanced_at = last_tick_at + ticks * interval
    return refreshed, advanced_at


def energy_snapshot(
    current: int,
    cap: int,
    cap_upgrades: int,
    last_tick_at: float,
    *,
    now: float | None = None,
    regen_per_tick: int | None = None,
    tick_seconds: float | None = None,
) -> EnergySnapshot:
    ts = time.time() if now is None else now
    interval = (
        config.ENERGY_REGEN_INTERVAL_SECONDS if tick_seconds is None else tick_seconds
    )
    refreshed, _ = apply_energy_regen(
        current,
        cap,
        last_tick_at,
        now=ts,
        regen_per_tick=regen_per_tick,
        tick_seconds=tick_seconds,
    )
    if refreshed >= cap:
        until = 0
    else:
        elapsed = max(0.0, ts - last_tick_at)
        into_tick = elapsed % interval if interval > 0 else 0.0
        until = max(0, int(interval - into_tick)) if interval > 0 else 0
    per_tick = config.ENERGY_REGEN_PER_TICK if regen_per_tick is None else regen_per_tick
    return EnergySnapshot(
        current=refreshed,
        cap=cap,
        cap_upgrades=cap_upgrades,
        regen_per_tick=per_tick,
        tick_seconds=int(interval),
        seconds_until_tick=until,
    )
