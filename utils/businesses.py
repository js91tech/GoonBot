"""Business Empire catalog and income math.

Defines the 7 business tiers, attribute/branch effects, and pure helper
functions used by the business cog, UI, and background income tick. All money
values are in goonbux (config.CURRENCY_NAME), keeping the design doc's relative
scale (Tier 1 costs 500, earns 20/hr).
"""
from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True, slots=True)
class BusinessTierDef:
    tier: int
    tier_id: str
    name: str
    purchase_cost: float
    base_income_per_hour: float
    emoji: str
    blurb: str


# Ordered by tier. Costs/income mirror the design document.
BUSINESS_TIERS: tuple[BusinessTierDef, ...] = (
    BusinessTierDef(
        1, "tip_jar_cam", "Tip Jar Cam", 500.0, 20.0, "📸",
        "A shaky phone stand and a tip jar. Everyone starts somewhere.",
    ),
    BusinessTierDef(
        2, "afterparty_cart", "Afterparty Cart", 2_500.0, 100.0, "🍸",
        "Wheels, drinks, and foot traffic from the clubs.",
    ),
    BusinessTierDef(
        3, "late_night_lounge", "Late-Night Lounge", 10_000.0, 350.0, "🥂",
        "Low lights, long nights, and loyal regulars.",
    ),
    BusinessTierDef(
        4, "vip_booth_club", "VIP Booth Club", 50_000.0, 1_500.0, "💃",
        "Private booths, bottle service, and real cover charges.",
    ),
    BusinessTierDef(
        5, "franchise_clubs", "Franchise Clubs", 250_000.0, 8_000.0, "🏙️",
        "Stamp the brand across the server's nightlife map.",
    ),
    BusinessTierDef(
        6, "content_studio", "Content Studio", 1_000_000.0, 30_000.0, "🎥",
        "Sets, lights, and studio-scale goonbux output.",
    ),
    BusinessTierDef(
        7, "adult_empire_hq", "Adult Empire HQ", 5_000_000.0, 250_000.0, "👑",
        "The tower at the top of the ladder. Own the night.",
    ),
)

# Old NuggetBot tycoon ids still stored on existing rows.
LEGACY_TIER_IDS: dict[str, str] = {
    "lemon_stand": "tip_jar_cam",
    "food_cart": "afterparty_cart",
    "coffee_shop": "late_night_lounge",
    "restaurant": "vip_booth_club",
    "chain_restaurant": "franchise_clubs",
    "factory": "content_studio",
    "corporation": "adult_empire_hq",
}

BUSINESS_TIERS_BY_ID: dict[str, BusinessTierDef] = {
    defn.tier_id: defn for defn in BUSINESS_TIERS
}
BUSINESS_TIERS_BY_NUMBER: dict[int, BusinessTierDef] = {
    defn.tier: defn for defn in BUSINESS_TIERS
}

MAX_TIER: int = max(defn.tier for defn in BUSINESS_TIERS)
MIN_TIER: int = min(defn.tier for defn in BUSINESS_TIERS)

# Upgrade branches (Phase 2 wires interactive upgrades; Phase 1 stores levels).
UPGRADE_BRANCHES: dict[str, tuple[str, ...]] = {
    "security": (
        "Door Cameras",
        "Bouncer Alarms",
        "Security Team",
        "Reinforced Vault",
        "Empire Security Division",
    ),
    "growth": (
        "Flyer Runs",
        "Club Ads",
        "Social Tease Campaigns",
        "Creator Sponsorships",
        "National Branding",
    ),
    "production": (
        "Better Lights",
        "Set Optimization",
        "Automation",
        "Multi-Cam Rigs",
        "AI Scheduling",
    ),
}


def tier_def(tier: int) -> BusinessTierDef | None:
    return BUSINESS_TIERS_BY_NUMBER.get(int(tier))


def normalize_tier_id(tier_id: str) -> str:
    raw = tier_id.strip().lower()
    return LEGACY_TIER_IDS.get(raw, raw)


def tier_def_by_id(tier_id: str) -> BusinessTierDef | None:
    return BUSINESS_TIERS_BY_ID.get(normalize_tier_id(tier_id))


def next_tier_def(tier: int) -> BusinessTierDef | None:
    return BUSINESS_TIERS_BY_NUMBER.get(int(tier) + 1)


def _scaled_attribute_bonus(level: int, per_level: float) -> float:
    """Linear bonus with diminishing returns after ``BUSINESS_ATTRIBUTE_DIMINISHING_AFTER``."""
    lvl = max(0, int(level))
    cap = config.BUSINESS_ATTRIBUTE_DIMINISHING_AFTER
    factor = config.BUSINESS_ATTRIBUTE_DIMINISHING_FACTOR
    full = min(lvl, cap)
    reduced = max(0, lvl - cap)
    return full * per_level + reduced * per_level * factor


def efficiency_multiplier(efficiency_level: int) -> float:
    """Each efficiency level adds a flat percentage to output."""
    return 1.0 + _scaled_attribute_bonus(
        efficiency_level, config.BUSINESS_EFFICIENCY_BONUS_PER_LEVEL,
    )


def reputation_multiplier(reputation_level: int, *, effectiveness: float = 1.0) -> float:
    """Reputation drives customer traffic -> income."""
    return 1.0 + _scaled_attribute_bonus(
        reputation_level,
        config.BUSINESS_REPUTATION_BONUS_PER_LEVEL * max(0.0, effectiveness),
    )


def production_branch_multiplier(branch_level: int) -> float:
    return 1.0 + max(0, int(branch_level)) * config.BUSINESS_PRODUCTION_BRANCH_BONUS_PER_LEVEL


def growth_branch_multiplier(branch_level: int) -> float:
    """Growth branch boosts customer traffic -> income."""
    return 1.0 + max(0, int(branch_level)) * config.BUSINESS_GROWTH_BRANCH_BONUS_PER_LEVEL


def prestige_multiplier(business_prestige: int) -> float:
    return 1.0 + max(0, int(business_prestige)) * config.BUSINESS_PRESTIGE_INCOME_BONUS_PER_LEVEL


def satisfaction_multiplier(satisfaction: int) -> float:
    """Low employee satisfaction drags income; high satisfaction gives a small lift.

    Satisfaction is 0-100, centered on 50 (neutral). The multiplier ranges from
    ``1 - BUSINESS_SATISFACTION_SWING`` at 0 up to ``1 + BUSINESS_SATISFACTION_SWING``
    at 100.
    """
    clamped = max(0, min(100, int(satisfaction)))
    swing = config.BUSINESS_SATISFACTION_SWING
    return 1.0 + ((clamped - 50) / 50.0) * swing


def capacity_for_level(tier: int, capacity_level: int) -> float:
    """Maximum stored income before collection is required.

    Base capacity scales with the tier's hourly income (a buffer of N hours),
    extended by each capacity upgrade.
    """
    defn = tier_def(tier)
    base_rate = defn.base_income_per_hour if defn else 0.0
    base = base_rate * config.BUSINESS_BASE_CAPACITY_HOURS
    extra = (
        max(0, int(capacity_level))
        * base_rate
        * config.BUSINESS_CAPACITY_HOURS_PER_LEVEL
    )
    return max(base + extra, config.BUSINESS_MIN_CAPACITY)


def hourly_income(
    *,
    tier: int,
    efficiency_level: int = 0,
    reputation_level: int = 0,
    production_branch_level: int = 0,
    growth_branch_level: int = 0,
    satisfaction: int = 50,
    business_prestige: int = 0,
    district_mult: float = 1.0,
    reputation_effectiveness: float = 1.0,
) -> float:
    """Effective income per hour after all multipliers.

    Attribute/branch effects:
    - Efficiency: +output per level (production)
    - Reputation: +customer traffic per level
    - Production branch: +output per level (Better Lights .. AI Scheduling)
    - Growth branch: +customer traffic per level (Flyer Runs .. National Branding)
    - Employee satisfaction: -/+ swing around a neutral 50
    - Business prestige: permanent global business income bonus
    - District: placement bonus (Phase 3)
    """
    defn = tier_def(tier)
    if defn is None:
        return 0.0
    return (
        defn.base_income_per_hour
        * efficiency_multiplier(efficiency_level)
        * reputation_multiplier(reputation_level, effectiveness=reputation_effectiveness)
        * production_branch_multiplier(production_branch_level)
        * growth_branch_multiplier(growth_branch_level)
        * satisfaction_multiplier(satisfaction)
        * prestige_multiplier(business_prestige)
        * max(0.0, district_mult)
    )


def accrue_income(
    *,
    stored: float,
    capacity: float,
    hourly: float,
    elapsed_seconds: float,
) -> float:
    """Return the new stored income after ``elapsed_seconds``, capped at capacity."""
    if elapsed_seconds <= 0 or hourly <= 0:
        return min(max(stored, 0.0), capacity)
    earned = hourly * (elapsed_seconds / 3600.0)
    return min(max(stored, 0.0) + earned, capacity)


def upgrade_cost(tier: int, current_level: int) -> float:
    """Escalating cost for the next attribute/branch level at a given tier."""
    base = config.BUSINESS_UPGRADE_BASE_BY_TIER.get(
        int(tier), config.BUSINESS_UPGRADE_BASE_COST,
    )
    factor = config.BUSINESS_UPGRADE_COST_GROWTH ** max(0, int(current_level))
    return round(base * factor, 2)


@dataclass(frozen=True, slots=True)
class BusinessIncomeBreakdown:
    """Hourly income from business stats vs. all active multipliers."""

    base_hourly: float
    effective_hourly: float
    corp_mult: float = 1.0
    buff_mult: float = 1.0
    event_mult: float = 1.0
    mega_mult: float = 1.0

    @property
    def bonus_mult(self) -> float:
        return self.corp_mult * self.buff_mult * self.event_mult * self.mega_mult


def row_income_kwargs(row: object) -> dict[str, int | float]:
    """Keyword args for ``hourly_income`` from a ``user_businesses`` row."""
    from utils.districts import district_income_mult

    return {
        "tier": int(row["tier"]),
        "efficiency_level": int(row["efficiency"]),
        "reputation_level": int(row["reputation"]),
        "production_branch_level": int(row["branch_production"]),
        "growth_branch_level": int(row["branch_growth"]),
        "satisfaction": int(row["employee_satisfaction"]),
        "business_prestige": int(row["business_prestige"]),
        "district_mult": district_income_mult(row["district_id"]),
    }


def hourly_income_from_row(row: object) -> float:
    """Effective hourly income from a ``user_businesses`` row (no external multipliers)."""
    return hourly_income(**row_income_kwargs(row))


def upgrade_income_delta(row: object, attribute: str) -> float | None:
    """Return the +1 level income gain, or ``None`` if the upgrade is not income-related."""
    column_map = {
        "reputation": "reputation_level",
        "efficiency": "efficiency_level",
        "branch_growth": "growth_branch_level",
        "branch_production": "production_branch_level",
    }
    kwarg = column_map.get(attribute)
    if kwarg is None:
        return None
    kwargs = row_income_kwargs(row)
    before = hourly_income(**kwargs)
    kwargs[kwarg] = int(kwargs[kwarg]) + 1  # type: ignore[assignment]
    after = hourly_income(**kwargs)
    return after - before


UPGRADE_EFFECT_HINTS: dict[str, str] = {
    "security": "Defense only — raises security rating",
    "capacity": "Storage only — raises revenue cap",
    "branch_security": "Defense only — raises security rating",
}


def security_rating(
    *,
    security_level: int,
    branch_security_level: int,
    tier: int,
    bonus: int = 0,
) -> int:
    """Resistance score used by the defense system (Phase 4)."""
    return (
        max(0, int(security_level)) * config.BUSINESS_SECURITY_PER_LEVEL
        + max(0, int(branch_security_level)) * config.BUSINESS_SECURITY_PER_BRANCH_LEVEL
        + max(0, int(tier))
        + max(0, int(bonus))
    )
