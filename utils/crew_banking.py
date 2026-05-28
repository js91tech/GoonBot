from __future__ import annotations

import config


def crew_level_from_xp(xp: int) -> int:
    return min(config.CREW_LEVEL_CAP, 1 + max(0, xp) // config.CREW_XP_PER_LEVEL)


def max_loan_fraction(level: int) -> float:
    base = config.CREW_LOAN_MAX_TREASURY_FRACTION
    bonus = max(0, level - 1) * config.CREW_LEVEL_LOAN_BONUS_PER_LEVEL
    return min(0.75, base + bonus)


def effective_interest_rate(level: int) -> float:
    reduction = 0.0
    if level >= 3:
        reduction += 0.01
    if level >= 5:
        reduction += 0.01
    return max(0.05, config.CREW_LOAN_INTEREST_RATE - reduction)


def max_loan_amount(treasury: float, level: int) -> float:
    if treasury <= 0:
        return 0.0
    return treasury * max_loan_fraction(level)


def heist_same_crew_bonus(participant_ids: list[int], crew_by_user: dict[int, str | None]) -> float:
    """Extra success chance from persistent crew roster (excludes leader at index 0)."""
    if len(participant_ids) < 2:
        return 0.0
    leader_crew = crew_by_user.get(participant_ids[0])
    if not leader_crew:
        return 0.0
    bonus = 0.0
    cap = config.CREW_HEIST_SAME_CREW_BONUS_CAP
    for uid in participant_ids[1:]:
        if crew_by_user.get(uid) == leader_crew:
            bonus += config.CREW_HEIST_SAME_CREW_BONUS
            if bonus >= cap:
                return cap
    return bonus


def perks_summary(level: int) -> str:
    loan_pct = int(round(max_loan_fraction(level) * 100))
    rate_pct = int(round(effective_interest_rate(level) * 100))
    lines = [
        f"Max loan: **{loan_pct}%** of treasury",
        f"Loan interest: **{rate_pct}%** of each repayment",
    ]
    if level >= 4:
        lines.append("Same-crew `/heist` mates: **+5%** success each (stacking)")
    return " · ".join(lines)
