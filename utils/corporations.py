"""Corporation (crew extension) catalog: upgrades, projects, and war scoring."""
from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True, slots=True)
class CorporateUpgradeDef:
    upgrade_id: str
    name: str
    emoji: str
    description: str


CORPORATE_UPGRADES: tuple[CorporateUpgradeDef, ...] = (
    CorporateUpgradeDef(
        "income",
        "Income Division",
        "💹",
        f"+{int(config.CORP_UPGRADE_INCOME_BONUS_PER_LEVEL * 100)}% business income "
        "for every member, per level.",
    ),
    CorporateUpgradeDef(
        "defense",
        "Security Division",
        "🛡️",
        f"+{config.CORP_UPGRADE_DEFENSE_BONUS_PER_LEVEL} security rating for every "
        "member's business, per level.",
    ),
    CorporateUpgradeDef(
        "territory",
        "Expansion Division",
        "🌐",
        f"+{int(config.CORP_UPGRADE_TERRITORY_BONUS_PER_LEVEL * 100)}% district "
        "influence gains, per level.",
    ),
)

CORPORATE_UPGRADES_BY_ID: dict[str, CorporateUpgradeDef] = {
    u.upgrade_id: u for u in CORPORATE_UPGRADES
}


@dataclass(frozen=True, slots=True)
class CorporateProjectDef:
    project_id: str
    name: str
    emoji: str
    target_amount: float
    reward_label: str
    reward_treasury: float


CORPORATE_PROJECTS: tuple[CorporateProjectDef, ...] = (
    CorporateProjectDef(
        "mega_mall", "Mega Mall", "🏬", 2_000_000.0,
        "Treasury windfall + bragging rights", 500_000.0,
    ),
    CorporateProjectDef(
        "theme_park", "Theme Park", "🎢", 5_000_000.0,
        "Treasury windfall + tourism prestige", 1_250_000.0,
    ),
    CorporateProjectDef(
        "ai_research_center", "AI Research Center", "🤖", 10_000_000.0,
        "Treasury windfall + automation edge", 2_500_000.0,
    ),
    CorporateProjectDef(
        "space_program", "Space Program", "🚀", 25_000_000.0,
        "Massive treasury windfall + legendary status", 6_000_000.0,
    ),
)

CORPORATE_PROJECTS_BY_ID: dict[str, CorporateProjectDef] = {
    p.project_id: p for p in CORPORATE_PROJECTS
}


def upgrade_by_id(upgrade_id: str) -> CorporateUpgradeDef | None:
    return CORPORATE_UPGRADES_BY_ID.get(upgrade_id.strip().lower())


def project_by_id(project_id: str) -> CorporateProjectDef | None:
    return CORPORATE_PROJECTS_BY_ID.get(project_id.strip().lower())


def upgrade_cost(level: int) -> float:
    """Cost for the next corporate upgrade level."""
    factor = config.CORP_UPGRADE_COST_GROWTH ** max(0, int(level))
    return round(config.CORP_UPGRADE_BASE_COST * factor, 2)


def income_bonus_multiplier(income_level: int) -> float:
    return 1.0 + max(0, int(income_level)) * config.CORP_UPGRADE_INCOME_BONUS_PER_LEVEL


def defense_bonus(defense_level: int) -> int:
    return max(0, int(defense_level)) * config.CORP_UPGRADE_DEFENSE_BONUS_PER_LEVEL


def territory_bonus_multiplier(territory_level: int) -> float:
    return 1.0 + max(0, int(territory_level)) * config.CORP_UPGRADE_TERRITORY_BONUS_PER_LEVEL
