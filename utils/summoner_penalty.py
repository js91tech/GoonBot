from __future__ import annotations

from typing import Any

import config


def boss_summoner_id(boss_row: Any) -> int | None:
    try:
        raw = boss_row["summoner_id"]
    except (KeyError, IndexError, TypeError):
        return None
    if raw is None:
        return None
    try:
        uid = int(raw)
    except (TypeError, ValueError):
        return None
    return uid if uid > 0 else None


def is_summoner_debuffed(boss_row: Any, user_id: int) -> bool:
    summoner_id = boss_summoner_id(boss_row)
    return summoner_id is not None and summoner_id == user_id


def apply_summoner_attack_debuff(damage: int) -> int:
    return max(1, int(damage * config.SUMMONER_DEBUFF_ATK_DEF_RETENTION))


def apply_summoner_crit_chance(crit_chance: float) -> float:
    return max(0.0, crit_chance * config.SUMMONER_DEBUFF_CRIT_RETENTION)


def summoner_defense_retention() -> float:
    return config.SUMMONER_DEBUFF_ATK_DEF_RETENTION


def apply_summoner_counter_damage(damage: int) -> int:
    return max(1, int(damage * config.SUMMONER_BOSS_COUNTER_MULTIPLIER))


def summoner_penalty_summary() -> str:
    atk_def = int(round((1.0 - config.SUMMONER_DEBUFF_ATK_DEF_RETENTION) * 100))
    crit = int(round((1.0 - config.SUMMONER_DEBUFF_CRIT_RETENTION) * 100))
    mana = int(round((1.0 - config.SUMMONER_DEBUFF_MANA_RETENTION) * 100))
    counter = int(round((config.SUMMONER_BOSS_COUNTER_MULTIPLIER - 1.0) * 100))
    return (
        f"**-{atk_def}%** atk/def · **-{crit}%** crit · **-{mana}%** mana regen · "
        f"boss hits you **+{counter}%** harder"
    )
