"""Velvet Walks In — scheduled nightlife boss windows."""
from __future__ import annotations

from datetime import datetime, timezone

import config


def velvet_night_active_now(event: object | None = None) -> bool:
    """True when admin velvet_night event is live or UTC hour is in the auto window."""
    if event is not None:
        try:
            if str(event["event_type"]) == "velvet_night":
                return True
        except (KeyError, TypeError, IndexError):
            pass
    if not config.VELVET_NIGHT_AUTO_ENABLED:
        return False
    hour = datetime.now(timezone.utc).hour
    return hour in config.VELVET_NIGHT_UTC_HOURS


def velvet_night_label() -> str:
    return "Velvet Walks In"
