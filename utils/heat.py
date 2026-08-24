"""VIP / heat status — lifetime goonbux spend unlocks table limits and raid perks."""
from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True)
class HeatTier:
    tier: int
    name: str
    spend_needed: float
    max_bet_mult: float
    slots_bet_mult: float
    door_counter_mult: float
    mood_soften: bool
    blurb: str


HEAT_TIERS: tuple[HeatTier, ...] = (
    HeatTier(
        0,
        "Guest",
        0.0,
        1.0,
        1.0,
        1.0,
        False,
        "Standard floor tables.",
    ),
    HeatTier(
        1,
        "Regular",
        config.HEAT_TIER_REGULAR_SPEND,
        1.25,
        1.25,
        0.95,
        False,
        "Recognized face — higher table limits.",
    ),
    HeatTier(
        2,
        "VIP",
        config.HEAT_TIER_VIP_SPEND,
        1.75,
        1.5,
        0.85,
        False,
        "Door privilege — softer counters on Door role.",
    ),
    HeatTier(
        3,
        "Booth",
        config.HEAT_TIER_BOOTH_SPEND,
        2.5,
        2.0,
        0.75,
        True,
        "Private booth — top tables + Velvet mood softens for you.",
    ),
)


def heat_tier_for_spend(spent: float) -> HeatTier:
    current = HEAT_TIERS[0]
    for tier in HEAT_TIERS:
        if spent + 1e-9 >= tier.spend_needed:
            current = tier
    return current


def next_heat_tier(spent: float) -> HeatTier | None:
    current = heat_tier_for_spend(spent)
    for tier in HEAT_TIERS:
        if tier.tier > current.tier:
            return tier
    return None


def cost_to_reach_tier(spent: float, target: HeatTier) -> float:
    return max(0.0, target.spend_needed - spent)


def gambling_max_bet(spent: float) -> float:
    tier = heat_tier_for_spend(spent)
    return float(config.GAMBLING_MAX_BET) * tier.max_bet_mult


def slots_max_bet(spent: float) -> float:
    tier = heat_tier_for_spend(spent)
    return float(config.SLOTS_MAX_BET) * tier.slots_bet_mult


def door_counter_mult_for_spend(spent: float) -> float:
    return heat_tier_for_spend(spent).door_counter_mult


def mood_soften_for_spend(spent: float) -> bool:
    return heat_tier_for_spend(spent).mood_soften


def format_heat_line(spent: float) -> str:
    tier = heat_tier_for_spend(spent)
    nxt = next_heat_tier(spent)
    if nxt is None:
        return f"**{tier.name}** — {tier.blurb}"
    need = cost_to_reach_tier(spent, nxt)
    return (
        f"**{tier.name}** ({tier.blurb})\n"
        f"Next **{nxt.name}** in **{need:,.0f}** more goonbux spent."
    )
