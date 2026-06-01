"""Rich procedural raid portrait generator — unique bust art per player."""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ARCHETYPES: tuple[str, ...] = (
    "vanguard",
    "shadow",
    "arcanist",
    "medic",
    "gunslinger",
    "berserker",
    "ranger",
    "fortune_hunter",
)

HAIR_STYLES: tuple[str, ...] = (
    "short_crop",
    "long_flow",
    "mohawk",
    "braided",
    "bald",
    "wild_mane",
    "undercut",
    "topknot",
    "dreadlocks",
    "side_shave",
)

ACCESSORIES: tuple[str, ...] = (
    "none",
    "scar",
    "eyepatch",
    "goggles",
    "horn_band",
    "face_markings",
    "respirator",
)

BACKGROUNDS: tuple[str, ...] = (
    "ember_forge",
    "frost_citadel",
    "void_rift",
    "verdant_ruins",
    "storm_spire",
    "gold_vault",
    "midnight_raid",
    "celestial_gate",
)


@dataclass(frozen=True)
class PortraitSpec:
    archetype: str
    hair_style: str
    accessory: str
    background: str
    skin: tuple[int, int, int]
    hair: tuple[int, int, int]
    eyes: tuple[int, int, int]
    armor_primary: tuple[int, int, int]
    armor_secondary: tuple[int, int, int]
    accent: tuple[int, int, int]
    label: str
    seed: int


def _rng(user_id: int, guild_id: int, salt: str = "") -> random.Random:
    digest = hashlib.sha256(f"{user_id}:{guild_id}:{salt}".encode()).digest()
    seed = int.from_bytes(digest[:8], "big")
    return random.Random(seed)


def portrait_spec_for_user(user_id: int, guild_id: int) -> PortraitSpec:
    rng = _rng(user_id, guild_id, "portrait")
    digest = hashlib.sha256(f"{user_id}:{guild_id}:avatar".encode()).digest()
    label = f"R-{digest[0]:02X}{digest[1]:02X}"
    return PortraitSpec(
        archetype=rng.choice(ARCHETYPES),
        hair_style=rng.choice(HAIR_STYLES),
        accessory=rng.choice(ACCESSORIES),
        background=rng.choice(BACKGROUNDS),
        skin=(
            120 + digest[2] % 90,
            90 + digest[3] % 70,
            70 + digest[4] % 55,
        ),
        hair=(
            30 + digest[5] % 120,
            25 + digest[6] % 110,
            20 + digest[7] % 100,
        ),
        eyes=(
            40 + digest[8] % 180,
            60 + digest[9] % 180,
            80 + digest[10] % 175,
        ),
        armor_primary=(
            50 + digest[11] % 160,
            50 + digest[12] % 160,
            60 + digest[13] % 150,
        ),
        armor_secondary=tuple(max(10, c - 35) for c in (
            50 + digest[11] % 160,
            50 + digest[12] % 160,
            60 + digest[13] % 150,
        )),
        accent=(
            140 + digest[14] % 115,
            100 + digest[15] % 130,
            40 + digest[16] % 200,
        ),
        label=label,
        seed=int.from_bytes(digest[17:21], "big"),
    )


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _gradient_bg(size: tuple[int, int], spec: PortraitSpec) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    themes: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
        "ember_forge": ((38, 12, 8), (120, 40, 18)),
        "frost_citadel": ((8, 18, 38), (70, 130, 180)),
        "void_rift": ((12, 8, 28), (70, 20, 110)),
        "verdant_ruins": ((10, 28, 14), (40, 110, 60)),
        "storm_spire": ((16, 20, 36), (50, 80, 150)),
        "gold_vault": ((28, 22, 8), (180, 140, 40)),
        "midnight_raid": ((8, 10, 18), (35, 40, 70)),
        "celestial_gate": ((20, 16, 40), (120, 90, 200)),
    }
    top, bottom = themes.get(spec.background, ((12, 12, 20), (40, 40, 60)))
    rng = random.Random(spec.seed)
    for y in range(h):
        t = y / max(h - 1, 1)
        row = (_lerp(top[0], bottom[0], t), _lerp(top[1], bottom[1], t), _lerp(top[2], bottom[2], t))
        for x in range(w):
            px[x, y] = row
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(35):
        sx = rng.randint(0, w)
        sy = rng.randint(0, h // 2)
        radius = rng.randint(20, 90)
        alpha = rng.randint(8, 28)
        color = (*spec.accent, alpha)
        draw.ellipse((sx - radius, sy - radius, sx + radius, sy + radius), fill=color)
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    vignette = Image.new("RGBA", size, (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse((-w * 0.15, -h * 0.05, w * 1.15, h * 1.15), fill=(0, 0, 0, 90))
    return Image.alpha_composite(img, vignette)


def _draw_hair_back(draw: ImageDraw.ImageDraw, cx: int, head_y: int, spec: PortraitSpec) -> None:
    color = spec.hair
    style = spec.hair_style
    if style == "bald":
        return
    if style in ("long_flow", "wild_mane", "dreadlocks"):
        draw.ellipse((cx - 58, head_y - 10, cx + 58, head_y + 95), fill=color)
    if style == "mohawk":
        draw.polygon(
            [(cx - 8, head_y + 5), (cx, head_y - 28), (cx + 8, head_y + 5)],
            fill=color,
        )
    if style == "topknot":
        draw.ellipse((cx - 14, head_y - 32, cx + 14, head_y - 4), fill=color)


def _draw_hair_front(draw: ImageDraw.ImageDraw, cx: int, head_y: int, spec: PortraitSpec) -> None:
    color = spec.hair
    style = spec.hair_style
    if style == "bald":
        return
    if style in ("short_crop", "undercut", "side_shave"):
        draw.arc((cx - 34, head_y - 8, cx + 34, head_y + 40), 190, 350, fill=color, width=14)
    elif style == "braided":
        for offset in (-18, 0, 18):
            draw.line((cx + offset, head_y + 10, cx + offset - 6, head_y + 55), fill=color, width=8)
    elif style == "long_flow":
        draw.polygon(
            [(cx - 36, head_y + 8), (cx - 48, head_y + 70), (cx - 20, head_y + 45)],
            fill=color,
        )
        draw.polygon(
            [(cx + 36, head_y + 8), (cx + 48, head_y + 70), (cx + 20, head_y + 45)],
            fill=color,
        )
    elif style == "wild_mane":
        for angle in range(0, 360, 40):
            rad = math.radians(angle)
            x1 = cx + int(math.cos(rad) * 30)
            y1 = head_y + 15 + int(math.sin(rad) * 22)
            x2 = cx + int(math.cos(rad) * 48)
            y2 = head_y + 15 + int(math.sin(rad) * 38)
            draw.line((x1, y1, x2, y2), fill=color, width=6)


def _draw_face(draw: ImageDraw.ImageDraw, cx: int, head_y: int, spec: PortraitSpec) -> None:
    skin = spec.skin
    shadow = tuple(max(0, c - 30) for c in skin)
    draw.ellipse((cx - 34, head_y, cx + 34, head_y + 68), fill=skin, outline=shadow, width=2)
    draw.ellipse((cx - 28, head_y + 38, cx + 28, head_y + 72), fill=shadow)
    eye_y = head_y + 28
    for ex in (cx - 14, cx + 14):
        draw.ellipse((ex - 7, eye_y - 4, ex + 7, eye_y + 6), fill=(240, 240, 245))
        draw.ellipse((ex - 3, eye_y, ex + 3, eye_y + 5), fill=spec.eyes)
        draw.ellipse((ex - 1, eye_y + 1, ex + 1, eye_y + 3), fill=(20, 20, 25))
    draw.arc((cx - 10, head_y + 42, cx + 10, head_y + 52), 10, 170, fill=shadow, width=2)
    if spec.accessory == "scar":
        draw.line((cx - 20, head_y + 12, cx + 8, head_y + 38), fill=(120, 40, 40), width=3)
    elif spec.accessory == "eyepatch":
        draw.polygon(
            [(cx + 6, eye_y - 2), (cx + 24, eye_y - 8), (cx + 22, eye_y + 12), (cx + 4, eye_y + 8)],
            fill=(25, 25, 30),
        )
    elif spec.accessory == "goggles":
        draw.rounded_rectangle((cx - 30, eye_y - 8, cx + 30, eye_y + 12), radius=8, fill=(50, 50, 55, 180))
        draw.line((cx, eye_y - 8, cx, eye_y + 12), fill=(80, 80, 90), width=2)
    elif spec.accessory == "face_markings":
        for dx in (-12, 12):
            draw.line((cx + dx, head_y + 18, cx + dx + 4, head_y + 48), fill=spec.accent, width=2)
    elif spec.accessory == "respirator":
        draw.rounded_rectangle((cx - 18, head_y + 38, cx + 18, head_y + 58), radius=6, fill=(60, 70, 75))


def _draw_archetype_gear(
    draw: ImageDraw.ImageDraw,
    cx: int,
    head_y: int,
    body_y: int,
    spec: PortraitSpec,
    *,
    scale: float = 1.0,
) -> None:
    p, s, a = spec.armor_primary, spec.armor_secondary, spec.accent
    arch = spec.archetype

    def sh(x: float) -> int:
        return int(x * scale)

    if arch == "vanguard":
        draw.polygon(
            [(cx - sh(52), body_y + sh(10)), (cx + sh(52), body_y + sh(10)), (cx + sh(62), body_y + sh(95)), (cx - sh(62), body_y + sh(95))],
            fill=p,
            outline=s,
        )
        draw.polygon([(cx - sh(18), head_y + sh(55)), (cx + sh(18), head_y + sh(55)), (cx, head_y + sh(78))], fill=s)
        draw.rectangle((cx - sh(8), head_y - sh(8), cx + sh(8), head_y + sh(20)), fill=a)
    elif arch == "shadow":
        draw.polygon(
            [(cx - sh(58), head_y + sh(10)), (cx + sh(58), head_y + sh(10)), (cx + sh(70), body_y + sh(110)), (cx - sh(70), body_y + sh(110))],
            fill=(30, 32, 38),
            outline=s,
        )
        draw.polygon([(cx - sh(40), head_y + sh(5)), (cx + sh(40), head_y + sh(5)), (cx, head_y + sh(35))], fill=(20, 22, 28))
    elif arch == "arcanist":
        draw.polygon(
            [(cx - sh(46), body_y), (cx + sh(46), body_y), (cx + sh(58), body_y + sh(100)), (cx - sh(58), body_y + sh(100))],
            fill=(45, 30, 70),
            outline=a,
        )
        draw.ellipse((cx + sh(38), body_y + sh(20), cx + sh(58), body_y + sh(70)), fill=a, outline=(240, 220, 255))
        draw.line((cx + sh(48), body_y - sh(30), cx + sh(48), body_y + sh(25)), fill=(120, 90, 40), width=sh(4))
    elif arch == "medic":
        draw.rounded_rectangle((cx - sh(50), body_y, cx + sh(50), body_y + sh(95)), radius=sh(12), fill=(240, 240, 245), outline=p)
        cross = sh(16)
        draw.rectangle((cx - cross // 2, body_y + sh(25), cx + cross // 2, body_y + sh(55)), fill=(200, 40, 40))
        draw.rectangle((cx - cross // 2 - sh(8), body_y + sh(35), cx + cross // 2 + sh(8), body_y + sh(45)), fill=(200, 40, 40))
    elif arch == "gunslinger":
        draw.polygon([(cx - sh(48), body_y + sh(5)), (cx + sh(48), body_y + sh(5)), (cx + sh(55), body_y + sh(90)), (cx - sh(55), body_y + sh(90))], fill=p)
        draw.ellipse((cx - sh(50), head_y + sh(48), cx + sh(50), head_y + sh(62)), fill=(80, 50, 30))
        draw.rectangle((cx + sh(30), body_y + sh(40), cx + sh(75), body_y + sh(52)), fill=s)
    elif arch == "berserker":
        draw.polygon([(cx - sh(58), body_y), (cx + sh(58), body_y), (cx + sh(66), body_y + sh(98)), (cx - sh(66), body_y + sh(98))], fill=p)
        for ox in (-38, -10, 18, 42):
            draw.polygon(
                [(cx + sh(ox), body_y + sh(8)), (cx + sh(ox + 10), body_y - sh(5)), (cx + sh(ox + 20), body_y + sh(8))],
                fill=(120, 80, 50),
            )
    elif arch == "ranger":
        draw.polygon([(cx - sh(44), body_y + sh(8)), (cx + sh(44), body_y + sh(8)), (cx + sh(52), body_y + sh(92)), (cx - sh(52), body_y + sh(92))], fill=(50, 70, 45))
        draw.polygon([(cx - sh(62), body_y + sh(15)), (cx - sh(44), body_y + sh(5)), (cx - sh(48), body_y + sh(80))], fill=(35, 50, 30))
        draw.arc((cx - sh(70), body_y + sh(10), cx + sh(20), body_y + sh(120)), 290, 70, fill=(90, 60, 30), width=sh(5))
    elif arch == "fortune_hunter":
        draw.polygon([(cx - sh(46), body_y), (cx + sh(46), body_y), (cx + sh(54), body_y + sh(88)), (cx - sh(54), body_y + sh(88))], fill=p)
        draw.polygon([(cx - sh(36), head_y + sh(8)), (cx + sh(36), head_y + sh(8)), (cx + sh(44), head_y + sh(28)), (cx - sh(44), head_y + sh(28))], fill=(50, 40, 25))
        draw.ellipse((cx - sh(6), head_y + sh(14), cx + sh(6), head_y + sh(20)), fill=a)
    if spec.accessory == "horn_band":
        draw.polygon([(cx - sh(28), head_y + sh(5)), (cx - sh(38), head_y - sh(18)), (cx - sh(22), head_y + sh(8))], fill=s)
        draw.polygon([(cx + sh(28), head_y + sh(5)), (cx + sh(38), head_y - sh(18)), (cx + sh(22), head_y + sh(8))], fill=s)


def _render_bust(spec: PortraitSpec, size: tuple[int, int]) -> Image.Image:
    w, h = size
    base = _gradient_bg(size, spec)
    draw = ImageDraw.Draw(base)
    cx = w // 2
    scale = w / 512.0
    head_y = int(70 * scale)
    body_y = int(150 * scale)

    _draw_hair_back(draw, cx, head_y, spec)
    _draw_archetype_gear(draw, cx, head_y, body_y, spec, scale=scale)
    _draw_face(draw, cx, head_y, spec)
    _draw_hair_front(draw, cx, head_y, spec)

    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse(
        (cx - int(80 * scale), head_y + int(40 * scale), cx + int(80 * scale), body_y + int(100 * scale)),
        fill=(*spec.accent, 35),
    )
    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(radius=max(2, int(6 * scale)))))
    return base.convert("RGBA")


def render_portrait(spec: PortraitSpec, *, size: int = 512) -> Image.Image:
    return _render_bust(spec, (size, size))


def render_victory_banner(spec: PortraitSpec, *, width: int = 640, height: int = 360) -> Image.Image:
    img = _render_bust(spec, (width, height))
    draw = ImageDraw.Draw(img)
    font = _font(max(22, width // 22))
    small = _font(max(12, width // 40))
    draw.rounded_rectangle((width * 0.08, height * 0.72, width * 0.92, height * 0.92), radius=12, fill=(0, 0, 0, 140))
    draw.text((width // 2, height * 0.79), "VICTORY!", fill=(255, 220, 100), font=font, anchor="mm")
    draw.text((width // 2, height * 0.87), spec.label, fill=spec.accent, font=small, anchor="mm")
    arch_label = spec.archetype.replace("_", " ").title()
    draw.text((width * 0.12, height * 0.12), arch_label, fill=(255, 255, 255, 200), font=small, anchor="lm")
    return img


def render_victory_gif(spec: PortraitSpec, dest: Path, *, width: int = 640, height: int = 360) -> None:
    frames: list[Image.Image] = []
    for pulse in (0, 1, 0, -1):
        frame = render_victory_banner(spec, width=width, height=height)
        if pulse != 0:
            overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            alpha = 30 + abs(pulse) * 20
            odraw.ellipse(
                (width * 0.25, height * 0.15, width * 0.75, height * 0.75),
                fill=(*spec.accent, alpha),
            )
            frame = Image.alpha_composite(frame, overlay.filter(ImageFilter.GaussianBlur(radius=8)))
        frames.append(frame.convert("P", palette=Image.ADAPTIVE))
    frames[0].save(
        dest,
        save_all=True,
        append_images=frames[1:],
        duration=200,
        loop=0,
        disposal=2,
    )


def write_portrait_assets(spec: PortraitSpec, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    render_portrait(spec, size=512).save(folder / "portrait.png")
    render_victory_banner(spec).save(folder / "victory.png")
    render_victory_gif(spec, folder / "victory.gif")
