from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite

from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "nuggetbot.sqlite3")
GUILD_ID = int(os.environ["GUILD_ID"]) if os.getenv("GUILD_ID") else None

CURRENCY_NAME = "nuggets"
CURRENCY_EMOJI = "🍘"

PASSIVE_CHAT_REWARD = 0.5
PASSIVE_ACTIVE_BONUS = 15.0
VOICE_CHAT_REWARD = 3.0
DAILY_REWARD = 75.0
DAILY_COOLDOWN_SECONDS = 24 * 60 * 60

BOUNTY_MIN_AMOUNT = 50.0
BOUNTY_TAX = 5.0
BOUNTY_TRIGGER_MAX_LENGTH = 32

HEIST_BASE_SUCCESS = 0.20
HEIST_CREW_BONUS = 0.10
HEIST_MAX_SUCCESS = 0.80
HEIST_LOOT_FRACTION = 0.20
HEIST_COOLDOWN_SECONDS = 30 * 60
HEIST_ARREST_WINDOW_SECONDS = 5 * 60
HEIST_ARREST_SECONDS = 60 * 60

HACK_BASE_PENALTY = 35.0
HACK_PASS_PENALTY = 2.0
HACK_TRANSFER_SECONDS = 60

BOSS_AUTO_SPAWN_SECONDS = 2 * 60 * 60
BOSS_MIN_HP = 500.0
BOSS_CIRCULATION_HP_FACTOR = 0.05
BOSS_ATTACK_MIN = 20
BOSS_ATTACK_MAX = 75
BOSS_DOWN_SECONDS = 2 * 60
BOSS_VARIANTS = {
    "normal": {"multiplier": 1.0, "counter_chance": 0.08},
    "enraged": {"multiplier": 1.5, "counter_chance": 0.12},
    "shadow": {"multiplier": 2.0, "counter_chance": 0.16},
    "celestial": {"multiplier": 3.0, "counter_chance": 0.20},
}

IMPOSTER_CHANCE = 0.01
IMPOSTER_MIN_WORDS = 3
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://api.openai.com/v1/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
AI_TIMEOUT_SECONDS = 8

TRIVIA_REWARD = 25.0
TRIVIA_SECONDS = 30
TRIVIA_MAX_CHANNELS = 10
TRIVIA_HISTORY_DAYS = 45
TRIVIA_MESSAGES_PER_CHANNEL = 50


@dataclass(frozen=True)
class LiveSetting:
    default: float
    description: str
    minimum: float = 0.0
    maximum: float | None = None
    integer: bool = False

    def validate(self, value: float) -> float:
        if not isfinite(value):
            msg = "must be a finite number"
            raise ValueError(msg)
        if value < self.minimum:
            msg = f"must be at least {self.minimum:g}"
            raise ValueError(msg)
        if self.maximum is not None and value > self.maximum:
            msg = f"must be no more than {self.maximum:g}"
            raise ValueError(msg)
        if self.integer and not value.is_integer():
            msg = "must be a whole number"
            raise ValueError(msg)
        return int(value) if self.integer else value


LIVE_SETTINGS: dict[str, LiveSetting] = {
    "passive_chat_reward": LiveSetting(PASSIVE_CHAT_REWARD, "Per-message earning"),
    "passive_active_bonus": LiveSetting(PASSIVE_ACTIVE_BONUS, "Per active hour earning"),
    "voice_chat_reward": LiveSetting(VOICE_CHAT_REWARD, "Per minute in VC"),
    "daily_reward": LiveSetting(DAILY_REWARD, "/daily claim amount"),
    "bounty_min_amount": LiveSetting(BOUNTY_MIN_AMOUNT, "Minimum bounty", minimum=0.01),
    "bounty_bot_tax": LiveSetting(BOUNTY_TAX, "Bot tax on bounties"),
    "heist_base_success": LiveSetting(
        HEIST_BASE_SUCCESS,
        "Heist success rate",
        maximum=HEIST_MAX_SUCCESS,
    ),
    "heist_cooldown_seconds": LiveSetting(
        HEIST_COOLDOWN_SECONDS,
        "Heist cooldown",
        integer=True,
    ),
    "arrest_lockout_seconds": LiveSetting(
        HEIST_ARREST_SECONDS,
        "Arrest lockout duration",
        integer=True,
    ),
    "hack_timer_seconds": LiveSetting(HACK_TRANSFER_SECONDS, "Hot potato timer", minimum=1, integer=True),
    "hack_base_penalty": LiveSetting(HACK_BASE_PENALTY, "Starting virus penalty"),
    "hack_penalty_increment": LiveSetting(HACK_PASS_PENALTY, "Penalty increase per pass"),
    "boss_health_scale_factor": LiveSetting(BOSS_CIRCULATION_HP_FACTOR, "Boss HP scaling"),
    "boss_downed_seconds": LiveSetting(BOSS_DOWN_SECONDS, "Boss downed duration", minimum=1, integer=True),
    "imposter_chance": LiveSetting(IMPOSTER_CHANCE, "Per-message sabotage chance", maximum=1.0),
    "trivia_reward": LiveSetting(TRIVIA_REWARD, "Trivia answer reward"),
}


def live_setting_default(name: str) -> float:
    return LIVE_SETTINGS[name].default
