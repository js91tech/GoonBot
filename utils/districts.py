"""Business districts: placement bonuses and influence competition.

Districts are server-wide locations a business can relocate to for an income
bonus. They coexist with crew territories (different scope) and do not affect
the existing /territory system. Influence is a 0-100 competitive metric tracked
per district that feeds the Phase 4 Market Expansion action.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import config

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "districts"


def district_image_path(district_id: str | None) -> Path | None:
    if not district_id:
        return None
    path = ASSET_DIR / f"{district_id}.png"
    return path if path.is_file() else None


@dataclass(frozen=True, slots=True)
class DistrictDef:
    district_id: str
    name: str
    emoji: str
    income_mult: float
    label: str


# Each district resolves to an effective income multiplier. Flavor (traffic vs.
# tourism vs. lower costs) is captured in the label; the net effect is income.
DISTRICT_MAP: dict[str, DistrictDef] = {
    "downtown": DistrictDef(
        "downtown", "Downtown", "🏙️", 1.20, "+20% customer traffic",
    ),
    "financial": DistrictDef(
        "financial", "Financial District", "🏦", 1.25, "+25% business income",
    ),
    "industrial": DistrictDef(
        "industrial", "Industrial Zone", "🏭", 1.30, "+30% production efficiency",
    ),
    "beachfront": DistrictDef(
        "beachfront", "Beachfront", "🏖️", 1.15, "+15% tourism income",
    ),
    "residential": DistrictDef(
        "residential", "Residential District", "🏘️", 1.10, "-10% operating costs",
    ),
}

DISTRICT_IDS: tuple[str, ...] = tuple(DISTRICT_MAP.keys())


def district_by_id(district_id: str | None) -> DistrictDef | None:
    if not district_id:
        return None
    return DISTRICT_MAP.get(district_id.strip().lower())


def district_income_mult(district_id: str | None) -> float:
    defn = district_by_id(district_id)
    return defn.income_mult if defn is not None else 1.0


def relocate_cost(tier: int) -> float:
    """Relocation fee scales with business tier so it stays meaningful."""
    return config.BUSINESS_DISTRICT_RELOCATE_BASE_COST * max(1, int(tier))
