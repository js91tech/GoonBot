"""Drug trade catalog and pricing math (fictional contraband strains).

A risky, high-reward economy layer: grow product in a lab over time, then sell
it on the street (volatile prices, raid risk) or to other players. Kept in the
same tongue-in-cheek tone as heists, bounties, and the scourge virus.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import config


@dataclass(frozen=True, slots=True)
class DrugDef:
    drug_id: str
    name: str
    emoji: str
    seed_cost: float
    grow_seconds: int
    yield_min: int
    yield_max: int
    street_price: float  # base nuggets per unit


DRUGS: tuple[DrugDef, ...] = (
    DrugDef("greenleaf", "Greenleaf", "🌿", 200.0, 30 * 60, 4, 8, 120.0),
    DrugDef("bluecrystal", "Blue Crystal", "💎", 1_500.0, 90 * 60, 3, 6, 700.0),
    DrugDef("whitedust", "White Dust", "❄️", 5_000.0, 3 * 3600, 2, 5, 2_500.0),
    DrugDef("goldenpoppy", "Golden Poppy", "🌺", 15_000.0, 6 * 3600, 2, 4, 7_000.0),
)

DRUGS_BY_ID: dict[str, DrugDef] = {d.drug_id: d for d in DRUGS}


def drug_by_id(drug_id: str) -> DrugDef | None:
    return DRUGS_BY_ID.get(drug_id.strip().lower())


def roll_yield(defn: DrugDef, *, yield_bonus: float = 0.0, rng: random.Random | None = None) -> int:
    """Harvest yield, including any district/equipment bonus."""
    r = rng or random
    base = r.randint(defn.yield_min, defn.yield_max)
    return max(1, int(round(base * (1.0 + max(0.0, yield_bonus)))))


def street_price(defn: DrugDef, *, rng: random.Random | None = None) -> float:
    """Current street price with random volatility around the base."""
    r = rng or random
    variance = config.DRUG_STREET_PRICE_VARIANCE
    factor = 1.0 + r.uniform(-variance, variance)
    return max(1.0, defn.street_price * factor)


def sale_total(defn: DrugDef, quantity: int, *, rng: random.Random | None = None) -> float:
    return street_price(defn, rng=rng) * max(0, int(quantity))
