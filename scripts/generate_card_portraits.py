#!/usr/bin/env python3
"""Generate GoonCards portrait PNGs.

Shipped original-48 art is the illustrated set in assets/cards/card_*.png.
The 100 lust-set plates from the #21 expansion stay compositor-style unless
you pass --force. This script fills gaps or optionally regenerates:

    python3 scripts/generate_card_portraits.py
    python3 scripts/generate_card_portraits.py --only-missing
    python3 scripts/generate_card_portraits.py --force --ai
    python3 scripts/generate_card_portraits.py --force --procedural-only

`--force` without `--ai` / `--procedural-only` still prefers the images API
when a key is set, otherwise writes the local compositor fallback.
`--procedural-only` always writes compositor plates (not the illustrated look).
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


async def _generate(
    force: bool,
    use_ai: bool,
    only_ids: set[str] | None,
    procedural_only: bool,
) -> int:
    written = 0
    skipped = 0
    ai_ok = 0
    catalog = CARD_DEFINITIONS.values()
    if only_ids is not None:
        catalog = [c for c in catalog if c.card_id in only_ids]
    for card in catalog:
        dest = portrait_path(card.card_id)
        if dest.is_file() and not force:
            skipped += 1
            continue
        used_ai = False
        if use_ai and not procedural_only:
            used_ai = await try_generate_ai_portrait(card, dest)
        if not used_ai:
            write_procedural_portrait(card, dest)
        else:
            ai_ok += 1
        written += 1
        kind = "ai" if used_ai else "fallback"
        print(f"{card.card_id}: {kind} -> {dest}")
    print(f"done: wrote {written}, skipped {skipped}, ai {ai_ok}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate GoonCards portrait PNGs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing portraits")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only write catalog ids that have no PNG yet (default behavior without --force)",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Try the images API first (falls back to the local compositor)",
    )
    parser.add_argument(
        "--procedural-only",
        action="store_true",
        help="Write local compositor fallbacks only (not illustrated art).",
    )
    args = parser.parse_args()
    only_ids = None
    if args.only_missing:
        from utils.card_ai import portrait_path as _p
        only_ids = {cid for cid in CARD_DEFINITIONS if not _p(cid).is_file()}
        args.force = False
    return asyncio.run(_generate(args.force, args.ai, only_ids, args.procedural_only))


if __name__ == "__main__":
    raise SystemExit(main())
