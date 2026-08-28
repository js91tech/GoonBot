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
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.businesses import tier_def_by_id

WIDTH = 480
HEIGHT = 320
GROUND_Y = 264

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "businesses"


def _static_asset(tier_id: str) -> Path | None:
    from utils.businesses import normalize_tier_id

    canonical = normalize_tier_id(tier_id)
    for candidate in (canonical, tier_id.strip().lower()):
        path = ASSET_DIR / f"{candidate}.png"
        if path.is_file():
            return path
    return None


def _cover_resize(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize and center-crop an image to exactly fill width×height."""
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_h = height
        new_w = int(round(height * src_ratio))
    else:
        new_w = width
        new_h = int(round(width / src_ratio))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


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
        # Tip-jar cam: desk, ring light, and a phone tripod.
        draw.rectangle([cx - 80, GROUND_Y - 48, cx + 80, GROUND_Y - 8], fill=(42, 34, 48))
        draw.rectangle([cx - 18, GROUND_Y - 36, cx + 18, GROUND_Y - 16], fill=(90, 70, 50))
        draw.ellipse([cx - 36, GROUND_Y - 118, cx + 36, GROUND_Y - 46], outline=accent, width=8)
        draw.rectangle([cx - 4, GROUND_Y - 70, cx + 4, GROUND_Y - 20], fill=(70, 70, 78))
        draw.rectangle([cx + 40, GROUND_Y - 40, cx + 62, GROUND_Y - 16], fill=(200, 180, 90))
    elif tier == 2:
        # Afterparty cart: bottle cart on wheels.
        draw.rectangle([cx - 64, GROUND_Y - 70, cx + 64, GROUND_Y - 18], fill=wall_light)
        draw.rectangle([cx - 64, GROUND_Y - 70, cx + 64, GROUND_Y - 52], fill=accent)
        for bx in (cx - 40, cx - 10, cx + 20):
            draw.rectangle([bx, GROUND_Y - 96, bx + 14, GROUND_Y - 70], fill=accent)
        draw.ellipse([cx - 56, GROUND_Y - 26, cx - 30, GROUND_Y], fill=(30, 30, 34))
        draw.ellipse([cx + 30, GROUND_Y - 26, cx + 56, GROUND_Y], fill=(30, 30, 34))
    elif tier == 3:
        # Late-night lounge: neon storefront.
        draw.rectangle([cx - 90, GROUND_Y - 120, cx + 90, GROUND_Y], fill=wall)
        draw.rectangle([cx - 90, GROUND_Y - 150, cx + 90, GROUND_Y - 120], fill=accent)
        _lit_windows(
            draw, rng, (cx - 90, GROUND_Y - 110, cx + 90, GROUND_Y - 20),
            cols=3, rows=1, glass=glass, lit=lit,
        )
    elif tier == 4:
        # VIP booth club: two-floor velvet club.
        draw.rectangle([cx - 110, GROUND_Y - 160, cx + 110, GROUND_Y], fill=wall)
        draw.rectangle([cx - 118, GROUND_Y - 178, cx + 118, GROUND_Y - 160], fill=accent)
        _lit_windows(
            draw, rng, (cx - 110, GROUND_Y - 150, cx + 110, GROUND_Y - 20),
            cols=4, rows=2, glass=glass, lit=lit,
        )
    elif tier == 5:
        # Franchise clubs: matching storefront plus a neon pylon.
        draw.rectangle([cx - 120, GROUND_Y - 150, cx + 80, GROUND_Y], fill=wall)
        _lit_windows(
            draw, rng, (cx - 120, GROUND_Y - 140, cx + 80, GROUND_Y - 20),
            cols=4, rows=2, glass=glass, lit=lit,
        )
        draw.rectangle([cx + 92, GROUND_Y - 210, cx + 104, GROUND_Y], fill=(90, 90, 96))
        draw.ellipse([cx + 74, GROUND_Y - 244, cx + 122, GROUND_Y - 196], fill=accent)
    elif tier == 6:
        # Content studio: soundstage box with cinema lights.
        draw.rectangle([cx - 140, GROUND_Y - 140, cx + 140, GROUND_Y], fill=wall)
        draw.rectangle([cx - 140, GROUND_Y - 158, cx + 140, GROUND_Y - 140], fill=wall_light)
        for sx in (cx - 90, cx, cx + 70):
            draw.polygon(
                [(sx, GROUND_Y - 200), (sx + 22, GROUND_Y - 158), (sx - 22, GROUND_Y - 158)],
                fill=accent,
            )
        _lit_windows(
            draw, rng, (cx - 80, GROUND_Y - 120, cx + 130, GROUND_Y - 20),
            cols=4, rows=2, glass=glass, lit=lit,
        )
    else:
        # Adult empire HQ: neon-crowned skyscraper trio.
        for offset, h, w in ((-130, 230, 70), (-30, 280, 80), (80, 200, 60)):
            x0 = cx + offset
            draw.rectangle([x0, GROUND_Y - h, x0 + w, GROUND_Y], fill=wall)
            draw.rectangle([x0, GROUND_Y - h, x0 + w, GROUND_Y - h + 12], fill=accent)
            _lit_windows(
                draw, rng, (x0, GROUND_Y - h + 16, x0 + w, GROUND_Y - 16),
                cols=3, rows=max(3, h // 40), glass=glass, lit=lit,
            )


def _render_with_static_base(
    base_path: Path, *, name: str, tier: int, accent: tuple[int, int, int], emoji: str,
) -> bytes:
    """Composite a label bar + per-player accent border over generated art."""
    canvas = _cover_resize(Image.open(base_path).convert("RGB"), WIDTH, HEIGHT)
    draw = ImageDraw.Draw(canvas)
    # Per-player accent top border keeps each empire's card distinct.
    draw.rectangle([0, 0, WIDTH, 6], fill=accent)
    title_font, small_font = _fonts()
    draw.rectangle([0, HEIGHT - 34, WIDTH, HEIGHT], fill=(14, 16, 22))
    label = f"{emoji + ' ' if emoji else ''}{name}"
    draw.text((14, HEIGHT - 28), label, font=title_font, fill=(255, 255, 255))
    tier_text = f"Tier {tier}"
    tw = draw.textlength(tier_text, font=small_font)
    draw.text((WIDTH - tw - 14, HEIGHT - 24), tier_text, font=small_font, fill=accent)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def render_business_image(user_id: int, guild_id: int, tier_id: str) -> bytes:
    """Render the business building PNG and return raw bytes.

    Uses a generated base asset when available (with a per-player accent strip),
    otherwise falls back to fully procedural art.
    """
    defn = tier_def_by_id(tier_id)
    tier = defn.tier if defn else 1
    name = defn.name if defn else "Business"
    rng = _rng(user_id, guild_id, tier_id)
    accent = _accent(rng)

    base = _static_asset(tier_id)
    if base is not None:
        try:
            return _render_with_static_base(
                base, name=name, tier=tier, accent=accent,
                emoji=defn.emoji if defn else "",
            )
        except OSError:
            pass

    canvas = Image.new("RGB", (WIDTH, HEIGHT), (24, 26, 32))
    draw = ImageDraw.Draw(canvas)

    sky_top = (18, 12, 36)
    sky_bottom = (70, 28, 68)
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
