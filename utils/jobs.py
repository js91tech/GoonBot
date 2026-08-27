from __future__ import annotations

import random
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class JobDef:
    job_id: str
    name: str
    description: str
    energy_cost: int
    payout_min: float
    payout_max: float
    emoji: str
    required_root: str | None = None  # vanguard / mogul / shade — None = open floor


JOBS: tuple[JobDef, ...] = (
    JobDef(
        "miner",
        "Goon Cave Shift",
        "Scroll, edge, collect tributes. Don't finish on the clock.",
        10,
        85.0,
        130.0,
        "💋",
    ),
    JobDef(
        "medic",
        "Aftercare",
        "Wipe them down. Get them hard again. Keep the session going.",
        10,
        70.0,
        115.0,
        "🩹",
    ),
    JobDef(
        "raider",
        "Velvet Tease",
        "Scout what she's wearing. Report back dripping.",
        12,
        60.0,
        105.0,
        "⚔️",
    ),
    JobDef(
        "courier",
        "Clip Runner",
        "Haul clips, stash, and goonbux across the floor.",
        8,
        75.0,
        120.0,
        "📦",
    ),
    JobDef(
        "stage_talent",
        "Main-Stage Edge",
        "Talent-only — own the lights. Stay edged until last call.",
        12,
        110.0,
        165.0,
        "🎤",
        required_root="vanguard",
    ),
    JobDef(
        "floor_host",
        "Private Booth",
        "Host-only — work the booths. Keep them tipping and leaking.",
        10,
        120.0,
        175.0,
        "🥂",
        required_root="mogul",
    ),
    JobDef(
        "backroom_fixer",
        "Back-Room Peek",
        "Fixer-only — quiet jobs behind the curtain. Nobody asks what the clip is for.",
        11,
        100.0,
        160.0,
        "🕶️",
        required_root="shade",
    ),
)

JOBS_BY_ID: dict[str, JobDef] = {job.job_id: job for job in JOBS}


def get_job(job_id: str) -> JobDef | None:
    return JOBS_BY_ID.get(job_id.lower().strip())


def roll_job_payout(job: JobDef, *, payout_mult: float = 1.0) -> float:
    low = int(job.payout_min * config.JOB_PAYOUT_MULTIPLIER * payout_mult)
    high = int(job.payout_max * config.JOB_PAYOUT_MULTIPLIER * payout_mult)
    if high < low:
        high = low
    return float(random.randint(low, high))
