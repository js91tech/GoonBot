"""Shared database types and helpers."""
from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from typing import NamedTuple


class DailyClaimResult(NamedTuple):
    remaining: float | None
    reward: float
    streak: int
    streak_bonus_mult: float


class WalletPanelData(NamedTuple):
    wallet: float
    bank: float
    bank_capacity: float
    bank_expansions: dict[int, int]


def _spendable_cents(value: object) -> int:
    """Floor wallet/price to cents for comparisons (avoids float vs shop integer prices)."""
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int) and not isinstance(value, bool):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(repr(value))
    else:
        d = Decimal(str(value))
    d = d.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    return int(d * 100)
