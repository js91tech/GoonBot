#!/usr/bin/env python3
"""Generate representative building art for each business tier.

The bot renders unique per-player building images at runtime via
``utils.business_art.render_business_image``. This script produces one
showcase PNG per tier under ``assets/businesses/`` for documentation, the
player guide, and as static fallbacks.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.business_art import render_business_image
from utils.businesses import BUSINESS_TIERS

OUT_DIR = ROOT / "assets" / "businesses"

# Deterministic showcase seed so regenerated assets stay stable in git.
SHOWCASE_USER_ID = 100_000
SHOWCASE_GUILD_ID = 1


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for defn in BUSINESS_TIERS:
        png = render_business_image(SHOWCASE_USER_ID, SHOWCASE_GUILD_ID, defn.tier_id)
        path = OUT_DIR / f"{defn.tier_id}.png"
        path.write_bytes(png)
        created += 1
        print(f"wrote {path.relative_to(ROOT)}")
    print(f"Generated {created} business tier images.")


if __name__ == "__main__":
    main()
