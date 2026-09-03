"""Unique GoonCards plates — seeded painterly compositor, not asset crops.

House palettes and mood are sampled statistically from existing GoonBot art
(velvet crimson/gold, neon lounge, grow-lab violet, pixel-city dusk). Faces,
logos, banner copy, and raid portraits are never pasted. Every catalog id has
its own recipe: silhouette, lighting, props, and composition kind.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from utils.cards import CARD_DEFINITIONS, CardDefinition

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
PORTRAIT_SIZE = 512

Kind = Literal["bust", "creature", "still", "pixel"]
Body = Literal["femme", "masc", "andro", "none"]

RGB = tuple[int, int, int]


def _clamp_rgb(color: RGB) -> RGB:
    return (int(max(0, min(255, color[0]))), int(max(0, min(255, color[1]))), int(max(0, min(255, color[2]))))


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return _clamp_rgb((int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t)))


def _shade(color: RGB, t: float) -> RGB:
    return _mix(color, (0, 0, 0), t)


def _tint(color: RGB, t: float) -> RGB:
    return _mix(color, (255, 255, 255), t)


def _hash_seed(card_id: str) -> int:
    return int.from_bytes(hashlib.sha256(f"gooncards:{card_id}".encode()).digest()[:8], "big")


def _rng(card_id: str) -> np.random.Generator:
    return np.random.default_rng(_hash_seed(card_id))


_MOOD_CACHE: dict[str, tuple[RGB, ...]] = {}


def _mood_colors(relpath: str) -> tuple[RGB, ...]:
    """Statistical palette only — tiny box-filter means, never pasted pixels."""
    if relpath in _MOOD_CACHE:
        return _MOOD_CACHE[relpath]
    path = ASSETS / relpath
    if not path.is_file():
        _MOOD_CACHE[relpath] = ()
        return ()
    with Image.open(path) as image:
        n_frames = getattr(image, "n_frames", 1)
        if n_frames > 1:
            image.seek(0)
        small = image.convert("RGB").resize((8, 8), Image.Resampling.BOX)
    arr = np.asarray(small, dtype=np.float32)
    colors: list[RGB] = []
    for y in range(0, 8, 2):
        for x in range(0, 8, 2):
            patch = arr[y : y + 2, x : x + 2].mean(axis=(0, 1))
            if float(patch.mean()) < 22:
                continue
            colors.append((int(patch[0]), int(patch[1]), int(patch[2])))
    _MOOD_CACHE[relpath] = tuple(colors[:6])
    return _MOOD_CACHE[relpath]


@dataclass(frozen=True)
class CardRecipe:
    kind: Kind
    body: Body
    hair: str
    hair_rgb: RGB
    skin: RGB
    lip: RGB
    eye: RGB
    clothing: str
    cloth_rgb: RGB
    accent: RGB
    bg: str
    bg_top: RGB
    bg_bot: RGB
    glow: RGB
    pose: str
    extras: tuple[str, ...]
    props: tuple[str, ...]
    mood_asset: str
    scene: str = ""


# One recipe per catalog id. Silhouettes, palettes, and props are unique —
# not a single bust template with recolors.
CARD_RECIPES: dict[str, CardRecipe] = {
    # --- Velvet Court ---
    "card_hostess": CardRecipe(
        "bust", "femme", "cascade", (118, 22, 38), (212, 168, 142), (168, 28, 48), (48, 28, 24),
        "velvet_scoop", (128, 18, 36), (212, 168, 72), "curtains", (28, 8, 12), (72, 18, 28),
        (220, 140, 70), "front_smile", ("gold_drops", "choker"), ("necklace",),
        "bosses/glam/velvet_vixen_normal.png",
    ),
    "card_stagehand": CardRecipe(
        "bust", "andro", "pixie", (28, 24, 28), (186, 148, 122), (96, 60, 58), (40, 80, 70),
        "black_crew", (22, 20, 24), (176, 42, 48), "backstage", (12, 10, 16), (48, 22, 28),
        (255, 210, 140), "three_left", ("headset", "lanyard"), ("gel_lights",),
        "bosses/armored/velvet_vixen_normal.png",
    ),
    "card_tomass": CardRecipe(
        "bust", "masc", "slick", (28, 22, 20), (168, 118, 88), (92, 48, 42), (28, 92, 48),
        "leather_v", (18, 16, 18), (46, 196, 92), "lounge_neon", (18, 6, 12), (86, 18, 42),
        (60, 220, 110), "front_smirk", ("stubble", "hoop", "chain"), ("green_aura",),
        "bosses/tomass.png",
    ),
    "card_shadow_velvet": CardRecipe(
        "bust", "femme", "void_fall", (12, 10, 16), (196, 188, 198), (72, 64, 88), (180, 190, 210),
        "black_high", (16, 14, 22), (168, 176, 196), "void", (4, 4, 12), (28, 24, 48),
        (140, 160, 200), "three_right", ("silver_drops", "cold_rim"), (),
        "bosses/glam/velvet_vixen_shadow.png",
    ),
    "card_freaky_nikki": CardRecipe(
        "bust", "femme", "pink_bob", (232, 96, 148), (224, 176, 158), (220, 70, 120), (80, 36, 70),
        "satin_lace", (196, 48, 110), (255, 140, 190), "neon_pink", (40, 8, 36), (120, 24, 78),
        (255, 120, 180), "wink_left", ("bow", "wink"), ("neon_tubes",),
        "bosses/freaky_nikki/spawn.gif",
    ),
    "card_zz_wrath": CardRecipe(
        "bust", "femme", "platinum", (230, 214, 186), (236, 220, 210), (28, 18, 22), (220, 160, 48),
        "wrath_collar", (12, 10, 12), (212, 168, 64), "storm_gold", (8, 6, 4), (48, 32, 12),
        (255, 200, 80), "pierce", ("skull_jewel", "gold_filigree"), ("gold_wisps",),
        "bosses/zz_wrath.png",
    ),
    "card_leviathan": CardRecipe(
        "bust", "femme", "teal_kelp", (16, 48, 52), (176, 196, 186), (96, 28, 40), (32, 180, 160),
        "scale_cape", (18, 42, 48), (196, 148, 52), "abyss", (4, 16, 24), (12, 48, 56),
        (48, 220, 190), "tower", ("scale_crown", "fin_ear"), ("depth_rays",),
        "bosses/glam/velvet_vixen_celestial.png",
    ),
    "card_velvet_vixen": CardRecipe(
        "bust", "femme", "crimson_crown", (92, 12, 24), (220, 176, 148), (150, 22, 40), (40, 22, 18),
        "throne_gown", (110, 10, 28), (214, 170, 64), "throne", (16, 4, 8), (64, 12, 20),
        (255, 196, 90), "command", ("tall_crown", "ruby_collar"), ("god_rays",),
        "bosses/glam/velvet_vixen_mythic.png",
    ),
    # --- Floor Staff ---
    "card_floor_runner": CardRecipe(
        "bust", "femme", "pony", (48, 28, 22), (208, 164, 132), (176, 70, 70), (50, 32, 24),
        "waiter_vest", (28, 22, 26), (212, 176, 80), "busy_floor", (32, 14, 16), (90, 36, 32),
        (255, 214, 120), "three_left", ("vest_buttons",), ("champagne_tray",),
        "bosses/glam/velvet_vixen_enraged.png",
    ),
    "card_velvet_imp": CardRecipe(
        "creature", "none", "imp", (168, 28, 36), (176, 48, 42), (120, 16, 24), (255, 200, 80),
        "motley", (128, 16, 28), (212, 168, 56), "jester_dark", (20, 6, 10), (70, 16, 24),
        (255, 160, 40), "impish", ("horns", "jester_ruff"), ("spark",),
        "bosses/glam/velvet_vixen_normal.png",
    ),
    "card_bottle_bird": CardRecipe(
        "creature", "none", "bird", (36, 28, 40), (48, 40, 52), (176, 40, 48), (255, 210, 90),
        "bowtie", (176, 28, 48), (212, 168, 64), "neon_perch", (18, 8, 28), (80, 24, 70),
        (255, 140, 80), "perch", ("bowtie", "crest"), ("bottle",),
        "brand/goonbot-icon-explicit.png",
    ),
    "card_vault_bunny": CardRecipe(
        "bust", "femme", "cream_waves", (232, 210, 186), (228, 186, 164), (200, 80, 110), (70, 40, 32),
        "satin_bunny", (210, 150, 170), (220, 176, 80), "vault_glow", (28, 18, 12), (96, 70, 28),
        (255, 210, 110), "front_smile", ("bunny_ears", "key_charm"), ("vault_ring",),
        "bosses/armored/velvet_vixen_celestial.png",
    ),
    "card_tip_hound": CardRecipe(
        "creature", "none", "hound", (28, 22, 20), (48, 36, 30), (80, 40, 32), (212, 168, 64),
        "collar", (28, 22, 18), (212, 168, 64), "carpet_lamps", (24, 12, 10), (80, 40, 24),
        (255, 180, 80), "sit", ("gold_collar",), ("tip_jar",),
        "districts/downtown.png",
    ),
    "card_aftercare_softie": CardRecipe(
        "bust", "femme", "messy_bun", (96, 64, 48), (222, 186, 168), (176, 90, 100), (70, 48, 42),
        "silk_robe", (196, 140, 150), (232, 186, 160), "rose_room", (48, 18, 28), (140, 60, 70),
        (255, 170, 150), "soft", ("robe_tie",), ("steam",),
        "bosses/freaky_nikki/down.gif",
    ),
    "card_house_blend": CardRecipe(
        "bust", "andro", "leaf_crop", (40, 72, 36), (176, 148, 112), (96, 64, 48), (40, 110, 60),
        "lab_coat", (210, 214, 196), (120, 196, 80), "grow_mood", (12, 20, 28), (48, 24, 72),
        (160, 255, 120), "three_right", ("gold_glasses", "vials"), ("herbs",),
        "drugs/grow_lab.png",
    ),
    "card_empire_drone": CardRecipe(
        "bust", "andro", "slick_short", (32, 28, 36), (198, 168, 148), (80, 50, 48), (40, 50, 80),
        "velvet_blazer", (48, 28, 56), (180, 150, 80), "penthouse", (12, 10, 28), (40, 28, 70),
        (120, 180, 255), "cool", ("holo_clip",), ("city_windows",),
        "businesses/corporation.png",
    ),
    # --- Personas ---
    "card_talent": CardRecipe(
        "bust", "femme", "stage_curl", (176, 36, 28), (208, 160, 130), (168, 36, 36), (40, 24, 20),
        "fire_jacket", (176, 28, 32), (255, 160, 50), "spotlight", (18, 8, 8), (90, 28, 18),
        (255, 180, 60), "three_left", ("mic_stand",), ("mic",),
        "bosses/glam/velvet_vixen_enraged.png",
    ),
    "card_host": CardRecipe(
        "bust", "masc", "side_part", (36, 28, 24), (186, 148, 118), (96, 52, 46), (40, 32, 24),
        "gold_vest", (36, 28, 22), (214, 176, 72), "velvet_rope", (22, 10, 12), (70, 28, 22),
        (255, 210, 110), "front_smirk", ("guest_list",), ("rope",),
        "bosses/armored/velvet_vixen_enraged.png",
    ),
    "card_fixer": CardRecipe(
        "bust", "masc", "undercut", (18, 16, 18), (150, 118, 98), (60, 40, 36), (20, 20, 24),
        "long_coat", (18, 16, 22), (120, 48, 180), "alley", (8, 6, 16), (48, 12, 70),
        (180, 80, 255), "three_right", ("shades",), ("neon_sign",),
        "bosses/armored/velvet_vixen_shadow.png",
    ),
    "card_headliner": CardRecipe(
        "bust", "femme", "updo", (40, 16, 20), (216, 172, 150), (180, 40, 60), (48, 24, 28),
        "sequin", (160, 24, 48), (255, 200, 90), "encore", (24, 6, 16), (110, 24, 40),
        (255, 80, 80), "pose_up", ("sparkle",), ("smoke",),
        "bosses/glam/velvet_vixen_celestial.png",
    ),
    "card_promoter": CardRecipe(
        "bust", "masc", "fade", (32, 24, 20), (164, 112, 82), (88, 48, 40), (36, 28, 22),
        "bomber", (72, 18, 36), (220, 176, 64), "city_posters", (16, 10, 20), (70, 24, 48),
        (255, 170, 50), "front_smirk", ("gold_chains",), ("posters",),
        "bosses/tomass.png",
    ),
    "card_ghost": CardRecipe(
        "bust", "femme", "white_wisps", (230, 232, 240), (210, 220, 230), (160, 180, 200), (180, 210, 230),
        "pale_silk", (200, 210, 224), (160, 190, 220), "moonlit", (8, 12, 24), (40, 50, 80),
        (180, 220, 255), "fade", ("translucent",), ("mist",),
        "bosses/armored/velvet_vixen_mythic.png",
    ),
    "card_circuit_boss": CardRecipe(
        "bust", "andro", "spark_crest", (20, 12, 12), (176, 132, 108), (120, 28, 24), (255, 140, 40),
        "split_coat", (28, 12, 16), (255, 120, 30), "dual_fire", (20, 6, 8), (70, 20, 90),
        (255, 90, 30), "warlord", ("spark_crown",), ("embers",),
        "bosses/zz_wrath.png",
    ),
    "card_house_idol": CardRecipe(
        "bust", "femme", "gold_coils", (196, 156, 72), (230, 196, 168), (180, 70, 80), (80, 48, 28),
        "idol_gown", (212, 176, 80), (255, 230, 150), "cathedral", (28, 16, 8), (96, 64, 24),
        (255, 220, 120), "regal", ("small_crown", "gold_shoulder"), ("adoring_lights",),
        "bosses/glam/velvet_vixen_mythic.png",
    ),
    # --- Hustle ---
    "card_wallet_lift": CardRecipe(
        "bust", "andro", "cap_hair", (36, 28, 24), (176, 140, 112), (80, 48, 42), (36, 28, 24),
        "thief_gloves", (28, 22, 24), (180, 140, 80), "crowd_blur", (18, 10, 16), (70, 28, 40),
        (255, 190, 90), "glance", ("cap", "gloves"), ("wallet",),
        "districts/downtown.png",
    ),
    "card_name_drop": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (90, 40, 40), (212, 168, 64), "board", (40, 22, 18), (90, 48, 32),
        (200, 40, 40), "scene", (), (), "districts/financial.png", "notice_board",
    ),
    "card_table_games": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (128, 18, 36), (212, 168, 64), "felt", (20, 8, 10), (90, 18, 28),
        (255, 200, 80), "scene", (), (), "brand/goonbot-icon-explicit.png", "felt_table",
    ),
    "card_crew_panel": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (36, 24, 28), (212, 168, 64), "alley_gold", (12, 8, 10), (70, 40, 18),
        (255, 180, 70), "scene", (), (), "businesses/chain_restaurant.png", "crew_night",
    ),
    "card_bank_heist": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (20, 24, 32), (80, 220, 200), "vault", (8, 12, 18), (24, 40, 48),
        (80, 255, 220), "scene", (), (), "districts/financial.png", "heist_vault",
    ),
    "card_bodyguard": CardRecipe(
        "bust", "masc", "buzz", (20, 18, 18), (150, 116, 92), (70, 44, 38), (28, 24, 22),
        "tux_guard", (12, 12, 14), (212, 176, 72), "club_door", (8, 8, 10), (36, 28, 24),
        (220, 180, 80), "stoic", ("earpiece", "lapel_pin"), ("door",),
        "bosses/armored/velvet_vixen_normal.png",
    ),
    "card_black_card": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (8, 8, 10), (212, 168, 64), "obsidian", (4, 4, 6), (28, 18, 12),
        (255, 210, 90), "macro", (), ("black_card",), "brand/goonbot-icon-explicit.png",
    ),
    "card_cartel_title": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (28, 64, 32), (212, 176, 64), "lab_throne", (8, 16, 12), (24, 48, 28),
        (120, 255, 90), "scene", (), (), "businesses/factory.png", "cartel_lab",
    ),
    # --- Lounge ---
    "card_edge": CardRecipe(
        "bust", "femme", "heat_fall", (72, 18, 22), (214, 164, 140), (160, 32, 40), (48, 20, 18),
        "chair_grip", (96, 16, 28), (255, 90, 40), "heat", (28, 6, 8), (110, 28, 18),
        (255, 80, 30), "intense", ("chair",), ("haze",),
        "bosses/glam/velvet_vixen_enraged.png",
    ),
    "card_floor_dare": CardRecipe(
        "bust", "andro", "dare_spike", (40, 20, 48), (200, 168, 140), (180, 60, 80), (50, 30, 40),
        "spotlight_fit", (40, 20, 36), (255, 210, 80), "spot", (8, 8, 12), (60, 40, 16),
        (255, 230, 120), "dare", ("confetti",), ("spot_cone",),
        "bosses/freaky_nikki/grab.gif",
    ),
    "card_tease": CardRecipe(
        "bust", "femme", "kiss_curl", (176, 80, 90), (228, 186, 168), (200, 70, 90), (70, 40, 40),
        "booth_satin", (176, 70, 90), (255, 170, 140), "rose_gold", (40, 16, 22), (140, 60, 60),
        (255, 160, 130), "kiss_blow", ("kiss_hand",), ("bokeh_warm",),
        "bosses/freaky_nikki/twist.gif",
    ),
    "card_group_round": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (80, 30, 36), (255, 180, 90), "couches", (18, 10, 14), (70, 28, 24),
        (255, 170, 80), "scene", (), (), "brand/goonbot-banner-explicit.png", "group_lounge",
    ),
    "card_afterglow": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (210, 170, 150), (255, 210, 120), "sheets", (40, 20, 24), (160, 90, 70),
        (255, 220, 160), "macro", (), ("silk_sheets",), "bosses/freaky_nikki/defeat.gif",
    ),
    "card_ruin": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (180, 40, 50), (255, 220, 140), "chaos", (20, 6, 10), (90, 20, 28),
        (255, 80, 80), "macro", (), ("spilled_glass",), "bosses/freaky_nikki/slap.gif",
    ),
    "card_kisses_velvet": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (140, 16, 32), (214, 170, 64), "lip_close", (16, 4, 8), (80, 16, 24),
        (255, 180, 80), "macro", (), ("crimson_lips",), "brand/goonbot-icon-explicit.png",
    ),
    "card_velvet_ready": CardRecipe(
        "bust", "femme", "ready_mane", (88, 14, 24), (218, 174, 148), (150, 24, 40), (40, 22, 18),
        "champion", (120, 16, 32), (255, 210, 80), "gold_rain", (20, 8, 10), (90, 40, 16),
        (255, 220, 90), "hero", ("arm_up", "small_crown"), ("coin_rain",),
        "bosses/glam/velvet_vixen_normal.png",
    ),
    # --- Reliquary ---
    "card_street_token": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (40, 28, 48), (212, 168, 64), "alley", (12, 8, 24), (70, 24, 80),
        (255, 80, 180), "scene", (), (), "districts/downtown.png", "token_alley",
    ),
    "card_jester_bell": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (140, 20, 36), (212, 168, 64), "shrine", (18, 8, 12), (70, 20, 28),
        (255, 200, 80), "macro", (), ("bell",), "bosses/freaky_nikki/slap.gif",
    ),
    "card_medic_patch": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (200, 80, 80), (212, 176, 80), "clinic", (28, 12, 16), (90, 40, 44),
        (255, 160, 140), "macro", (), ("patch",), "bosses/freaky_nikki/down.gif",
    ),
    "card_scrap_idol": CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (120, 88, 40), (212, 168, 64), "workshop", (16, 12, 8), (60, 40, 18),
        (255, 180, 60), "scene", (), (), "districts/industrial.png", "brass_idol",
    ),
    "card_plunder_seal": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (160, 110, 40), (255, 210, 80), "treasure", (18, 10, 6), (80, 50, 16),
        (255, 200, 60), "macro", (), ("signet",), "brand/goonbot-banner-explicit.png",
    ),
    "card_duelist_coin": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (180, 140, 40), (255, 220, 90), "sparks", (12, 10, 8), (50, 36, 12),
        (255, 230, 100), "macro", (), ("lucky_coin",), "brand/goonbot-banner.png",
    ),
    "card_void_heart": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (80, 32, 120), (180, 80, 255), "rift", (8, 4, 18), (40, 12, 70),
        (200, 80, 255), "macro", (), ("void_heart",), "bosses/glam/velvet_vixen_shadow.png",
    ),
    "card_velvet_vault_key": CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (140, 20, 36), (214, 170, 64), "open_vault", (12, 6, 8), (70, 36, 16),
        (255, 200, 80), "macro", (), ("vault_key",), "bosses/glam/velvet_vixen_mythic.png",
    ),
}

assert set(CARD_RECIPES) == set(CARD_DEFINITIONS), "CARD_RECIPES must cover the full catalog"


# ---------------------------------------------------------------------------
# Numpy paint
# ---------------------------------------------------------------------------

def _canvas(size: int) -> np.ndarray:
    return np.zeros((size, size, 4), dtype=np.float32)


def _over(dst: np.ndarray, src_rgb: np.ndarray, alpha: np.ndarray) -> None:
    a = np.clip(alpha, 0.0, 1.0)
    out_a = a + dst[..., 3] * (1.0 - a)
    for i in range(3):
        dst[..., i] = np.where(
            out_a > 1e-6,
            (src_rgb[i] * a + dst[..., i] * dst[..., 3] * (1.0 - a)) / np.maximum(out_a, 1e-6),
            dst[..., i],
        )
    dst[..., 3] = out_a


def _stamp_blob(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    color: RGB,
    alpha: float = 1.0,
    power: float = 1.2,
    core: float = 0.55,
) -> None:
    h, w = canvas.shape[:2]
    pad = 1.15
    x0, x1 = max(0, int(cx - rx * pad)), min(w, int(cx + rx * pad) + 1)
    y0, y1 = max(0, int(cy - ry * pad)), min(h, int(cy + ry * pad) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    d = np.sqrt(((xx - cx) / max(rx, 0.5)) ** 2 + ((yy - cy) / max(ry, 0.5)) ** 2)
    t = np.clip((d - core) / max(1e-6, 1.0 - core), 0.0, 1.0)
    a = (1.0 - t) ** power * alpha
    a = np.where(d <= 1.0, a, 0.0)
    rgb = np.array(color, dtype=np.float32) / 255.0
    _over(canvas[y0:y1, x0:x1], rgb, a)


def _stamp_capsule(
    canvas: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float,
    color: RGB,
    alpha: float = 1.0,
) -> None:
    h, w = canvas.shape[:2]
    pad = radius * 2.4
    xa, xb = max(0, int(min(x0, x1) - pad)), min(w, int(max(x0, x1) + pad) + 1)
    ya, yb = max(0, int(min(y0, y1) - pad)), min(h, int(max(y0, y1) + pad) + 1)
    if xb <= xa or yb <= ya:
        return
    yy, xx = np.ogrid[ya:yb, xa:xb]
    dx, dy = x1 - x0, y1 - y0
    length = max((dx * dx + dy * dy) ** 0.5, 1e-3)
    t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / (length * length), 0.0, 1.0)
    px = x0 + t * dx
    py = y0 + t * dy
    dist = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
    fade = np.clip((dist / max(radius, 0.5) - 0.4) / 0.6, 0.0, 1.0)
    a = (1.0 - fade) ** 1.15 * alpha
    a = np.where(dist <= radius, a, 0.0)
    rgb = np.array(color, dtype=np.float32) / 255.0
    _over(canvas[ya:yb, xa:xb], rgb, a)


def _head_r2(
    xx: np.ndarray,
    yy: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    jaw: float,
    chin: float,
    squash: float,
) -> np.ndarray:
    """Tapered jaw + chin — a face silhouette, not a circle."""
    nx = (xx - cx) / max(rx, 0.5) * squash
    ny = (yy - cy) / max(ry, 0.5)
    taper = np.where(ny > 0.0, 1.0 - jaw * np.power(np.clip(ny, 0.0, 1.0), 1.25), 1.0)
    nx = nx / np.maximum(taper, 0.30)
    ny = ny + chin * np.power(np.clip(ny, 0.0, 1.0), 1.8)
    return nx * nx + ny * ny


def _stamp_head(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    albedo: RGB,
    *,
    jaw: float,
    chin: float,
    squash: float,
    light: tuple[float, float, float],
    rim: RGB,
    ambient: float = 0.24,
) -> np.ndarray:
    """Return the head alpha mask (for later feature placement)."""
    h, w = canvas.shape[:2]
    pad = 1.25
    x0, x1 = max(0, int(cx - rx * pad)), min(w, int(cx + rx * pad) + 1)
    y0, y1 = max(0, int(cy - ry * pad)), min(h, int(cy + ry * pad) + 1)
    if x1 <= x0 or y1 <= y0:
        return np.zeros((h, w), dtype=np.float32)
    yy, xx = np.ogrid[y0:y1, x0:x1]
    r2 = _head_r2(xx, yy, cx, cy, rx, ry, jaw, chin, squash)
    inside = r2 <= 1.0
    # Approximate normals from the warped ellipse so lighting follows the jaw.
    nx = (xx - cx) / max(rx, 0.5) * squash
    ny = (yy - cy) / max(ry, 0.5)
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))
    lx, ly, lz = light
    ln = (lx * lx + ly * ly + lz * lz) ** 0.5
    lx, ly, lz = lx / ln, ly / ln, lz / ln
    lambert = np.clip(nx * lx + ny * ly + nz * lz, 0.0, 1.0)
    rim_term = np.clip(1.0 - nz, 0.0, 1.0) ** 2.2 * np.clip(1.0 - lambert, 0.0, 1.0)
    base = np.array(albedo, dtype=np.float32) / 255.0
    rim_c = np.array(rim, dtype=np.float32) / 255.0
    lit = ambient + 0.82 * lambert
    rgb = np.zeros((*r2.shape, 3), dtype=np.float32)
    for i in range(3):
        rgb[..., i] = np.clip(base[i] * lit + rim_c[i] * rim_term * 0.5, 0.0, 1.0)
    edge = np.clip(1.0 - r2, 0.0, 1.0) ** 0.28
    a = np.where(inside, edge, 0.0).astype(np.float32)
    _over(canvas[y0:y1, x0:x1], (rgb[..., 0], rgb[..., 1], rgb[..., 2]), a)
    mask = np.zeros((h, w), dtype=np.float32)
    mask[y0:y1, x0:x1] = a
    return mask


def _fill_gradient(canvas: np.ndarray, top: RGB, bot: RGB, mood: tuple[RGB, ...]) -> None:
    h, w = canvas.shape[:2]
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    t = np.repeat(t, w, axis=1)
    for i in range(3):
        canvas[..., i] = (top[i] + (bot[i] - top[i]) * t) / 255.0
    canvas[..., 3] = 1.0
    if mood:
        overlay = np.zeros_like(canvas)
        for idx, color in enumerate(mood[:4]):
            cx = w * (0.18 + 0.22 * idx)
            cy = h * (0.12 + 0.2 * (idx % 3))
            _stamp_blob(overlay, cx, cy, w * 0.3, h * 0.24, color, 0.2, 1.4)
        a = overlay[..., 3]
        for i in range(3):
            canvas[..., i] = canvas[..., i] * (1 - a * 0.5) + overlay[..., i] * a * 0.5


def _value_noise(h: int, w: int, scale: int, rng: np.random.Generator) -> np.ndarray:
    gh, gw = h // scale + 2, w // scale + 2
    grid = rng.random((gh, gw)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    gy = yy / scale
    gx = xx / scale
    y0 = np.floor(gy).astype(np.int32)
    x0 = np.floor(gx).astype(np.int32)
    fy = gy - y0
    fx = gx - x0
    n00 = grid[y0, x0]
    n10 = grid[y0 + 1, x0]
    n01 = grid[y0, x0 + 1]
    n11 = grid[y0 + 1, x0 + 1]
    return n00 * (1 - fy) * (1 - fx) + n10 * fy * (1 - fx) + n01 * (1 - fy) * fx + n11 * fy * fx


def _bokeh(canvas: np.ndarray, rng: np.random.Generator, color: RGB, count: int, y_frac: float = 0.55) -> None:
    h, w = canvas.shape[:2]
    for _ in range(count):
        cx = float(rng.uniform(0, w))
        cy = float(rng.uniform(0, h * y_frac))
        r = float(rng.uniform(6, 26) * (w / 512))
        _stamp_blob(canvas, cx, cy, r, r * 0.85, color, float(rng.uniform(0.1, 0.24)), 1.8)


def _curtains(canvas: np.ndarray, color: RGB, rng: np.random.Generator) -> None:
    h, w = canvas.shape[:2]
    folds = 8
    for i in range(folds):
        x = w * (i + 0.4) / folds
        shade = _shade(color, 0.18 + 0.1 * (i % 2))
        hi = _tint(color, 0.14)
        _stamp_capsule(canvas, x, 0, x + rng.uniform(-10, 10), h * 0.95, w * 0.075, shade, 0.78)
        _stamp_capsule(canvas, x - w * 0.025, 0, x - w * 0.012, h * 0.92, w * 0.012, hi, 0.4)
    _stamp_blob(canvas, w * 0.5, h * 0.06, w * 0.58, h * 0.14, _shade(color, 0.4), 0.6, 1.6)


def _city_windows(canvas: np.ndarray, rng: np.random.Generator, gold: RGB) -> None:
    h, w = canvas.shape[:2]
    horizon = int(h * 0.62)
    _stamp_blob(canvas, w * 0.5, horizon + 40, w * 0.7, 80, (6, 8, 18), 0.7, 2.0)
    for x in range(0, w, max(7, w // 36)):
        bh = int(rng.integers(int(h * 0.14), int(h * 0.42)))
        bw = int(rng.integers(10, 24) * w / 512)
        _stamp_blob(canvas, x + bw * 0.5, horizon - bh * 0.35, bw * 0.75, bh * 0.75, (8, 10, 24), 0.92, 4.2)
        for _wy in range(10):
            if rng.random() > 0.5:
                _stamp_blob(
                    canvas,
                    x + rng.uniform(0, bw),
                    horizon - rng.uniform(8, bh),
                    1.8 * w / 512,
                    2.6 * w / 512,
                    gold,
                    0.75,
                    2.0,
                )


def _vignette(canvas: np.ndarray, strength: float = 0.55) -> None:
    h, w = canvas.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    nx = (xx - w * 0.5) / (w * 0.64)
    ny = (yy - h * 0.4) / (h * 0.64)
    d = np.sqrt(nx * nx + ny * ny)
    v = np.clip((d - 0.5) / 0.9, 0.0, 1.0) ** 1.35 * strength
    canvas[..., :3] *= (1.0 - v)[..., None]


def _grain(canvas: np.ndarray, rng: np.random.Generator, amount: float = 0.04) -> None:
    noise = rng.normal(0.0, amount, canvas.shape[:2]).astype(np.float32)
    canvas[..., :3] = np.clip(canvas[..., :3] + noise[..., None], 0.0, 1.0)


def _oil_strokes(canvas: np.ndarray, rng: np.random.Generator, count: int = 220) -> None:
    """Break smooth blobs into short painterly dashes."""
    h, w = canvas.shape[:2]
    ys, xs = np.where(canvas[..., 3] > 0.35)
    if len(xs) < 8:
        return
    pick = rng.integers(0, len(xs), size=min(count, len(xs)))
    for idx in pick:
        x, y = float(xs[idx]), float(ys[idx])
        col = tuple(int(np.clip(canvas[int(y), int(x), i] * 255, 0, 255)) for i in range(3))
        ang = float(rng.uniform(0, 6.28))
        length = float(rng.uniform(7, 18))
        thick = float(rng.uniform(1.6, 3.4))
        _stamp_capsule(
            canvas,
            x - np.cos(ang) * length,
            y - np.sin(ang) * length * 0.45,
            x + np.cos(ang) * length,
            y + np.sin(ang) * length * 0.45,
            thick,
            col,
            0.28,
        )


def _to_image(canvas: np.ndarray) -> Image.Image:
    arr = np.clip(canvas * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------------------
# Backgrounds
# ---------------------------------------------------------------------------

def _paint_background(canvas: np.ndarray, recipe: CardRecipe, rng: np.random.Generator) -> None:
    mood = _mood_colors(recipe.mood_asset)
    _fill_gradient(canvas, recipe.bg_top, recipe.bg_bot, mood)
    h, w = canvas.shape[:2]
    n = _value_noise(h, w, max(10, w // 20), rng)
    canvas[..., :3] *= 0.9 + 0.16 * n[..., None]
    name = recipe.bg
    if name in ("curtains", "throne", "jester_dark", "rose_room", "velvet_rope"):
        _curtains(canvas, _mix(recipe.bg_bot, recipe.cloth_rgb, 0.45), rng)
    if name in ("lounge_neon", "neon_pink", "neon_perch"):
        _bokeh(canvas, rng, recipe.glow, 22, 0.72)
        _stamp_capsule(canvas, w * 0.07, h * 0.18, w * 0.07, h * 0.88, 11, (220, 40, 140), 0.5)
        _stamp_capsule(canvas, w * 0.93, h * 0.12, w * 0.93, h * 0.82, 9, recipe.glow, 0.45)
    if name in ("spotlight", "spot", "encore", "cathedral", "gold_rain"):
        _stamp_blob(canvas, w * 0.5, h * -0.04, w * 0.48, h * 0.42, recipe.glow, 0.38, 1.15)
        _bokeh(canvas, rng, recipe.glow, 14, 0.48)
    if name in ("void", "moonlit", "rift", "abyss", "alley"):
        _stamp_blob(canvas, w * 0.5, h * 0.46, w * 0.42, h * 0.42, recipe.glow, 0.2, 1.3)
        for _ in range(18):
            _stamp_blob(
                canvas,
                float(rng.uniform(0, w)),
                float(rng.uniform(0, h * 0.62)),
                float(rng.uniform(2, 7)),
                float(rng.uniform(2, 7)),
                recipe.glow,
                0.28,
                2.0,
            )
    if name in ("storm_gold", "dual_fire"):
        for _ in range(12):
            x = float(rng.uniform(w * 0.08, w * 0.92))
            _stamp_capsule(
                canvas, x, float(rng.uniform(0, h * 0.38)), x + rng.uniform(-50, 50),
                h * 0.92, float(rng.uniform(4, 14)), recipe.glow, 0.22,
            )
    if name in ("penthouse", "city_posters", "club_door", "crowd_blur"):
        _city_windows(canvas, rng, recipe.accent)
    if name == "grow_mood":
        for i in range(5):
            _stamp_blob(canvas, w * (0.14 + i * 0.18), h * 0.2, 30, 9, (180, 80, 255), 0.38, 2.0)
            _stamp_blob(canvas, w * (0.14 + i * 0.18), h * 0.58, 24, 48, (36, 118, 48), 0.28, 2.0)
    if name in ("vault_glow", "open_vault"):
        _stamp_blob(canvas, w * 0.5, h * 0.56, w * 0.44, h * 0.44, recipe.accent, 0.28, 1.55)
        _stamp_blob(canvas, w * 0.5, h * 0.56, w * 0.3, h * 0.3, (18, 12, 8), 0.58, 2.4)
    if name == "backstage":
        for i, col in enumerate(((255, 70, 70), (70, 255, 110), (70, 110, 255))):
            _stamp_blob(canvas, w * (0.18 + i * 0.32), h * 0.1, 44, 16, col, 0.45, 1.7)
    if name == "busy_floor":
        _bokeh(canvas, rng, recipe.glow, 26, 0.78)
    if name == "carpet_lamps":
        _stamp_blob(canvas, w * 0.18, h * 0.16, 34, 20, (255, 200, 120), 0.4, 1.5)
        _stamp_blob(canvas, w * 0.82, h * 0.16, 34, 20, (255, 200, 120), 0.4, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.85, w * 0.55, 40, (90, 30, 24), 0.35, 1.8)
    if name == "heat":
        for _ in range(10):
            _stamp_blob(
                canvas,
                float(rng.uniform(w * 0.18, w * 0.82)),
                float(rng.uniform(h * 0.08, h * 0.72)),
                float(rng.uniform(18, 52)),
                float(rng.uniform(36, 88)),
                recipe.glow,
                0.13,
                1.25,
            )
    if name in ("lip_close", "sheets", "chaos", "obsidian", "treasure", "sparks", "shrine", "clinic"):
        canvas[..., :3] *= 0.88 + 0.22 * n[..., None]
    if "god_rays" in recipe.extras or "god_rays" in recipe.props or name == "throne":
        for i in range(7):
            ang = -0.45 + i * 0.16
            _stamp_capsule(canvas, w * 0.74, h * -0.06, w * (0.32 + ang), h * 0.92, 16, recipe.glow, 0.13)


def _layout(recipe: CardRecipe, size: int) -> dict[str, float]:
    s = size / 512.0
    pose = recipe.pose
    cx = size * 0.5
    turn = 0.0
    if pose in ("three_left", "wink_left", "glance"):
        cx = size * 0.45
        turn = -1.0
    elif pose in ("three_right",):
        cx = size * 0.55
        turn = 1.0
    if recipe.body == "masc":
        hx, hy, jaw, chin = 86 * s, 104 * s, 0.06, 0.14
    elif recipe.body == "andro":
        hx, hy, jaw, chin = 80 * s, 102 * s, 0.18, 0.1
    else:
        hx, hy, jaw, chin = 76 * s, 108 * s, 0.34, 0.08
    head_y = 176 * s
    if pose == "command":
        head_y, hx, hy = 158 * s, 84 * s, 114 * s
    elif pose == "tower":
        head_y, hx, hy = 148 * s, 90 * s, 122 * s
        jaw = 0.22
    elif pose in ("kiss_blow",):
        head_y, hx, hy = 210 * s, 108 * s, 128 * s
    elif pose == "hero":
        head_y = 164 * s
    elif pose == "stoic":
        head_y, hx, hy = 154 * s, 90 * s, 112 * s
        cx = size * 0.5
        turn = 0.0
    elif pose == "soft":
        head_y = 188 * s
        jaw = 0.38
    elif pose == "intense":
        head_y, hx, hy = 198 * s, 88 * s, 116 * s
    elif pose == "dare":
        head_y = 168 * s
    elif pose == "fade":
        hx, hy = 74 * s, 100 * s
    elif pose == "pierce":
        jaw = 0.2
        hy = 110 * s
    squash = 1.08 if turn == 0 else 1.18
    return {
        "cx": cx, "head_y": head_y, "hx": hx, "hy": hy, "s": s,
        "size": float(size), "turn": turn, "jaw": jaw, "chin": chin, "squash": squash,
    }


# ---------------------------------------------------------------------------
# Hair / clothing / face
# ---------------------------------------------------------------------------

def _paint_hair_back(canvas: np.ndarray, L: dict[str, float], recipe: CardRecipe, rng: np.random.Generator) -> None:
    cx, hy, hx, hyy, s = L["cx"], L["head_y"], L["hx"], L["hy"], L["s"]
    c, d = recipe.hair_rgb, _shade(recipe.hair_rgb, 0.32)
    style = recipe.hair
    long_styles = (
        "cascade", "crimson_crown", "void_fall", "heat_fall", "ready_mane",
        "cream_waves", "teal_kelp", "stage_curl", "kiss_curl",
    )
    if style in long_styles:
        _stamp_blob(canvas, cx, hy + 48 * s, hx * 1.55, hyy * 1.85, d, 0.96, 1.55)
        for side in (-1.0, 1.0):
            for i in range(9):
                _stamp_capsule(
                    canvas,
                    cx + side * (hx * 0.55),
                    hy + 8 * s,
                    cx + side * (hx * (1.15 + i * 0.09)),
                    hy + (70 + i * 22) * s,
                    (18 - i * 0.8) * s,
                    c if i % 2 == 0 else d,
                    0.88,
                )
    elif style in ("pink_bob",):
        _stamp_blob(canvas, cx, hy + 18 * s, hx * 1.42, hyy * 1.2, c, 0.96, 1.5)
        _stamp_blob(canvas, cx - hx * 1.05, hy + 78 * s, 40 * s, 72 * s, d, 0.92, 1.6)
        _stamp_blob(canvas, cx + hx * 1.05, hy + 78 * s, 40 * s, 72 * s, d, 0.92, 1.6)
    elif style in ("platinum", "white_wisps", "gold_coils"):
        _stamp_blob(canvas, cx + 16 * s, hy + 28 * s, hx * 1.55, hyy * 1.5, c, 0.9, 1.45)
        for _i in range(12):
            _stamp_capsule(
                canvas,
                cx + rng.uniform(-hx, hx),
                hy - 8 * s,
                cx + rng.uniform(-hx * 1.5, hx * 1.5),
                hy + rng.uniform(50, 160) * s,
                rng.uniform(7, 15) * s,
                _tint(c, 0.18),
                0.55,
            )
    elif style in ("slick", "side_part", "fade", "buzz", "slick_short", "undercut", "leaf_crop"):
        _stamp_blob(canvas, cx, hy - 4 * s, hx * 1.12, hyy * 0.78, d, 0.96, 1.9)
    elif style in ("pixie", "dare_spike", "spark_crest"):
        _stamp_blob(canvas, cx, hy - 2 * s, hx * 1.18, hyy * 0.7, c, 0.92, 1.7)
        for _i in range(8):
            _stamp_capsule(
                canvas,
                cx + rng.uniform(-hx * 0.7, hx * 0.7), hy - 16 * s,
                cx + rng.uniform(-hx * 1.1, hx * 1.1), hy - 58 * s,
                7 * s, c, 0.75,
            )
    elif style in ("pony", "messy_bun", "updo"):
        _stamp_blob(canvas, cx, hy + 12 * s, hx * 1.22, hyy * 0.92, d, 0.92, 1.7)
    elif style == "cap_hair":
        _stamp_blob(canvas, cx, hy + 8 * s, hx * 1.1, hyy * 0.7, d, 0.9, 1.9)


def _paint_hair_front(canvas: np.ndarray, L: dict[str, float], recipe: CardRecipe, rng: np.random.Generator) -> None:
    cx, hy, hx, s = L["cx"], L["head_y"], L["hx"], L["s"]
    c, hi = recipe.hair_rgb, _tint(recipe.hair_rgb, 0.28)
    style = recipe.hair
    if style in ("cascade", "crimson_crown", "heat_fall", "ready_mane", "cream_waves", "stage_curl"):
        _stamp_blob(canvas, cx - hx * 0.42, hy + 10 * s, 46 * s, 32 * s, c, 0.92, 1.6)
        _stamp_blob(canvas, cx + hx * 0.46, hy + 6 * s, 40 * s, 26 * s, c, 0.8, 1.6)
        _stamp_capsule(canvas, cx - hx * 0.78, hy + 4 * s, cx - hx * 0.15, hy + 62 * s, 11 * s, hi, 0.5)
        _stamp_capsule(canvas, cx + hx * 0.7, hy, cx + hx * 0.2, hy + 48 * s, 9 * s, hi, 0.4)
    elif style == "void_fall":
        _stamp_blob(canvas, cx, hy + 8 * s, hx * 1.02, 26 * s, c, 0.88, 1.8)
        _stamp_capsule(canvas, cx - hx * 0.6, hy, cx - hx * 0.1, hy + 70 * s, 10 * s, c, 0.7)
    elif style == "pink_bob":
        _stamp_blob(canvas, cx, hy + 4 * s, hx * 1.12, 30 * s, c, 0.96, 1.55)
        _stamp_blob(canvas, cx - 12 * s, hy + 22 * s, 56 * s, 18 * s, hi, 0.45, 1.9)
    elif style == "platinum":
        for _i in range(7):
            _stamp_capsule(
                canvas, cx + rng.uniform(-48, 48) * s, hy - 6 * s,
                cx + rng.uniform(-80, 80) * s, hy + 48 * s, 6 * s, hi, 0.55,
            )
    elif style in ("slick", "side_part", "fade", "slick_short"):
        _stamp_blob(canvas, cx, hy - 6 * s, hx * 1.0, 24 * s, c, 0.96, 2.0)
        _stamp_capsule(canvas, cx - hx * 0.45, hy - 2 * s, cx + hx * 0.55, hy + 10 * s, 8 * s, hi, 0.5)
    elif style == "buzz":
        _stamp_blob(canvas, cx, hy, hx * 0.98, 18 * s, _mix(c, recipe.skin, 0.4), 0.85, 1.9)
    elif style == "pixie":
        _stamp_blob(canvas, cx - 10 * s, hy + 6 * s, 54 * s, 20 * s, c, 0.85, 1.7)
    elif style == "pony":
        _stamp_blob(canvas, cx + 52 * s, hy - 8 * s, 30 * s, 58 * s, c, 0.96, 1.55)
        _stamp_blob(canvas, cx, hy + 6 * s, hx * 0.95, 20 * s, c, 0.85, 1.9)
    elif style == "messy_bun":
        _stamp_blob(canvas, cx + 8 * s, hy - 52 * s, 44 * s, 40 * s, c, 0.96, 1.45)
        _stamp_blob(canvas, cx, hy + 4 * s, hx * 0.78, 16 * s, c, 0.6, 1.9)
        for _i in range(5):
            _stamp_capsule(canvas, cx, hy - 48 * s, cx + rng.uniform(-40, 40) * s, hy - 70 * s, 4 * s, hi, 0.5)
    elif style == "updo":
        _stamp_blob(canvas, cx, hy - 46 * s, 56 * s, 44 * s, c, 0.96, 1.45)
        _stamp_blob(canvas, cx, hy + 2 * s, hx * 0.7, 14 * s, hi, 0.4, 2.0)
    elif style == "gold_coils":
        for i in range(7):
            _stamp_blob(canvas, cx + (i - 3) * 16 * s, hy - 34 * s, 13 * s, 24 * s, c, 0.85, 1.55)
    elif style == "teal_kelp":
        for side in (-1.0, 1.0):
            _stamp_capsule(canvas, cx + side * hx * 0.35, hy, cx + side * hx * 1.25, hy + 140 * s, 15 * s, c, 0.82)
    elif style == "white_wisps":
        for _i in range(9):
            _stamp_capsule(
                canvas, cx, hy, cx + rng.uniform(-90, 90) * s, hy + rng.uniform(16, 110) * s, 7 * s, c, 0.38,
            )
    elif style == "spark_crest":
        _stamp_blob(canvas, cx, hy - 32 * s, 26 * s, 44 * s, recipe.accent, 0.85, 1.5)
    elif style == "cap_hair":
        _stamp_blob(canvas, cx, hy - 16 * s, hx * 1.12, 26 * s, (30, 24, 26), 0.96, 2.2)
        _stamp_blob(canvas, cx, hy - 42 * s, 40 * s, 18 * s, (30, 24, 26), 0.96, 1.9)
        _stamp_blob(canvas, cx + 36 * s, hy - 8 * s, 18 * s, 10 * s, (40, 32, 28), 0.7, 2.0)
    elif style == "undercut":
        _stamp_blob(canvas, cx - 12 * s, hy - 4 * s, hx * 0.78, 22 * s, c, 0.92, 1.9)
    elif style == "leaf_crop":
        _stamp_blob(canvas, cx, hy - 2 * s, hx * 0.95, 20 * s, c, 0.88, 1.9)
        _stamp_blob(canvas, cx + 20 * s, hy + 8 * s, 16 * s, 10 * s, (48, 110, 40), 0.45, 2.0)
    elif style == "dare_spike":
        for i in range(6):
            _stamp_capsule(canvas, cx + (i - 2.5) * 15 * s, hy, cx + (i - 2.5) * 22 * s, hy - 46 * s, 5.5 * s, c, 0.8)
    elif style == "kiss_curl":
        _stamp_blob(canvas, cx + 34 * s, hy + 10 * s, 44 * s, 56 * s, c, 0.85, 1.55)
        _stamp_blob(canvas, cx - 40 * s, hy + 16 * s, 28 * s, 40 * s, c, 0.7, 1.6)


def _paint_torso(canvas: np.ndarray, L: dict[str, float], recipe: CardRecipe) -> None:
    cx, hy, s = L["cx"], L["head_y"], L["s"]
    cloth, acc = recipe.cloth_rgb, recipe.accent
    dark = _shade(cloth, 0.38)
    neck_y = hy + L["hy"] * 0.78
    _stamp_capsule(canvas, cx, neck_y, cx, neck_y + 44 * s, 16 * s, _shade(recipe.skin, 0.1), 0.96)
    body = recipe.clothing
    shoulder_y = neck_y + 52 * s
    width = 158 * s
    # Shoulders as a trapezoid of overlapping strokes — not one oval.
    _stamp_blob(canvas, cx, shoulder_y + 48 * s, width, 120 * s, cloth, 0.96, 1.55)
    _stamp_capsule(canvas, cx - width * 0.85, shoulder_y + 8 * s, cx - 20 * s, neck_y + 20 * s, 22 * s, cloth, 0.9)
    _stamp_capsule(canvas, cx + width * 0.85, shoulder_y + 8 * s, cx + 20 * s, neck_y + 20 * s, 22 * s, cloth, 0.9)
    _stamp_capsule(canvas, cx - width * 0.5, shoulder_y + 30 * s, cx - width * 0.15, shoulder_y + 110 * s, 10 * s, dark, 0.35)
    _stamp_capsule(canvas, cx + width * 0.5, shoulder_y + 30 * s, cx + width * 0.15, shoulder_y + 110 * s, 10 * s, dark, 0.35)
    if body in ("throne_gown", "velvet_scoop", "idol_gown", "champion", "scale_cape"):
        _stamp_capsule(canvas, cx - 18 * s, neck_y + 10 * s, cx - 90 * s, shoulder_y + 90 * s, 16 * s, acc, 0.4)
        _stamp_capsule(canvas, cx + 18 * s, neck_y + 10 * s, cx + 90 * s, shoulder_y + 90 * s, 16 * s, acc, 0.4)
        _stamp_blob(canvas, cx, neck_y + 30 * s, 42 * s, 30 * s, _shade(recipe.skin, 0.04), 0.9, 1.7)
        if body == "scale_cape":
            for i in range(6):
                _stamp_blob(canvas, cx + (i - 2.5) * 22 * s, shoulder_y + 20 * s, 16 * s, 20 * s, acc, 0.35, 2.0)
    elif body == "leather_v":
        _stamp_blob(canvas, cx, neck_y + 32 * s, 38 * s, 44 * s, (14, 12, 14), 0.92, 1.9)
        _stamp_capsule(canvas, cx - 78 * s, shoulder_y, cx - 36 * s, shoulder_y + 90 * s, 7 * s, (190, 190, 200), 0.65)
        _stamp_capsule(canvas, cx + 36 * s, shoulder_y, cx + 78 * s, shoulder_y + 90 * s, 7 * s, (80, 80, 90), 0.4)
    elif body == "waiter_vest":
        _stamp_blob(canvas, cx, shoulder_y + 22 * s, 76 * s, 96 * s, (16, 14, 16), 0.92, 2.0)
        _stamp_blob(canvas, cx - 10 * s, shoulder_y + 6 * s, 9 * s, 9 * s, acc, 0.92, 2.0)
        _stamp_blob(canvas, cx + 10 * s, shoulder_y + 6 * s, 9 * s, 9 * s, acc, 0.92, 2.0)
        _stamp_blob(canvas, cx, neck_y + 18 * s, 30 * s, 18 * s, (242, 242, 246), 0.88, 2.0)
    elif body == "gold_vest":
        _stamp_blob(canvas, cx, shoulder_y + 18 * s, 84 * s, 96 * s, acc, 0.88, 1.9)
        _stamp_blob(canvas, cx, neck_y + 18 * s, 26 * s, 16 * s, (240, 236, 220), 0.85, 2.0)
        _stamp_capsule(canvas, cx, neck_y + 12 * s, cx, shoulder_y + 80 * s, 4 * s, (40, 28, 16), 0.5)
    elif body == "tux_guard":
        _stamp_capsule(canvas, cx, neck_y + 12 * s, cx, shoulder_y + 100 * s, 9 * s, (232, 232, 236), 0.75)
        _stamp_blob(canvas, cx - 20 * s, shoulder_y + 10 * s, 11 * s, 11 * s, acc, 0.92, 2.0)
    elif body == "fire_jacket":
        _stamp_blob(canvas, cx, neck_y + 26 * s, 32 * s, 32 * s, (18, 10, 10), 0.88, 1.9)
        _stamp_capsule(canvas, cx - 96 * s, shoulder_y, cx - 18 * s, shoulder_y + 12 * s, 15 * s, recipe.glow, 0.45)
    elif body == "long_coat":
        _stamp_blob(canvas, cx, shoulder_y + 24 * s, width * 1.12, 150 * s, cloth, 0.96, 1.65)
        _stamp_blob(canvas, cx + 44 * s, shoulder_y + 12 * s, 54 * s, 88 * s, _shade(cloth, 0.22), 0.55, 1.7)
        _stamp_capsule(canvas, cx - 70 * s, shoulder_y + 10 * s, cx - 40 * s, shoulder_y + 120 * s, 8 * s, acc, 0.35)
    elif body == "bomber":
        _stamp_blob(canvas, cx, neck_y + 22 * s, 42 * s, 26 * s, (18, 10, 14), 0.88, 1.9)
        _stamp_capsule(canvas, cx - 86 * s, shoulder_y + 22 * s, cx + 86 * s, shoulder_y + 22 * s, 11 * s, acc, 0.45)
    elif body == "velvet_blazer":
        _stamp_blob(canvas, cx, neck_y + 24 * s, 30 * s, 22 * s, (222, 214, 204), 0.85, 1.9)
        _stamp_capsule(canvas, cx - 70 * s, shoulder_y, cx - 20 * s, shoulder_y + 80 * s, 6 * s, acc, 0.4)
    elif body == "split_coat":
        _stamp_blob(canvas, cx - 54 * s, shoulder_y + 32 * s, 86 * s, 118 * s, (92, 14, 20), 0.92, 1.65)
        _stamp_blob(canvas, cx + 54 * s, shoulder_y + 32 * s, 86 * s, 118 * s, (26, 10, 46), 0.92, 1.65)
    elif body == "black_crew":
        _stamp_blob(canvas, cx, neck_y + 22 * s, 34 * s, 20 * s, recipe.skin, 0.75, 1.9)
        _stamp_blob(canvas, cx + 48 * s, shoulder_y + 8 * s, 36 * s, 14 * s, (176, 42, 48), 0.7, 2.0)
    elif body in ("satin_lace", "satin_bunny", "silk_robe", "booth_satin", "pale_silk", "chair_grip", "spotlight_fit"):
        _stamp_blob(canvas, cx, neck_y + 26 * s, 50 * s, 32 * s, _tint(recipe.skin, 0.06), 0.88, 1.7)
        if body == "silk_robe":
            _stamp_capsule(canvas, cx - 12 * s, neck_y + 22 * s, cx + 44 * s, shoulder_y + 88 * s, 17 * s, acc, 0.5)
        if body == "satin_bunny":
            _stamp_blob(canvas, cx, neck_y + 44 * s, 74 * s, 42 * s, _tint(cloth, 0.18), 0.55, 1.7)
        if body == "pale_silk":
            _stamp_blob(canvas, cx, shoulder_y + 22 * s, width * 0.72, 86 * s, _tint(cloth, 0.22), 0.4, 1.45)
        if body == "chair_grip":
            _stamp_capsule(canvas, cx - 96 * s, hy + 36 * s, cx - 40 * s, hy + 170 * s, 13 * s, (58, 18, 22), 0.88)
    elif body == "lab_coat":
        _stamp_blob(canvas, cx, neck_y + 26 * s, 30 * s, 32 * s, (38, 78, 46), 0.75, 1.9)
        _stamp_capsule(canvas, cx + 70 * s, shoulder_y + 20 * s, cx + 70 * s, shoulder_y + 90 * s, 8 * s, (200, 200, 180), 0.5)
    elif body == "thief_gloves":
        _stamp_blob(canvas, cx + 88 * s, shoulder_y + 74 * s, 38 * s, 30 * s, (16, 14, 14), 0.96, 1.7)
        _stamp_blob(canvas, cx - 70 * s, shoulder_y + 60 * s, 28 * s, 22 * s, (16, 14, 14), 0.9, 1.8)
    elif body == "wrath_collar":
        _stamp_blob(canvas, cx, neck_y + 18 * s, 76 * s, 30 * s, acc, 0.75, 1.9)
        _stamp_capsule(canvas, cx - 50 * s, neck_y + 8 * s, cx + 50 * s, neck_y + 8 * s, 8 * s, acc, 0.85)
    elif body == "sequin":
        for i in range(14):
            _stamp_blob(
                canvas, cx + (i % 7 - 3) * 18 * s, shoulder_y + 20 * s + (i // 7) * 28 * s,
                8 * s, 6 * s, acc if i % 2 == 0 else _tint(cloth, 0.2), 0.7, 2.0,
            )


def _paint_face(canvas: np.ndarray, L: dict[str, float], recipe: CardRecipe) -> None:
    cx, hy, hx, hyy, s = L["cx"], L["head_y"], L["hx"], L["hy"], L["s"]
    turn = L["turn"]
    skin = recipe.skin
    head_cx = cx + turn * 8 * s
    head_cy = hy + hyy * 0.12
    _stamp_head(
        canvas, head_cx, head_cy, hx, hyy, skin,
        jaw=L["jaw"], chin=L["chin"], squash=L["squash"],
        light=(-0.35 - turn * 0.25, -0.52, 0.78),
        rim=recipe.glow, ambient=0.26,
    )
    # Cheeks / nose bridge sit on the jaw form, not a second sphere.
    blush = _mix(skin, recipe.lip, 0.32)
    _stamp_blob(canvas, head_cx - hx * 0.42, head_cy + hyy * 0.22, 24 * s, 16 * s, blush, 0.38, 1.7)
    _stamp_blob(canvas, head_cx + hx * 0.42, head_cy + hyy * 0.22, 24 * s, 16 * s, blush, 0.38, 1.7)
    _stamp_blob(canvas, head_cx + turn * 4 * s, head_cy + hyy * 0.08, 10 * s, 22 * s, _shade(skin, 0.14), 0.4, 1.9)
    _stamp_blob(canvas, head_cx + turn * 4 * s - 4 * s, head_cy, 6 * s, 10 * s, _tint(skin, 0.22), 0.5, 2.0)
    _stamp_blob(canvas, head_cx - 8 * s, head_cy + hyy * 0.18, 5 * s, 4 * s, _shade(skin, 0.22), 0.35, 2.0)
    _stamp_blob(canvas, head_cx + 8 * s, head_cy + hyy * 0.18, 5 * s, 4 * s, _shade(skin, 0.22), 0.35, 2.0)
    # Ears break the head silhouette.
    near = 1.0 if turn >= 0 else -1.0
    _stamp_blob(
        canvas, head_cx + near * hx * 0.98, head_cy + hyy * 0.02,
        16 * s, 26 * s, _shade(skin, 0.08), 0.92, 1.7,
    )
    _stamp_blob(
        canvas, head_cx + near * hx * 0.96, head_cy + hyy * 0.02,
        8 * s, 14 * s, blush, 0.45, 1.8,
    )
    if abs(turn) < 0.5:
        _stamp_blob(canvas, head_cx - hx * 0.98, head_cy + hyy * 0.02, 14 * s, 24 * s, _shade(skin, 0.1), 0.88, 1.7)
    wink = "wink" in recipe.extras or recipe.pose == "wink_left"
    eye_y = head_cy - hyy * 0.08
    for i, side in enumerate((-1.0, 1.0)):
        ex = head_cx + side * hx * (0.34 - abs(turn) * 0.04) + turn * 6 * s
        tilt = side * 0.0
        if wink and i == 0:
            _stamp_capsule(canvas, ex - 16 * s, eye_y + 2 * s, ex + 16 * s, eye_y + 6 * s, 4 * s, _shade(skin, 0.35), 0.9)
            _stamp_capsule(canvas, ex - 14 * s, eye_y, ex + 14 * s, eye_y + 3 * s, 2.4 * s, recipe.hair_rgb, 0.7)
            continue
        # Almond eye: lid, sclera, iris, pupil, catchlight, crease.
        _stamp_blob(canvas, ex, eye_y + 2 * s, 20 * s, 13 * s, (22, 14, 16), 0.55, 1.8)
        _stamp_blob(canvas, ex, eye_y + 3 * s, 17 * s, 10 * s, (240, 232, 224), 0.96, 2.0)
        _stamp_blob(canvas, ex + 3 * s + turn * 2 * s, eye_y + 3 * s, 9 * s, 9 * s, recipe.eye, 0.96, 1.9)
        _stamp_blob(canvas, ex + 3 * s + turn * 2 * s, eye_y + 3 * s, 4 * s, 4 * s, (8, 6, 8), 0.96, 2.0)
        _stamp_blob(canvas, ex + 6 * s, eye_y, 3.2 * s, 2.6 * s, (255, 255, 255), 0.95, 2.0)
        _stamp_capsule(canvas, ex - 18 * s, eye_y - 6 * s + tilt, ex + 18 * s, eye_y - 4 * s, 4.2 * s, recipe.hair_rgb, 0.88)
        _stamp_capsule(canvas, ex - 16 * s, eye_y + 10 * s, ex + 16 * s, eye_y + 8 * s, 2.6 * s, _shade(skin, 0.25), 0.45)
    brow = _shade(recipe.hair_rgb, 0.12) if recipe.body != "masc" else _mix(recipe.hair_rgb, skin, 0.28)
    _stamp_capsule(canvas, head_cx - hx * 0.52, eye_y - 16 * s, head_cx - hx * 0.1, eye_y - 18 * s, 3.6 * s, brow, 0.92)
    _stamp_capsule(canvas, head_cx + hx * 0.1, eye_y - 18 * s, head_cx + hx * 0.52, eye_y - 16 * s, 3.6 * s, brow, 0.92)
    my = head_cy + hyy * 0.42
    if recipe.pose == "kiss_blow":
        _stamp_blob(canvas, head_cx, my, 20 * s, 14 * s, recipe.lip, 0.96, 1.65)
        _stamp_blob(canvas, head_cx, my - 3 * s, 12 * s, 7 * s, _tint(recipe.lip, 0.22), 0.55, 1.9)
        _stamp_blob(canvas, head_cx, my + 2 * s, 8 * s, 5 * s, (80, 20, 28), 0.4, 2.0)
    elif recipe.pose == "pierce":
        _stamp_blob(canvas, head_cx, my, 22 * s, 8 * s, recipe.lip, 0.96, 1.9)
        _stamp_capsule(canvas, head_cx - 18 * s, my, head_cx + 18 * s, my + 2 * s, 2.5 * s, _shade(recipe.lip, 0.3), 0.7)
    else:
        smile = recipe.pose in ("front_smile", "front_smirk", "command", "soft", "regal", "hero")
        ry = 10 * s if smile else 7 * s
        _stamp_blob(canvas, head_cx, my - 4 * s, 18 * s, 8 * s, recipe.lip, 0.96, 1.7)
        _stamp_blob(canvas, head_cx, my + 6 * s, 22 * s, ry, _shade(recipe.lip, 0.12), 0.96, 1.6)
        _stamp_blob(canvas, head_cx, my, 12 * s, 4 * s, (70, 22, 28), 0.4, 2.0)
        _stamp_blob(canvas, head_cx, my - 6 * s, 10 * s, 4 * s, _tint(recipe.lip, 0.3), 0.5, 2.0)
        if smile:
            _stamp_blob(canvas, head_cx, my + 3 * s, 12 * s, 4 * s, (90, 36, 36), 0.35, 2.0)
    if "stubble" in recipe.extras:
        _stamp_blob(canvas, head_cx, my + 18 * s, 46 * s, 24 * s, _mix(skin, (36, 24, 20), 0.5), 0.5, 1.55)


def _paint_extras(canvas: np.ndarray, L: dict[str, float], recipe: CardRecipe, rng: np.random.Generator) -> None:
    cx, hy, hx, hyy, s = L["cx"], L["head_y"], L["hx"], L["hy"], L["s"]
    gold = recipe.accent
    if "tall_crown" in recipe.extras:
        for i in range(-2, 3):
            _stamp_capsule(canvas, cx + i * 18 * s, hy - hyy * 0.52, cx + i * 18 * s, hy - hyy * 1.12, 8 * s, gold, 0.96)
        _stamp_blob(canvas, cx, hy - hyy * 0.68, hx * 1.0, 20 * s, gold, 0.96, 1.9)
        _stamp_blob(canvas, cx, hy - hyy * 0.88, 16 * s, 20 * s, (160, 20, 40), 0.92, 1.9)
        _stamp_blob(canvas, cx, hy - hyy * 0.88, 7 * s, 9 * s, (255, 220, 160), 0.75, 2.0)
    if "small_crown" in recipe.extras:
        _stamp_blob(canvas, cx, hy - hyy * 0.74, 54 * s, 16 * s, gold, 0.96, 1.9)
        _stamp_blob(canvas, cx, hy - hyy * 0.96, 12 * s, 18 * s, gold, 0.92, 1.9)
    if "scale_crown" in recipe.extras:
        for i in range(5):
            _stamp_blob(canvas, cx + (i - 2) * 20 * s, hy - hyy * 0.72, 17 * s, 22 * s, recipe.hair_rgb, 0.88, 1.65)
            _stamp_blob(canvas, cx + (i - 2) * 20 * s, hy - hyy * 0.72, 7 * s, 9 * s, gold, 0.75, 2.0)
    if "headset" in recipe.extras:
        _stamp_capsule(canvas, cx - hx * 1.02, hy, cx + hx * 1.02, hy, 6 * s, (36, 36, 44), 0.96)
        _stamp_blob(canvas, cx - hx * 1.08, hy + 20 * s, 16 * s, 20 * s, (28, 28, 34), 0.96, 1.9)
        _stamp_blob(canvas, cx - hx * 1.08, hy + 20 * s, 6 * s, 6 * s, (80, 220, 120), 0.85, 2.0)
    if "bunny_ears" in recipe.extras:
        for side in (-1.0, 1.0):
            _stamp_capsule(canvas, cx + side * 30 * s, hy - 18 * s, cx + side * 44 * s, hy - 118 * s, 13 * s, recipe.hair_rgb, 0.96)
            _stamp_capsule(canvas, cx + side * 30 * s, hy - 18 * s, cx + side * 42 * s, hy - 108 * s, 6 * s, (232, 160, 170), 0.88)
    if "horns" in recipe.extras:
        for side in (-1.0, 1.0):
            _stamp_capsule(canvas, cx + side * 26 * s, hy - 8 * s, cx + side * 52 * s, hy - 76 * s, 9 * s, (120, 20, 24), 0.96)
    if "gold_glasses" in recipe.extras:
        for side in (-1.0, 1.0):
            _stamp_blob(canvas, cx + side * hx * 0.34, hy + 6 * s, 20 * s, 15 * s, gold, 0.4, 2.8)
        _stamp_capsule(canvas, cx - 20 * s, hy + 6 * s, cx + 20 * s, hy + 6 * s, 2.4 * s, gold, 0.85)
    if "shades" in recipe.extras:
        _stamp_blob(canvas, cx, hy + 8 * s, 52 * s, 16 * s, (10, 10, 14), 0.94, 2.2)
        _stamp_blob(canvas, cx, hy + 8 * s, 46 * s, 11 * s, (48, 22, 70), 0.4, 1.9)
    if "hoop" in recipe.extras:
        _stamp_blob(canvas, cx + hx * 0.92, hy + hyy * 0.22, 8 * s, 10 * s, (210, 210, 220), 0.9, 2.4)
        _stamp_blob(canvas, cx + hx * 0.92, hy + hyy * 0.22, 4 * s, 5 * s, recipe.skin, 0.9, 2.0)
    if "chain" in recipe.extras or "gold_chains" in recipe.extras:
        _stamp_blob(canvas, cx, hy + hyy * 0.88, 44 * s, 20 * s, gold, 0.75, 1.9)
        _stamp_blob(canvas, cx, hy + hyy * 1.08, 10 * s, 12 * s, gold, 0.92, 1.9)
        _stamp_capsule(canvas, cx - 24 * s, hy + hyy * 0.78, cx + 24 * s, hy + hyy * 1.05, 3 * s, gold, 0.7)
    if "choker" in recipe.extras or "ruby_collar" in recipe.extras:
        _stamp_capsule(canvas, cx - 30 * s, hy + hyy * 0.8, cx + 30 * s, hy + hyy * 0.8, 6 * s, gold, 0.92)
        _stamp_blob(canvas, cx, hy + hyy * 0.84, 12 * s, 14 * s, (160, 20, 40), 0.92, 1.9)
    if "gold_drops" in recipe.extras or "silver_drops" in recipe.extras:
        drop = gold if "gold_drops" in recipe.extras else (180, 190, 210)
        for side in (-1.0, 1.0):
            _stamp_capsule(canvas, cx + side * hx * 0.82, hy + hyy * 0.12, cx + side * hx * 0.86, hy + hyy * 0.52, 3.2 * s, drop, 0.92)
            _stamp_blob(canvas, cx + side * hx * 0.86, hy + hyy * 0.56, 7 * s, 9 * s, (160, 24, 40) if "gold_drops" in recipe.extras else drop, 0.88, 1.9)
    if "lanyard" in recipe.extras:
        _stamp_capsule(canvas, cx - 22 * s, hy + hyy * 0.72, cx - 8 * s, hy + hyy * 1.45, 5 * s, (160, 30, 40), 0.88)
        _stamp_blob(canvas, cx - 6 * s, hy + hyy * 1.48, 16 * s, 12 * s, gold, 0.8, 2.0)
    if "earpiece" in recipe.extras:
        _stamp_blob(canvas, cx + hx * 0.98, hy + 10 * s, 9 * s, 11 * s, (40, 40, 48), 0.96, 1.9)
        _stamp_capsule(canvas, cx + hx * 0.98, hy + 10 * s, cx + hx * 0.72, hy - 22 * s, 2.2 * s, (40, 40, 48), 0.85)
    if "bow" in recipe.extras:
        _stamp_blob(canvas, cx + hx * 0.72, hy - 8 * s, 24 * s, 18 * s, (220, 40, 100), 0.92, 1.65)
        _stamp_blob(canvas, cx + hx * 0.9, hy - 8 * s, 24 * s, 18 * s, (220, 40, 100), 0.92, 1.65)
        _stamp_blob(canvas, cx + hx * 0.82, hy - 8 * s, 8 * s, 10 * s, (180, 20, 70), 0.9, 2.0)
    if "key_charm" in recipe.extras:
        _stamp_capsule(canvas, cx + 42 * s, hy + hyy * 0.92, cx + 42 * s, hy + hyy * 1.28, 4.5 * s, gold, 0.92)
        _stamp_blob(canvas, cx + 42 * s, hy + hyy * 0.9, 12 * s, 12 * s, gold, 0.92, 1.9)
    if "skull_jewel" in recipe.extras:
        _stamp_blob(canvas, cx, hy + hyy * 0.88, 18 * s, 16 * s, gold, 0.92, 1.9)
        _stamp_blob(canvas, cx, hy + hyy * 0.88, 9 * s, 8 * s, (18, 14, 10), 0.75, 2.0)
    if "spark_crown" in recipe.extras:
        for i in range(7):
            _stamp_blob(canvas, cx + (i - 3) * 16 * s, hy - hyy * 0.78 - abs(i - 3) * 5 * s, 9 * s, 16 * s, recipe.glow, 0.85, 1.5)
    if "arm_up" in recipe.extras:
        _stamp_capsule(canvas, cx + 74 * s, hy + 86 * s, cx + 118 * s, hy - 44 * s, 17 * s, recipe.skin, 0.96)
        _stamp_blob(canvas, cx + 126 * s, hy - 54 * s, 24 * s, 22 * s, recipe.skin, 0.96, 1.65)
    if "chair" in recipe.extras:
        _stamp_capsule(canvas, cx - 96 * s, hy + 42 * s, cx - 42 * s, hy + 168 * s, 13 * s, (58, 18, 22), 0.88)
    if "kiss_hand" in recipe.extras:
        _stamp_blob(canvas, cx + 70 * s, hy + hyy * 0.55, 28 * s, 24 * s, recipe.skin, 0.92, 1.7)
        _stamp_blob(canvas, cx + 88 * s, hy + hyy * 0.4, 12 * s, 18 * s, recipe.skin, 0.9, 1.8)
    if "mic" in recipe.props:
        _stamp_capsule(canvas, cx + 54 * s, hy + 42 * s, cx + 76 * s, hy + 138 * s, 7 * s, (36, 36, 44), 0.96)
        _stamp_blob(canvas, cx + 50 * s, hy + 30 * s, 18 * s, 22 * s, (28, 28, 34), 0.96, 1.9)
    if "champagne_tray" in recipe.props:
        _stamp_blob(canvas, cx + 96 * s, hy + 118 * s, 54 * s, 12 * s, gold, 0.92, 2.2)
        _stamp_capsule(canvas, cx + 82 * s, hy + 72 * s, cx + 82 * s, hy + 118 * s, 5.5 * s, (220, 220, 230), 0.85)
        _stamp_blob(canvas, cx + 82 * s, hy + 64 * s, 11 * s, 9 * s, (255, 240, 180), 0.75, 2.0)
    if "wallet" in recipe.props:
        _stamp_blob(canvas, cx + 90 * s, hy + 108 * s, 30 * s, 20 * s, (42, 24, 16), 0.96, 1.9)
        _stamp_blob(canvas, cx + 90 * s, hy + 108 * s, 20 * s, 7 * s, gold, 0.65, 2.0)
    if "holo_clip" in recipe.extras:
        _stamp_blob(canvas, cx + 74 * s, hy + 96 * s, 26 * s, 34 * s, (80, 180, 255), 0.5, 1.65)
    if "green_aura" in recipe.props:
        _stamp_blob(canvas, cx, hy + 40 * s, 150 * s, 170 * s, (40, 220, 90), 0.14, 1.25)
    if "confetti" in recipe.extras:
        span = L["size"]
        for _ in range(28):
            _stamp_blob(
                canvas, float(rng.uniform(30, span - 30)), float(rng.uniform(16, span * 0.82)),
                float(rng.uniform(3, 9)) * s, float(rng.uniform(2, 6)) * s,
                gold if rng.random() > 0.5 else recipe.lip, 0.72, 2.0,
            )
    if "coin_rain" in recipe.props:
        for _ in range(20):
            _stamp_blob(
                canvas,
                float(rng.uniform(24, 488)) * (L["size"] / 512),
                float(rng.uniform(16, 270)) * (L["size"] / 512),
                9 * s, 7 * s, gold, 0.78, 2.0,
            )
    if "vials" in recipe.extras:
        _stamp_capsule(canvas, cx + 86 * s, hy + 70 * s, cx + 86 * s, hy + 120 * s, 8 * s, (180, 255, 140), 0.55)
        _stamp_capsule(canvas, cx + 104 * s, hy + 80 * s, cx + 104 * s, hy + 124 * s, 7 * s, (160, 80, 255), 0.5)
    if "translucent" in recipe.extras:
        canvas[..., 3] = np.clip(canvas[..., 3] * 0.9 + 0.08, 0, 1)


def _paint_creature(canvas: np.ndarray, recipe: CardRecipe, rng: np.random.Generator) -> None:
    h, w = canvas.shape[:2]
    s = w / 512.0
    if recipe.hair == "imp":
        cx, cy = w * 0.5, h * 0.5
        _stamp_head(canvas, cx, cy + 8 * s, 62 * s, 70 * s, recipe.skin, jaw=0.2, chin=0.1, squash=1.05,
                    light=(-0.4, -0.5, 0.75), rim=recipe.glow)
        _stamp_blob(canvas, cx, cy + 70 * s, 80 * s, 70 * s, recipe.cloth_rgb, 0.95, 1.6)
        for side in (-1.0, 1.0):
            _stamp_capsule(canvas, cx + side * 26 * s, cy - 40 * s, cx + side * 58 * s, cy - 118 * s, 11 * s, (120, 20, 24), 0.96)
        _stamp_blob(canvas, cx, cy + 18 * s, 54 * s, 20 * s, recipe.accent, 0.72, 1.9)
        for side in (-1.0, 1.0):
            _stamp_blob(canvas, cx + side * 22 * s, cy - 16 * s, 15 * s, 17 * s, (255, 230, 80), 0.96, 1.9)
            _stamp_blob(canvas, cx + side * 22 * s, cy - 16 * s, 6 * s, 6 * s, (18, 8, 8), 0.96, 2.0)
        _stamp_blob(canvas, cx, cy + 18 * s, 18 * s, 12 * s, recipe.lip, 0.92, 1.9)
        _stamp_blob(canvas, cx, cy + 108 * s, 36 * s, 22 * s, recipe.skin, 0.9, 1.8)
        _stamp_blob(canvas, cx, cy + 108 * s, 16 * s, 10 * s, recipe.accent, 0.7, 2.0)
    elif recipe.hair == "bird":
        cx, cy = w * 0.46, h * 0.52
        _stamp_blob(canvas, cx, cy + 18 * s, 78 * s, 58 * s, recipe.hair_rgb, 0.96, 1.5)
        _stamp_head(canvas, cx + 48 * s, cy - 8 * s, 40 * s, 38 * s, recipe.hair_rgb, jaw=0.15, chin=0.2, squash=1.1,
                    light=(-0.3, -0.5, 0.8), rim=recipe.glow)
        _stamp_capsule(canvas, cx + 78 * s, cy - 2 * s, cx + 122 * s, cy + 10 * s, 9 * s, (220, 170, 60), 0.96)
        _stamp_blob(canvas, cx + 52 * s, cy - 14 * s, 9 * s, 9 * s, recipe.eye, 0.96, 2.0)
        _stamp_blob(canvas, cx + 52 * s, cy - 14 * s, 3 * s, 3 * s, (10, 8, 8), 0.96, 2.0)
        _stamp_blob(canvas, cx, cy + 10 * s, 24 * s, 16 * s, (176, 28, 48), 0.92, 1.9)
        _stamp_capsule(canvas, cx + 16 * s, cy + 48 * s, cx + 16 * s, cy + 138 * s, 11 * s, (180, 40, 50), 0.92)
        _stamp_blob(canvas, cx + 16 * s, cy + 40 * s, 18 * s, 22 * s, (40, 120, 50), 0.85, 1.9)
        _stamp_blob(canvas, cx + 6 * s, cy - 42 * s, 20 * s, 24 * s, recipe.accent, 0.85, 1.65)
        _stamp_blob(canvas, cx - 40 * s, cy + 10 * s, 36 * s, 16 * s, _shade(recipe.hair_rgb, 0.2), 0.7, 1.8)
    else:
        cx, cy = w * 0.48, h * 0.56
        _stamp_blob(canvas, cx, cy + 18 * s, 100 * s, 72 * s, recipe.hair_rgb, 0.96, 1.5)
        _stamp_head(canvas, cx + 78 * s, cy - 8 * s, 52 * s, 44 * s, recipe.hair_rgb, jaw=0.25, chin=0.2, squash=1.15,
                    light=(-0.35, -0.5, 0.75), rim=recipe.glow)
        _stamp_capsule(canvas, cx + 118 * s, cy, cx + 162 * s, cy + 12 * s, 11 * s, recipe.hair_rgb, 0.96)
        _stamp_blob(canvas, cx + 88 * s, cy - 16 * s, 11 * s, 11 * s, recipe.accent, 0.92, 1.9)
        _stamp_blob(canvas, cx + 88 * s, cy - 16 * s, 4 * s, 4 * s, (10, 8, 8), 0.96, 2.0)
        _stamp_blob(canvas, cx, cy - 6 * s, 44 * s, 16 * s, recipe.accent, 0.88, 1.9)
        _stamp_blob(canvas, cx - 24 * s, cy + 96 * s, 30 * s, 24 * s, (80, 50, 30), 0.85, 1.9)
        _stamp_blob(canvas, cx + 86 * s, cy + 74 * s, 20 * s, 30 * s, (40, 28, 20), 0.75, 1.8)
        _stamp_blob(canvas, cx + 40 * s, cy + 40 * s, 22 * s, 28 * s, (70, 40, 24), 0.5, 1.8)


# ---------------------------------------------------------------------------
# Still-life painterly plates
# ---------------------------------------------------------------------------

def _paint_still(canvas: np.ndarray, recipe: CardRecipe, rng: np.random.Generator) -> None:
    h, w = canvas.shape[:2]
    s = w / 512.0
    prop = recipe.props[0] if recipe.props else ""
    gold = recipe.accent
    # Table / cloth plane under every still life so it isn't a floating blob.
    _stamp_blob(canvas, w * 0.5, h * 0.78, 240 * s, 90 * s, _shade(recipe.bg_bot, 0.1), 0.55, 1.5)
    if prop == "black_card":
        _stamp_blob(canvas, w * 0.5, h * 0.72, 200 * s, 50 * s, (36, 16, 14), 0.45, 1.6)
        _stamp_capsule(canvas, w * 0.28, h * 0.22, w * 0.72, h * 0.22, 7 * s, gold, 0.92)
        _stamp_capsule(canvas, w * 0.28, h * 0.78, w * 0.72, h * 0.78, 7 * s, gold, 0.92)
        _stamp_capsule(canvas, w * 0.28, h * 0.22, w * 0.28, h * 0.78, 7 * s, gold, 0.92)
        _stamp_capsule(canvas, w * 0.72, h * 0.22, w * 0.72, h * 0.78, 7 * s, gold, 0.92)
        _stamp_blob(canvas, w * 0.5, h * 0.5, 118 * s, 160 * s, (8, 8, 10), 0.96, 2.6)
        _stamp_blob(canvas, w * 0.42, h * 0.36, 22 * s, 28 * s, gold, 0.75, 1.9)
        _stamp_blob(canvas, w * 0.58, h * 0.64, 18 * s, 24 * s, gold, 0.55, 1.9)
        _stamp_blob(canvas, w * 0.5, h * 0.48, 16 * s, 16 * s, (160, 24, 40), 0.7, 2.0)
    elif prop == "crimson_lips":
        _stamp_blob(canvas, w * 0.5, h * 0.42, 210 * s, 170 * s, (214, 170, 148), 0.9, 1.45)
        _stamp_blob(canvas, w * 0.5, h * 0.28, 32 * s, 40 * s, (214, 170, 148), 0.75, 1.7)
        _stamp_blob(canvas, w * 0.42, h * 0.44, 58 * s, 32 * s, (176, 28, 48), 0.96, 1.55)
        _stamp_blob(canvas, w * 0.58, h * 0.44, 58 * s, 32 * s, (176, 28, 48), 0.96, 1.55)
        _stamp_blob(canvas, w * 0.5, h * 0.42, 90 * s, 22 * s, (150, 18, 36), 0.9, 1.7)
        _stamp_blob(canvas, w * 0.5, h * 0.58, 128 * s, 52 * s, (130, 14, 32), 0.96, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.54, 70 * s, 14 * s, (70, 8, 18), 0.5, 1.9)
        _stamp_blob(canvas, w * 0.54, h * 0.5, 44 * s, 14 * s, (255, 150, 150), 0.38, 1.9)
        _stamp_blob(canvas, w * 0.48, h * 0.64, 54 * s, 16 * s, gold, 0.28, 1.7)
        _stamp_blob(canvas, w * 0.36, h * 0.22, 18 * s, 10 * s, (40, 22, 18), 0.35, 2.0)
        _stamp_blob(canvas, w * 0.64, h * 0.22, 18 * s, 10 * s, (40, 22, 18), 0.35, 2.0)
    elif prop == "silk_sheets":
        for i in range(10):
            col = _mix((214, 174, 154), gold, i / 12)
            _stamp_capsule(canvas, w * 0.06, h * (0.22 + i * 0.07), w * 0.94, h * (0.18 + i * 0.08), 32 * s, col, 0.52)
        _stamp_blob(canvas, w * 0.58, h * 0.42, 130 * s, 86 * s, (255, 224, 186), 0.28, 1.4)
        _stamp_blob(canvas, w * 0.38, h * 0.62, 100 * s, 54 * s, (180, 80, 90), 0.22, 1.5)
        _stamp_blob(canvas, w * 0.7, h * 0.7, 40 * s, 20 * s, gold, 0.25, 1.8)
    elif prop == "spilled_glass":
        _stamp_blob(canvas, w * 0.42, h * 0.72, 180 * s, 44 * s, (200, 180, 80), 0.5, 1.5)
        _stamp_capsule(canvas, w * 0.6, h * 0.32, w * 0.8, h * 0.74, 17 * s, (230, 230, 242), 0.72)
        _stamp_blob(canvas, w * 0.72, h * 0.3, 30 * s, 20 * s, (255, 255, 255), 0.55, 1.9)
        _stamp_blob(canvas, w * 0.78, h * 0.28, 18 * s, 12 * s, gold, 0.4, 2.0)
        for _ in range(24):
            _stamp_blob(
                canvas, float(rng.uniform(w * 0.16, w * 0.84)), float(rng.uniform(h * 0.18, h * 0.82)),
                float(rng.uniform(4, 14)) * s, float(rng.uniform(3, 9)) * s, gold, 0.58, 2.0,
            )
        _stamp_blob(canvas, w * 0.28, h * 0.48, 40 * s, 28 * s, (180, 40, 50), 0.35, 1.7)
    elif prop == "bell":
        _stamp_blob(canvas, w * 0.5, h * 0.5, 96 * s, 108 * s, gold, 0.96, 1.45)
        _stamp_blob(canvas, w * 0.5, h * 0.2, 26 * s, 22 * s, gold, 0.96, 1.9)
        _stamp_blob(canvas, w * 0.5, h * 0.74, 20 * s, 24 * s, gold, 0.96, 1.9)
        _stamp_capsule(canvas, w * 0.26, h * 0.28, w * 0.16, h * 0.74, 9 * s, (160, 20, 40), 0.88)
        _stamp_capsule(canvas, w * 0.74, h * 0.28, w * 0.84, h * 0.74, 9 * s, (40, 90, 40), 0.88)
        _stamp_blob(canvas, w * 0.38, h * 0.4, 18 * s, 12 * s, (255, 245, 200), 0.45, 2.0)
        _stamp_blob(canvas, w * 0.5, h * 0.86, 70 * s, 16 * s, (80, 20, 28), 0.4, 1.8)
    elif prop == "patch":
        _stamp_blob(canvas, w * 0.5, h * 0.58, 200 * s, 120 * s, (214, 176, 160), 0.55, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.5, 150 * s, 96 * s, (232, 222, 212), 0.96, 2.0)
        _stamp_capsule(canvas, w * 0.3, h * 0.5, w * 0.7, h * 0.5, 11 * s, gold, 0.88)
        _stamp_blob(canvas, w * 0.5, h * 0.5, 44 * s, 30 * s, (180, 50, 50), 0.75, 1.9)
        _stamp_blob(canvas, w * 0.34, h * 0.4, 9 * s, 9 * s, gold, 0.85, 2.0)
        _stamp_blob(canvas, w * 0.66, h * 0.6, 9 * s, 9 * s, gold, 0.85, 2.0)
        _stamp_capsule(canvas, w * 0.32, h * 0.38, w * 0.38, h * 0.62, 2.5 * s, (180, 180, 170), 0.5)
    elif prop == "signet":
        _stamp_blob(canvas, w * 0.4, h * 0.52, 90 * s, 56 * s, gold, 0.96, 1.5)
        _stamp_blob(canvas, w * 0.4, h * 0.52, 32 * s, 26 * s, (120, 30, 30), 0.88, 1.9)
        _stamp_blob(canvas, w * 0.4, h * 0.5, 12 * s, 10 * s, (80, 16, 16), 0.7, 2.0)
        for i in range(9):
            _stamp_blob(canvas, w * (0.58 + (i % 3) * 0.09), h * (0.4 + (i // 3) * 0.13), 24 * s, 18 * s, gold, 0.9, 1.7)
        _stamp_blob(canvas, w * 0.7, h * 0.72, 50 * s, 16 * s, (40, 20, 10), 0.4, 1.8)
    elif prop == "lucky_coin":
        _stamp_blob(canvas, w * 0.5, h * 0.5, 118 * s, 118 * s, gold, 0.96, 1.45)
        _stamp_blob(canvas, w * 0.5, h * 0.5, 74 * s, 74 * s, (160, 110, 30), 0.4, 1.9)
        _stamp_blob(canvas, w * 0.4, h * 0.38, 22 * s, 14 * s, (255, 255, 230), 0.5, 1.9)
        _stamp_blob(canvas, w * 0.5, h * 0.48, 20 * s, 28 * s, (120, 30, 30), 0.55, 2.0)
        for i in range(14):
            ang = i / 14 * 6.28
            _stamp_capsule(
                canvas, w * 0.5, h * 0.5,
                w * 0.5 + np.cos(ang) * 190 * s, h * 0.5 + np.sin(ang) * 190 * s, 4 * s, gold, 0.32,
            )
    elif prop == "void_heart":
        _stamp_blob(canvas, w * 0.5, h * 0.42, 76 * s, 64 * s, (140, 40, 200), 0.92, 1.5)
        _stamp_blob(canvas, w * 0.36, h * 0.36, 58 * s, 52 * s, (100, 30, 170), 0.92, 1.5)
        _stamp_blob(canvas, w * 0.64, h * 0.36, 58 * s, 52 * s, (100, 30, 170), 0.92, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.6, 86 * s, 76 * s, (70, 20, 140), 0.92, 1.5)
        _stamp_blob(canvas, w * 0.46, h * 0.4, 22 * s, 18 * s, (230, 180, 255), 0.55, 1.9)
        _stamp_blob(canvas, w * 0.5, h * 0.52, 20 * s, 44 * s, (40, 0, 80), 0.4, 1.9)
        for _ in range(10):
            _stamp_blob(canvas, float(rng.uniform(w * 0.2, w * 0.8)), float(rng.uniform(h * 0.12, h * 0.4)),
                        4 * s, 4 * s, (200, 140, 255), 0.5, 2.0)
    elif prop == "vault_key":
        _stamp_capsule(canvas, w * 0.24, h * 0.5, w * 0.8, h * 0.5, 16 * s, gold, 0.96)
        _stamp_blob(canvas, w * 0.26, h * 0.5, 52 * s, 52 * s, gold, 0.96, 1.5)
        _stamp_blob(canvas, w * 0.26, h * 0.5, 20 * s, 20 * s, (40, 10, 16), 0.92, 1.9)
        _stamp_blob(canvas, w * 0.74, h * 0.5, 18 * s, 30 * s, gold, 0.96, 1.9)
        _stamp_blob(canvas, w * 0.8, h * 0.6, 14 * s, 24 * s, gold, 0.96, 1.9)
        _stamp_blob(canvas, w * 0.5, h * 0.74, 170 * s, 44 * s, (120, 20, 36), 0.38, 1.5)
        _stamp_blob(canvas, w * 0.34, h * 0.38, 16 * s, 10 * s, (255, 240, 180), 0.45, 2.0)
    else:
        _stamp_blob(canvas, w * 0.5, h * 0.5, 96 * s, 96 * s, gold, 0.95, 1.5)


# ---------------------------------------------------------------------------
# Pixel plates (location / hustle / relic scenes)
# ---------------------------------------------------------------------------

def _px(n: int = 128) -> np.ndarray:
    return np.zeros((n, n, 3), dtype=np.uint8)


def _px_fill(a: np.ndarray, x: int, y: int, w: int, h: int, c: RGB) -> None:
    n = a.shape[0]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(n, x + w), min(n, y + h)
    if x1 > x0 and y1 > y0:
        a[y0:y1, x0:x1] = c


def _px_disc(a: np.ndarray, cx: int, cy: int, r: int, c: RGB) -> None:
    n = a.shape[0]
    y0, y1 = max(0, cy - r), min(n, cy + r + 1)
    x0, x1 = max(0, cx - r), min(n, cx + r + 1)
    yy, xx = np.ogrid[y0:y1, x0:x1]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    a[y0:y1, x0:x1][mask] = c


def _px_person(a: np.ndarray, x: int, y: int, skin: RGB, cloth: RGB, hair: RGB) -> None:
    _px_fill(a, x + 1, y, 6, 4, hair)
    _px_disc(a, x + 4, y + 6, 4, skin)
    _px_fill(a, x + 3, y + 5, 2, 2, (20, 12, 12))
    _px_fill(a, x, y + 11, 8, 14, cloth)
    _px_fill(a, x - 2, y + 13, 3, 8, cloth)
    _px_fill(a, x + 7, y + 13, 3, 8, cloth)
    _px_fill(a, x + 1, y + 24, 3, 8, _shade(cloth, 0.25))
    _px_fill(a, x + 5, y + 24, 3, 8, _shade(cloth, 0.25))


def _paint_pixel(recipe: CardRecipe, size: int, rng: np.random.Generator) -> Image.Image:
    a = _px(128)
    scene = recipe.scene
    top, bot, gold, cloth = recipe.bg_top, recipe.bg_bot, recipe.accent, recipe.cloth_rgb
    for y in range(128):
        t = y / 127
        a[y, :] = [int(top[i] + (bot[i] - top[i]) * t) for i in range(3)]
    if scene == "notice_board":
        _px_fill(a, 10, 8, 108, 112, (72, 42, 28))
        _px_fill(a, 14, 12, 100, 104, (118, 76, 46))
        notes = (
            (20, 20, (228, 210, 168), 26, 32),
            (52, 28, (242, 232, 204), 24, 30),
            (82, 16, (196, 48, 48), 20, 26),
            (24, 68, (232, 214, 176), 28, 34),
            (60, 64, (72, 24, 24), 22, 28),
            (88, 70, (220, 190, 140), 18, 30),
        )
        for x, y, c, nw, nh in notes:
            _px_fill(a, x, y, nw, nh, c)
            _px_fill(a, x + nw // 2 - 2, y - 2, 4, 4, gold)
            _px_fill(a, x + 4, y + 6, nw - 8, 2, (40, 24, 16))
            _px_fill(a, x + 4, y + 12, nw - 10, 2, (40, 24, 16))
        for t in range(16):
            _px_fill(a, 34 + t * 2, 24 + t, 2, 2, (160, 20, 28))
            _px_fill(a, 64 + t, 46 + t, 2, 2, (160, 20, 28))
        _px_person(a, 6, 86, (186, 140, 110), (40, 20, 24), (28, 18, 16))
    elif scene == "felt_table":
        _px_fill(a, 0, 36, 128, 92, cloth)
        _px_fill(a, 6, 44, 116, 76, _shade(cloth, 0.18))
        _px_fill(a, 10, 48, 108, 8, gold)
        _px_disc(a, 36, 80, 11, gold)
        _px_disc(a, 56, 86, 11, (240, 240, 246))
        _px_disc(a, 48, 98, 11, (36, 36, 44))
        _px_fill(a, 86, 70, 20, 28, (242, 238, 222))
        _px_fill(a, 90, 74, 12, 18, (180, 28, 40))
        _px_fill(a, 88, 70, 16, 4, (40, 40, 48))
        _px_disc(a, 28, 68, 6, (220, 220, 230))
        _px_disc(a, 38, 64, 6, (200, 40, 40))
        _px_fill(a, 18, 104, 8, 8, gold)
        _px_fill(a, 28, 108, 8, 8, gold)
        _px_fill(a, 96, 100, 10, 10, gold)
        _px_person(a, 100, 40, (176, 132, 104), (20, 16, 18), (24, 18, 16))
        _px_fill(a, 54, 16, 20, 18, (255, 210, 120))
        _px_fill(a, 60, 8, 8, 12, (40, 28, 16))
    elif scene == "crew_night":
        _px_fill(a, 0, 88, 128, 40, (26, 16, 12))
        _px_fill(a, 0, 70, 128, 20, (48, 28, 14))
        _px_fill(a, 0, 0, 18, 90, (22, 16, 18))
        _px_fill(a, 110, 0, 18, 96, (18, 14, 16))
        skins = ((180, 140, 110), (120, 80, 60), (200, 168, 140))
        clothes = ((36, 24, 28), (80, 20, 30), (24, 28, 40))
        hair = ((20, 14, 12), (48, 24, 18), (176, 140, 80))
        for i, (sk, cl, hr) in enumerate(zip(skins, clothes, hair)):
            _px_person(a, 28 + i * 32, 48, sk, cl, hr)
            _px_fill(a, 32 + i * 32, 72, 8, 5, gold)
        _px_fill(a, 8, 18, 5, 56, gold)
        _px_fill(a, 118, 30, 4, 40, (255, 80, 40))
    elif scene == "heist_vault":
        _px_fill(a, 16, 16, 96, 96, (32, 44, 52))
        _px_fill(a, 20, 20, 88, 88, (44, 58, 66))
        _px_disc(a, 64, 64, 38, (52, 66, 74))
        _px_disc(a, 64, 64, 26, (16, 20, 24))
        for i in range(8):
            ang = i / 8 * 6.28
            _px_fill(a, int(64 + np.cos(ang) * 30), int(64 + np.sin(ang) * 30), 5, 5, gold)
        _px_fill(a, 18, 28, 92, 3, (80, 255, 220))
        _px_fill(a, 22, 84, 84, 3, (80, 255, 220))
        _px_fill(a, 46, 98, 16, 20, (14, 12, 16))
        _px_disc(a, 54, 92, 8, (28, 26, 30))
        _px_person(a, 8, 78, (150, 110, 90), (12, 12, 16), (16, 12, 12))
        _px_fill(a, 10, 84, 10, 6, (8, 8, 10))  # mask
    elif scene == "cartel_lab":
        _px_fill(a, 0, 102, 128, 26, (40, 36, 32))
        for i in range(4):
            x = 14 + i * 28
            _px_fill(a, x, 16, 22, 7, (180, 80, 255))
            _px_fill(a, x + 2, 24, 18, 54, (36, 118, 48))
            _px_fill(a, x + 5, 34, 12, 38, (60, 168, 72))
            _px_fill(a, x + 8, 44, 6, 16, (90, 210, 90))
        _px_fill(a, 48, 72, 32, 42, gold)
        _px_fill(a, 54, 62, 20, 14, gold)
        _px_fill(a, 92, 80, 16, 32, (180, 180, 200))
        _px_person(a, 50, 70, (176, 140, 110), (210, 214, 196), (40, 72, 36))
    elif scene == "group_lounge":
        _px_fill(a, 6, 72, 116, 42, (90, 24, 32))
        _px_fill(a, 14, 64, 100, 18, (120, 36, 44))
        skins = ((200, 160, 130), (160, 110, 90), (210, 176, 150), (140, 96, 70), (186, 148, 118))
        for i, sk in enumerate(skins):
            x = 18 + i * 20
            _px_disc(a, x + 6, 56, 7, sk)
            _px_fill(a, x + 2, 62, 10, 16, (60, 20, 28) if i != 2 else (140, 30, 40))
        _px_disc(a, 64, 36, 14, (255, 180, 80))
        _px_fill(a, 18, 102, 92, 12, (40, 20, 24))
        _px_fill(a, 40, 28, 8, 8, gold)
        _px_fill(a, 80, 24, 6, 6, gold)
    elif scene == "token_alley":
        _px_fill(a, 0, 84, 128, 44, (28, 22, 36))
        _px_fill(a, 8, 16, 20, 74, (40, 30, 50))
        _px_fill(a, 100, 8, 22, 84, (30, 24, 44))
        _px_fill(a, 10, 26, 16, 10, (255, 40, 140))
        _px_fill(a, 104, 34, 14, 8, (80, 180, 255))
        _px_fill(a, 12, 48, 12, 6, (255, 200, 40))
        _px_disc(a, 64, 80, 18, gold)
        _px_disc(a, 64, 80, 10, (120, 80, 24))
        _px_fill(a, 60, 76, 8, 8, (255, 220, 120))
        _px_fill(a, 38, 100, 52, 14, (50, 40, 30))
        _px_person(a, 86, 68, (164, 120, 92), (36, 24, 40), (24, 16, 20))
    elif scene == "brass_idol":
        _px_fill(a, 16, 92, 96, 22, (60, 40, 20))
        _px_fill(a, 34, 70, 60, 26, (140, 100, 40))
        _px_fill(a, 46, 38, 36, 38, (180, 130, 50))
        _px_disc(a, 64, 30, 16, (200, 150, 60))
        _px_fill(a, 58, 26, 4, 4, (20, 16, 10))
        _px_fill(a, 70, 26, 4, 4, (20, 16, 10))
        _px_fill(a, 60, 34, 8, 3, (80, 40, 20))
        _px_fill(a, 22, 18, 8, 74, (255, 160, 40))
        _px_fill(a, 98, 22, 6, 68, (255, 160, 40))
        _px_fill(a, 48, 102, 32, 8, gold)
        _px_fill(a, 8, 100, 12, 8, (80, 60, 30))
        _px_fill(a, 108, 96, 10, 12, (80, 60, 30))
    else:
        _px_disc(a, 64, 64, 30, gold)
    img = Image.fromarray(a, "RGB").resize((size, size), Image.Resampling.NEAREST).convert("RGBA")
    grain = Image.effect_noise((size, size), 10).convert("L")
    g = Image.merge("RGBA", (grain, grain, grain, Image.new("L", (size, size), 22)))
    return Image.alpha_composite(img, g)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _finish(canvas: np.ndarray, recipe: CardRecipe, rng: np.random.Generator) -> Image.Image:
    _oil_strokes(canvas, rng, 180 if recipe.kind == "bust" else 90)
    _vignette(canvas, 0.52 if recipe.kind != "pixel" else 0.22)
    _grain(canvas, rng, 0.032)
    img = _to_image(canvas)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.45))
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = ImageEnhance.Color(img).enhance(1.14 if recipe.kind == "bust" else 1.08)
    return img


def render_card_art(card: CardDefinition, size: int = PORTRAIT_SIZE) -> Image.Image:
    """Original 512 plate for this catalog id. Never crops a boss/brand file."""
    recipe = CARD_RECIPES[card.card_id]
    rng = _rng(card.card_id)
    if recipe.kind == "pixel":
        return _paint_pixel(recipe, size, rng)

    canvas = _canvas(size)
    _paint_background(canvas, recipe, rng)
    if recipe.kind == "still":
        _paint_still(canvas, recipe, rng)
        return _finish(canvas, recipe, rng)
    if recipe.kind == "creature":
        _paint_creature(canvas, recipe, rng)
        return _finish(canvas, recipe, rng)

    layout = _layout(recipe, size)
    _paint_hair_back(canvas, layout, recipe, rng)
    _paint_torso(canvas, layout, recipe)
    _paint_face(canvas, layout, recipe)
    _paint_hair_front(canvas, layout, recipe, rng)
    _paint_extras(canvas, layout, recipe, rng)
    return _finish(canvas, recipe, rng)


# ---------------------------------------------------------------------------
# Numpy paint (backgrounds, lighting, grain)
# ---------------------------------------------------------------------------

def _canvas(size: int) -> np.ndarray:
    return np.zeros((size, size, 4), dtype=np.float32)


def _over(dst: np.ndarray, src_rgb: np.ndarray, alpha: np.ndarray) -> None:
    a = np.clip(alpha, 0.0, 1.0)
    out_a = a + dst[..., 3] * (1.0 - a)
    for i in range(3):
        dst[..., i] = np.where(
            out_a > 1e-6,
            (src_rgb[i] * a + dst[..., i] * dst[..., 3] * (1.0 - a)) / np.maximum(out_a, 1e-6),
            dst[..., i],
        )
    dst[..., 3] = out_a


def _stamp_blob(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    color: RGB,
    alpha: float = 1.0,
    power: float = 1.2,
    core: float = 0.55,
) -> None:
    h, w = canvas.shape[:2]
    pad = 1.15
    x0, x1 = max(0, int(cx - rx * pad)), min(w, int(cx + rx * pad) + 1)
    y0, y1 = max(0, int(cy - ry * pad)), min(h, int(cy + ry * pad) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    d = np.sqrt(((xx - cx) / max(rx, 0.5)) ** 2 + ((yy - cy) / max(ry, 0.5)) ** 2)
    t = np.clip((d - core) / max(1e-6, 1.0 - core), 0.0, 1.0)
    a = np.where(d <= 1.0, (1.0 - t) ** power * alpha, 0.0)
    rgb = np.array(color, dtype=np.float32) / 255.0
    _over(canvas[y0:y1, x0:x1], rgb, a)


def _stamp_capsule(
    canvas: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float,
    color: RGB,
    alpha: float = 1.0,
) -> None:
    h, w = canvas.shape[:2]
    pad = radius * 2.4
    xa, xb = max(0, int(min(x0, x1) - pad)), min(w, int(max(x0, x1) + pad) + 1)
    ya, yb = max(0, int(min(y0, y1) - pad)), min(h, int(max(y0, y1) + pad) + 1)
    if xb <= xa or yb <= ya:
        return
    yy, xx = np.ogrid[ya:yb, xa:xb]
    dx, dy = x1 - x0, y1 - y0
    length = max((dx * dx + dy * dy) ** 0.5, 1e-3)
    t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / (length * length), 0.0, 1.0)
    px = x0 + t * dx
    py = y0 + t * dy
    dist = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
    fall = np.clip((dist / max(radius, 0.5) - 0.45) / 0.55, 0.0, 1.0)
    a = np.where(dist <= radius, (1.0 - fall) ** 1.1 * alpha, 0.0)
    rgb = np.array(color, dtype=np.float32) / 255.0
    _over(canvas[ya:yb, xa:xb], rgb, a)


def _fill_gradient(canvas: np.ndarray, top: RGB, bot: RGB, mood: tuple[RGB, ...]) -> None:
    h, w = canvas.shape[:2]
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    t = np.repeat(t, w, axis=1)
    for i in range(3):
        canvas[..., i] = (top[i] + (bot[i] - top[i]) * t) / 255.0
    canvas[..., 3] = 1.0
    if mood:
        overlay = np.zeros_like(canvas)
        for idx, color in enumerate(mood[:4]):
            cx = w * (0.2 + 0.2 * idx)
            cy = h * (0.15 + 0.18 * (idx % 3))
            _stamp_blob(overlay, cx, cy, w * 0.28, h * 0.22, color, 0.22, 1.4)
        a = overlay[..., 3]
        for i in range(3):
            canvas[..., i] = canvas[..., i] * (1 - a * 0.55) + overlay[..., i] * a * 0.55


def _bokeh(canvas: np.ndarray, rng: np.random.Generator, color: RGB, count: int, y_frac: float = 0.55) -> None:
    h, w = canvas.shape[:2]
    for _ in range(count):
        _stamp_blob(
            canvas, float(rng.uniform(0, w)), float(rng.uniform(0, h * y_frac)),
            float(rng.uniform(8, 28) * (w / 512)), float(rng.uniform(8, 26) * (w / 512)),
            color, float(rng.uniform(0.08, 0.22)), 1.8, 0.2,
        )


def _curtains(canvas: np.ndarray, color: RGB, rng: np.random.Generator) -> None:
    h, w = canvas.shape[:2]
    for i in range(7):
        x = w * (i + 0.5) / 7
        shade = _shade(color, 0.15 + 0.08 * (i % 2))
        _stamp_capsule(canvas, x, 0, x + rng.uniform(-8, 8), h * 0.92, w * 0.08, shade, 0.7)
        _stamp_capsule(canvas, x - w * 0.02, 0, x - w * 0.01, h * 0.9, w * 0.015, _tint(color, 0.12), 0.35)


def _city_windows(canvas: np.ndarray, rng: np.random.Generator, gold: RGB) -> None:
    h, w = canvas.shape[:2]
    horizon = int(h * 0.58)
    for x in range(0, w, max(6, w // 40)):
        bh = int(rng.integers(h * 0.12, h * 0.38))
        bw = int(rng.integers(8, 22) * w / 512)
        _stamp_blob(canvas, x + bw * 0.5, horizon - bh * 0.3, bw * 0.7, bh * 0.7, (8, 10, 22), 0.9, 1.2, 0.7)
        for _ in range(8):
            if rng.random() > 0.55:
                _stamp_blob(canvas, x + rng.uniform(0, bw), horizon - rng.uniform(0, bh),
                            1.6 * w / 512, 2.2 * w / 512, gold, 0.7, 2.0, 0.4)


def _vignette(canvas: np.ndarray, strength: float = 0.55) -> None:
    h, w = canvas.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    nx = (xx - w * 0.5) / (w * 0.62)
    ny = (yy - h * 0.42) / (h * 0.62)
    d = np.sqrt(nx * nx + ny * ny)
    v = np.clip((d - 0.55) / 0.85, 0.0, 1.0) ** 1.4 * strength
    canvas[..., :3] *= (1.0 - v)[..., None]


def _grain(canvas: np.ndarray, rng: np.random.Generator, amount: float = 0.045) -> None:
    noise = rng.normal(0.0, amount, canvas.shape[:2]).astype(np.float32)
    canvas[..., :3] = np.clip(canvas[..., :3] + noise[..., None], 0.0, 1.0)


def _value_noise(h: int, w: int, scale: int, rng: np.random.Generator) -> np.ndarray:
    gh, gw = h // scale + 2, w // scale + 2
    grid = rng.random((gh, gw)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    gy = yy / scale
    gx = xx / scale
    y0 = np.floor(gy).astype(np.int32)
    x0 = np.floor(gx).astype(np.int32)
    fy, fx = gy - y0, gx - x0
    n00 = grid[y0, x0]
    n10 = grid[y0 + 1, x0]
    n01 = grid[y0, x0 + 1]
    n11 = grid[y0 + 1, x0 + 1]
    return n00 * (1 - fy) * (1 - fx) + n10 * fy * (1 - fx) + n01 * (1 - fy) * fx + n11 * fy * fx


def _to_image(canvas: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(canvas * 255.0, 0, 255).astype(np.uint8), "RGBA")


def _paint_background(canvas: np.ndarray, recipe: CardRecipe, rng: np.random.Generator) -> None:
    mood = _mood_colors(recipe.mood_asset)
    _fill_gradient(canvas, recipe.bg_top, recipe.bg_bot, mood)
    h, w = canvas.shape[:2]
    name = recipe.bg
    if name in ("curtains", "throne", "jester_dark", "rose_room"):
        _curtains(canvas, _mix(recipe.bg_bot, recipe.cloth_rgb, 0.4), rng)
    if name in ("lounge_neon", "neon_pink", "neon_perch"):
        _bokeh(canvas, rng, recipe.glow, 18, 0.7)
        _stamp_capsule(canvas, w * 0.08, h * 0.2, w * 0.08, h * 0.85, 10, (220, 40, 140), 0.45)
        _stamp_capsule(canvas, w * 0.92, h * 0.15, w * 0.92, h * 0.8, 8, recipe.glow, 0.4)
    if name in ("spotlight", "spot", "encore", "cathedral", "gold_rain"):
        _stamp_blob(canvas, w * 0.5, h * -0.05, w * 0.45, h * 0.4, recipe.glow, 0.35, 1.2, 0.2)
        _bokeh(canvas, rng, recipe.glow, 12, 0.45)
    if name in ("void", "moonlit", "rift", "abyss"):
        _stamp_blob(canvas, w * 0.5, h * 0.45, w * 0.4, h * 0.4, recipe.glow, 0.18, 1.3, 0.2)
    if name in ("storm_gold", "dual_fire"):
        for _ in range(10):
            x = float(rng.uniform(w * 0.1, w * 0.9))
            _stamp_capsule(canvas, x, float(rng.uniform(0, h * 0.4)), x + rng.uniform(-40, 40), h * 0.9,
                           float(rng.uniform(4, 12)), recipe.glow, 0.2)
    if name in ("penthouse", "city_posters", "club_door"):
        _city_windows(canvas, rng, recipe.accent)
    if name == "grow_mood":
        for i in range(5):
            _stamp_blob(canvas, w * (0.15 + i * 0.18), h * 0.22, 28, 8, (180, 80, 255), 0.35, 2.0, 0.4)
            _stamp_blob(canvas, w * (0.15 + i * 0.18), h * 0.55, 22, 40, (40, 120, 50), 0.25, 2.0, 0.4)
    if name in ("vault_glow", "open_vault"):
        _stamp_blob(canvas, w * 0.5, h * 0.55, w * 0.42, h * 0.42, recipe.accent, 0.25, 1.6, 0.3)
        _stamp_blob(canvas, w * 0.5, h * 0.55, w * 0.28, h * 0.28, (20, 14, 10), 0.55, 1.4, 0.6)
    if name == "backstage":
        for i, col in enumerate(((255, 80, 80), (80, 255, 120), (80, 120, 255))):
            _stamp_blob(canvas, w * (0.2 + i * 0.3), h * 0.12, 40, 18, col, 0.4, 1.8, 0.3)
    if name == "busy_floor":
        _bokeh(canvas, rng, recipe.glow, 22, 0.75)
    if name == "carpet_lamps":
        _stamp_blob(canvas, w * 0.2, h * 0.18, 30, 18, (255, 200, 120), 0.35, 1.6, 0.3)
        _stamp_blob(canvas, w * 0.8, h * 0.18, 30, 18, (255, 200, 120), 0.35, 1.6, 0.3)
    if name == "heat":
        for _ in range(8):
            _stamp_blob(canvas, float(rng.uniform(w * 0.2, w * 0.8)), float(rng.uniform(h * 0.1, h * 0.7)),
                        float(rng.uniform(20, 50)), float(rng.uniform(40, 80)), recipe.glow, 0.12, 1.3, 0.15)
    if name in ("lip_close", "sheets", "chaos", "obsidian", "treasure", "sparks", "shrine", "clinic"):
        n = _value_noise(h, w, max(8, w // 24), rng)
        canvas[..., :3] *= 0.85 + 0.2 * n[..., None]
    if name == "throne":
        for i in range(6):
            ang = -0.4 + i * 0.18
            _stamp_capsule(canvas, w * 0.72, h * -0.05, w * (0.35 + ang), h * 0.9, 14, recipe.glow, 0.12)


def _layout(recipe: CardRecipe, size: int) -> dict[str, float]:
    s = size / 512.0
    pose = recipe.pose
    cx, head_y, hx, hy = size * 0.5, 168 * s, 92 * s, 112 * s
    if pose in ("three_left", "wink_left", "glance"):
        cx = size * 0.46
    elif pose == "three_right":
        cx = size * 0.54
    if pose == "command":
        head_y, hx, hy = 150 * s, 100 * s, 118 * s
    elif pose == "tower":
        head_y, hx, hy = 140 * s, 108 * s, 128 * s
    elif pose == "kiss_blow":
        head_y, hx, hy = 200 * s, 120 * s, 140 * s
    elif pose == "hero":
        head_y, hx, hy = 158 * s, 96 * s, 114 * s
    elif pose == "stoic":
        head_y, hx, hy = 150 * s, 100 * s, 118 * s
    elif pose == "soft":
        head_y = 180 * s
    elif pose == "intense":
        head_y, hx, hy = 190 * s, 100 * s, 120 * s
    elif pose == "dare":
        head_y = 160 * s
    elif pose == "impish":
        head_y, hx, hy = 220 * s, 70 * s, 78 * s
    return {"cx": cx, "head_y": head_y, "hx": hx, "hy": hy, "s": s, "size": float(size)}


def _ell(draw: ImageDraw.ImageDraw, cx: float, cy: float, rx: float, ry: float, fill: RGB, outline: RGB | None = None, width: int = 1) -> None:
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=fill, outline=outline, width=width)


def _poly(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], fill: RGB) -> None:
    draw.polygon([(int(x), int(y)) for x, y in pts], fill=fill)


def _line(draw: ImageDraw.ImageDraw, a: tuple[float, float], b: tuple[float, float], fill: RGB, width: int) -> None:
    draw.line((a, b), fill=fill, width=max(1, width))


def _paint_hair_mass(draw: ImageDraw.ImageDraw, cx: float, hy: float, hx: float, hyy: float, recipe: CardRecipe, s: float) -> None:
    c, d, hi = recipe.hair_rgb, _shade(recipe.hair_rgb, 0.28), _tint(recipe.hair_rgb, 0.22)
    style = recipe.hair
    if style in ("cascade", "crimson_crown", "heat_fall", "ready_mane", "cream_waves", "void_fall"):
        _ell(draw, cx, hy + 8 * s, hx * 1.28, hyy * 1.15, d)
        _ell(draw, cx, hy - 18 * s, hx * 1.18, hyy * 0.72, c)
        _poly(draw, [(cx - hx * 1.15, hy), (cx - hx * 1.55, hy + 210 * s), (cx - hx * 0.35, hy + 160 * s), (cx - hx * 0.7, hy + 20 * s)], c)
        _poly(draw, [(cx + hx * 1.15, hy), (cx + hx * 1.55, hy + 210 * s), (cx + hx * 0.35, hy + 160 * s), (cx + hx * 0.7, hy + 20 * s)], d)
        _ell(draw, cx - hx * 0.25, hy - 10 * s, 38 * s, 22 * s, hi)
    elif style in ("pink_bob", "kiss_curl", "stage_curl"):
        _ell(draw, cx, hy + 10 * s, hx * 1.35, hyy * 1.05, c)
        _ell(draw, cx - hx * 0.95, hy + 70 * s, 42 * s, 70 * s, d)
        _ell(draw, cx + hx * 1.0, hy + 70 * s, 42 * s, 70 * s, d)
        _ell(draw, cx - 8 * s, hy - 6 * s, hx * 1.05, 28 * s, c)
    elif style in ("platinum", "white_wisps", "gold_coils", "teal_kelp"):
        _ell(draw, cx + 16 * s, hy + 6 * s, hx * 1.4, hyy * 1.2, c)
        _poly(draw, [(cx + hx * 0.2, hy - 40 * s), (cx + hx * 1.6, hy + 40 * s), (cx + hx * 1.3, hy + 160 * s), (cx + 10 * s, hy + 40 * s)], hi)
    elif style in ("slick", "side_part", "fade", "slick_short", "undercut", "leaf_crop"):
        _ell(draw, cx, hy - 18 * s, hx * 1.02, hyy * 0.55, d)
        _ell(draw, cx, hy - 28 * s, hx * 0.85, 24 * s, c)
    elif style == "buzz":
        _ell(draw, cx, hy - 8 * s, hx * 0.98, hyy * 0.42, _mix(c, recipe.skin, 0.4))
    elif style in ("pixie", "dare_spike", "spark_crest"):
        _ell(draw, cx, hy - 10 * s, hx * 1.1, hyy * 0.55, c)
        for i in range(-3, 4):
            _poly(draw, [(cx + i * 16 * s, hy - 8 * s), (cx + i * 18 * s, hy - 55 * s), (cx + i * 22 * s, hy - 8 * s)], hi if i == 0 else c)
    elif style == "pony":
        _ell(draw, cx, hy - 8 * s, hx * 1.05, hyy * 0.5, c)
        _ell(draw, cx + 58 * s, hy + 8 * s, 36 * s, 70 * s, d)
    elif style == "messy_bun":
        _ell(draw, cx, hy - 8 * s, hx * 0.9, hyy * 0.4, d)
        _ell(draw, cx + 8 * s, hy - 58 * s, 48 * s, 42 * s, c)
    elif style == "updo":
        _ell(draw, cx, hy - 50 * s, 62 * s, 48 * s, c)
        _ell(draw, cx, hy - 8 * s, hx * 0.95, 22 * s, d)
    elif style == "cap_hair":
        _ell(draw, cx, hy - 10 * s, hx * 1.05, hyy * 0.42, d)
        _ell(draw, cx, hy - 36 * s, hx * 1.12, 22 * s, (24, 20, 22))
        _poly(draw, [(cx - 28 * s, hy - 48 * s), (cx, hy - 70 * s), (cx + 28 * s, hy - 48 * s)], (24, 20, 22))


def _paint_hair_wrap(draw: ImageDraw.ImageDraw, cx: float, hy: float, hx: float, hyy: float, recipe: CardRecipe, s: float) -> None:
    c, d, hi = recipe.hair_rgb, _shade(recipe.hair_rgb, 0.22), _tint(recipe.hair_rgb, 0.28)
    style = recipe.hair
    _ell(draw, cx, hy - hyy * 0.62, hx * 1.2, hyy * 0.58, c)
    _ell(draw, cx, hy - hyy * 0.72, hx * 1.0, hyy * 0.4, d)
    if style in ("cascade", "crimson_crown", "heat_fall", "ready_mane", "cream_waves", "void_fall", "pink_bob", "kiss_curl", "stage_curl", "platinum", "teal_kelp"):
        _ell(draw, cx - hx * 0.55, hy + 2 * s, 44 * s, 22 * s, c)
        _ell(draw, cx + hx * 0.58, hy - 2 * s, 36 * s, 18 * s, d)
        for i in range(8):
            side = -1 if i % 2 == 0 else 1
            _line(draw, (cx + side * hx * 0.92, hy + (8 + i * 4) * s),
                  (cx + side * hx * (1.15 + (i % 3) * 0.1), hy + (90 + i * 14) * s),
                  hi if i % 3 == 0 else c, int((12 - i * 0.6) * s))
    elif style in ("slick", "side_part", "fade", "slick_short", "undercut", "leaf_crop", "buzz", "cap_hair"):
        _ell(draw, cx, hy - hyy * 0.48, hx * 1.08, hyy * 0.48, c)
        _line(draw, (cx - hx * 0.55, hy - hyy * 0.32), (cx + hx * 0.65, hy - hyy * 0.42), hi, int(8 * s))
    elif style in ("pony", "messy_bun", "updo", "gold_coils"):
        _ell(draw, cx, hy - hyy * 0.35, hx * 1.1, hyy * 0.45, c)
    elif style in ("pixie", "dare_spike", "spark_crest"):
        _ell(draw, cx, hy - hyy * 0.4, hx * 1.12, hyy * 0.5, c)


def _paint_body(draw: ImageDraw.ImageDraw, cx: float, hy: float, hx: float, hyy: float, recipe: CardRecipe, s: float) -> None:
    cloth, acc, dark = recipe.cloth_rgb, recipe.accent, _shade(recipe.cloth_rgb, 0.35)
    neck_y = hy + hyy * 0.72
    _ell(draw, cx, neck_y + 16 * s, 24 * s, 32 * s, _shade(recipe.skin, 0.08))
    sy = neck_y + 36 * s
    sw, bh = 155 * s, 210 * s
    body = recipe.clothing
    if body in ("throne_gown", "velvet_scoop", "idol_gown", "champion", "scale_cape", "satin_lace", "satin_bunny", "booth_satin", "chair_grip"):
        sw = 175 * s
        _poly(draw, [(cx - sw * 0.55, sy), (cx + sw * 0.55, sy), (cx + sw, sy + bh), (cx - sw, sy + bh)], cloth)
        _poly(draw, [(cx - 28 * s, neck_y), (cx + 28 * s, neck_y), (cx + 70 * s, sy + 50 * s), (cx - 70 * s, sy + 50 * s)], _shade(recipe.skin, 0.04))
        _line(draw, (cx - 70 * s, sy + 8 * s), (cx - 20 * s, neck_y + 8 * s), acc, int(8 * s))
        _line(draw, (cx + 70 * s, sy + 8 * s), (cx + 20 * s, neck_y + 8 * s), acc, int(8 * s))
        if body == "idol_gown":
            _poly(draw, [(cx - sw, sy + 40 * s), (cx + sw, sy + 20 * s), (cx + sw, sy + 80 * s), (cx - sw, sy + 90 * s)], acc)
        if body == "satin_bunny":
            _ell(draw, cx, sy + 30 * s, 55 * s, 28 * s, _tint(cloth, 0.2))
        if body == "scale_cape":
            for i in range(6):
                _ell(draw, cx + (i - 2.5) * 28 * s, sy + 20 * s + (i % 2) * 16 * s, 18 * s, 14 * s, _mix(cloth, acc, 0.4))
    elif body in ("leather_v", "black_crew", "waiter_vest", "gold_vest", "tux_guard", "velvet_blazer", "fire_jacket", "bomber", "long_coat", "split_coat", "thief_gloves", "spotlight_fit", "lab_coat", "wrath_collar"):
        _poly(draw, [(cx - sw * 0.62, sy), (cx + sw * 0.62, sy), (cx + sw * 0.95, sy + bh), (cx - sw * 0.95, sy + bh)], cloth)
        if body == "leather_v":
            _poly(draw, [(cx - 22 * s, neck_y + 4 * s), (cx + 22 * s, neck_y + 4 * s), (cx, sy + 70 * s)], (16, 14, 16))
            _line(draw, (cx - 80 * s, sy + 20 * s), (cx - 50 * s, sy + 110 * s), (190, 190, 200), int(5 * s))
        elif body == "waiter_vest":
            _poly(draw, [(cx - 48 * s, sy + 8 * s), (cx + 48 * s, sy + 8 * s), (cx + 40 * s, sy + 130 * s), (cx - 40 * s, sy + 130 * s)], (16, 14, 16))
            _ell(draw, cx - 10 * s, sy + 24 * s, 6 * s, 6 * s, acc)
            _ell(draw, cx + 10 * s, sy + 24 * s, 6 * s, 6 * s, acc)
            _poly(draw, [(cx - 16 * s, neck_y), (cx + 16 * s, neck_y), (cx + 18 * s, sy + 10 * s), (cx - 18 * s, sy + 10 * s)], (240, 236, 230))
        elif body == "gold_vest":
            _poly(draw, [(cx - 52 * s, sy), (cx + 52 * s, sy), (cx + 44 * s, sy + 120 * s), (cx - 44 * s, sy + 120 * s)], acc)
        elif body == "tux_guard":
            _line(draw, (cx, neck_y), (cx, sy + 140 * s), (230, 230, 235), int(10 * s))
            _ell(draw, cx - 22 * s, sy + 18 * s, 8 * s, 8 * s, acc)
        elif body == "fire_jacket":
            _poly(draw, [(cx - 18 * s, neck_y), (cx + 18 * s, neck_y), (cx + 24 * s, sy + 40 * s), (cx - 24 * s, sy + 40 * s)], (24, 12, 12))
        elif body == "long_coat":
            _poly(draw, [(cx - sw * 0.8, sy - 10 * s), (cx + sw * 0.8, sy - 10 * s), (cx + sw * 1.05, sy + bh), (cx - sw * 1.05, sy + bh)], dark)
        elif body == "bomber":
            _line(draw, (cx - 90 * s, sy + 28 * s), (cx + 90 * s, sy + 28 * s), acc, int(10 * s))
        elif body == "velvet_blazer":
            _poly(draw, [(cx - 16 * s, neck_y), (cx + 16 * s, neck_y), (cx + 20 * s, sy + 16 * s), (cx - 20 * s, sy + 16 * s)], (220, 210, 200))
        elif body == "split_coat":
            _poly(draw, [(cx - sw * 0.9, sy), (cx, sy + 10 * s), (cx, sy + bh), (cx - sw, sy + bh)], (110, 18, 24))
            _poly(draw, [(cx + sw * 0.9, sy), (cx, sy + 10 * s), (cx, sy + bh), (cx + sw, sy + bh)], (32, 14, 52))
        elif body == "lab_coat":
            _poly(draw, [(cx - sw * 0.7, sy), (cx + sw * 0.7, sy), (cx + sw * 0.85, sy + bh), (cx - sw * 0.85, sy + bh)], (220, 222, 210))
            _poly(draw, [(cx - 20 * s, neck_y), (cx + 20 * s, neck_y), (cx + 16 * s, sy + 50 * s), (cx - 16 * s, sy + 50 * s)], (40, 90, 48))
        elif body == "wrath_collar":
            _poly(draw, [(cx - 70 * s, neck_y - 6 * s), (cx + 70 * s, neck_y - 6 * s), (cx + 50 * s, sy + 20 * s), (cx - 50 * s, sy + 20 * s)], acc)
        elif body == "thief_gloves":
            _ell(draw, cx + 95 * s, sy + 90 * s, 36 * s, 24 * s, (18, 16, 16))
    elif body in ("silk_robe", "pale_silk"):
        _poly(draw, [(cx - sw * 0.7, sy), (cx + sw * 0.7, sy), (cx + sw * 0.95, sy + bh), (cx - sw * 0.5, sy + bh)], cloth)
        _line(draw, (cx - 8 * s, neck_y + 8 * s), (cx + 50 * s, sy + 120 * s), acc, int(12 * s))
    else:
        _poly(draw, [(cx - sw * 0.65, sy), (cx + sw * 0.65, sy), (cx + sw, sy + bh), (cx - sw, sy + bh)], cloth)


def _paint_head_face(draw: ImageDraw.ImageDraw, cx: float, hy: float, hx: float, hyy: float, recipe: CardRecipe, s: float, *, features_only: bool = False) -> None:
    skin, shadow, hi = recipe.skin, _shade(recipe.skin, 0.22), _tint(recipe.skin, 0.18)
    if not features_only:
        _ell(draw, cx + 10 * s, hy + 14 * s, hx * 0.98, hyy * 1.02, shadow)
        _ell(draw, cx, hy, hx, hyy, skin)
        _ell(draw, cx - hx * 0.22, hy - hyy * 0.18, hx * 0.45, hyy * 0.38, hi)
        _ell(draw, cx - hx * 0.95, hy + hyy * 0.12, 16 * s, 24 * s, skin)
        _ell(draw, cx + hx * 0.95, hy + hyy * 0.12, 16 * s, 24 * s, skin)
    blush = _mix(skin, recipe.lip, 0.4)
    _ell(draw, cx - hx * 0.42, hy + hyy * 0.28, 24 * s, 14 * s, blush)
    _ell(draw, cx + hx * 0.42, hy + hyy * 0.28, 24 * s, 14 * s, blush)
    _ell(draw, cx + 2 * s, hy + hyy * 0.18, 9 * s, 16 * s, _shade(skin, 0.12))
    wink = "wink" in recipe.extras or recipe.pose == "wink_left"
    eye_y = hy - hyy * 0.02
    for i, side in enumerate((-1.0, 1.0)):
        ex = cx + side * hx * 0.34
        if wink and i == 0:
            _line(draw, (ex - 16 * s, eye_y + 4 * s), (ex + 16 * s, eye_y), _shade(skin, 0.4), int(5 * s))
            continue
        _ell(draw, ex, eye_y + 4 * s, 20 * s, 13 * s, (24, 16, 16))
        _ell(draw, ex, eye_y + 3 * s, 17 * s, 11 * s, (244, 238, 230))
        _ell(draw, ex + 3 * s, eye_y + 3 * s, 9 * s, 9 * s, recipe.eye)
        _ell(draw, ex + 3 * s, eye_y + 3 * s, 4 * s, 4 * s, (12, 10, 12))
        _ell(draw, ex + 6 * s, eye_y - 1 * s, 3 * s, 3 * s, (255, 255, 255))
    brow = _shade(recipe.hair_rgb, 0.1)
    _line(draw, (cx - hx * 0.52, eye_y - 18 * s), (cx - hx * 0.12, eye_y - 20 * s), brow, int(6 * s))
    _line(draw, (cx + hx * 0.12, eye_y - 20 * s), (cx + hx * 0.52, eye_y - 16 * s), brow, int(6 * s))
    my = hy + hyy * 0.48
    if recipe.pose == "kiss_blow":
        _ell(draw, cx, my, 22 * s, 16 * s, recipe.lip)
    elif recipe.pose == "pierce":
        _ell(draw, cx, my, 24 * s, 9 * s, recipe.lip)
    else:
        smile = recipe.pose in ("front_smile", "front_smirk", "command", "soft", "hero", "regal")
        _ell(draw, cx, my, 26 * s, 12 * s if smile else 9 * s, recipe.lip)
        _ell(draw, cx, my - 3 * s, 16 * s, 5 * s, _tint(recipe.lip, 0.28))
    if "stubble" in recipe.extras:
        _ell(draw, cx, my + 22 * s, 44 * s, 24 * s, _mix(skin, (36, 24, 20), 0.45))
    if "shades" in recipe.extras:
        _ell(draw, cx, eye_y + 4 * s, 52 * s, 16 * s, (16, 14, 18))


def _paint_jewelry_props(draw: ImageDraw.ImageDraw, cx: float, hy: float, hx: float, hyy: float, recipe: CardRecipe, s: float, rng: np.random.Generator, size: int) -> None:
    gold = recipe.accent
    extras = recipe.extras
    if "tall_crown" in extras:
        band_y = hy - hyy * 0.62
        _poly(draw, [(cx - hx * 0.95, band_y + 12 * s), (cx + hx * 0.95, band_y + 12 * s), (cx + hx * 0.85, band_y + 32 * s), (cx - hx * 0.85, band_y + 32 * s)], gold)
        for ox, ht in ((-0.7, 70), (-0.35, 100), (0.0, 130), (0.35, 100), (0.7, 70)):
            _poly(draw, [(cx + ox * hx - 12 * s, band_y + 8 * s), (cx + ox * hx, band_y - ht * s), (cx + ox * hx + 12 * s, band_y + 8 * s)], gold)
        _ell(draw, cx, band_y - 20 * s, 16 * s, 20 * s, (160, 18, 36))
    if "small_crown" in extras:
        _poly(draw, [(cx - 48 * s, hy - hyy * 0.7), (cx, hy - hyy * 1.05), (cx + 48 * s, hy - hyy * 0.7), (cx + 40 * s, hy - hyy * 0.55), (cx - 40 * s, hy - hyy * 0.55)], gold)
    if "scale_crown" in extras:
        for i in range(5):
            _ell(draw, cx + (i - 2) * 22 * s, hy - hyy * 0.72, 16 * s, 22 * s, recipe.hair_rgb)
            _ell(draw, cx + (i - 2) * 22 * s, hy - hyy * 0.72, 6 * s, 8 * s, gold)
    if "headset" in extras:
        _line(draw, (cx - hx * 1.05, hy), (cx + hx * 1.05, hy), (36, 36, 42), int(8 * s))
        _ell(draw, cx - hx * 1.08, hy + 20 * s, 16 * s, 20 * s, (28, 28, 34))
        _ell(draw, cx - hx * 1.08, hy + 20 * s, 6 * s, 6 * s, (70, 220, 110))
    if "bunny_ears" in extras:
        for side in (-1, 1):
            _poly(draw, [(cx + side * 22 * s, hy - 10 * s), (cx + side * 48 * s, hy - 125 * s), (cx + side * 62 * s, hy - 10 * s)], recipe.hair_rgb)
            _poly(draw, [(cx + side * 28 * s, hy - 16 * s), (cx + side * 48 * s, hy - 108 * s), (cx + side * 54 * s, hy - 16 * s)], (232, 150, 164))
    if "horns" in extras:
        for side in (-1, 1):
            _poly(draw, [(cx + side * 20 * s, hy - 8 * s), (cx + side * 58 * s, hy - 90 * s), (cx + side * 36 * s, hy - 8 * s)], (130, 22, 28))
    if "gold_glasses" in extras:
        draw.ellipse((cx - hx * 0.32 - 20 * s, hy - 14 * s, cx - hx * 0.32 + 20 * s, hy + 14 * s), outline=gold, width=int(4 * s))
        draw.ellipse((cx + hx * 0.32 - 20 * s, hy - 14 * s, cx + hx * 0.32 + 20 * s, hy + 14 * s), outline=gold, width=int(4 * s))
        _line(draw, (cx - 18 * s, hy), (cx + 18 * s, hy), gold, int(3 * s))
    if "hoop" in extras:
        draw.ellipse((cx + hx * 0.78, hy + hyy * 0.2, cx + hx * 0.96, hy + hyy * 0.42), outline=(210, 210, 220), width=int(3 * s))
    if "chain" in extras or "gold_chains" in extras:
        _ell(draw, cx, hy + hyy * 0.92, 46 * s, 16 * s, gold)
        _ell(draw, cx, hy + hyy * 1.12, 10 * s, 12 * s, gold)
    if "choker" in extras or "ruby_collar" in extras:
        _line(draw, (cx - 32 * s, hy + hyy * 0.78), (cx + 32 * s, hy + hyy * 0.78), gold, int(8 * s))
        _ell(draw, cx, hy + hyy * 0.84, 12 * s, 14 * s, (150, 18, 36))
    if "gold_drops" in extras or "silver_drops" in extras:
        drop = gold if "gold_drops" in extras else (186, 196, 214)
        for side in (-1, 1):
            _line(draw, (cx + side * hx * 0.92, hy + hyy * 0.12), (cx + side * hx * 0.96, hy + hyy * 0.48), drop, int(4 * s))
            _ell(draw, cx + side * hx * 0.96, hy + hyy * 0.55, 8 * s, 11 * s, (150, 20, 36) if "gold_drops" in extras else drop)
    if "lanyard" in extras:
        _line(draw, (cx - 22 * s, hy + hyy * 0.7), (cx - 8 * s, hy + hyy * 1.5), (170, 32, 42), int(6 * s))
    if "earpiece" in extras:
        _ell(draw, cx + hx * 0.98, hy + 6 * s, 9 * s, 12 * s, (40, 40, 46))
    if "bow" in extras:
        _ell(draw, cx + hx * 0.72, hy - 12 * s, 24 * s, 16 * s, (220, 36, 96))
        _ell(draw, cx + hx * 0.92, hy - 12 * s, 24 * s, 16 * s, (220, 36, 96))
    if "key_charm" in extras:
        _ell(draw, cx + 48 * s, hy + hyy * 0.95, 12 * s, 12 * s, gold)
        _line(draw, (cx + 48 * s, hy + hyy * 0.95), (cx + 48 * s, hy + hyy * 1.35), gold, int(5 * s))
    if "skull_jewel" in extras:
        _ell(draw, cx, hy + hyy * 0.88, 18 * s, 16 * s, gold)
    if "spark_crown" in extras:
        for i in range(7):
            _poly(draw, [(cx + (i - 3) * 16 * s - 6 * s, hy - hyy * 0.6), (cx + (i - 3) * 16 * s, hy - hyy * 0.95 - abs(i - 3) * 6 * s), (cx + (i - 3) * 16 * s + 6 * s, hy - hyy * 0.6)], recipe.glow)
    if "arm_up" in extras:
        _line(draw, (cx + 70 * s, hy + 90 * s), (cx + 120 * s, hy - 50 * s), recipe.skin, int(22 * s))
        _ell(draw, cx + 128 * s, hy - 58 * s, 22 * s, 20 * s, recipe.skin)
    if "chair" in extras:
        _line(draw, (cx - 100 * s, hy + 30 * s), (cx - 40 * s, hy + 170 * s), (70, 24, 28), int(16 * s))
    if "mic" in recipe.props:
        _line(draw, (cx + 52 * s, hy + 36 * s), (cx + 78 * s, hy + 150 * s), (36, 36, 42), int(8 * s))
        _ell(draw, cx + 48 * s, hy + 24 * s, 18 * s, 22 * s, (28, 28, 34))
    if "champagne_tray" in recipe.props:
        _ell(draw, cx + 100 * s, hy + 130 * s, 56 * s, 12 * s, gold)
        _line(draw, (cx + 82 * s, hy + 70 * s), (cx + 82 * s, hy + 128 * s), (230, 230, 236), int(7 * s))
        _ell(draw, cx + 82 * s, hy + 62 * s, 12 * s, 10 * s, (255, 240, 180))
    if "wallet" in recipe.props:
        draw.rounded_rectangle((cx + 70 * s, hy + 100 * s, cx + 125 * s, hy + 138 * s), radius=int(6 * s), fill=(42, 26, 20))
    if "holo_clip" in extras:
        draw.rounded_rectangle((cx + 58 * s, hy + 70 * s, cx + 108 * s, hy + 130 * s), radius=int(6 * s), fill=(70, 170, 255))
    if "guest_list" in extras:
        draw.rectangle((cx + 70 * s, hy + 60 * s, cx + 120 * s, hy + 140 * s), fill=(236, 228, 210))
    if "confetti" in extras:
        for _ in range(28):
            _ell(draw, float(rng.uniform(30, size - 30)), float(rng.uniform(20, size * 0.75)), float(rng.uniform(3, 9)), float(rng.uniform(2, 6)), gold if rng.random() > 0.5 else recipe.lip)
    if "coin_rain" in recipe.props:
        for _ in range(20):
            _ell(draw, float(rng.uniform(24, size - 24)), float(rng.uniform(16, size * 0.55)), 10 * s, 7 * s, gold)


def _paint_creature_pil(draw: ImageDraw.ImageDraw, recipe: CardRecipe, s: float, size: int) -> None:
    cx, cy = size * 0.5, size * 0.52
    if recipe.hair == "imp":
        _ell(draw, cx, cy + 40 * s, 80 * s, 90 * s, recipe.skin)
        _ell(draw, cx, cy - 30 * s, 64 * s, 66 * s, recipe.skin)
        for side in (-1, 1):
            _poly(draw, [(cx + side * 24 * s, cy - 50 * s), (cx + side * 62 * s, cy - 120 * s), (cx + side * 40 * s, cy - 46 * s)], (130, 20, 26))
        _ell(draw, cx, cy + 8 * s, 54 * s, 20 * s, recipe.accent)
        for side in (-1, 1):
            _ell(draw, cx + side * 22 * s, cy - 38 * s, 16 * s, 18 * s, (255, 230, 80))
            _ell(draw, cx + side * 22 * s, cy - 38 * s, 6 * s, 6 * s, (20, 10, 10))
        _ell(draw, cx, cy + 6 * s, 18 * s, 12 * s, recipe.lip)
    elif recipe.hair == "bird":
        _ell(draw, cx - 10 * s, cy + 16 * s, 78 * s, 58 * s, recipe.hair_rgb)
        _ell(draw, cx + 48 * s, cy - 12 * s, 40 * s, 38 * s, recipe.hair_rgb)
        _poly(draw, [(cx + 78 * s, cy - 8 * s), (cx + 128 * s, cy + 6 * s), (cx + 78 * s, cy + 16 * s)], (220, 170, 50))
        _ell(draw, cx + 54 * s, cy - 16 * s, 8 * s, 8 * s, recipe.eye)
        _line(draw, (cx + 16 * s, cy + 40 * s), (cx + 16 * s, cy + 130 * s), (170, 36, 48), int(12 * s))
        _ell(draw, cx + 16 * s, cy + 36 * s, 16 * s, 20 * s, (36, 110, 48))
        _ell(draw, cx + 4 * s, cy - 48 * s, 20 * s, 24 * s, recipe.accent)
    else:
        _ell(draw, cx - 10 * s, cy + 18 * s, 100 * s, 72 * s, recipe.hair_rgb)
        _ell(draw, cx + 78 * s, cy - 8 * s, 52 * s, 42 * s, recipe.hair_rgb)
        _poly(draw, [(cx + 120 * s, cy - 4 * s), (cx + 168 * s, cy + 10 * s), (cx + 118 * s, cy + 18 * s)], recipe.hair_rgb)
        _ell(draw, cx + 90 * s, cy - 14 * s, 10 * s, 10 * s, recipe.accent)
        _ell(draw, cx, cy - 10 * s, 44 * s, 16 * s, recipe.accent)


def _paint_still_pil(draw: ImageDraw.ImageDraw, recipe: CardRecipe, s: float, size: int, rng: np.random.Generator) -> None:
    gold = recipe.accent
    prop = recipe.props[0] if recipe.props else ""
    cx, cy = size * 0.5, size * 0.5
    if prop == "black_card":
        draw.rounded_rectangle((cx - 110 * s, cy - 150 * s, cx + 110 * s, cy + 150 * s), radius=int(18 * s), fill=(10, 10, 12), outline=gold, width=int(10 * s))
        _ell(draw, cx, cy - 10 * s, 22 * s, 22 * s, gold)
        _poly(draw, [(cx, cy - 40 * s), (cx + 18 * s, cy - 10 * s), (cx, cy + 20 * s), (cx - 18 * s, cy - 10 * s)], gold)
    elif prop == "crimson_lips":
        _ell(draw, cx, cy + 30 * s, 190 * s, 150 * s, (214, 168, 146))
        _ell(draw, cx, cy - 90 * s, 40 * s, 48 * s, (214, 168, 146))
        _poly(draw, [(cx - 130 * s, cy - 8 * s), (cx - 46 * s, cy - 48 * s), (cx, cy - 14 * s), (cx + 46 * s, cy - 48 * s), (cx + 130 * s, cy - 8 * s), (cx + 100 * s, cy + 22 * s), (cx - 100 * s, cy + 22 * s)], (150, 16, 36))
        _ell(draw, cx, cy + 52 * s, 140 * s, 58 * s, (128, 12, 30))
        _ell(draw, cx, cy + 40 * s, 90 * s, 18 * s, (70, 8, 18))
        _ell(draw, cx + 18 * s, cy + 6 * s, 48 * s, 14 * s, (255, 150, 150))
        _ell(draw, cx + 12 * s, cy + 68 * s, 56 * s, 16 * s, gold)
    elif prop == "silk_sheets":
        for i, col in enumerate(((210, 170, 148), (232, 196, 170), (180, 90, 90), gold, (255, 220, 180))):
            y = 80 * s + i * 70 * s
            _poly(draw, [(0, y), (size, y - 30 * s), (size, y + 50 * s), (0, y + 70 * s)], col)
    elif prop == "spilled_glass":
        _ell(draw, cx - 20 * s, cy + 90 * s, 160 * s, 40 * s, (210, 180, 70))
        _poly(draw, [(cx + 40 * s, cy - 80 * s), (cx + 90 * s, cy + 90 * s), (cx + 60 * s, cy + 96 * s), (cx + 20 * s, cy - 70 * s)], (230, 230, 240))
        for _ in range(22):
            _ell(draw, float(rng.uniform(40, size - 40)), float(rng.uniform(40, size - 40)), float(rng.uniform(4, 12)), float(rng.uniform(3, 8)), gold)
    elif prop == "bell":
        _ell(draw, cx, cy + 10 * s, 100 * s, 110 * s, gold)
        _ell(draw, cx, cy - 90 * s, 28 * s, 22 * s, gold)
        _ell(draw, cx, cy + 110 * s, 16 * s, 22 * s, gold)
        _line(draw, (cx - 90 * s, cy - 40 * s), (cx - 120 * s, cy + 90 * s), (160, 24, 40), int(10 * s))
        _line(draw, (cx + 90 * s, cy - 40 * s), (cx + 120 * s, cy + 90 * s), (36, 90, 40), int(10 * s))
    elif prop == "patch":
        draw.rounded_rectangle((cx - 130 * s, cy - 80 * s, cx + 130 * s, cy + 80 * s), radius=int(16 * s), fill=(236, 226, 214), outline=gold, width=int(8 * s))
        _line(draw, (cx - 90 * s, cy), (cx + 90 * s, cy), gold, int(10 * s))
        _ell(draw, cx, cy, 36 * s, 24 * s, (176, 48, 48))
    elif prop == "signet":
        _ell(draw, cx - 50 * s, cy, 90 * s, 58 * s, gold)
        _ell(draw, cx - 50 * s, cy, 32 * s, 26 * s, (120, 28, 28))
        for i in range(7):
            _ell(draw, cx + 40 * s + (i % 3) * 36 * s, cy - 30 * s + (i // 3) * 36 * s, 22 * s, 16 * s, gold)
    elif prop == "lucky_coin":
        _ell(draw, cx, cy, 120 * s, 120 * s, gold)
        _ell(draw, cx, cy, 88 * s, 88 * s, (150, 100, 28))
        _ell(draw, cx - 20 * s, cy - 24 * s, 24 * s, 14 * s, (255, 250, 220))
        for i in range(10):
            ang = i / 10 * 6.28
            _line(draw, (cx, cy), (cx + np.cos(ang) * 170 * s, cy + np.sin(ang) * 170 * s), gold, int(4 * s))
    elif prop == "void_heart":
        _ell(draw, cx - 55 * s, cy - 20 * s, 70 * s, 62 * s, (120, 36, 180))
        _ell(draw, cx + 55 * s, cy - 20 * s, 70 * s, 62 * s, (120, 36, 180))
        _poly(draw, [(cx - 118 * s, cy - 8 * s), (cx + 118 * s, cy - 8 * s), (cx, cy + 140 * s)], (80, 20, 140))
        _ell(draw, cx - 30 * s, cy - 30 * s, 22 * s, 16 * s, (230, 180, 255))
    elif prop == "vault_key":
        _ell(draw, cx - 90 * s, cy, 56 * s, 56 * s, gold)
        _ell(draw, cx - 90 * s, cy, 22 * s, 22 * s, (36, 10, 14))
        _line(draw, (cx - 40 * s, cy), (cx + 130 * s, cy), gold, int(18 * s))
        _line(draw, (cx + 110 * s, cy), (cx + 110 * s, cy + 36 * s), gold, int(14 * s))
        _line(draw, (cx + 130 * s, cy), (cx + 130 * s, cy + 28 * s), gold, int(14 * s))
    else:
        _ell(draw, cx, cy, 90 * s, 90 * s, gold)


def _shade_figure(layer: Image.Image, recipe: CardRecipe, rng: np.random.Generator) -> Image.Image:
    arr = np.asarray(layer, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    alpha = arr[..., 3]
    yy, xx = np.ogrid[:h, :w]
    light = np.clip(1.22 - np.sqrt((xx - w * 0.34) ** 2 + (yy - h * 0.22) ** 2) / w * 0.9, 0.52, 1.28)
    fabric = 0.86 + 0.22 * _value_noise(h, w, max(6, w // 40), rng)
    lit = light * fabric
    for i in range(3):
        arr[..., i] = np.clip(arr[..., i] * lit, 0.0, 1.0)
    sx = np.abs(np.diff(alpha, axis=1, prepend=alpha[:, :1]))
    sy = np.abs(np.diff(alpha, axis=0, prepend=alpha[:1, :]))
    edge = np.clip((sx + sy) * 1.6, 0.0, 1.0)
    glow = np.array(recipe.glow, dtype=np.float32) / 255.0
    for i in range(3):
        arr[..., i] = np.clip(arr[..., i] + edge * glow[i] * 0.28, 0.0, 1.0)
    return Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), "RGBA")


def _paint_figure_pil(recipe: CardRecipe, size: int, rng: np.random.Generator) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    s = size / 512.0
    if recipe.kind == "still":
        _paint_still_pil(draw, recipe, s, size, rng)
    elif recipe.kind == "creature":
        _paint_creature_pil(draw, recipe, s, size)
    else:
        L = _layout(recipe, size)
        cx, hy, hx, hyy = L["cx"], L["head_y"], L["hx"], L["hy"]
        _paint_hair_mass(draw, cx, hy, hx, hyy, recipe, s)
        _paint_body(draw, cx, hy, hx, hyy, recipe, s)
        _paint_head_face(draw, cx, hy, hx, hyy, recipe, s)
        _paint_hair_wrap(draw, cx, hy, hx, hyy, recipe, s)
        _paint_head_face(draw, cx, hy, hx, hyy, recipe, s, features_only=True)
        _paint_jewelry_props(draw, cx, hy, hx, hyy, recipe, s, rng, size)
        if "green_aura" in recipe.props:
            glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.ellipse((cx - 150 * s, hy - 80 * s, cx + 150 * s, hy + 210 * s), fill=(40, 220, 90, 55))
            layer = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)), layer)
    layer = layer.filter(ImageFilter.GaussianBlur(radius=0.85))
    layer = layer.filter(ImageFilter.SMOOTH_MORE)
    return _shade_figure(layer, recipe, rng)


def _px(n: int = 128) -> np.ndarray:
    return np.zeros((n, n, 3), dtype=np.uint8)


def _px_fill(a: np.ndarray, x: int, y: int, w: int, h: int, c: RGB) -> None:
    n = a.shape[0]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(n, x + w), min(n, y + h)
    if x1 > x0 and y1 > y0:
        a[y0:y1, x0:x1] = c


def _px_disc(a: np.ndarray, cx: int, cy: int, r: int, c: RGB) -> None:
    n = a.shape[0]
    y0, y1 = max(0, cy - r), min(n, cy + r + 1)
    x0, x1 = max(0, cx - r), min(n, cx + r + 1)
    yy, xx = np.ogrid[y0:y1, x0:x1]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    a[y0:y1, x0:x1][mask] = c


def _paint_pixel(recipe: CardRecipe, size: int, rng: np.random.Generator) -> Image.Image:
    a = _px(128)
    scene = recipe.scene
    top, bot, gold, cloth = recipe.bg_top, recipe.bg_bot, recipe.accent, recipe.cloth_rgb
    for y in range(128):
        t = y / 127
        a[y, :] = [int(top[i] + (bot[i] - top[i]) * t) for i in range(3)]
    if scene == "notice_board":
        _px_fill(a, 14, 10, 100, 108, (92, 54, 36))
        _px_fill(a, 18, 14, 92, 100, (120, 78, 48))
        notes = ((24, 22, (220, 200, 160)), (55, 30, (240, 230, 200)), (78, 18, (200, 60, 60)),
                 (30, 70, (230, 210, 170)), (62, 64, (80, 30, 30)), (86, 72, (220, 190, 140)))
        for x, y, c in notes:
            _px_fill(a, x, y, 22, 28, c)
            _px_fill(a, x + 8, y - 2, 4, 4, gold)
        for x0, y0, x1, y1 in ((34, 22, 66, 30), (66, 44, 90, 72), (40, 84, 74, 78)):
            for t in range(12):
                xx = int(x0 + (x1 - x0) * t / 11)
                yy = int(y0 + (y1 - y0) * t / 11)
                _px_fill(a, xx, yy, 2, 2, (160, 20, 28))
    elif scene == "felt_table":
        _px_fill(a, 0, 36, 128, 92, cloth)
        _px_fill(a, 6, 44, 116, 76, _shade(cloth, 0.12))
        _px_fill(a, 10, 48, 108, 68, _mix(cloth, (80, 10, 20), 0.2))
        for i, col in enumerate(((212, 168, 64), (240, 240, 245), (40, 40, 48), (180, 30, 40), (40, 90, 180))):
            x, y = 22 + i * 14, 70 + (i % 2) * 8
            _px_disc(a, x, y, 8, col)
            _px_disc(a, x, y - 4, 8, _tint(col, 0.2))
            _px_disc(a, x, y - 7, 7, col)
        _px_fill(a, 96, 60, 14, 14, (240, 236, 230))
        _px_fill(a, 99, 63, 3, 3, (20, 16, 16))
        _px_fill(a, 104, 68, 3, 3, (20, 16, 16))
        _px_fill(a, 109, 63, 3, 3, (20, 16, 16))
        _px_fill(a, 88, 78, 12, 12, (220, 40, 40))
        _px_fill(a, 92, 82, 3, 3, (240, 240, 245))
        _px_fill(a, 70, 52, 16, 22, (244, 240, 230))
        _px_fill(a, 74, 48, 16, 22, (244, 240, 230))
        _px_fill(a, 78, 54, 10, 14, (160, 24, 36))
        _px_fill(a, 18, 100, 10, 8, gold)
        _px_fill(a, 28, 104, 10, 8, gold)
    elif scene == "crew_night":
        _px_fill(a, 0, 90, 128, 38, (28, 18, 14))
        colors = ((36, 24, 28), (80, 20, 30), (24, 28, 40))
        for i, col in enumerate(colors):
            x = 28 + i * 34
            _px_fill(a, x, 48, 22, 50, col)
            _px_disc(a, x + 11, 40, 10, (180, 140, 110) if i != 1 else (120, 80, 60))
            _px_fill(a, x + 6, 70, 10, 6, gold)
    elif scene == "heist_vault":
        _px_fill(a, 18, 18, 92, 92, (36, 48, 56))
        _px_disc(a, 64, 64, 40, (50, 64, 72))
        _px_disc(a, 64, 64, 28, (20, 24, 28))
        for i in range(8):
            ang = i / 8 * 6.28
            _px_fill(a, int(64 + np.cos(ang) * 22), int(64 + np.sin(ang) * 22), 4, 4, gold)
        _px_fill(a, 20, 30, 90, 2, (80, 255, 220))
        _px_fill(a, 24, 80, 80, 2, (80, 255, 220))
        _px_fill(a, 48, 96, 14, 18, (18, 16, 20))
    elif scene == "cartel_lab":
        _px_fill(a, 0, 100, 128, 28, (40, 36, 32))
        for i in range(4):
            x = 16 + i * 28
            _px_fill(a, x, 20, 20, 6, (180, 80, 255))
            _px_fill(a, x + 2, 28, 16, 50, (40, 120, 50))
            _px_fill(a, x + 4, 36, 12, 36, (60, 160, 70))
        _px_fill(a, 50, 70, 28, 40, gold)
        _px_fill(a, 56, 62, 16, 12, gold)
    elif scene == "group_lounge":
        _px_fill(a, 8, 70, 112, 40, (90, 24, 32))
        _px_fill(a, 16, 64, 96, 16, (120, 36, 44))
        for i in range(5):
            x = 22 + i * 18
            _px_disc(a, x, 58, 8, (200, 160, 130) if i % 2 == 0 else (160, 110, 90))
            _px_fill(a, x - 6, 64, 12, 18, (60, 20, 28) if i != 2 else (140, 30, 40))
        _px_disc(a, 64, 40, 16, (255, 180, 80))
    elif scene == "token_alley":
        _px_fill(a, 0, 80, 128, 48, (28, 22, 36))
        _px_fill(a, 10, 20, 18, 70, (40, 30, 50))
        _px_fill(a, 100, 10, 20, 80, (30, 24, 44))
        _px_fill(a, 12, 28, 14, 8, (255, 40, 140))
        _px_disc(a, 64, 78, 18, gold)
        _px_disc(a, 64, 78, 10, (120, 80, 24))
        _px_fill(a, 40, 96, 48, 12, (50, 40, 30))
    elif scene == "brass_idol":
        _px_fill(a, 20, 90, 88, 20, (60, 40, 20))
        _px_fill(a, 36, 70, 56, 24, (140, 100, 40))
        _px_fill(a, 48, 40, 32, 36, (180, 130, 50))
        _px_disc(a, 64, 32, 16, (200, 150, 60))
        _px_fill(a, 24, 20, 8, 70, (255, 160, 40))
        _px_fill(a, 96, 24, 6, 64, (255, 160, 40))
    else:
        _px_disc(a, 64, 64, 30, gold)
    img = Image.fromarray(a, "RGB").resize((size, size), Image.Resampling.NEAREST).convert("RGBA")
    grain = Image.effect_noise((size, size), 12).convert("L")
    g = Image.merge("RGBA", (grain, grain, grain, Image.new("L", (size, size), 28)))
    return Image.alpha_composite(img, g)


def _finish(canvas: np.ndarray, recipe: CardRecipe, rng: np.random.Generator) -> Image.Image:
    _vignette(canvas, 0.5 if recipe.kind != "pixel" else 0.25)
    _grain(canvas, rng, 0.035)
    img = _to_image(canvas)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.55))
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.12 if recipe.kind == "bust" else 1.06)
    return img


def render_card_art(card: CardDefinition, size: int = PORTRAIT_SIZE) -> Image.Image:
    """Original 512 plate for this catalog id. Never crops a boss/brand file."""
    recipe = CARD_RECIPES[card.card_id]
    rng = _rng(card.card_id)
    if recipe.kind == "pixel":
        return _paint_pixel(recipe, size, rng)
    canvas = _canvas(size)
    _paint_background(canvas, recipe, rng)
    bg = _finish(canvas, recipe, rng)
    figure = _paint_figure_pil(recipe, size, rng)
    return Image.alpha_composite(bg.convert("RGBA"), figure)

