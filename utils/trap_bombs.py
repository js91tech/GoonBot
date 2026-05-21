from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import config

TRAP_BOMB_ITEM_ID = "trap_bomb"
TRAP_BOMB_GIF_PATH = Path(__file__).resolve().parent.parent / "assets" / "trap_bomb.gif"


@dataclass(frozen=True)
class TrapBombProc:
    damage: int
    bombs_remaining: int
    true_damage: bool = True


def trap_proc_chance(bomb_count: int) -> float:
    if bomb_count <= 0:
        return 0.0
    chance = config.TRAP_BOMB_BASE_CHANCE + config.TRAP_BOMB_PER_ITEM_CHANCE * bomb_count
    return min(config.TRAP_BOMB_MAX_CHANCE, chance)


def roll_trap_proc(bomb_count: int) -> bool:
    if bomb_count <= 0:
        return False
    return random.random() < trap_proc_chance(bomb_count)


def roll_trap_damage() -> int:
    low, high = config.TRAP_BOMB_DAMAGE
    return random.randint(low, high)


def try_trap_proc(bomb_count: int) -> TrapBombProc | None:
    if not roll_trap_proc(bomb_count):
        return None
    return TrapBombProc(
        damage=roll_trap_damage(),
        bombs_remaining=max(0, bomb_count - 1),
    )
