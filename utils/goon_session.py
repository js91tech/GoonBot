"""Goon session loop — edging meter, streaks, ruin, dares."""
from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass

import config

GROUP_GOON_PROMPT = "Is the chat ready for a group goon session?"
GROUP_GOON_PROMPTS: tuple[str, ...] = (
    "Is the chat ready for a group goon session?",
    "Floor's open. Who's edging?",
    "Group session. Don't finish unless you mean it.",
    "Main chat looks bored. Ready to goon?",
    "Velvet's watching. Group goon — first yes gets paid.",
    "Anyone still edged? Group session starting.",
)
_GROUP_GOON_YES = re.compile(
    r"^\s*(yes+|yeah+|yep|yea|yup|yas+|ready|i['’]?m\s+ready|let['’]?s\s+go|down|here)\b",
    re.IGNORECASE,
)
_GROUP_GOON_TOPIC = ("goon", "session", "ready", "condom", "goonbux", "let's go", "lets go")
_GROUP_GOON_SHORT_YES = 40

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
    "Look at her. **What would you let her do to you?** Type it. Then `/goon edge`.",
    "She's waiting. Tell the channel **what you'd let her do to you.** Then `/goon edge`.",
    "What are you letting her do tonight? Be specific. Then `/goon edge`.",
    "Don't finish. Tell her (and us) **what you'd let her do.** Edge once.",
    "Caption it: her, you, the booth. **What does she get to do?** Then `/goon edge`.",
    "Look at those hands. **What are they allowed to do to you?** Type it.",
    "She's got you. **What do you let her do?** Then `/goon edge`.",
    "Private booth with her. Headphones on. Type **what you'd let her do**, then `/goon edge` until 80.",
    "One look. One answer. **What would you let her do to you?** Then `/goon edge`.",
    "She's watching your session. **What would you let her do if she took over?** Type it.",
    "You don't get to finish until you say **what you'd let her do to you** and someone `/goon tease`s you.",
    "Edging with her on screen. If you're alone, say **what you'd let her do** anyway.",
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
    condom_charges: int = 0
    dare_expires_at: float = 0.0
    lifetime_group_rounds: int = 0


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
        condom_charges=_i("condom_charges"),
        dare_expires_at=_f("dare_expires_at"),
        lifetime_group_rounds=_i("lifetime_group_rounds"),
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


def ruin_cost(target_streak: int, *, cost_mult: float = 1.0) -> float:
    base = config.GOON_RUIN_COST_BASE + max(0, target_streak) * config.GOON_RUIN_COST_PER_STREAK
    return max(1.0, round(base * max(0.1, cost_mult), 2))


def safe_finish_streak(streak: int) -> int:
    if streak < 2:
        return 0
    kept = int(streak * config.GOON_SAFE_FINISH_STREAK_KEEP)
    return max(1, kept)


def persona_edge_mult(class_id: str | None) -> float:
    from utils.persona_floors import starter_root_for

    if starter_root_for(class_id) == "vanguard":
        return float(config.GOON_PERSONA_EDGE_MULT)
    return 1.0


def persona_tease_cost_mult(class_id: str | None) -> float:
    from utils.persona_floors import starter_root_for

    if starter_root_for(class_id) == "mogul":
        return float(config.GOON_PERSONA_TEASE_COST_MULT)
    return 1.0


def persona_ruin_cost_mult(class_id: str | None) -> float:
    from utils.persona_floors import starter_root_for

    if starter_root_for(class_id) == "shade":
        return float(config.GOON_PERSONA_RUIN_COST_MULT)
    return 1.0


def tease_cost_for(class_id: str | None) -> float:
    return max(1.0, round(config.GOON_TEASE_COST * persona_tease_cost_mult(class_id), 2))


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
    if state.condom_charges > 0:
        lines.append(
            f"Wrapped **{state.condom_charges}×** — blocks a ruin, holds a leak, or keeps streak on finish"
        )
    remaining_dare = state.dare_expires_at - time.time()
    if remaining_dare > 0:
        lines.append(f"Dare live **{int(remaining_dare)}s** — `/goon edge` to cash it")
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


def is_group_goon_yes(text: str | None) -> bool:
    """True when a chat reply is answering the group-session call."""
    if not text:
        return False
    return _GROUP_GOON_YES.search(text.strip()) is not None


def is_group_goon_chat_claim(text: str | None, *, replied_to_prompt: bool = False) -> bool:
    """First-answer detector that ignores long unrelated 'yeah' chatter."""
    if not is_group_goon_yes(text):
        return False
    if replied_to_prompt:
        return True
    stripped = (text or "").strip()
    if len(stripped) <= _GROUP_GOON_SHORT_YES:
        return True
    lowered = stripped.lower()
    return any(token in lowered for token in _GROUP_GOON_TOPIC)


def next_group_goon_call_minutes() -> int:
    base = int(config.GOON_CALL_INTERVAL_MINUTES)
    jitter = int(config.GOON_CALL_INTERVAL_JITTER_MINUTES)
    lo = max(1, base - jitter)
    hi = max(lo, base + jitter)
    return random.randint(lo, hi)


def roll_group_goon_reward() -> float:
    lo, hi = config.GOON_CALL_REWARD
    return float(random.randint(int(lo), int(hi)))


def pick_group_goon_prompt() -> str:
    return random.choice(GROUP_GOON_PROMPTS)
