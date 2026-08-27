"""Goon session loop — edging meter, streaks, ruin, dares."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

import config

_STOP = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "your",
        "have",
        "been",
        "they",
        "them",
        "then",
        "than",
        "when",
        "what",
        "just",
        "into",
        "over",
        "until",
        "about",
        "don't",
        "does",
        "were",
        "we're",
        "you're",
        "their",
        "there",
        "where",
        "which",
        "while",
        "would",
        "could",
        "should",
        "still",
        "every",
        "after",
        "before",
        "velvet",
    },
)

GOON_DARES: tuple[str, ...] = (
    "Don't finish. Count to sixty. Edge once. That's the round.",
    "Caption it: Velvet has you against the booth glass.",
    "No hands for the next song. Meter still counts.",
    "Type what you'd let the floor do to you. Then `/goon edge`.",
    "Last one to say **still edged** buys the next round. Honor system.",
    "Watch someone else's session. Don't touch yours until they ruin or finish.",
    "Put the phone closer. Stay on the edge until the next `/daily`.",
    "One clip. One edge. No skipping to the end.",
    "Tell the channel what ruined you last. Then start a new streak.",
    "Private booth rules: headphones on, `/goon edge` every 45s until 80.",
    "You don't get to finish until someone else uses `/goon tease` on you.",
    "Edging in VC is a watch party. If you're alone, that's pathetic — get company.",
)

GOON_LORE_LINES: tuple[str, ...] = (
    "Velvet said don't finish until the bass drops.",
    "The booth is soundproof but everyone still knows.",
    "Goonbux hit different when you're not allowed to finish.",
    "Aftercare is a lie they tell you so you'll go again.",
    "The guest list is just people who haven't ruined yet.",
    "Main stage lights make it impossible to hide the shake.",
    "Fixers don't ask what the clip is for. They already know.",
    "Heat is just how long you lasted with the tab open.",
    "Somebody in voice is breathing like they lost the streak.",
    "Private rooms exist so the floor doesn't have to watch you leak.",
    "The virus is just a goon you can't put down.",
    "Tip the host. They're keeping you edged on purpose.",
)


@dataclass(frozen=True)
class GoonSessionState:
    meter: float = 0.0
    streak: int = 0
    session_started_at: float = 0.0
    last_edge_at: float = 0.0
    last_passive_at: float = 0.0
    last_tease_at: float = 0.0
    last_ruin_at: float = 0.0
    last_finish_at: float = 0.0
    ruined_by: int | None = None
    lifetime_edges: int = 0
    lifetime_ruins: int = 0
    lifetime_finishes: int = 0


def session_from_row(row: object | None) -> GoonSessionState:
    if row is None:
        return GoonSessionState()

    def _f(key: str, default: float = 0.0) -> float:
        try:
            return float(row[key])  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return default

    def _i(key: str, default: int = 0) -> int:
        try:
            return int(row[key])  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return default

    ruined_raw = None
    try:
        ruined_raw = row["ruined_by"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        ruined_raw = None
    ruined_by = int(ruined_raw) if ruined_raw not in (None, 0) else None
    return GoonSessionState(
        meter=_f("meter"),
        streak=_i("streak"),
        session_started_at=_f("session_started_at"),
        last_edge_at=_f("last_edge_at"),
        last_passive_at=_f("last_passive_at"),
        last_tease_at=_f("last_tease_at"),
        last_ruin_at=_f("last_ruin_at"),
        last_finish_at=_f("last_finish_at"),
        ruined_by=ruined_by,
        lifetime_edges=_i("lifetime_edges"),
        lifetime_ruins=_i("lifetime_ruins"),
        lifetime_finishes=_i("lifetime_finishes"),
    )


def meter_bar(meter: float, *, length: int = 10) -> str:
    cap = config.GOON_METER_MAX
    if cap <= 0:
        return "░" * length
    filled = int(round((max(0.0, min(cap, meter)) / cap) * length))
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


def clamp_meter(meter: float) -> float:
    return max(0.0, min(config.GOON_METER_MAX, meter))


def roll_edge_gain() -> float:
    lo, hi = config.GOON_EDGE_GAIN
    return float(random.randint(int(lo), int(hi)))


def roll_tease_gain() -> float:
    lo, hi = config.GOON_TEASE_GAIN
    return float(random.randint(int(lo), int(hi)))


def watch_multiplier(other_humans: int) -> float:
    if other_humans <= 0:
        return 1.0
    return min(
        config.GOON_WATCH_MULT_CAP,
        1.0 + config.GOON_WATCH_PER_PERSON * other_humans,
    )


def finish_payout(streak: int, meter: float) -> float:
    if streak <= 0 and meter < 10:
        return 0.0
    base = config.GOON_FINISH_BASE + max(0, streak) * config.GOON_FINISH_PER_STREAK
    meter_mult = 0.5 + clamp_meter(meter) / 200.0
    return max(1.0, round(base * meter_mult, 2))


def ruin_cost(target_streak: int) -> float:
    return config.GOON_RUIN_COST_BASE + max(0, target_streak) * config.GOON_RUIN_COST_PER_STREAK


def daily_edge_bonus_mult(streak: int) -> float:
    bonus = min(
        config.GOON_DAILY_STREAK_BONUS_CAP,
        max(0, streak) * config.GOON_DAILY_STREAK_BONUS_PER,
    )
    return 1.0 + bonus


def cooldown_remaining(last_at: float, cooldown: float, now: float) -> float:
    if last_at <= 0 or cooldown <= 0:
        return 0.0
    remaining = (last_at + cooldown) - now
    return remaining if remaining > 0 else 0.0


def format_session_block(state: GoonSessionState) -> str:
    bar = meter_bar(state.meter)
    meter_i = int(round(state.meter))
    lines = [
        f"`{bar}` **{meter_i}/{int(config.GOON_METER_MAX)}** edged",
        f"Streak **{state.streak}** · finishes **{state.lifetime_finishes}** · ruined **{state.lifetime_ruins}**",
    ]
    if state.ruined_by:
        lines.append(f"Last ruined by <@{state.ruined_by}>")
    payout = finish_payout(state.streak, state.meter)
    if payout > 0:
        from utils.helpers import fmt_amount

        lines.append(f"Finish now: **{fmt_amount(payout)}** · `/goon finish` or get `/goon ruin`'d")
    else:
        lines.append("Not edged yet — `/goon edge` to start a session")
    return "\n".join(lines)


def pick_dare() -> str:
    return random.choice(GOON_DARES)


def pick_lore_line() -> str:
    return random.choice(GOON_LORE_LINES)


def blank_lore_line(line: str | None = None) -> tuple[str, str]:
    """Return (prompt with blank, answer word) from a gooner lore line."""
    source = (line or pick_lore_line()).strip()
    words = source.split()
    candidates: list[int] = []
    for i, raw in enumerate(words):
        token = re.sub(r"[^A-Za-z']", "", raw)
        if len(token) < 4:
            continue
        if token.lower().strip("'") in _STOP:
            continue
        candidates.append(i)
    if not candidates:
        return source.replace("finish", "______", 1), "finish"
    idx = random.choice(candidates)
    answer = re.sub(r"[^A-Za-z']", "", words[idx])
    words[idx] = "______"
    return " ".join(words), answer


def voice_watchers(member: object) -> int:
    voice = getattr(member, "voice", None)
    channel = getattr(voice, "channel", None) if voice is not None else None
    if channel is None:
        return 0
    members = getattr(channel, "members", None) or []
    uid = getattr(member, "id", None)
    count = 0
    for other in members:
        if getattr(other, "bot", False):
            continue
        if uid is not None and getattr(other, "id", None) == uid:
            continue
        count += 1
    return count
