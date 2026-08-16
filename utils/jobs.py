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
        "Lounge Grinder",
        "Work the VIP lounge circuit for steady goonbux.",
        10,
        85.0,
        130.0,
        "💋",
    ),
    JobDef(
        "medic",
        "Aftercare Medic",
        "Patch up spent raiders and keep the session going.",
        10,
        70.0,
        115.0,
        "🩹",
    ),
    JobDef(
        "raider",
        "Velvet Scout",
        "Scout Velvet Vixen weak points for the war band.",
        12,
        60.0,
        105.0,
        "⚔️",
    ),
    JobDef(
        "courier",
        "Stash Runner",
        "Haul goonbux, gear, and stash across the server.",
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
