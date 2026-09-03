#!/usr/bin/env python3
"""Generate unique GoonCards portraits via the seeded painterly compositor.

Run from repo root:

    python3 scripts/generate_card_portraits.py
    python3 scripts/generate_card_portraits.py --only-missing
    python3 scripts/generate_card_portraits.py --force
    python3 scripts/generate_card_portraits.py --ai
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


async def _generate(force: bool, use_ai: bool, only_ids: set[str] | None) -> int:
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
        if use_ai:
            used_ai = await try_generate_ai_portrait(card, dest)
        if not used_ai:
            write_procedural_portrait(card, dest)
        else:
            ai_ok += 1
        written += 1
        kind = "ai" if used_ai else "unique"
        print(f"{card.card_id}: {kind} -> {dest}")
    print(f"done: wrote {written}, skipped {skipped}, ai {ai_ok}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate unique GoonCards portrait PNGs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing portraits")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only write catalog ids that have no PNG yet (default behavior without --force)",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Try the images API first (falls back to the unique local compositor)",
    )
    parser.add_argument(
        "--procedural-only",
        action="store_true",
        help="Deprecated no-op alias: unique local plates are the default.",
    )
    args = parser.parse_args()
    only_ids = None
    if args.only_missing:
        from utils.card_ai import portrait_path as _p
        only_ids = {cid for cid in CARD_DEFINITIONS if not _p(cid).is_file()}
        args.force = False
    return asyncio.run(_generate(args.force, args.ai and not args.procedural_only, only_ids))


if __name__ == "__main__":
    raise SystemExit(main())
