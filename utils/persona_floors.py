"""Persona-gated floors — Talent / Host / Fixer exclusive hustles."""
from __future__ import annotations

from utils.classes import get_class
from utils.jobs import JOBS, JobDef


PERSONA_FLOOR_BLURBS: dict[str, str] = {
    "vanguard": "Talent floor — main-stage edges and Velvet teases.",
    "mogul": "Host floor — private booths and tribute hustles.",
    "shade": "Fixer floor — back-room peeks and clip runs.",
}


def starter_root_for(class_id: str | None) -> str | None:
    cls = get_class(class_id)
    if cls is None:
        return None
    if cls.starter_root:
        return cls.starter_root
    if cls.class_id in ("vanguard", "mogul", "shade"):
        return cls.class_id
    return None


def job_unlocked(job: JobDef, class_id: str | None) -> bool:
    required = job.required_root
    if not required:
        return True
    root = starter_root_for(class_id)
    return root == required


def available_jobs(class_id: str | None) -> tuple[JobDef, ...]:
    return tuple(job for job in JOBS if job_unlocked(job, class_id))


def locked_jobs(class_id: str | None) -> tuple[JobDef, ...]:
    return tuple(job for job in JOBS if not job_unlocked(job, class_id))


def persona_floor_blurb(class_id: str | None) -> str:
    root = starter_root_for(class_id)
    if root is None:
        return "Pick a persona (`/class choose`) to unlock your floor hustles."
    return PERSONA_FLOOR_BLURBS.get(root, "Your floor is open.")
