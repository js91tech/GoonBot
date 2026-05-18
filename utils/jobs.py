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


JOBS: tuple[JobDef, ...] = (
    JobDef(
        "miner",
        "Miner",
        "Chip away at the nugget mines for steady pay.",
        10,
        85.0,
        130.0,
        "⛏️",
    ),
    JobDef(
        "medic",
        "Field Medic",
        "Run supplies to downed raiders and clinics.",
        10,
        70.0,
        115.0,
        "🩹",
    ),
    JobDef(
        "raider",
        "Raid Scout",
        "Scout boss weak points for the war band.",
        12,
        60.0,
        105.0,
        "⚔️",
    ),
    JobDef(
        "courier",
        "Courier",
        "Haul wallets and parcels across the server.",
        8,
        75.0,
        120.0,
        "📦",
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
