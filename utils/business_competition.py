"""Corporate competition: temporary strategic actions and defense math.

All actions create *temporary* income multipliers (buffs on yourself or debuffs
on a rival). Nothing here permanently removes progression — every effect expires
and attacks can be mitigated by security (passive) and by responding in time
(active defense).
"""
from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True, slots=True)
class CompetitiveAction:
    action_id: str
    name: str
    emoji: str
    description: str
    cost: float
    duration_seconds: float
    target: str  # "self" | "opponent" | "district"
    kind: str  # "buff" | "attack" | "influence"
    magnitude: float  # bonus (buff) or penalty (attack) as a fraction


COMPETITIVE_ACTIONS: tuple[CompetitiveAction, ...] = (
    CompetitiveAction(
        "marketing_campaign",
        "Marketing Campaign",
        "📣",
        f"+{int(config.BUSINESS_ACTION_MARKETING_BONUS * 100)}% your revenue "
        f"for {int(config.BUSINESS_ACTION_MARKETING_DURATION // 3600)}h.",
        config.BUSINESS_ACTION_MARKETING_COST,
        config.BUSINESS_ACTION_MARKETING_DURATION,
        "self",
        "buff",
        config.BUSINESS_ACTION_MARKETING_BONUS,
    ),
    CompetitiveAction(
        "talent_recruitment",
        "Talent Recruitment",
        "🧑‍💼",
        f"+{int(config.BUSINESS_ACTION_TALENT_BONUS * 100)}% your revenue "
        f"for {int(config.BUSINESS_ACTION_TALENT_DURATION // 3600)}h (poach talent).",
        config.BUSINESS_ACTION_TALENT_COST,
        config.BUSINESS_ACTION_TALENT_DURATION,
        "self",
        "buff",
        config.BUSINESS_ACTION_TALENT_BONUS,
    ),
    CompetitiveAction(
        "price_war",
        "Price War",
        "💸",
        f"-{int(config.BUSINESS_ACTION_PRICE_WAR_PENALTY * 100)}% a rival's revenue "
        f"for {int(config.BUSINESS_ACTION_PRICE_WAR_DURATION // 3600)}h.",
        config.BUSINESS_ACTION_PRICE_WAR_COST,
        config.BUSINESS_ACTION_PRICE_WAR_DURATION,
        "opponent",
        "attack",
        config.BUSINESS_ACTION_PRICE_WAR_PENALTY,
    ),
    CompetitiveAction(
        "reputation_attack",
        "Reputation Attack",
        "📰",
        f"-{int(config.BUSINESS_ACTION_REPUTATION_PENALTY * 100)}% a rival's revenue "
        f"for {int(config.BUSINESS_ACTION_REPUTATION_DURATION // 3600)}h.",
        config.BUSINESS_ACTION_REPUTATION_COST,
        config.BUSINESS_ACTION_REPUTATION_DURATION,
        "opponent",
        "attack",
        config.BUSINESS_ACTION_REPUTATION_PENALTY,
    ),
    CompetitiveAction(
        "market_expansion",
        "Market Expansion",
        "🗺️",
        f"+{config.BUSINESS_ACTION_MARKET_EXPANSION_INFLUENCE} influence in your "
        "current district (instant).",
        config.BUSINESS_ACTION_MARKET_EXPANSION_COST,
        0.0,
        "district",
        "influence",
        0.0,
    ),
)

ACTIONS_BY_ID: dict[str, CompetitiveAction] = {a.action_id: a for a in COMPETITIVE_ACTIONS}


def action_by_id(action_id: str) -> CompetitiveAction | None:
    return ACTIONS_BY_ID.get(action_id.strip().lower())


def security_mitigation(security_rating: int) -> float:
    """Fraction of an incoming attack neutralised passively by security."""
    rating = max(0, int(security_rating))
    raw = rating / (rating + config.BUSINESS_SECURITY_MITIGATION_K)
    return min(config.BUSINESS_SECURITY_MITIGATION_CAP, raw)


def effective_penalty(base_penalty: float, security_rating: int) -> float:
    """Apply passive security mitigation to an attack's base penalty."""
    return max(0.0, base_penalty * (1.0 - security_mitigation(security_rating)))


def defended_penalty(current_penalty: float) -> float:
    """Remaining penalty after a successful active defense."""
    return max(0.0, current_penalty * (1.0 - config.BUSINESS_DEFENSE_MITIGATION))


def penalty_to_multiplier(penalty: float) -> float:
    return max(0.0, 1.0 - penalty)


def bonus_to_multiplier(bonus: float) -> float:
    return 1.0 + max(0.0, bonus)
