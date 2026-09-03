#!/usr/bin/env python3
"""Generate GoonCards portraits. Prefers the images API; falls back to procedural art.

Run from repo root:

    python3 scripts/generate_card_portraits.py
    python3 scripts/generate_card_portraits.py --force
    python3 scripts/generate_card_portraits.py --procedural-only
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.card_ai import portrait_path, try_generate_ai_portrait
from utils.card_canvas import write_procedural_portrait
from utils.cards import CARD_DEFINITIONS


async def _generate(force: bool, procedural_only: bool) -> int:
    written = 0
    skipped = 0
    ai_ok = 0
    for card in CARD_DEFINITIONS.values():
        dest = portrait_path(card.card_id)
        if dest.is_file() and not force:
            skipped += 1
            continue
        used_ai = False
        if not procedural_only:
            used_ai = await try_generate_ai_portrait(card, dest)
        if not used_ai:
            write_procedural_portrait(card, dest)
        else:
            ai_ok += 1
        written += 1
        kind = "ai" if used_ai else "procedural"
        print(f"{card.card_id}: {kind} -> {dest}")
    print(f"done: wrote {written}, skipped {skipped}, ai {ai_ok}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate GoonCards portrait PNGs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing portraits")
    parser.add_argument(
        "--procedural-only",
        action="store_true",
        help="Skip the images API even if AI_API_KEY is set",
    )
    args = parser.parse_args()
    return asyncio.run(_generate(args.force, args.procedural_only))


if __name__ == "__main__":
    raise SystemExit(main())
