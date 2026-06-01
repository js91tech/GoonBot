"""Optional AI-generated unique default avatars (OpenAI-compatible images API)."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from PIL import Image

import config
from utils.avatar_portrait import portrait_spec_for_user

logger = logging.getLogger(__name__)


def _image_api_url() -> str:
    parsed = urlparse(config.AI_API_URL)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return config.AVATAR_IMAGE_API_URL or f"{base}/v1/images/generations"


def _build_prompt(user_id: int, guild_id: int) -> str:
    spec = portrait_spec_for_user(user_id, guild_id)
    arch = spec.archetype.replace("_", " ")
    hair = spec.hair_style.replace("_", " ")
    accessory = spec.accessory.replace("_", " ")
    bg = spec.background.replace("_", " ")
    parts = [
        "Fantasy RPG raid hero portrait bust, shoulders up, painterly game art",
        f"class: {arch}",
        f"hair: {hair}",
        f"accessory: {accessory}" if spec.accessory != "none" else "",
        f"background mood: {bg}",
        "dramatic rim lighting, detailed armor and face, heroic expression",
        "no text, no watermark, no logo, single character centered",
    ]
    return ", ".join(p for p in parts if p)


async def try_generate_ai_avatar(user_id: int, guild_id: int, folder: Path) -> bool:
    """Return True if AI portrait + victory assets were written to folder."""
    if not config.AI_API_KEY or not config.AVATAR_AI_GENERATION:
        return False

    prompt = _build_prompt(user_id, guild_id)
    payload = {
        "model": config.AVATAR_IMAGE_MODEL,
        "prompt": prompt,
        "size": config.AVATAR_IMAGE_SIZE,
        "n": 1,
    }
    headers = {"Authorization": f"Bearer {config.AI_API_KEY}"}
    timeout = aiohttp.ClientTimeout(total=config.AVATAR_AI_TIMEOUT_SECONDS)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(_image_api_url(), json=payload, headers=headers) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning(
                        "Avatar AI generation failed (%s): %s",
                        response.status,
                        body[:300],
                    )
                    return False
                data = await response.json()
            url = data["data"][0]["url"]
            async with session.get(url) as img_response:
                if img_response.status != 200:
                    return False
                raw = await img_response.read()
    except (aiohttp.ClientError, TimeoutError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Avatar AI generation error: %s", exc)
        return False

    try:
        source = Image.open(io.BytesIO(raw)).convert("RGBA")
    except OSError:
        logger.warning("Avatar AI returned invalid image bytes")
        return False

    folder.mkdir(parents=True, exist_ok=True)
    portrait = _crop_square(source, 512)
    portrait.save(folder / "portrait.png")

    victory = _compose_victory(source, user_id, guild_id)
    victory.save(folder / "victory.png")
    _save_victory_gif(victory, folder / "victory.gif")
    return True


def _crop_square(img: Image.Image, size: int) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 3
    top = max(0, min(top, h - side))
    cropped = img.crop((left, top, left + side, top + side))
    return cropped.resize((size, size), Image.Resampling.LANCZOS)


def _compose_victory(source: Image.Image, user_id: int, guild_id: int) -> Image.Image:
    from PIL import ImageDraw

    from utils.avatar_portrait import _font

    spec = portrait_spec_for_user(user_id, guild_id)
    target_w, target_h = 640, 360
    scaled = source.copy()
    scaled.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (target_w, target_h), (12, 14, 22, 255))
    ox = (target_w - scaled.width) // 2
    oy = (target_h - scaled.height) // 2
    canvas.paste(scaled, (ox, oy), scaled if scaled.mode == "RGBA" else None)
    draw = ImageDraw.Draw(canvas)
    font = _font(28)
    small = _font(14)
    draw.rounded_rectangle((48, 258, 592, 330), radius=12, fill=(0, 0, 0, 140))
    draw.text((target_w // 2, 278), "VICTORY!", fill=(255, 220, 100), font=font, anchor="mm")
    draw.text((target_w // 2, 308), spec.label, fill=spec.accent, font=small, anchor="mm")
    return canvas


def _save_victory_gif(victory: Image.Image, dest: Path) -> None:
    frames = []
    for brightness in (1.0, 1.06, 1.0, 0.96):
        frame = victory.copy()
        if brightness != 1.0:
            from PIL import ImageEnhance

            frame = ImageEnhance.Brightness(frame).enhance(brightness)
        frames.append(frame.convert("P", palette=Image.ADAPTIVE))
    frames[0].save(
        dest,
        save_all=True,
        append_images=frames[1:],
        duration=200,
        loop=0,
        disposal=2,
    )
