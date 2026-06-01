from __future__ import annotations

from pathlib import Path

import discord

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "bosses"

# Hannah tiers share art keyed by variant; TomAss and ZZ's Wrath have dedicated portraits.
VARIANT_ART_FILES: dict[str, str] = {
    "normal": "hannah_normal.png",
    "enraged": "hannah_enraged.png",
    "shadow": "hannah_shadow.png",
    "celestial": "hannah_celestial.png",
    "mythic": "hannah_mythic.png",
    "tomass": "tomass.png",
    "zz_wrath": "zz_wrath.png",
}


def boss_art_path(variant: str) -> Path | None:
    filename = VARIANT_ART_FILES.get(variant)
    if filename is None:
        return None
    path = ASSETS_ROOT / filename
    return path if path.is_file() else None


def attach_boss_art(embed: discord.Embed, variant: str) -> discord.File | None:
    path = boss_art_path(variant)
    if path is None:
        return None
    filename = path.name
    embed.set_image(url=f"attachment://{filename}")
    return discord.File(str(path), filename=filename)
