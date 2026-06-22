"""Procedural building art for the Business Empire.

Renders a unique storefront/building PNG per business tier, with a seeded
accent palette derived from ``(user_id, guild_id)`` so every player's empire
looks distinct. Mirrors the procedural style used by avatar portraits and the
shop canvas (pure Pillow, no external assets required).
"""
from __future__ import annotations

import hashlib
import io
import random

from PIL import Image, ImageDraw, ImageFont

from utils.businesses import tier_def_by_id

WIDTH = 480
HEIGHT = 320
GROUND_Y = 264


def _rng(user_id: int, guild_id: int, tier_id: str) -> random.Random:
    digest = hashlib.sha256(f"{user_id}:{guild_id}:{tier_id}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont]:
    try:
        title = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
        small = ImageFont.truetype("DejaVuSans.ttf", 14)
        return title, small
    except OSError:
        default = ImageFont.load_default()
        return default, default


def _accent(rng: random.Random) -> tuple[int, int, int]:
    palettes = [
        (224, 92, 92),
        (92, 148, 224),
        (96, 196, 128),
        (224, 176, 84),
        (168, 112, 220),
        (96, 200, 200),
        (232, 132, 176),
    ]
    base = rng.choice(palettes)
    jitter = lambda c: max(20, min(245, c + rng.randint(-18, 18)))  # noqa: E731
    return (jitter(base[0]), jitter(base[1]), jitter(base[2]))


def _sky_gradient(draw: ImageDraw.ImageDraw, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    for y in range(GROUND_Y):
        t = y / GROUND_Y
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def _lit_windows(
    draw: ImageDraw.ImageDraw,
    rng: random.Random,
    box: tuple[int, int, int, int],
    *,
    cols: int,
    rows: int,
    glass: tuple[int, int, int],
    lit: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    pad = 10
    gap = 8
    cell_w = (x1 - x0 - pad * 2 - gap * (cols - 1)) / cols
    cell_h = (y1 - y0 - pad * 2 - gap * (rows - 1)) / rows
    if cell_w <= 1 or cell_h <= 1:
        return
    for c in range(cols):
        for r in range(rows):
            wx = x0 + pad + c * (cell_w + gap)
            wy = y0 + pad + r * (cell_h + gap)
            fill = lit if rng.random() < 0.45 else glass
            draw.rectangle(
                [wx, wy, wx + cell_w, wy + cell_h],
                fill=fill,
                outline=(28, 30, 36),
            )


def _draw_building(
    draw: ImageDraw.ImageDraw,
    rng: random.Random,
    tier: int,
    accent: tuple[int, int, int],
) -> None:
    wall = (54, 58, 68)
    wall_light = (74, 78, 90)
    glass = (60, 92, 120)
    lit = (240, 214, 130)
    cx = WIDTH // 2

    if tier <= 1:
        # Lemon stand: small booth with awning.
        draw.rectangle([cx - 70, GROUND_Y - 70, cx + 70, GROUND_Y], fill=(150, 110, 70))
        draw.rectangle([cx - 78, GROUND_Y - 92, cx + 78, GROUND_Y - 70], fill=accent)
        for i, sx in enumerate(range(cx - 78, cx + 78, 22)):
            stripe = (250, 250, 250) if i % 2 == 0 else accent
            draw.rectangle([sx, GROUND_Y - 92, sx + 22, GROUND_Y - 70], fill=stripe)
        draw.rectangle([cx - 70, GROUND_Y - 70, cx + 70, GROUND_Y - 40], fill=(120, 88, 56))
    elif tier == 2:
        # Food cart: body on wheels with parasol.
        draw.rectangle([cx - 64, GROUND_Y - 64, cx + 64, GROUND_Y - 18], fill=wall_light)
        draw.rectangle([cx - 64, GROUND_Y - 64, cx + 64, GROUND_Y - 48], fill=accent)
        draw.ellipse([cx - 56, GROUND_Y - 26, cx - 30, GROUND_Y], fill=(30, 30, 34))
        draw.ellipse([cx + 30, GROUND_Y - 26, cx + 56, GROUND_Y], fill=(30, 30, 34))
        draw.line([cx, GROUND_Y - 64, cx, GROUND_Y - 120], fill=(90, 90, 96), width=4)
        draw.polygon(
            [(cx - 60, GROUND_Y - 120), (cx + 60, GROUND_Y - 120), (cx, GROUND_Y - 150)],
            fill=accent,
        )
    elif tier == 3:
        # Coffee shop: single storefront with a sign.
        draw.rectangle([cx - 90, GROUND_Y - 120, cx + 90, GROUND_Y], fill=wall)
        draw.rectangle([cx - 90, GROUND_Y - 150, cx + 90, GROUND_Y - 120], fill=accent)
        _lit_windows(
            draw, rng, (cx - 90, GROUND_Y - 110, cx + 90, GROUND_Y - 20),
            cols=3, rows=1, glass=glass, lit=lit,
        )
    elif tier == 4:
        # Restaurant: wider two-floor building.
        draw.rectangle([cx - 110, GROUND_Y - 160, cx + 110, GROUND_Y], fill=wall)
        draw.rectangle([cx - 118, GROUND_Y - 178, cx + 118, GROUND_Y - 160], fill=accent)
        _lit_windows(
            draw, rng, (cx - 110, GROUND_Y - 150, cx + 110, GROUND_Y - 20),
            cols=4, rows=2, glass=glass, lit=lit,
        )
    elif tier == 5:
        # Chain restaurant: building plus a tall pylon sign.
        draw.rectangle([cx - 120, GROUND_Y - 150, cx + 80, GROUND_Y], fill=wall)
        _lit_windows(
            draw, rng, (cx - 120, GROUND_Y - 140, cx + 80, GROUND_Y - 20),
            cols=4, rows=2, glass=glass, lit=lit,
        )
        draw.rectangle([cx + 92, GROUND_Y - 210, cx + 104, GROUND_Y], fill=(90, 90, 96))
        draw.ellipse([cx + 74, GROUND_Y - 244, cx + 122, GROUND_Y - 196], fill=accent)
    elif tier == 6:
        # Factory: long hall with sawtooth roof and smokestacks.
        draw.rectangle([cx - 140, GROUND_Y - 120, cx + 140, GROUND_Y], fill=wall)
        for sx in range(cx - 140, cx + 140, 40):
            draw.polygon(
                [(sx, GROUND_Y - 120), (sx + 40, GROUND_Y - 120), (sx + 40, GROUND_Y - 150)],
                fill=wall_light,
            )
        for sx in (cx - 110, cx - 70):
            draw.rectangle([sx, GROUND_Y - 200, sx + 22, GROUND_Y - 120], fill=(70, 72, 80))
            draw.rectangle([sx, GROUND_Y - 210, sx + 22, GROUND_Y - 200], fill=accent)
        _lit_windows(
            draw, rng, (cx - 40, GROUND_Y - 110, cx + 140, GROUND_Y - 20),
            cols=4, rows=2, glass=glass, lit=lit,
        )
    else:
        # Corporation: skyscraper trio.
        for offset, h, w in ((-130, 230, 70), (-30, 280, 80), (80, 200, 60)):
            x0 = cx + offset
            draw.rectangle([x0, GROUND_Y - h, x0 + w, GROUND_Y], fill=wall)
            draw.rectangle([x0, GROUND_Y - h, x0 + w, GROUND_Y - h + 12], fill=accent)
            _lit_windows(
                draw, rng, (x0, GROUND_Y - h + 16, x0 + w, GROUND_Y - 16),
                cols=3, rows=max(3, h // 40), glass=glass, lit=lit,
            )


def render_business_image(user_id: int, guild_id: int, tier_id: str) -> bytes:
    """Render the business building PNG and return raw bytes."""
    defn = tier_def_by_id(tier_id)
    tier = defn.tier if defn else 1
    name = defn.name if defn else "Business"
    rng = _rng(user_id, guild_id, tier_id)
    accent = _accent(rng)

    canvas = Image.new("RGB", (WIDTH, HEIGHT), (24, 26, 32))
    draw = ImageDraw.Draw(canvas)

    sky_top = (28 + tier * 4, 32 + tier * 3, 60 + tier * 6)
    sky_bottom = (90, 96, 120)
    _sky_gradient(draw, sky_top, sky_bottom)

    # Distant skyline silhouette for depth.
    for _ in range(10):
        bx = rng.randint(-10, WIDTH)
        bw = rng.randint(24, 60)
        bh = rng.randint(30, 120)
        draw.rectangle([bx, GROUND_Y - bh, bx + bw, GROUND_Y], fill=(44, 48, 62))

    draw.rectangle([0, GROUND_Y, WIDTH, HEIGHT], fill=(38, 40, 46))

    _draw_building(draw, rng, tier, accent)

    title_font, small_font = _fonts()
    label = f"{defn.emoji + ' ' if defn else ''}{name}"
    draw.rectangle([0, HEIGHT - 34, WIDTH, HEIGHT], fill=(18, 20, 26))
    draw.text((14, HEIGHT - 28), label, font=title_font, fill=(255, 255, 255))
    tier_text = f"Tier {tier}"
    tw = draw.textlength(tier_text, font=small_font)
    draw.text((WIDTH - tw - 14, HEIGHT - 24), tier_text, font=small_font, fill=accent)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()
