from __future__ import annotations

import config


def bank_capacity(expansions: int) -> float:
    """Max nuggets storable in the personal bank for a given expansion count."""
    extra = max(0, int(expansions)) * config.BANK_EXPANSION_CAPACITY_PER_TOKEN
    return float(config.BANK_BASE_CAPACITY) + extra


def bank_deposit_room(current_bank: float, expansions: int) -> float:
    """How many more nuggets can be deposited before hitting capacity."""
    return max(0.0, bank_capacity(expansions) - max(0.0, current_bank))
