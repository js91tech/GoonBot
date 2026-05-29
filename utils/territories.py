from __future__ import annotations

from dataclasses import dataclass, field

import config
from utils.helpers import fmt_amount


@dataclass(frozen=True, slots=True)
class TerritoryDef:
    territory_id: str
    name: str
    income_per_hour: float
    max_guards: int
    tier: int
    perk_label: str


TERRITORY_MAP: dict[str, TerritoryDef] = {
    "docks": TerritoryDef(
        "docks", "Docks", 1_800.0, 3, 1, "+5% heist loot",
    ),
    "market": TerritoryDef(
        "market", "Market", 2_700.0, 4, 2, "+5% shop sell value",
    ),
    "foundry": TerritoryDef(
        "foundry", "Foundry", 3_600.0, 5, 3, "-5% craft cost",
    ),
    "vault": TerritoryDef(
        "vault", "Vault", 4_500.0, 6, 4, "+3% heist success",
    ),
    "citadel": TerritoryDef(
        "citadel", "Citadel", 6_000.0, 8, 5, "+10% Citadel income",
    ),
}

TERRITORY_IDS: tuple[str, ...] = tuple(TERRITORY_MAP.keys())


@dataclass
class CrewTerritoryPerks:
    held: set[str] = field(default_factory=set)
    sell_mult: float = 1.0
    craft_cost_mult: float = 1.0
    heist_loot_mult: float = 1.0
    heist_success_bonus: float = 0.0

    def income_mult(self, territory_id: str) -> float:
        if territory_id == "citadel" and "citadel" in self.held:
            return 1.0 + config.TERRITORY_PERK_CITADEL_INCOME_BONUS
        return 1.0

    def summary_lines(self) -> list[str]:
        if not self.held:
            return []
        return [
            f"**{TERRITORY_MAP[tid].name}** — {TERRITORY_MAP[tid].perk_label}"
            for tid in TERRITORY_IDS
            if tid in self.held
        ]


def territory_by_id(territory_id: str) -> TerritoryDef | None:
    return TERRITORY_MAP.get(territory_id.strip().lower())


def perks_from_held(held: set[str]) -> CrewTerritoryPerks:
    perks = CrewTerritoryPerks(held=set(held))
    if "market" in held:
        perks.sell_mult = 1.0 + config.TERRITORY_PERK_MARKET_SELL_BONUS
    if "foundry" in held:
        perks.craft_cost_mult = 1.0 - config.TERRITORY_PERK_FOUNDRY_CRAFT_DISCOUNT
    if "docks" in held:
        perks.heist_loot_mult = 1.0 + config.TERRITORY_PERK_DOCKS_HEIST_LOOT
    if "vault" in held:
        perks.heist_success_bonus = config.TERRITORY_PERK_VAULT_HEIST_SUCCESS
    return perks


def guard_cost_per_unit(territory: TerritoryDef) -> float:
    return config.TERRITORY_GUARD_COST_BASE + territory.tier * config.TERRITORY_GUARD_COST_PER_TIER


def siege_success_chance(
    attacker_members: int,
    guards: int,
    territory: TerritoryDef,
) -> float:
    """Chance attacker crew wins when siege timer ends."""
    attack = min(
        config.TERRITORY_SIEGE_ATTACK_CAP,
        attacker_members * config.TERRITORY_SIEGE_PER_MEMBER,
    )
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


def format_crew_territory_summary(
    held_rows: list[tuple[str, int]],
    *,
    income_per_hour_total: float,
) -> str:
    if not held_rows:
        return "_No zones held — `/territory` map_"
    lines = []
    for tid, guards in held_rows:
        defn = TERRITORY_MAP.get(tid)
        if defn is None:
            continue
        lines.append(
            f"**{defn.name}** · {fmt_amount(defn.income_per_hour)}/hr · "
            f"Guards {guards}/{defn.max_guards}",
        )
    lines.append(f"Total income ≈ **{fmt_amount(income_per_hour_total)}/hr** → crew treasury")
    return "\n".join(lines)
