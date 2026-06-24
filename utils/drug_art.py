"""Procedural art for drug strains and the lab panel."""
from __future__ import annotations

import hashlib
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.drugs import DRUGS, drug_by_id

WIDTH = 480
HEIGHT = 280

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "drugs"


def _static_asset(name: str) -> Path | None:
    path = ASSET_DIR / f"{name}.png"
    return path if path.is_file() else None


def _cover_resize(img: Image.Image, width: int, height: int) -> Image.Image:
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
    "blue_dream": (86, 176, 96),
    "og_kush": (72, 140, 68),
    "girl_scout_cookies": (168, 120, 72),
    "purple_haze": (148, 88, 196),
    "sour_diesel": (196, 196, 72),
    "gorilla_glue": (96, 120, 88),
    "white_widow": (210, 210, 220),
    "cocaine": (224, 224, 232),
    "crystal_meth": (96, 156, 224),
    "mdma": (224, 96, 160),
    "addies": (255, 196, 72),
    "adderall_xr": (255, 168, 88),
    "vyvanse": (255, 220, 96),
    "tylenol_3": (196, 208, 224),
    "codeine_pills": (176, 196, 216),
    "robitussin_ac": (196, 148, 96),
    "prometh_codeine": (168, 128, 196),
    "hi_tech": (148, 88, 196),
    "wockhardt": (128, 72, 168),
    "tris": (136, 96, 176),
    "par": (120, 84, 160),
    "quagen": (156, 100, 188),
    "actavis": (104, 56, 140),
    "heroin": (224, 176, 70),
    "fentanyl": (196, 72, 72),
    "lsd": (96, 220, 196),
    "shrooms": (168, 104, 56),
    # Legacy ids still in old stashes.
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


def _label_bar(canvas: Image.Image, name: str, defn: object, color: tuple[int, int, int]) -> bytes:
    draw = ImageDraw.Draw(canvas)
    title_font, small_font = _fonts()
    draw.rectangle([0, HEIGHT - 34, WIDTH, HEIGHT], fill=(14, 16, 22))
    label = f"{getattr(defn, 'emoji', '') + ' ' if defn else ''}{name}"
    draw.text((14, HEIGHT - 27), label, font=title_font, fill=(255, 255, 255))
    if defn is not None:
        price_text = f"~{int(defn.street_price)}/unit"
        tw = draw.textlength(price_text, font=small_font)
        draw.text((WIDTH - tw - 14, HEIGHT - 24), price_text, font=small_font, fill=color)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def render_drug_image(drug_id: str) -> bytes:
    defn = drug_by_id(drug_id)
    name = defn.name if defn else "Product"
    color = _STRAIN_COLORS.get(drug_id, _STRAIN_COLORS.get(defn.drug_id if defn else "", (160, 160, 170)))
    rng = _rng(drug_id)

    base = _static_asset(drug_id)
    if base is not None:
        try:
            canvas = _cover_resize(Image.open(base).convert("RGB"), WIDTH, HEIGHT)
            return _label_bar(canvas, name, defn, color)
        except OSError:
            pass

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
    """A lab/grow-room banner image (generated asset if present, else procedural)."""
    base = _static_asset("grow_lab")
    if base is not None:
        try:
            canvas = _cover_resize(Image.open(base).convert("RGB"), WIDTH, HEIGHT)
            draw = ImageDraw.Draw(canvas)
            title_font, _ = _fonts()
            draw.rectangle([0, HEIGHT - 32, WIDTH, HEIGHT], fill=(12, 14, 18))
            draw.text((14, HEIGHT - 26), "🧪 Grow Lab", font=title_font, fill=(220, 240, 220))
            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG")
            return buffer.getvalue()
        except OSError:
            pass

    canvas = Image.new("RGB", (WIDTH, HEIGHT), (18, 22, 26))
    draw = ImageDraw.Draw(canvas)
    rng = random.Random(42)
    for y in range(HEIGHT):
        t = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=(int(18 + t * 10), int(30 + t * 20), int(26 + t * 14)))
    # Show a sample of catalog strains under the grow lamps.
    showcase = DRUGS[:4]
    for i, defn in enumerate(showcase):
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
