"""Stock market math: share pricing, dividends, and market events."""
from __future__ import annotations

import config


def share_price(treasury: float, members: int, *, event_mult: float = 1.0) -> float:
    """Current price of one share in a corporation."""
    raw = (
        config.STOCK_BASE_PRICE
        + max(0.0, treasury) / config.STOCK_TREASURY_DIVISOR
        + max(0, int(members)) * config.STOCK_PRICE_PER_MEMBER
    )
    return max(config.STOCK_MIN_PRICE, raw * max(0.0, event_mult))


def buy_total(price: float, shares: int) -> float:
    return price * max(0, int(shares))


def sell_proceeds(price: float, shares: int) -> float:
    gross = price * max(0, int(shares))
    return gross * (1.0 - config.STOCK_SELL_TAX)


def dividend_amount(price: float, shares: int) -> float:
    return price * max(0, int(shares)) * config.STOCK_DIVIDEND_RATE


def event_multiplier(event_type: str | None) -> float:
    if not event_type:
        return 1.0
    return config.STOCK_MARKET_EVENTS.get(event_type, 1.0)


def event_label(event_type: str | None) -> str:
    labels = {
        "tech_boom": "📈 Tech Boom (+25%)",
        "economic_crash": "📉 Economic Crash (−30%)",
        "tourism_surge": "🏖️ Tourism Surge (+12%)",
        "supply_shortage": "📦 Supply Shortage (−15%)",
    }
    return labels.get(event_type or "", "—")
