#!/usr/bin/env python3
"""Generate default avatar portrait + victory PNG/GIF assets. Run from repo root."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from utils.avatars import ASSETS_ROOT, AVATARS

PALETTES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], str]] = {
    "nugget_raider": ((218, 165, 32), (40, 30, 10), "RAIDER"),
    "duel_champion": ((220, 60, 60), (30, 10, 10), "CHAMP"),
    "raid_medic": ((80, 200, 120), (10, 40, 20), "MEDIC"),
    "vault_mogul": ((100, 180, 255), (10, 20, 50), "MOGUL"),
    "boss_slayer": ((180, 100, 255), (30, 10, 50), "SLAYER"),
}


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_character(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    accent: tuple[int, int, int],
    shadow: tuple[int, int, int],
) -> None:
    cx = w // 2
    draw.ellipse((cx - 28, 20, cx + 28, 76), fill=accent, outline=shadow, width=2)
    draw.rounded_rectangle((cx - 40, 72, cx + 40, 150), radius=12, fill=accent, outline=shadow, width=2)
    draw.rounded_rectangle((cx - 55, 85, cx - 38, 130), radius=8, fill=shadow)
    draw.rounded_rectangle((cx + 38, 85, cx + 55, 130), radius=8, fill=shadow)


def make_portrait(avatar_id: str) -> Image.Image:
    accent, shadow, _ = PALETTES[avatar_id]
    img = Image.new("RGBA", (128, 128), (24, 24, 32, 255))
    draw = ImageDraw.Draw(img)
    _draw_character(draw, 128, 128, accent, shadow)
    return img


def make_victory_png(avatar_id: str) -> Image.Image:
    accent, shadow, label = PALETTES[avatar_id]
    img = Image.new("RGBA", (400, 220), (18, 18, 28, 255))
    draw = ImageDraw.Draw(img)
    _draw_character(draw, 400, 220, accent, shadow)
    font = _font(28)
    draw.text((200, 168), "VICTORY!", fill=(255, 220, 100), font=font, anchor="mm")
    small = _font(16)
    draw.text((200, 198), label, fill=accent, font=small, anchor="mm")
    return img


def make_victory_gif(avatar_id: str) -> Image.Image:
    frames = []
    for offset in (0, 6, 0, -4):
        accent, shadow, label = PALETTES[avatar_id]
        img = Image.new("RGBA", (400, 220), (18, 18, 28, 255))
        draw = ImageDraw.Draw(img)
        _draw_character(draw, 400, 220, accent, shadow)
        draw.rounded_rectangle(
            (120, 160 + offset, 280, 210 + offset),
            radius=8,
            fill=(255, 220, 100, 180),
        )
        font = _font(28)
        draw.text((200, 168 + offset), "VICTORY!", fill=(255, 220, 100), font=font, anchor="mm")
        small = _font(16)
        draw.text((200, 198 + offset), label, fill=accent, font=small, anchor="mm")
        frames.append(img.convert("P", palette=Image.ADAPTIVE))
    out = frames[0]
    out.save(
        ASSETS_ROOT / avatar_id / "victory.gif",
        save_all=True,
        append_images=frames[1:],
        duration=180,
        loop=0,
        disposal=2,
    )
    return frames[0]


def main() -> None:
    ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    for avatar in AVATARS:
        folder = ASSETS_ROOT / avatar.id
        folder.mkdir(parents=True, exist_ok=True)
        make_portrait(avatar.id).save(folder / "portrait.png")
        make_victory_png(avatar.id).save(folder / "victory.png")
        make_victory_gif(avatar.id)
        print(f"Wrote {folder}")


if __name__ == "__main__":
    main()
