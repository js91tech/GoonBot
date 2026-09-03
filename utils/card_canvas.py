"""PIL GoonCards frames — portrait + rarity border for inspect, binder, and packs."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.card_ai import CARDS_ASSETS_ROOT, PORTRAIT_SIZE, portrait_path
from utils.card_art import render_card_art
from utils.cards import (
    RARITY_FRAME_RGB,
    RARITY_LABELS,
    CardDefinition,
    card_by_id,
)

CARD_W = 360
CARD_H = 520
PORTRAIT_BOX = 280
PAD = 16
BG = (26, 18, 24, 255)
INK = (255, 236, 210)
DIM = (190, 170, 160)

BINDER_COLS = 3
BINDER_ROWS = 2
BINDER_PER_PAGE = BINDER_COLS * BINDER_ROWS
THUMB_W = 200
THUMB_H = 280
GRID_PAD = 12


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    names = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf") if bold else ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _truncate(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    trimmed = text
    while trimmed and draw.textlength(trimmed + "…", font=font) > max_w:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed else "…"


def render_procedural_portrait(card: CardDefinition, size: int = PORTRAIT_SIZE) -> Image.Image:
    """Unique painterly plate for this catalog id when no cached PNG exists."""
    return render_card_art(card, size=size)


def load_portrait(card: CardDefinition) -> Image.Image:
    path = portrait_path(card.card_id)
    if path.is_file():
        try:
            return Image.open(path).convert("RGBA")
        except OSError:
            pass
    return render_procedural_portrait(card)


def write_procedural_portrait(card: CardDefinition, dest: Path | None = None) -> Path:
    target = dest or portrait_path(card.card_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    render_procedural_portrait(card).save(target)
    return target


def _draw_card_face(
    card: CardDefinition,
    *,
    print_number: int | None,
    width: int,
    height: int,
    portrait: Image.Image | None = None,
) -> Image.Image:
    frame = RARITY_FRAME_RGB[card.rarity]
    canvas = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((4, 4, width - 5, height - 5), radius=18, outline=frame + (255,), width=6)
    draw.rounded_rectangle((14, 14, width - 15, 52), radius=10, fill=frame + (255,))
    title_font = _font(18, bold=True)
    small = _font(13)
    name = _truncate(draw, card.name, title_font, width - 40)
    draw.text((width // 2, 33), name, fill=(20, 12, 16), font=title_font, anchor="mm")

    box = PORTRAIT_BOX if width >= CARD_W else min(width - 40, height - 160)
    px = (width - box) // 2
    py = 64
    source = (portrait or load_portrait(card)).convert("RGBA")
    source.thumbnail((box, box), Image.Resampling.LANCZOS)
    portrait_img = source.resize((box, box), Image.Resampling.LANCZOS)
    canvas.paste(portrait_img, (px, py), portrait_img)
    draw.rectangle((px - 2, py - 2, px + box + 1, py + box + 1), outline=frame + (255,), width=2)

    meta_y = py + box + 16
    rarity_line = f"{card.emoji} {RARITY_LABELS[card.rarity]}"
    draw.text((width // 2, meta_y), rarity_line, fill=frame + (255,), font=title_font, anchor="mm")
    draw.text((width // 2, meta_y + 22), card.set_name, fill=DIM, font=small, anchor="mm")
    if print_number is not None:
        draw.text(
            (width // 2, height - 28),
            f"#{print_number:04d}",
            fill=INK,
            font=_font(16, bold=True),
            anchor="mm",
        )
    else:
        draw.text((width // 2, height - 28), "GoonCards", fill=DIM, font=small, anchor="mm")
    return canvas


def render_card_png(card: CardDefinition, *, print_number: int | None = None) -> bytes:
    image = _draw_card_face(card, print_number=print_number, width=CARD_W, height=CARD_H)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def render_binder_page(
    entries: list[tuple[CardDefinition, int, int]],
) -> bytes:
    """Render a binder grid. Each entry is (card, print_number, owned_count)."""
    width = BINDER_COLS * THUMB_W + (BINDER_COLS + 1) * GRID_PAD
    height = BINDER_ROWS * THUMB_H + (BINDER_ROWS + 1) * GRID_PAD
    canvas = Image.new("RGBA", (width, height), (18, 14, 18, 255))
    draw = ImageDraw.Draw(canvas)
    for index in range(BINDER_PER_PAGE):
        col = index % BINDER_COLS
        row = index // BINDER_COLS
        x = GRID_PAD + col * (THUMB_W + GRID_PAD)
        y = GRID_PAD + row * (THUMB_H + GRID_PAD)
        draw.rounded_rectangle(
            (x, y, x + THUMB_W, y + THUMB_H),
            radius=10,
            fill=(28, 22, 28, 255),
            outline=(55, 45, 52, 255),
        )
        if index >= len(entries):
            continue
        card, print_number, owned = entries[index]
        face = _draw_card_face(
            card, print_number=print_number, width=THUMB_W, height=THUMB_H,
        )
        canvas.paste(face, (x, y), face)
        if owned > 1:
            badge = _font(12, bold=True)
            label = f"×{owned}"
            draw.rounded_rectangle(
                (x + THUMB_W - 48, y + 6, x + THUMB_W - 8, y + 26),
                radius=6,
                fill=(201, 162, 39, 230),
            )
            draw.text((x + THUMB_W - 28, y + 16), label, fill=(20, 12, 16), font=badge, anchor="mm")
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def render_pack_reveal(cards: list[CardDefinition], prints: list[int]) -> bytes:
    n = max(len(cards), 1)
    width = n * (THUMB_W + GRID_PAD) + GRID_PAD
    height = THUMB_H + GRID_PAD * 2
    canvas = Image.new("RGBA", (width, height), (18, 14, 18, 255))
    for index, card in enumerate(cards):
        print_number = prints[index] if index < len(prints) else 0
        face = _draw_card_face(card, print_number=print_number, width=THUMB_W, height=THUMB_H)
        x = GRID_PAD + index * (THUMB_W + GRID_PAD)
        canvas.paste(face, (x, GRID_PAD), face)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def card_from_row(row: object) -> CardDefinition | None:
    card_id = str(row["card_id"])  # type: ignore[index]
    return card_by_id(card_id)


def ensure_assets_dir() -> Path:
    CARDS_ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    return CARDS_ASSETS_ROOT
