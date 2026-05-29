from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True, slots=True)
class TerritoryDef:
    territory_id: str
    name: str
    income_per_hour: float
    max_guards: int
    tier: int


TERRITORY_MAP: dict[str, TerritoryDef] = {
    "docks": TerritoryDef("docks", "Docks", 30.0, 3, 1),
    "market": TerritoryDef("market", "Market", 45.0, 4, 2),
    "foundry": TerritoryDef("foundry", "Foundry", 60.0, 5, 3),
    "vault": TerritoryDef("vault", "Vault", 75.0, 6, 4),
    "citadel": TerritoryDef("citadel", "Citadel", 100.0, 8, 5),
}

TERRITORY_IDS: tuple[str, ...] = tuple(TERRITORY_MAP.keys())


def territory_by_id(territory_id: str) -> TerritoryDef | None:
    return TERRITORY_MAP.get(territory_id.strip().lower())


def guard_cost_per_unit(territory: TerritoryDef) -> float:
    return config.TERRITORY_GUARD_COST_BASE + territory.tier * config.TERRITORY_GUARD_COST_PER_TIER


def siege_success_chance(
    attacker_members: int,
    guards: int,
    territory: TerritoryDef,
) -> float:
    """Chance attacker crew wins when siege timer ends."""
    attack = min(config.TERRITORY_SIEGE_ATTACK_CAP, attacker_members * config.TERRITORY_SIEGE_PER_MEMBER)
    defense = guards * config.TERRITORY_GUARD_DEFENSE_BONUS + territory.tier * 0.02
    return min(
        config.TERRITORY_SIEGE_MAX_CHANCE,
        max(
            config.TERRITORY_SIEGE_MIN_CHANCE,
            config.TERRITORY_SIEGE_BASE_CHANCE + attack - defense,
        ),
    )


def income_multiplier_under_siege() -> float:
    return config.TERRITORY_INCOME_UNDER_SIEGE_MULT
