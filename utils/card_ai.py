"""Optional AI-generated GoonCards portraits (OpenAI-compatible images API)."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from PIL import Image

import config
from utils.cards import CARD_DEFINITIONS, CardDefinition

logger = logging.getLogger(__name__)

CARDS_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "cards"
PORTRAIT_SIZE = 512


def portrait_path(card_id: str) -> Path:
    return CARDS_ASSETS_ROOT / f"{card_id}.png"


def _image_api_url() -> str:
    parsed = urlparse(config.AI_API_URL)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return config.AVATAR_IMAGE_API_URL or f"{base}/v1/images/generations"


def _crop_square(img: Image.Image, size: int) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 3
    top = max(0, min(top, h - side))
    cropped = img.crop((left, top, left + side, top + side))
    return cropped.resize((size, size), Image.Resampling.LANCZOS)


async def try_generate_ai_portrait(card: CardDefinition, dest: Path | None = None) -> bool:
    """Return True if an AI portrait was written for this card."""
    if not config.AI_API_KEY:
        return False
    target = dest or portrait_path(card.card_id)
    payload = {
        "model": config.AVATAR_IMAGE_MODEL,
        "prompt": card.portrait_prompt,
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
                        "Card AI generation failed for %s (%s): %s",
                        card.card_id,
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
    except (aiohttp.ClientError, TimeoutError, KeyError, TypeError, ValueError, IndexError) as exc:
        logger.warning("Card AI generation error for %s: %s", card.card_id, exc)
        return False

    try:
        source = Image.open(io.BytesIO(raw)).convert("RGBA")
    except OSError:
        logger.warning("Card AI returned invalid image bytes for %s", card.card_id)
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    _crop_square(source, PORTRAIT_SIZE).save(target)
    return True


async def maybe_backfill_missing_portrait(card_id: str) -> bool:
    """Write a missing portrait with the unique local compositor (AI is opt-in via the generator)."""
    card = CARD_DEFINITIONS.get(card_id)
    if card is None:
        return False
    path = portrait_path(card_id)
    if path.is_file():
        return True
    from utils.card_canvas import write_procedural_portrait

    write_procedural_portrait(card, path)
    return path.is_file()
