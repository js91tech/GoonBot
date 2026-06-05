#!/usr/bin/env python3
"""Generate simple placeholder PNG icons for shop items missing assets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from items import ITEMS

ICON_SIZE = 64
OUT_DIR = ROOT / "assets" / "items"

EMOJI_BY_ID: dict[str, str] = {
    "jail_key": "🔑",
    "pick_key": "🗝️",
}


def render_icon(item_id: str, emoji: str) -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (40, 44, 52, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    draw.text((ICON_SIZE // 2, ICON_SIZE // 2), emoji, fill=(220, 200, 120, 255), font=font, anchor="mm")
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for item_id, item in ITEMS.items():
        if item.category != "consumable" and item_id not in EMOJI_BY_ID:
            continue
        path = OUT_DIR / f"{item_id}.png"
        if path.is_file():
            continue
        emoji = EMOJI_BY_ID.get(item_id, "🧪")
        render_icon(item_id, emoji).save(path)
        created += 1
        print(f"Wrote {path}")
    print(f"Done — created {created} icon(s).")


if __name__ == "__main__":
    main()
