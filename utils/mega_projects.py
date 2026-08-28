"""Personal mega projects: large endgame goals with permanent rewards."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MegaProjectDef:
    project_id: str
    name: str
    emoji: str
    cost: float
    income_bonus: float  # permanent business income bonus on completion
    reward_label: str


MEGA_PROJECTS: tuple[MegaProjectDef, ...] = (
    MegaProjectDef(
        "space_program", "Satellite Cam Grid", "📡", 1_000_000_000.0, 0.05,
        "Exclusive prestige cosmetic + permanent +5% business income",
    ),
    MegaProjectDef(
        "global_logistics", "Bottle Pipeline", "🍾", 5_000_000_000.0, 0.10,
        "Permanent +10% business income",
    ),
    MegaProjectDef(
        "ai_research", "Creator AI Desk", "🧠", 10_000_000_000.0, 0.15,
        "Automation multiplier: permanent +15% business income",
    ),
    MegaProjectDef(
        "world_expo", "World Afterparty", "🌍", 25_000_000_000.0, 0.20,
        "Unique server-wide benefit + permanent +20% business income",
    ),
)

MEGA_PROJECTS_BY_ID: dict[str, MegaProjectDef] = {p.project_id: p for p in MEGA_PROJECTS}


def mega_project_by_id(project_id: str) -> MegaProjectDef | None:
    return MEGA_PROJECTS_BY_ID.get(project_id.strip().lower())


def income_bonus_from_completed(completed_ids: set[str]) -> float:
    """Sum of permanent income bonuses from completed mega projects."""
    total = 0.0
    for pid in completed_ids:
        defn = MEGA_PROJECTS_BY_ID.get(pid)
        if defn is not None:
            total += defn.income_bonus
    return total
