"""Procedural unique default avatar art per player."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "defaults"
UNIQUE_DEFAULT_PREFIX = "raider_"


@dataclass(frozen=True)
class AvatarTraits:
    accent: tuple[int, int, int]
    shadow: tuple[int, int, int]
    label: str
    visor: bool
    cape: bool
    hair_offset: int


def unique_default_avatar_id(user_id: int, guild_id: int) -> str:
    digest = hashlib.sha256(f"{user_id}:{guild_id}".encode()).hexdigest()[:10]
    return f"{UNIQUE_DEFAULT_PREFIX}{digest}"


def unique_default_avatar_dir(guild_id: int, user_id: int) -> Path:
    return DEFAULT_ASSETS_ROOT / str(guild_id) / str(user_id)


def default_assets_ready(guild_id: int, user_id: int) -> bool:
    folder = unique_default_avatar_dir(guild_id, user_id)
    if not (folder / "portrait.png").is_file():
        return False
    return (folder / "victory.gif").is_file() or (folder / "victory.png").is_file()


def traits_for_user(user_id: int, guild_id: int) -> AvatarTraits:
    digest = hashlib.sha256(f"{user_id}:{guild_id}:avatar".encode()).digest()
    accent = (
        70 + (digest[0] * 5) % 185,
        70 + (digest[1] * 5) % 185,
        70 + (digest[2] * 5) % 185,
    )
    shadow = tuple(max(8, channel - 45) for channel in accent)
    label = f"R-{digest[3]:02X}{digest[4]:02X}"
    return AvatarTraits(
        accent=accent,
        shadow=shadow,
        label=label,
        visor=digest[5] % 2 == 0,
        cape=digest[6] % 3 != 0,
        hair_offset=(digest[7] % 7) - 3,
    )


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
    traits: AvatarTraits,
) -> None:
    cx = w // 2
    accent, shadow = traits.accent, traits.shadow
    head_top = 20 + traits.hair_offset
    draw.ellipse((cx - 28, head_top, cx + 28, head_top + 56), fill=accent, outline=shadow, width=2)
    if traits.visor:
        draw.rounded_rectangle(
            (cx - 22, head_top + 18, cx + 22, head_top + 34),
            radius=6,
            fill=(40, 200, 220, 200),
            outline=shadow,
            width=1,
        )
    body_top = head_top + 52
    draw.rounded_rectangle(
        (cx - 40, body_top, cx + 40, body_top + 78),
        radius=12,
        fill=accent,
        outline=shadow,
        width=2,
    )
    draw.rounded_rectangle((cx - 55, body_top + 13, cx - 38, body_top + 58), radius=8, fill=shadow)
    draw.rounded_rectangle((cx + 38, body_top + 13, cx + 55, body_top + 58), radius=8, fill=shadow)
    if traits.cape:
        draw.polygon(
            [
                (cx - 48, body_top + 8),
                (cx + 48, body_top + 8),
                (cx + 62, body_top + 88),
                (cx - 62, body_top + 88),
            ],
            fill=(shadow[0], shadow[1], shadow[2], 180),
        )


def make_portrait(traits: AvatarTraits) -> Image.Image:
    img = Image.new("RGBA", (128, 128), (24, 24, 32, 255))
    draw = ImageDraw.Draw(img)
    _draw_character(draw, 128, 128, traits)
    return img


def make_victory_png(traits: AvatarTraits) -> Image.Image:
    img = Image.new("RGBA", (400, 220), (18, 18, 28, 255))
    draw = ImageDraw.Draw(img)
    _draw_character(draw, 400, 220, traits)
    font = _font(28)
    draw.text((200, 168), "VICTORY!", fill=(255, 220, 100), font=font, anchor="mm")
    small = _font(16)
    draw.text((200, 198), traits.label, fill=traits.accent, font=small, anchor="mm")
    return img


def make_victory_gif(traits: AvatarTraits, dest: Path) -> None:
    frames = []
    for offset in (0, 6, 0, -4):
        img = Image.new("RGBA", (400, 220), (18, 18, 28, 255))
        draw = ImageDraw.Draw(img)
        _draw_character(draw, 400, 220, traits)
        draw.rounded_rectangle(
            (120, 160 + offset, 280, 210 + offset),
            radius=8,
            fill=(255, 220, 100, 180),
        )
        font = _font(28)
        draw.text((200, 168 + offset), "VICTORY!", fill=(255, 220, 100), font=font, anchor="mm")
        small = _font(16)
        draw.text((200, 198 + offset), traits.label, fill=traits.accent, font=small, anchor="mm")
        frames.append(img.convert("P", palette=Image.ADAPTIVE))
    frames[0].save(
        dest,
        save_all=True,
        append_images=frames[1:],
        duration=180,
        loop=0,
        disposal=2,
    )


def ensure_default_avatar_assets(user_id: int, guild_id: int) -> Path:
    folder = unique_default_avatar_dir(guild_id, user_id)
    if default_assets_ready(guild_id, user_id):
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    traits = traits_for_user(user_id, guild_id)
    make_portrait(traits).save(folder / "portrait.png")
    make_victory_png(traits).save(folder / "victory.png")
    make_victory_gif(traits, folder / "victory.gif")
    return folder
