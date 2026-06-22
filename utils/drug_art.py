"""Procedural art for drug strains and the lab panel."""
from __future__ import annotations

import hashlib
import io
import random

from PIL import Image, ImageDraw, ImageFont

from utils.drugs import DRUGS, drug_by_id

WIDTH = 480
HEIGHT = 280


def _rng(drug_id: str) -> random.Random:
    digest = hashlib.sha256(drug_id.encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont]:
    try:
        title = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        small = ImageFont.truetype("DejaVuSans.ttf", 14)
        return title, small
    except OSError:
        default = ImageFont.load_default()
        return default, default


_STRAIN_COLORS: dict[str, tuple[int, int, int]] = {
    "greenleaf": (86, 176, 96),
    "bluecrystal": (96, 156, 224),
    "whitedust": (224, 224, 232),
    "goldenpoppy": (224, 176, 70),
}


def _draw_pouch(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: tuple[int, int, int], rng: random.Random) -> None:
    # A baggie of product.
    draw.rounded_rectangle([cx - 60, cy - 70, cx + 60, cy + 70], radius=16, fill=(40, 42, 48), outline=(90, 92, 100))
    draw.rectangle([cx - 40, cy - 90, cx + 40, cy - 64], fill=(120, 122, 130))
    for _ in range(70):
        px = rng.randint(cx - 52, cx + 52)
        py = rng.randint(cy - 56, cy + 60)
        r = rng.randint(2, 5)
        jitter = lambda c: max(20, min(255, c + rng.randint(-25, 25)))  # noqa: E731
        draw.ellipse([px, py, px + r, py + r], fill=(jitter(color[0]), jitter(color[1]), jitter(color[2])))


def render_drug_image(drug_id: str) -> bytes:
    defn = drug_by_id(drug_id)
    name = defn.name if defn else "Product"
    color = _STRAIN_COLORS.get(drug_id, (160, 160, 170))
    rng = _rng(drug_id)

    canvas = Image.new("RGB", (WIDTH, HEIGHT), (22, 24, 30))
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        t = y / HEIGHT
        shade = int(22 + t * 26)
        draw.line([(0, y), (WIDTH, y)], fill=(shade, shade + 2, shade + 8))

    _draw_pouch(draw, WIDTH // 2, HEIGHT // 2 - 10, color, rng)

    title_font, small_font = _fonts()
    draw.rectangle([0, HEIGHT - 34, WIDTH, HEIGHT], fill=(14, 16, 22))
    label = f"{defn.emoji + ' ' if defn else ''}{name}"
    draw.text((14, HEIGHT - 27), label, font=title_font, fill=(255, 255, 255))
    if defn is not None:
        price_text = f"~{int(defn.street_price)}/unit"
        tw = draw.textlength(price_text, font=small_font)
        draw.text((WIDTH - tw - 14, HEIGHT - 24), price_text, font=small_font, fill=color)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def render_lab_image() -> bytes:
    """A simple lab/grow-room banner image."""
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (18, 22, 26))
    draw = ImageDraw.Draw(canvas)
    rng = random.Random(42)
    for y in range(HEIGHT):
        t = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=(int(18 + t * 10), int(30 + t * 20), int(26 + t * 14)))
    # Grow lamps and plant rows.
    for i, defn in enumerate(DRUGS):
        x = 60 + i * 110
        draw.rectangle([x - 36, 30, x + 36, 44], fill=(240, 230, 150))
        for _ in range(40):
            px = rng.randint(x - 30, x + 30)
            py = rng.randint(70, 200)
            color = _STRAIN_COLORS.get(defn.drug_id, (120, 170, 120))
            draw.ellipse([px, py, px + 4, py + 4], fill=color)
        draw.rectangle([x - 40, 200, x + 40, 220], fill=(70, 54, 40))
    title_font, _ = _fonts()
    draw.rectangle([0, HEIGHT - 32, WIDTH, HEIGHT], fill=(12, 14, 18))
    draw.text((14, HEIGHT - 26), "🧪 Grow Lab", font=title_font, fill=(220, 240, 220))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()
