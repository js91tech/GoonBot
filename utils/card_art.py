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
from PIL import Image, ImageEnhance, ImageFilter

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
    # --- Lust expansion (100) ---
    'card_slow_stroke': CardRecipe(
        "bust", 'femme', 'cascade', (20, 0, 22), (178, 163, 166), (118, 13, 60), (8, 19, 46),
        'velvet_scoop', (55, 0, 43), (247, 191, 73), 'curtains', (2, 21, 20), (84, 25, 30),
        (255, 171, 65), 'front_smile', ('gold_drops', 'choker'), ('necklace',),
        'bosses/glam/velvet_vixen_normal.png',
    ),
    'card_hold_it': CardRecipe(
        "bust", 'masc', 'pixie', (0, 15, 57), (195, 193, 137), (135, 43, 3), (25, 49, 9),
        'black_crew', (72, 24, 86), (184, 141, 36), 'backstage', (19, 15, 27), (101, 0, 13),
        (209, 201, 108), 'three_left', ('headset', 'lanyard'), ('gel_lights',),
        'bosses/glam/velvet_vixen_enraged.png',
    ),
    'card_not_yet': CardRecipe(
        "bust", 'andro', 'slick', (0, 45, 0), (166, 101, 58), (152, 73, 46), (42, 0, 52),
        'leather_v', (89, 54, 19), (201, 171, 79), 'lounge_neon', (36, 9, 0), (58, 25, 56),
        (226, 131, 51), 'front_smirk', ('stubble', 'hoop', 'chain'), ('green_aura',),
        'bosses/glam/velvet_vixen_mythic.png',
    ),
    'card_meter_pulse': CardRecipe(
        "bust", 'femme', 'void_fall', (71, 71, 11), (229, 181, 151), (169, 3, 89), (59, 29, 15),
        'black_high', (106, 0, 62), (218, 201, 42), 'void', (17, 3, 5), (75, 0, 39),
        (243, 161, 94), 'three_right', ('silver_drops', 'cold_rim'), (),
        'bosses/glam/velvet_vixen_shadow.png',
    ),
    'card_edge_queen': CardRecipe(
        "bust", 'masc', 'pink_bob', (30, 0, 46), (246, 139, 122), (186, 33, 32), (76, 59, 58),
        'satin_lace', (123, 4, 0), (235, 151, 85), 'neon_pink', (34, 0, 12), (92, 25, 22),
        (255, 191, 37), 'wink_left', ('bow', 'wink'), ('neon_tubes',),
        'bosses/glam/velvet_vixen_celestial.png',
    ),
    'card_denial_coach': CardRecipe(
        "bust", 'andro', 'platinum', (47, 0, 89), (191, 169, 165), (203, 63, 75), (13, 9, 21),
        'wrath_collar', (140, 34, 38), (252, 181, 48), 'storm_gold', (15, 0, 19), (109, 0, 5),
        (255, 121, 80), 'pierce', ('skull_jewel', 'gold_filigree'), ('gold_wisps',),
        'bosses/armored/velvet_vixen_normal.png',
    ),
    'card_leak_scare': CardRecipe(
        "bust", 'femme', 'teal_kelp', (122, 21, 0), (162, 149, 86), (120, 0, 18), (30, 39, 0),
        'scale_cape', (157, 64, 81), (189, 131, 91), 'abyss', (32, 21, 26), (66, 25, 48),
        (255, 151, 123), 'tower', ('scale_crown', 'fin_ear'), ('depth_rays',),
        'bosses/armored/velvet_vixen_enraged.png',
    ),
    'card_ruined_edge': CardRecipe(
        "bust", 'masc', 'crimson_crown', (81, 55, 35), (225, 157, 107), (137, 23, 61), (47, 0, 27),
        'throne_gown', (64, 0, 14), (206, 161, 54), 'throne', (13, 15, 0), (83, 0, 31),
        (211, 181, 66), 'command', ('tall_crown', 'ruby_collar'), ('god_rays',),
        'bosses/armored/velvet_vixen_shadow.png',
    ),
    'card_overstim': CardRecipe(
        "bust", 'andro', 'pony', (98, 85, 78), (242, 187, 150), (154, 53, 4), (64, 19, 0),
        'waiter_vest', (81, 14, 57), (223, 191, 97), 'busy_floor', (30, 9, 4), (100, 25, 14),
        (228, 111, 109), 'soft', ('vest_buttons',), ('champagne_tray',),
        'bosses/armored/velvet_vixen_mythic.png',
    ),
    'card_forever_edge': CardRecipe(
        "bust", 'femme', 'messy_bun', (33, 0, 0), (187, 145, 121), (171, 0, 47), (81, 49, 33),
        'satin_bunny', (98, 44, 0), (240, 141, 60), 'jester_dark', (11, 3, 11), (57, 0, 57),
        (245, 141, 52), 'cool', ('bunny_ears', 'key_charm'), ('spark',),
        'bosses/tomass.png',
    ),
    'card_booth_curtain': CardRecipe(
        "bust", 'masc', 'leaf_crop', (0, 5, 24), (158, 125, 114), (188, 13, 90), (18, 0, 0),
        'silk_robe', (115, 0, 33), (177, 171, 103), 'neon_perch', (28, 0, 18), (74, 25, 40),
        (255, 171, 95), 'pose_up', ('robe_tie',), ('bottle',),
        'bosses/zz_wrath.png',
    ),
    'card_lap_heat': CardRecipe(
        "bust", 'andro', 'slick_short', (9, 35, 67), (221, 133, 135), (205, 43, 33), (35, 29, 39),
        'lab_coat', (132, 0, 76), (194, 201, 66), 'vault_glow', (9, 0, 25), (91, 0, 23),
        (255, 201, 38), 'fade', ('gold_glasses', 'vials'), ('vault_ring',),
        'bosses/freaky_nikki/spawn.gif',
    ),
    'card_whisper_tip': CardRecipe(
        "bust", 'femme', 'stage_curl', (84, 61, 0), (238, 163, 106), (122, 73, 76), (52, 59, 2),
        'velvet_blazer', (149, 24, 9), (211, 151, 29), 'carpet_lamps', (26, 21, 0), (108, 25, 6),
        (255, 131, 81), 'warlord', ('holo_clip',), ('tip_jar',),
        'bosses/freaky_nikki/down.gif',
    ),
    'card_champagne_solo': CardRecipe(
        "bust", 'masc', 'side_part', (43, 0, 13), (183, 193, 149), (139, 3, 19), (69, 9, 45),
        'fire_jacket', (56, 54, 52), (228, 181, 72), 'rose_room', (7, 15, 3), (65, 0, 49),
        (213, 161, 124), 'regal', ('mic_stand',), ('steam',),
        'bosses/freaky_nikki/twist.gif',
    ),
    'card_private_dance': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (128, 35, 20), (255, 151, 76), 'grow_mood', (56, 21, 0), (50, 55, 30),
        (255, 181, 98), "scene", (), (), 'bosses/freaky_nikki/grab.gif', 'lap_booth',
    ),
    'card_one_way_glass': CardRecipe(
        "bust", 'femme', 'updo', (135, 11, 0), (217, 181, 163), (173, 63, 5), (23, 0, 51),
        'long_coat', (90, 4, 28), (182, 161, 78), 'penthouse', (5, 3, 17), (99, 0, 15),
        (247, 121, 110), 'stoic', ('shades',), ('city_windows',),
        'bosses/freaky_nikki/defeat.gif',
    ),
    'card_hands_on_knees': CardRecipe(
        "bust", 'masc', 'fade', (94, 45, 2), (234, 139, 134), (190, 0, 48), (40, 19, 14),
        'sequin', (107, 34, 71), (199, 191, 41), 'spotlight', (22, 0, 24), (56, 25, 58),
        (255, 151, 53), 'intense', ('sparkle',), ('mic',),
        'bosses/freaky_nikki/slap.gif',
    ),
    'card_closed_booth': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (99, 45, 69), (252, 161, 45), 'velvet_rope', (27, 31, 47), (101, 0, 0),
        (240, 191, 67), "scene", (), (), 'brand/goonbot-icon-explicit.png', 'private_booth',
    ),
    'card_velvet_lap': CardRecipe(
        "bust", 'femme', 'spark_crest', (46, 0, 96), (150, 149, 98), (124, 53, 34), (74, 0, 20),
        'pale_silk', (141, 0, 47), (233, 171, 47), 'alley', (20, 21, 2), (90, 25, 24),
        (255, 111, 39), 'kiss_blow', ('translucent',), ('neon_sign',),
        'brand/goonbot-banner-explicit.png',
    ),
    'card_after_hours': CardRecipe(
        "bust", 'masc', 'gold_coils', (5, 0, 0), (213, 157, 119), (141, 0, 77), (11, 29, 63),
        'split_coat', (158, 14, 90), (250, 201, 90), 'encore', (37, 15, 9), (107, 0, 7),
        (215, 141, 82), 'hero', ('spark_crown',), ('smoke',),
        'brand/goonbot-banner.png',
    ),
    'card_warmup_circle': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (70, 55, 38), (223, 171, 94), 'city_posters', (0, 41, 16), (72, 0, 48),
        (255, 201, 116), "scene", (), (), 'districts/downtown.png', 'group_floor',
    ),
    'card_floor_grind': CardRecipe(
        "bust", 'femme', 'buzz', (97, 51, 85), (247, 145, 133), (175, 43, 63), (45, 9, 0),
        'thief_gloves', (82, 0, 66), (204, 181, 96), 'moonlit', (35, 3, 23), (81, 0, 33),
        (249, 201, 68), 'look_back', ('cap', 'gloves'), ('mist',),
        'districts/financial.png',
    ),
    'card_crowd_breath': CardRecipe(
        "bust", 'masc', 'heat_fall', (56, 85, 0), (146, 125, 54), (192, 73, 6), (62, 39, 32),
        'tux_guard', (99, 0, 0), (221, 131, 59), 'dual_fire', (16, 0, 0), (98, 25, 16),
        (255, 131, 111), 'close_up', ('earpiece', 'lapel_pin'), ('embers',),
        'districts/industrial.png',
    ),
    'card_sweaty_spot': CardRecipe(
        "bust", 'andro', 'dare_spike', (73, 0, 23), (209, 133, 147), (209, 3, 49), (79, 0, 0),
        'chair_grip', (116, 24, 42), (238, 161, 102), 'cathedral', (33, 0, 1), (55, 0, 59),
        (255, 161, 54), 'front_smile', ('chair',), ('adoring_lights',),
        'districts/beachfront.png',
    ),
    'card_group_pulse': CardRecipe(
        "creature", "none", 'moth', (168, 171, 154), (144, 39, 56), (88, 7, 38), (223, 191, 94),
        "motley", (96, 7, 42), (180, 159, 70), 'crowd_blur', (0, 0, 24), (38, 7, 38),
        (223, 151, 54), "impish", ("horns",), ("spark",),
        'districts/residential.png',
    ),
    'card_hands_everywhere': CardRecipe(
        "bust", 'masc', 'ready_mane', (0, 35, 0), (243, 193, 161), (143, 63, 35), (33, 49, 1),
        'booth_satin', (150, 0, 18), (192, 141, 28), 'club_door', (31, 15, 15), (89, 0, 25),
        (217, 121, 40), 'front_smirk', ('kiss_hand',), ('door',),
        'drugs/grow_lab.png',
    ),
    'card_voyeur_rail': CardRecipe(
        "bust", 'andro', 'cream_waves', (0, 65, 12), (142, 101, 82), (160, 0, 78), (50, 0, 44),
        'champion', (57, 4, 61), (209, 171, 71), 'heat', (12, 9, 22), (106, 25, 8),
        (234, 151, 83), 'three_right', ('arm_up', 'small_crown'), ('haze',),
        'businesses/corporation.png',
    ),
    'card_full_floor': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (109, 25, 19), (255, 141, 75), 'spot', (37, 11, 0), (31, 45, 29),
        (250, 171, 97), "scene", (), (), 'businesses/chain_restaurant.png', 'group_floor',
    ),
    'card_house_heatwave': CardRecipe(
        "bust", 'masc', 'braids', (18, 0, 0), (222, 139, 146), (194, 53, 64), (84, 59, 50),
        'corset', (91, 64, 37), (243, 151, 77), 'rose_gold', (10, 0, 0), (80, 25, 34),
        (255, 111, 69), 'pierce', ('blindfold',), ('bokeh_warm',),
        'businesses/factory.png',
    ),
    'card_the_room_came': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (63, 5, 25), (216, 201, 81), 'gold_rain', (0, 0, 3), (65, 25, 35),
        (255, 151, 103), "scene", (), (), 'businesses/coffee_shop.png', 'group_floor',
    ),
    'card_silk_rope': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (130, 41, 82), (173, 189, 65), 'open_vault', (10, 17, 42), (75, 21, 35),
        (255, 121, 93), "macro", (), ('silk_rope',),
        'businesses/restaurant.png',
    ),
    'card_soft_cuffs': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (147, 0, 45), (190, 139, 28), 'wax_glow', (27, 0, 5), (92, 51, 0),
        (221, 151, 56), "macro", (), ('soft_cuffs',),
        'businesses/food_cart.png',
    ),
    'card_collar_click': CardRecipe(
        "bust", 'andro', 'wet_fall', (86, 0, 0), (218, 187, 174), (162, 73, 36), (72, 19, 62),
        'open_robe', (159, 0, 0), (231, 191, 89), 'rope_dark', (6, 9, 28), (88, 25, 26),
        (236, 131, 41), 'cool', ('fan',), ('green_aura',),
        'businesses/lemon_stand.png',
    ),
    'card_wax_play': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (101, 51, 51), (224, 199, 34), 'steam_bath', (0, 27, 11), (46, 31, 4),
        (255, 131, 62), "macro", (), ('wax_pool',),
        'bosses/glam/velvet_vixen_normal.png',
    ),
    'card_riding_crop': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (118, 1, 14), (241, 149, 77), 'booth_red', (0, 0, 0), (63, 0, 47),
        (255, 161, 105), "macro", (), ('riding_crop',),
        'bosses/glam/velvet_vixen_enraged.png',
    ),
    'card_blindfold_kiss': CardRecipe(
        "bust", 'andro', 'slick', (0, 55, 0), (197, 133, 159), (213, 63, 65), (43, 29, 31),
        'leather_v', (100, 54, 8), (202, 201, 58), 'altar_gold', (21, 0, 13), (79, 0, 35),
        (255, 121, 70), 'warlord', ('blindfold', 'collar'), ('gold_wisps',),
        'bosses/glam/velvet_vixen_mythic.png',
    ),
    'card_worship_kneel': CardRecipe(
        "bust", 'femme', 'void_fall', (72, 81, 30), (214, 163, 130), (130, 0, 8), (60, 59, 0),
        'black_high', (117, 0, 51), (219, 151, 101), 'curtains', (2, 21, 20), (96, 25, 18),
        (255, 151, 113), 'regal', ('opera_gloves', 'fan'), ('depth_rays',),
        'bosses/glam/velvet_vixen_shadow.png',
    ),
    'card_harness_night': CardRecipe(
        "bust", 'masc', 'pink_bob', (31, 0, 65), (231, 193, 173), (147, 23, 51), (77, 9, 37),
        'satin_lace', (134, 4, 0), (236, 181, 64), 'backstage', (19, 15, 27), (53, 0, 61),
        (221, 181, 56), 'glance', ('lace_mask', 'gold_drops'), ('god_rays',),
        'bosses/glam/velvet_vixen_celestial.png',
    ),
    'card_full_kit': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (56, 35, 12), (255, 151, 68), 'lounge_neon', (0, 21, 0), (58, 55, 22),
        (255, 181, 90), "scene", (), (), 'bosses/armored/velvet_vixen_normal.png', 'toy_drawer',
    ),
    'card_dungeon_hostess': CardRecipe(
        "bust", 'femme', 'teal_kelp', (123, 31, 19), (193, 181, 115), (181, 0, 37), (31, 0, 43),
        'scale_cape', (58, 64, 70), (190, 161, 70), 'void', (17, 3, 5), (87, 0, 27),
        (255, 141, 42), 'intense', ('headset', 'lanyard'), ('spark',),
        'bosses/armored/velvet_vixen_enraged.png',
    ),
    'card_water_bottle': CardRecipe(
        "bust", 'masc', 'crimson_crown', (82, 65, 54), (210, 139, 158), (198, 13, 80), (48, 19, 6),
        'throne_gown', (75, 0, 3), (207, 191, 33), 'neon_pink', (34, 0, 12), (104, 25, 10),
        (255, 171, 85), 'dare', ('stubble', 'hoop', 'chain'), ('bottle',),
        'bosses/armored/velvet_vixen_shadow.png',
    ),
    'card_soft_towel': CardRecipe(
        "bust", 'andro', 'pony', (99, 0, 0), (227, 169, 129), (215, 43, 23), (65, 49, 49),
        'waiter_vest', (92, 14, 46), (224, 141, 76), 'storm_gold', (15, 0, 19), (61, 0, 53),
        (255, 201, 128), 'kiss_blow', ('silver_drops', 'cold_rim'), ('vault_ring',),
        'bosses/armored/velvet_vixen_mythic.png',
    ),
    'card_hair_stroke': CardRecipe(
        "bust", 'femme', 'messy_bun', (34, 0, 8), (198, 149, 122), (132, 73, 66), (82, 0, 12),
        'satin_bunny', (109, 44, 89), (241, 171, 39), 'abyss', (32, 21, 26), (78, 25, 36),
        (206, 131, 71), 'hero', ('bow', 'wink'), ('tip_jar',),
        'bosses/tomass.png',
    ),
    'card_check_in': CardRecipe(
        "bust", 'masc', 'leaf_crop', (0, 15, 43), (189, 157, 143), (149, 3, 9), (19, 29, 55),
        'silk_robe', (126, 0, 22), (178, 201, 82), 'throne', (13, 15, 0), (95, 0, 19),
        (223, 161, 114), 'kneel_up', ('skull_jewel', 'gold_filigree'), ('steam',),
        'bosses/zz_wrath.png',
    ),
    'card_silk_two': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (128, 61, 44), (251, 129, 27), 'busy_floor', (8, 37, 4), (73, 41, 0),
        (255, 141, 55), "macro", (), ('satin_pillow',),
        'bosses/freaky_nikki/spawn.gif',
    ),
    'card_warm_oil': CardRecipe(
        "bust", 'femme', 'stage_curl', (85, 71, 0), (223, 145, 157), (183, 63, 95), (53, 9, 61),
        'velvet_blazer', (160, 24, 0), (212, 181, 88), 'jester_dark', (11, 3, 11), (69, 0, 45),
        (255, 121, 100), 'close_up', ('tall_crown', 'ruby_collar'), ('city_windows',),
        'bosses/freaky_nikki/down.gif',
    ),
    'card_quiet_praise': CardRecipe(
        "bust", 'masc', 'side_part', (44, 0, 32), (194, 125, 78), (200, 0, 38), (70, 39, 24),
        'fire_jacket', (67, 54, 41), (229, 131, 51), 'neon_perch', (28, 0, 18), (86, 25, 28),
        (255, 151, 43), 'front_smile', ('vest_buttons',), ('mic',),
        'bosses/freaky_nikki/twist.gif',
    ),
    'card_afterglow_bath': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (129, 0, 0), (255, 181, 55), 'vault_glow', (57, 0, 0), (51, 5, 9),
        (255, 131, 77), "scene", (), (), 'bosses/freaky_nikki/grab.gif', 'bath_steam',
    ),
    'card_held_til_dawn': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (66, 15, 42), (219, 211, 98), 'carpet_lamps', (0, 1, 20), (68, 35, 52),
        (255, 161, 120), "scene", (), (), 'bosses/freaky_nikki/defeat.gif', 'aftercare_bed',
    ),
    'card_house_aftercare': CardRecipe(
        "bust", 'masc', 'fade', (95, 55, 21), (219, 193, 113), (151, 0, 67), (41, 49, 0),
        'sequin', (118, 34, 60), (200, 141, 100), 'rose_room', (7, 15, 3), (77, 0, 37),
        (225, 141, 72), 'three_right', ('gold_glasses', 'vials'), ('smoke',),
        'bosses/freaky_nikki/slap.gif',
    ),
    'card_bare_shoulder': CardRecipe(
        "bust", 'andro', 'white_wisps', (0, 85, 64), (190, 101, 106), (168, 13, 10), (58, 0, 36),
        'bomber', (135, 64, 0), (217, 171, 63), 'grow_mood', (24, 9, 10), (94, 25, 20),
        (242, 171, 115), 'wink_left', ('holo_clip',), ('posters',),
        'brand/goonbot-icon-explicit.png',
    ),
    'card_hip_sway': CardRecipe(
        "bust", 'femme', 'spark_crest', (47, 0, 0), (181, 181, 127), (185, 43, 53), (75, 29, 0),
        'pale_silk', (152, 0, 36), (234, 201, 26), 'penthouse', (5, 3, 17), (51, 0, 3),
        (255, 201, 58), 'pierce', ('mic_stand',), ('mist',),
        'brand/goonbot-banner-explicit.png',
    ),
    'card_lip_bite': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (104, 61, 68), (227, 129, 51), 'spotlight', (0, 37, 28), (49, 41, 21),
        (255, 141, 79), "macro", (), ('lipstick_kiss',),
        'brand/goonbot-banner.png',
    ),
    'card_glove_peel': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (121, 11, 31), (244, 159, 94), 'velvet_rope', (1, 0, 0), (66, 0, 64),
        (255, 171, 42), "macro", (), ('glove_pair',),
        'districts/downtown.png',
    ),
    'card_corset_breath': CardRecipe(
        "bust", 'femme', 'buzz', (98, 61, 0), (186, 149, 62), (136, 33, 82), (46, 39, 48),
        'thief_gloves', (93, 0, 55), (205, 131, 75), 'alley', (20, 21, 2), (102, 25, 12),
        (210, 191, 87), 'soft', ('sparkle',), ('wallet',),
        'districts/financial.png',
    ),
    'card_thigh_high': CardRecipe(
        "bust", 'masc', 'heat_fall', (57, 0, 0), (249, 157, 155), (153, 63, 25), (63, 0, 11),
        'tux_guard', (110, 0, 0), (222, 161, 38), 'encore', (37, 15, 9), (59, 0, 55),
        (227, 121, 30), 'cool', ('gold_chains',), ('door',),
        'districts/industrial.png',
    ),
    'card_stage_strip': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (122, 15, 66), (255, 211, 42), 'city_posters', (50, 1, 44), (44, 35, 0),
        (255, 161, 64), "scene", (), (), 'districts/beachfront.png', 'cabaret_stage',
    ),
    'card_body_heat': CardRecipe(
        "bust", 'femme', 'kiss_curl', (149, 11, 93), (211, 145, 169), (187, 23, 11), (17, 49, 17),
        'spotlight_fit', (144, 54, 74), (176, 141, 44), 'moonlit', (35, 3, 23), (93, 0, 21),
        (255, 181, 116), 'fade', ('spark_crown',), ('spot_cone',),
        'districts/residential.png',
    ),
    'card_skin_spotlight': CardRecipe(
        "bust", 'masc', 'ready_mane', (0, 45, 0), (182, 125, 90), (204, 53, 54), (34, 0, 60),
        'booth_satin', (161, 0, 7), (193, 171, 87), 'dual_fire', (16, 0, 0), (50, 25, 4),
        (255, 111, 59), 'warlord', ('small_crown', 'gold_shoulder'), ('bokeh_warm',),
        'drugs/grow_lab.png',
    ),
    'card_the_body_show': CardRecipe(
        "bust", 'andro', 'cream_waves', (0, 75, 31), (245, 133, 111), (121, 0, 97), (51, 29, 23),
        'champion', (68, 4, 50), (210, 201, 50), 'cathedral', (33, 0, 1), (67, 0, 47),
        (255, 141, 102), 'regal', ('cap', 'gloves'), ('coin_rain',),
        'businesses/corporation.png',
    ),
    'card_keyhole': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (160, 61, 12), (203, 129, 75), 'crowd_blur', (40, 37, 0), (105, 41, 45),
        (234, 141, 103), "macro", (), ('keyhole_view',),
        'businesses/chain_restaurant.png',
    ),
    'card_mirror_wall': CardRecipe(
        "bust", 'masc', 'braids', (19, 0, 0), (207, 193, 125), (155, 43, 83), (85, 9, 29),
        'corset', (102, 64, 26), (244, 181, 56), 'club_door', (31, 15, 15), (101, 0, 13),
        (229, 201, 88), 'stoic', ('chair',), ('gel_lights',),
        'businesses/factory.png',
    ),
    'card_dark_seat': CardRecipe(
        "bust", 'andro', 'shaved_side', (36, 25, 20), (178, 101, 118), (172, 73, 26), (22, 39, 0),
        'latex', (119, 0, 69), (181, 131, 99), 'heat', (12, 9, 22), (58, 25, 56),
        (246, 131, 31), 'intense', ('confetti',), ('green_aura',),
        'businesses/coffee_shop.png',
    ),
    'card_camera_red': CardRecipe(
        "bust", 'femme', 'afro_halo', (111, 51, 71), (241, 181, 139), (189, 3, 69), (39, 0, 35),
        'towel', (136, 14, 2), (198, 161, 62), 'spot', (29, 3, 29), (75, 0, 39),
        (255, 161, 74), 'dare', ('kiss_hand',), (),
        'businesses/restaurant.png',
    ),
    'card_watch_watch': CardRecipe(
        "bust", 'masc', 'wet_slick', (70, 85, 0), (186, 139, 110), (206, 33, 12), (56, 19, 0),
        'mesh_top', (153, 44, 45), (215, 191, 25), 'rose_gold', (10, 0, 0), (92, 25, 22),
        (255, 191, 117), 'kiss_blow', ('arm_up', 'small_crown'), ('neon_tubes',),
        'businesses/food_cart.png',
    ),
    'card_two_way': CardRecipe(
        "bust", 'andro', 'wet_fall', (87, 0, 9), (203, 169, 153), (123, 63, 55), (73, 49, 41),
        'open_robe', (60, 0, 88), (232, 141, 68), 'gold_rain', (27, 0, 7), (109, 0, 5),
        (255, 121, 60), 'hero', ('collar',), ('gold_wisps',),
        'businesses/lemon_stand.png',
    ),
    'card_peep_show': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (52, 0, 16), (255, 191, 72), 'open_vault', (0, 0, 0), (54, 15, 26),
        (255, 141, 94), "scene", (), (), 'bosses/glam/velvet_vixen_normal.png', 'voyeur_window',
    ),
    'card_hidden_rail': CardRecipe(
        "bust", 'masc', 'pixie', (0, 35, 0), (237, 157, 167), (157, 23, 41), (27, 29, 47),
        'black_crew', (94, 24, 64), (186, 201, 74), 'wax_glow', (25, 15, 21), (83, 0, 31),
        (231, 181, 46), 'look_back', ('lace_mask',), ('god_rays',),
        'bosses/glam/velvet_vixen_enraged.png',
    ),
    'card_gallery_pass': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (136, 61, 36), (179, 129, 99), 'rope_dark', (16, 37, 0), (81, 41, 0),
        (255, 141, 47), "macro", (), ('compact_mirror',),
        'bosses/glam/velvet_vixen_mythic.png',
    ),
    'card_night_optics': CardRecipe(
        "creature", "none", 'cat', (53, 1, 53), (61, 17, 59), (133, 0, 53), (255, 181, 109),
        "motley", (141, 0, 57), (225, 149, 85), 'steam_bath', (29, 0, 39), (83, 0, 53),
        (255, 141, 69), "impish", ("bunny_ears",), ("spark",),
        'bosses/glam/velvet_vixen_shadow.png',
    ),
    'card_hands_off': CardRecipe(
        "bust", 'masc', 'pink_bob', (32, 0, 84), (170, 125, 102), (208, 13, 70), (78, 39, 16),
        'satin_lace', (145, 4, 83), (237, 131, 43), 'booth_red', (4, 0, 6), (74, 25, 40),
        (255, 171, 75), 'three_left', ('fan',), ('bottle',),
        'bosses/glam/velvet_vixen_celestial.png',
    ),
    'card_wait': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (107, 0, 85), (230, 139, 68), 'altar_gold', (0, 0, 45), (52, 51, 38),
        (255, 151, 96), "macro", (), ('edge_timer',),
        'bosses/armored/velvet_vixen_normal.png',
    ),
    'card_permission': CardRecipe(
        "bust", 'femme', 'teal_kelp', (124, 41, 38), (178, 163, 166), (142, 73, 56), (32, 19, 22),
        'scale_cape', (69, 64, 59), (191, 191, 49), 'curtains', (2, 21, 20), (108, 25, 6),
        (216, 131, 61), 'three_right', ('collar', 'pearls'), ('tip_jar',),
        'bosses/armored/velvet_vixen_enraged.png',
    ),
    'card_count_ten': CardRecipe(
        "bust", 'masc', 'crimson_crown', (83, 75, 73), (195, 193, 137), (159, 3, 0), (49, 49, 0),
        'throne_gown', (86, 0, 0), (208, 141, 92), 'backstage', (19, 15, 27), (65, 0, 49),
        (233, 161, 104), 'wink_left', ('blindfold', 'collar'), ('steam',),
        'bosses/armored/velvet_vixen_shadow.png',
    ),
    'card_denied_again': CardRecipe(
        "bust", 'andro', 'pony', (100, 0, 0), (166, 101, 58), (176, 33, 42), (66, 0, 28),
        'waiter_vest', (103, 14, 35), (225, 171, 55), 'lounge_neon', (36, 9, 0), (82, 25, 32),
        (250, 191, 47), 'pierce', ('opera_gloves', 'fan'), ('herbs',),
        'bosses/armored/velvet_vixen_mythic.png',
    ),
    'card_beg_pretty': CardRecipe(
        "bust", 'femme', 'messy_bun', (35, 0, 27), (229, 181, 151), (193, 63, 85), (83, 29, 0),
        'satin_bunny', (120, 44, 78), (242, 201, 98), 'void', (17, 3, 5), (99, 0, 15),
        (255, 121, 90), 'tower', ('lace_mask', 'gold_drops'), ('city_windows',),
        'bosses/tomass.png',
    ),
    'card_locked_up': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (112, 61, 60), (235, 129, 43), 'neon_pink', (0, 37, 20), (57, 41, 13),
        (255, 141, 71), "macro", (), ('velvet_collar',),
        'bosses/zz_wrath.png',
    ),
    'card_edged_raw': CardRecipe(
        "bust", 'andro', 'slick_short', (11, 55, 0), (191, 169, 165), (127, 23, 71), (37, 9, 0),
        'lab_coat', (154, 0, 54), (196, 181, 24), 'storm_gold', (15, 0, 19), (73, 0, 41),
        (255, 181, 76), 'soft', ('headset', 'lanyard'), ('rope',),
        'bosses/freaky_nikki/spawn.gif',
    ),
    'card_orgasm_ban': CardRecipe(
        "bust", 'femme', 'stage_curl', (86, 81, 16), (162, 149, 86), (144, 53, 14), (54, 39, 40),
        'velvet_blazer', (61, 24, 0), (213, 131, 67), 'abyss', (32, 21, 26), (90, 25, 24),
        (218, 111, 119), 'cool', ('stubble', 'hoop', 'chain'), ('neon_sign',),
        'bosses/freaky_nikki/down.gif',
    ),
    'card_keyholder': CardRecipe(
        "bust", 'masc', 'side_part', (45, 0, 51), (225, 157, 107), (161, 0, 57), (71, 0, 3),
        'fire_jacket', (78, 54, 30), (230, 161, 30), 'throne', (13, 15, 0), (107, 0, 7),
        (235, 141, 62), 'pose_up', ('silver_drops', 'cold_rim'), ('smoke',),
        'bosses/freaky_nikki/twist.gif',
    ),
    'card_kneel': CardRecipe(
        "bust", 'andro', 'undercut', (62, 5, 0), (242, 187, 150), (178, 13, 0), (8, 19, 46),
        'gold_vest', (95, 0, 73), (247, 191, 73), 'busy_floor', (30, 9, 4), (64, 25, 50),
        (252, 171, 105), 'fade', ('bow', 'wink'), ('posters',),
        'bosses/freaky_nikki/grab.gif',
    ),
    'card_kiss_ring': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (117, 51, 35), (240, 199, 98), 'jester_dark', (0, 27, 0), (62, 31, 0),
        (255, 131, 46), "macro", (), ('pearl_strand',),
        'bosses/freaky_nikki/defeat.gif',
    ),
    'card_offer': CardRecipe(
        "bust", 'masc', 'fade', (96, 65, 40), (158, 125, 114), (212, 73, 86), (42, 0, 52),
        'sequin', (129, 34, 49), (201, 171, 79), 'neon_perch', (28, 0, 18), (98, 25, 16),
        (255, 131, 91), 'regal', ('scale_crown', 'fin_ear'), ('embers',),
        'bosses/freaky_nikki/slap.gif',
    ),
    'card_praise': CardRecipe(
        "bust", 'andro', 'white_wisps', (0, 0, 83), (221, 133, 135), (129, 3, 29), (59, 29, 15),
        'bomber', (146, 64, 0), (218, 201, 42), 'vault_glow', (9, 0, 25), (55, 0, 59),
        (255, 161, 34), 'glance', ('tall_crown', 'ruby_collar'), ('adoring_lights',),
        'brand/goonbot-icon-explicit.png',
    ),
    'card_tongue_service': CardRecipe(
        "bust", 'femme', 'spark_crest', (48, 0, 0), (238, 163, 106), (146, 33, 72), (76, 59, 58),
        'pale_silk', (163, 0, 25), (235, 151, 85), 'carpet_lamps', (26, 21, 0), (72, 25, 42),
        (220, 191, 77), 'stoic', ('vest_buttons',), ('wallet',),
        'brand/goonbot-banner-explicit.png',
    ),
    'card_footstool': CardRecipe(
        "bust", 'masc', 'gold_coils', (7, 15, 29), (183, 193, 149), (163, 63, 15), (13, 9, 21),
        'split_coat', (70, 14, 68), (252, 181, 48), 'rose_room', (7, 15, 3), (89, 0, 25),
        (237, 121, 120), 'intense', ('bunny_ears', 'key_charm'), ('door',),
        'brand/goonbot-banner.png',
    ),
    'card_altar_night': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (72, 35, 0), (225, 151, 52), 'grow_mood', (0, 21, 0), (74, 55, 6),
        (255, 181, 74), "scene", (), (), 'districts/downtown.png', 'altar_kneel',
    ),
    'card_holy_ruin': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (139, 0, 53), (182, 139, 36), 'penthouse', (19, 0, 13), (84, 51, 6),
        (255, 151, 64), "macro", (), ('wax_pool',),
        'districts/financial.png',
    ),
    'card_high_priestess': CardRecipe(
        "bust", 'masc', 'heat_fall', (58, 0, 18), (234, 139, 134), (214, 53, 44), (64, 19, 0),
        'tux_guard', (121, 0, 87), (223, 191, 97), 'spotlight', (22, 0, 24), (80, 25, 34),
        (255, 111, 49), 'hero', ('holo_clip',), ('bokeh_warm',),
        'districts/industrial.png',
    ),
    'card_divine_taste': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (173, 51, 59), (216, 199, 42), 'velvet_rope', (53, 27, 19), (118, 31, 12),
        (247, 131, 70), "macro", (), ('worship_chalice',),
        'districts/beachfront.png',
    ),
    'card_last_call': CardRecipe(
        "bust", 'femme', 'kiss_curl', (150, 21, 0), (150, 149, 98), (148, 13, 30), (18, 0, 0),
        'spotlight_fit', (155, 54, 63), (177, 171, 103), 'alley', (20, 21, 2), (54, 25, 60),
        (222, 171, 35), 'look_back', ('guest_list',), ('necklace',),
        'districts/residential.png',
    ),
    'card_lights_down': CardRecipe(
        "bust", 'masc', 'ready_mane', (0, 55, 7), (213, 157, 119), (165, 43, 73), (35, 29, 39),
        'booth_satin', (62, 0, 0), (194, 201, 66), 'encore', (37, 15, 9), (71, 0, 43),
        (239, 201, 78), 'close_up', ('shades',), ('gel_lights',),
        'drugs/grow_lab.png',
    ),
    'card_midnight_toast': CardRecipe(
        "bust", 'andro', 'cream_waves', (0, 85, 50), (230, 187, 162), (182, 73, 16), (52, 59, 2),
        'champion', (79, 4, 39), (211, 151, 29), 'city_posters', (18, 9, 16), (88, 25, 26),
        (255, 131, 121), 'front_smile', ('sparkle',), ('green_aura',),
        'businesses/corporation.png',
    ),
    'card_encore_strip': CardRecipe(
        "pixel", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (111, 5, 57), (255, 201, 113), 'moonlit', (39, 0, 35), (33, 25, 67),
        (252, 151, 55), "scene", (), (), 'businesses/chain_restaurant.png', 'encore_spot',
    ),
    'card_final_ruin': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (178, 41, 34), (221, 189, 97), 'dual_fire', (58, 17, 0), (43, 21, 67),
        (252, 121, 45), "macro", (), ('feather',),
        'businesses/factory.png',
    ),
    'card_house_closer': CardRecipe(
        "bust", 'andro', 'shaved_side', (37, 35, 39), (209, 133, 147), (133, 63, 45), (23, 0, 51),
        'latex', (130, 0, 58), (182, 161, 78), 'cathedral', (33, 0, 1), (79, 0, 35),
        (207, 121, 50), 'three_right', ('spark_crown',), ('gold_wisps',),
        'businesses/coffee_shop.png',
    ),
    'card_velvets_mouth': CardRecipe(
        "still", "none", "", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        "", (132, 21, 40), (175, 169, 103), 'crowd_blur', (12, 0, 0), (77, 1, 0),
        (255, 101, 51), "macro", (), ('lipstick_kiss',),
        'businesses/restaurant.png',
    ),
    'card_ruin_crown': CardRecipe(
        "bust", 'masc', 'wet_slick', (71, 0, 0), (243, 193, 161), (167, 23, 31), (57, 49, 57),
        'mesh_top', (164, 44, 34), (216, 141, 84), 'club_door', (31, 15, 15), (53, 0, 61),
        (241, 181, 36), 'pierce', ('cap', 'gloves'), ('god_rays',),
        'businesses/food_cart.png',
    ),
    'card_aftercare_goddess': CardRecipe(
        "bust", 'andro', 'wet_fall', (88, 0, 28), (142, 101, 82), (184, 53, 74), (74, 0, 20),
        'open_robe', (71, 0, 77), (233, 171, 47), 'heat', (12, 9, 22), (70, 25, 44),
        (255, 111, 79), 'tower', ('earpiece', 'lapel_pin'), ('champagne_tray',),
        'businesses/lemon_stand.png',
    ),
    'card_still_ready': CardRecipe(
        "bust", 'femme', 'cascade', (23, 11, 79), (205, 181, 175), (201, 0, 17), (11, 29, 63),
        'velvet_scoop', (88, 0, 10), (250, 201, 90), 'spot', (29, 3, 29), (87, 0, 27),
        (255, 141, 122), 'command', ('chair',), ('spark',),
        'bosses/glam/velvet_vixen_normal.png',
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
    if name in ("lip_close", "sheets", "chaos", "obsidian", "treasure", "sparks", "shrine", "clinic",
                "wax_glow", "rope_dark", "steam_bath", "booth_red", "altar_gold"):
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
    elif pose == "kneel_up":
        head_y, hx, hy = 220 * s, 82 * s, 108 * s
        jaw = 0.28
    elif pose == "look_back":
        cx = size * 0.62
        turn = 1.35
        head_y = 170 * s
    elif pose == "close_up":
        head_y, hx, hy = 228 * s, 118 * s, 136 * s
    elif pose == "warlord":
        head_y, hx, hy = 152 * s, 88 * s, 112 * s
        jaw = 0.16
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
        "cream_waves", "teal_kelp", "stage_curl", "kiss_curl", "long_straight",
        "braids", "wet_fall",
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
    elif style in ("slick", "side_part", "fade", "buzz", "slick_short", "undercut", "leaf_crop", "wet_slick"):
        _stamp_blob(canvas, cx, hy - 4 * s, hx * 1.12, hyy * 0.78, d, 0.96, 1.9)
    elif style == "shaved_side":
        _stamp_blob(canvas, cx + 18 * s, hy - 2 * s, hx * 0.95, hyy * 0.82, d, 0.96, 1.85)
        _stamp_blob(canvas, cx - hx * 0.7, hy + 6 * s, 22 * s, 28 * s, _shade(recipe.skin, 0.08), 0.55, 1.8)
    elif style == "afro_halo":
        _stamp_blob(canvas, cx, hy + 6 * s, hx * 1.72, hyy * 1.35, c, 0.96, 1.35)
        _stamp_blob(canvas, cx, hy - 10 * s, hx * 1.5, hyy * 0.85, _tint(c, 0.12), 0.55, 1.5)
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
    if style in ("cascade", "crimson_crown", "heat_fall", "ready_mane", "cream_waves", "stage_curl", "long_straight", "wet_fall"):
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
    elif style == "braids":
        for side in (-1.0, 1.0):
            for i in range(6):
                _stamp_blob(
                    canvas, cx + side * (hx * 0.7 + i * 4 * s), hy + (18 + i * 22) * s,
                    16 * s, 14 * s, c if i % 2 == 0 else hi, 0.9, 1.7,
                )
        _stamp_blob(canvas, cx, hy + 6 * s, hx * 0.92, 18 * s, c, 0.8, 1.8)
    elif style == "shaved_side":
        _stamp_capsule(canvas, cx + hx * 0.15, hy - 8 * s, cx + hx * 0.85, hy + 28 * s, 10 * s, hi, 0.7)
        _stamp_blob(canvas, cx - hx * 0.35, hy + 8 * s, 28 * s, 16 * s, _mix(c, recipe.skin, 0.45), 0.7, 1.9)
    elif style == "afro_halo":
        _stamp_blob(canvas, cx, hy + 2 * s, hx * 1.15, 22 * s, c, 0.55, 1.6)
        _stamp_blob(canvas, cx - hx * 0.9, hy + 8 * s, 22 * s, 28 * s, c, 0.7, 1.6)
        _stamp_blob(canvas, cx + hx * 0.9, hy + 8 * s, 22 * s, 28 * s, c, 0.7, 1.6)
    elif style == "wet_slick":
        _stamp_blob(canvas, cx, hy - 4 * s, hx * 1.02, 22 * s, c, 0.96, 2.0)
        _stamp_capsule(canvas, cx - hx * 0.5, hy, cx + hx * 0.55, hy + 18 * s, 6 * s, hi, 0.62)


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
    elif body == "harness":
        _stamp_blob(canvas, cx, neck_y + 28 * s, 46 * s, 36 * s, _tint(recipe.skin, 0.04), 0.9, 1.7)
        _stamp_capsule(canvas, cx - 40 * s, neck_y + 8 * s, cx + 40 * s, neck_y + 8 * s, 5 * s, (18, 12, 14), 0.92)
        _stamp_capsule(canvas, cx - 52 * s, neck_y + 6 * s, cx - 18 * s, shoulder_y + 90 * s, 6 * s, (18, 12, 14), 0.9)
        _stamp_capsule(canvas, cx + 52 * s, neck_y + 6 * s, cx + 18 * s, shoulder_y + 90 * s, 6 * s, (18, 12, 14), 0.9)
        _stamp_blob(canvas, cx, neck_y + 44 * s, 14 * s, 12 * s, acc, 0.92, 2.0)
    elif body == "corset":
        _stamp_blob(canvas, cx, neck_y + 36 * s, 38 * s, 28 * s, _shade(recipe.skin, 0.04), 0.88, 1.7)
        for i in range(5):
            _stamp_capsule(
                canvas, cx - 36 * s, shoulder_y + i * 16 * s, cx + 36 * s, shoulder_y + i * 16 * s,
                3.2 * s, acc, 0.7,
            )
        _stamp_capsule(canvas, cx, neck_y + 18 * s, cx, shoulder_y + 100 * s, 4 * s, (20, 12, 14), 0.55)
    elif body == "latex":
        _stamp_blob(canvas, cx, neck_y + 28 * s, 42 * s, 30 * s, _tint(cloth, 0.22), 0.55, 1.6)
        _stamp_blob(canvas, cx + 20 * s, neck_y + 18 * s, 18 * s, 10 * s, (255, 230, 230), 0.35, 1.9)
        _stamp_capsule(canvas, cx - 70 * s, shoulder_y + 8 * s, cx + 70 * s, shoulder_y + 8 * s, 8 * s, acc, 0.4)
    elif body == "towel":
        _stamp_blob(canvas, cx, neck_y + 40 * s, 70 * s, 50 * s, _tint(cloth, 0.12), 0.9, 1.55)
        _stamp_capsule(canvas, cx - 8 * s, neck_y + 12 * s, cx + 54 * s, shoulder_y + 70 * s, 16 * s, cloth, 0.75)
    elif body == "mesh_top":
        _stamp_blob(canvas, cx, neck_y + 26 * s, 48 * s, 32 * s, _tint(recipe.skin, 0.05), 0.88, 1.7)
        for i in range(8):
            _stamp_blob(
                canvas, cx + (i % 4 - 1.5) * 18 * s, neck_y + 30 * s + (i // 4) * 28 * s,
                7 * s, 6 * s, cloth, 0.55, 2.0,
            )
    elif body == "open_robe":
        _stamp_blob(canvas, cx, neck_y + 30 * s, 36 * s, 40 * s, _shade(recipe.skin, 0.02), 0.92, 1.65)
        _stamp_capsule(canvas, cx - 20 * s, neck_y + 8 * s, cx - 88 * s, shoulder_y + 110 * s, 18 * s, cloth, 0.88)
        _stamp_capsule(canvas, cx + 20 * s, neck_y + 8 * s, cx + 88 * s, shoulder_y + 110 * s, 18 * s, cloth, 0.88)
        _stamp_capsule(canvas, cx - 12 * s, neck_y + 16 * s, cx + 40 * s, shoulder_y + 80 * s, 8 * s, acc, 0.45)


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
        # Narrow almond — avoid giant white discs.
        _stamp_capsule(canvas, ex - 15 * s, eye_y, ex + 15 * s, eye_y + 2 * s, 7 * s, (28, 16, 18), 0.7)
        _stamp_capsule(canvas, ex - 12 * s, eye_y + 1 * s, ex + 12 * s, eye_y + 3 * s, 5.5 * s, (236, 228, 220), 0.85)
        _stamp_blob(canvas, ex + 2 * s + turn * 2 * s, eye_y + 2 * s, 7 * s, 8 * s, recipe.eye, 0.96, 1.85)
        _stamp_blob(canvas, ex + 2 * s + turn * 2 * s, eye_y + 2 * s, 3.2 * s, 3.2 * s, (8, 6, 8), 0.96, 2.0)
        _stamp_blob(canvas, ex + 4 * s, eye_y, 2.2 * s, 1.8 * s, (255, 255, 255), 0.95, 2.0)
        _stamp_capsule(canvas, ex - 16 * s, eye_y - 5 * s + tilt, ex + 16 * s, eye_y - 3 * s, 3.2 * s, recipe.hair_rgb, 0.9)
        _stamp_capsule(canvas, ex - 14 * s, eye_y + 8 * s, ex + 14 * s, eye_y + 6 * s, 2.2 * s, _shade(skin, 0.28), 0.5)
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
    if "collar" in recipe.extras:
        _stamp_capsule(canvas, cx - 34 * s, hy + hyy * 0.82, cx + 34 * s, hy + hyy * 0.82, 8 * s, (18, 12, 14), 0.96)
        _stamp_blob(canvas, cx, hy + hyy * 0.92, 16 * s, 14 * s, gold, 0.92, 1.9)
        _stamp_blob(canvas, cx, hy + hyy * 0.92, 7 * s, 6 * s, recipe.skin, 0.7, 2.0)
    if "blindfold" in recipe.extras:
        _stamp_capsule(canvas, cx - hx * 0.72, hy + 6 * s, cx + hx * 0.72, hy + 8 * s, 11 * s, (16, 10, 14), 0.96)
        _stamp_capsule(canvas, cx + hx * 0.7, hy + 8 * s, cx + hx * 1.05, hy + 40 * s, 5 * s, (16, 10, 14), 0.8)
    if "lace_mask" in recipe.extras:
        _stamp_blob(canvas, cx, hy + 10 * s, 56 * s, 22 * s, (12, 8, 10), 0.82, 1.8)
        _stamp_blob(canvas, cx - 18 * s, hy + 8 * s, 10 * s, 8 * s, recipe.skin, 0.5, 2.0)
        _stamp_blob(canvas, cx + 18 * s, hy + 8 * s, 10 * s, 8 * s, recipe.skin, 0.5, 2.0)
    if "pearls" in recipe.extras:
        for i in range(7):
            _stamp_blob(canvas, cx + (i - 3) * 10 * s, hy + hyy * 0.86 + abs(i - 3) * 3 * s, 7 * s, 7 * s, (240, 228, 210), 0.92, 2.0)
    if "opera_gloves" in recipe.extras:
        _stamp_capsule(canvas, cx + 70 * s, hy + 70 * s, cx + 118 * s, hy + 160 * s, 14 * s, (18, 12, 16), 0.94)
        _stamp_blob(canvas, cx + 122 * s, hy + 168 * s, 18 * s, 16 * s, (18, 12, 16), 0.94, 1.7)
    if "fan" in recipe.extras:
        for i in range(6):
            ang = -0.7 + i * 0.28
            _stamp_capsule(
                canvas, cx + 80 * s, hy + 40 * s,
                cx + 80 * s + np.cos(ang) * 70 * s, hy + 40 * s + np.sin(ang) * 70 * s,
                6 * s, gold if i % 2 == 0 else recipe.cloth_rgb, 0.8,
            )
    if "garter_clip" in recipe.extras:
        _stamp_capsule(canvas, cx - 40 * s, hy + hyy * 1.55, cx - 40 * s, hy + hyy * 1.9, 4 * s, gold, 0.9)
        _stamp_blob(canvas, cx - 40 * s, hy + hyy * 1.52, 12 * s, 8 * s, gold, 0.9, 2.0)


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
    elif recipe.hair == "moth":
        cx, cy = w * 0.5, h * 0.52
        _stamp_blob(canvas, cx, cy + 8 * s, 46 * s, 58 * s, recipe.skin, 0.96, 1.55)
        for side in (-1.0, 1.0):
            _stamp_blob(canvas, cx + side * 90 * s, cy, 70 * s, 110 * s, recipe.cloth_rgb, 0.88, 1.35)
            _stamp_blob(canvas, cx + side * 90 * s, cy, 28 * s, 40 * s, recipe.accent, 0.45, 1.7)
        _stamp_blob(canvas, cx, cy - 8 * s, 22 * s, 18 * s, recipe.hair_rgb, 0.9, 1.8)
        _stamp_blob(canvas, cx, cy + 16 * s, 16 * s, 10 * s, recipe.lip, 0.85, 1.9)
        _stamp_capsule(canvas, cx - 8 * s, cy - 30 * s, cx - 28 * s, cy - 70 * s, 4 * s, recipe.accent, 0.8)
        _stamp_capsule(canvas, cx + 8 * s, cy - 30 * s, cx + 28 * s, cy - 70 * s, 4 * s, recipe.accent, 0.8)
    elif recipe.hair == "cat":
        cx, cy = w * 0.5, h * 0.54
        _stamp_head(canvas, cx, cy, 70 * s, 62 * s, recipe.hair_rgb, jaw=0.22, chin=0.18, squash=1.12,
                    light=(-0.35, -0.5, 0.78), rim=recipe.glow)
        for side in (-1.0, 1.0):
            _stamp_blob(canvas, cx + side * 42 * s, cy - 48 * s, 22 * s, 32 * s, recipe.hair_rgb, 0.96, 1.55)
            _stamp_blob(canvas, cx + side * 42 * s, cy - 44 * s, 10 * s, 16 * s, (232, 160, 170), 0.75, 1.8)
            _stamp_blob(canvas, cx + side * 22 * s, cy - 8 * s, 12 * s, 10 * s, recipe.eye, 0.96, 1.9)
        _stamp_blob(canvas, cx, cy + 18 * s, 22 * s, 12 * s, recipe.lip, 0.9, 1.8)
        _stamp_blob(canvas, cx, cy + 70 * s, 80 * s, 50 * s, recipe.cloth_rgb, 0.9, 1.55)
        _stamp_blob(canvas, cx, cy + 88 * s, 16 * s, 40 * s, recipe.hair_rgb, 0.85, 1.7)
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
        # Macro lips on velvet — not a beige head oval.
        _stamp_blob(canvas, w * 0.5, h * 0.55, 220 * s, 160 * s, (40, 8, 14), 0.55, 1.4)
        _stamp_blob(canvas, w * 0.38, h * 0.42, 70 * s, 36 * s, (176, 24, 44), 0.96, 1.45)
        _stamp_blob(canvas, w * 0.62, h * 0.42, 70 * s, 36 * s, (176, 24, 44), 0.96, 1.45)
        _stamp_blob(canvas, w * 0.5, h * 0.4, 48 * s, 18 * s, (150, 16, 34), 0.9, 1.7)
        _stamp_blob(canvas, w * 0.5, h * 0.6, 140 * s, 58 * s, (128, 12, 30), 0.96, 1.4)
        _stamp_blob(canvas, w * 0.5, h * 0.52, 90 * s, 16 * s, (48, 6, 14), 0.55, 1.8)
        _stamp_blob(canvas, w * 0.56, h * 0.48, 50 * s, 16 * s, (255, 140, 150), 0.4, 1.8)
        _stamp_blob(canvas, w * 0.46, h * 0.66, 60 * s, 18 * s, gold, 0.3, 1.6)
        _stamp_blob(canvas, w * 0.18, h * 0.58, 28 * s, 40 * s, gold, 0.45, 1.7)
        _stamp_blob(canvas, w * 0.82, h * 0.4, 16 * s, 22 * s, gold, 0.5, 1.8)
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
        _stamp_capsule(canvas, w * 0.5, h * 0.12, w * 0.5, h * 0.22, 6 * s, gold, 0.95)
        _stamp_blob(canvas, w * 0.5, h * 0.48, 100 * s, 88 * s, gold, 0.96, 1.35)
        _stamp_blob(canvas, w * 0.5, h * 0.78, 36 * s, 18 * s, gold, 0.96, 1.8)
        _stamp_blob(canvas, w * 0.5, h * 0.86, 12 * s, 20 * s, gold, 0.96, 1.9)
        _stamp_capsule(canvas, w * 0.24, h * 0.3, w * 0.12, h * 0.78, 10 * s, (160, 20, 40), 0.9)
        _stamp_capsule(canvas, w * 0.76, h * 0.3, w * 0.88, h * 0.78, 10 * s, (36, 96, 40), 0.9)
        _stamp_blob(canvas, w * 0.12, h * 0.8, 16 * s, 16 * s, gold, 0.9, 2.0)
        _stamp_blob(canvas, w * 0.88, h * 0.8, 16 * s, 16 * s, gold, 0.9, 2.0)
        _stamp_blob(canvas, w * 0.36, h * 0.38, 22 * s, 14 * s, (255, 245, 200), 0.5, 1.9)
        _stamp_blob(canvas, w * 0.5, h * 0.94, 80 * s, 18 * s, (70, 18, 24), 0.4, 1.8)
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
    elif prop == "silk_rope":
        for i in range(5):
            _stamp_blob(canvas, w * (0.32 + (i % 3) * 0.14), h * (0.42 + (i // 3) * 0.16), 70 * s, 28 * s, recipe.cloth_rgb, 0.9, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.58, 90 * s, 40 * s, gold, 0.35, 1.6)
        _stamp_capsule(canvas, w * 0.22, h * 0.7, w * 0.78, h * 0.62, 10 * s, _shade(recipe.cloth_rgb, 0.2), 0.85)
    elif prop == "soft_cuffs":
        for x in (0.34, 0.66):
            _stamp_blob(canvas, w * x, h * 0.5, 70 * s, 54 * s, recipe.cloth_rgb, 0.96, 1.45)
            _stamp_blob(canvas, w * x, h * 0.5, 38 * s, 28 * s, _shade(recipe.bg_bot, 0.1), 0.9, 1.8)
            _stamp_blob(canvas, w * x, h * 0.42, 12 * s, 10 * s, gold, 0.9, 2.0)
        _stamp_capsule(canvas, w * 0.42, h * 0.5, w * 0.58, h * 0.5, 5 * s, gold, 0.8)
    elif prop == "velvet_collar":
        _stamp_blob(canvas, w * 0.5, h * 0.56, 160 * s, 70 * s, recipe.cloth_rgb, 0.96, 1.4)
        _stamp_blob(canvas, w * 0.5, h * 0.56, 90 * s, 36 * s, _shade(recipe.cloth_rgb, 0.25), 0.55, 1.7)
        _stamp_blob(canvas, w * 0.5, h * 0.7, 28 * s, 32 * s, gold, 0.96, 1.6)
        _stamp_blob(canvas, w * 0.5, h * 0.7, 12 * s, 12 * s, (20, 10, 12), 0.9, 2.0)
    elif prop == "wax_pool":
        for i, x in enumerate((0.28, 0.5, 0.72)):
            _stamp_capsule(canvas, w * x, h * 0.22, w * x, h * 0.48, 10 * s, (240, 230, 200), 0.92)
            _stamp_blob(canvas, w * x, h * 0.2, 16 * s, 12 * s, (255, 180, 80), 0.8, 1.8)
            _stamp_blob(canvas, w * x, h * (0.62 + i * 0.04), 50 * s, 22 * s, recipe.lip, 0.7, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.78, 180 * s, 40 * s, recipe.lip, 0.45, 1.4)
    elif prop == "riding_crop":
        _stamp_capsule(canvas, w * 0.18, h * 0.72, w * 0.82, h * 0.28, 8 * s, (28, 16, 14), 0.96)
        _stamp_blob(canvas, w * 0.82, h * 0.26, 36 * s, 22 * s, (18, 10, 10), 0.96, 1.8)
        _stamp_blob(canvas, w * 0.2, h * 0.74, 22 * s, 28 * s, gold, 0.85, 1.7)
        _stamp_blob(canvas, w * 0.5, h * 0.8, 140 * s, 30 * s, recipe.cloth_rgb, 0.4, 1.6)
    elif prop == "lace_mask":
        _stamp_blob(canvas, w * 0.5, h * 0.48, 150 * s, 90 * s, (16, 10, 14), 0.92, 1.45)
        _stamp_blob(canvas, w * 0.36, h * 0.46, 28 * s, 22 * s, recipe.skin, 0.35, 1.8)
        _stamp_blob(canvas, w * 0.64, h * 0.46, 28 * s, 22 * s, recipe.skin, 0.35, 1.8)
        for i in range(8):
            _stamp_blob(canvas, w * (0.28 + i * 0.06), h * 0.62, 10 * s, 16 * s, gold, 0.4, 1.8)
    elif prop == "perfume":
        _stamp_capsule(canvas, w * 0.5, h * 0.28, w * 0.5, h * 0.4, 8 * s, gold, 0.92)
        _stamp_blob(canvas, w * 0.5, h * 0.58, 50 * s, 90 * s, recipe.cloth_rgb, 0.96, 1.45)
        _stamp_blob(canvas, w * 0.5, h * 0.4, 28 * s, 18 * s, gold, 0.9, 1.8)
        _stamp_blob(canvas, w * 0.42, h * 0.5, 14 * s, 30 * s, (255, 220, 230), 0.35, 1.7)
        for _ in range(10):
            _stamp_blob(canvas, float(rng.uniform(w * 0.3, w * 0.7)), float(rng.uniform(h * 0.12, h * 0.32)),
                        6 * s, 10 * s, (255, 200, 210), 0.28, 1.8)
    elif prop == "pearl_strand":
        for i in range(12):
            t = i / 11
            _stamp_blob(canvas, w * (0.2 + t * 0.6), h * (0.38 + 0.18 * np.sin(i)), 16 * s, 16 * s, (240, 228, 210), 0.95, 1.8)
        _stamp_blob(canvas, w * 0.5, h * 0.7, 40 * s, 28 * s, gold, 0.7, 1.7)
    elif prop == "champagne_flute":
        _stamp_capsule(canvas, w * 0.5, h * 0.22, w * 0.5, h * 0.7, 18 * s, (230, 230, 240), 0.55)
        _stamp_blob(canvas, w * 0.5, h * 0.78, 22 * s, 16 * s, gold, 0.9, 1.8)
        _stamp_blob(canvas, w * 0.5, h * 0.42, 28 * s, 40 * s, (255, 220, 140), 0.45, 1.6)
        for _ in range(16):
            _stamp_blob(canvas, float(rng.uniform(w * 0.42, w * 0.58)), float(rng.uniform(h * 0.26, h * 0.5)),
                        3 * s, 3 * s, (255, 255, 255), 0.5, 2.0)
    elif prop == "aftercare_mug":
        _stamp_blob(canvas, w * 0.48, h * 0.52, 80 * s, 70 * s, recipe.cloth_rgb, 0.96, 1.45)
        _stamp_blob(canvas, w * 0.48, h * 0.38, 70 * s, 22 * s, _tint(recipe.cloth_rgb, 0.15), 0.8, 1.8)
        _stamp_blob(canvas, w * 0.7, h * 0.52, 28 * s, 18 * s, gold, 0.9, 1.7)
        _stamp_blob(canvas, w * 0.48, h * 0.28, 40 * s, 24 * s, (255, 230, 210), 0.3, 1.6)
    elif prop == "lipstick_kiss":
        _stamp_blob(canvas, w * 0.5, h * 0.5, 160 * s, 120 * s, (236, 220, 200), 0.92, 1.5)
        _stamp_blob(canvas, w * 0.46, h * 0.46, 50 * s, 28 * s, recipe.lip, 0.9, 1.5)
        _stamp_blob(canvas, w * 0.56, h * 0.5, 54 * s, 32 * s, recipe.lip, 0.88, 1.45)
        _stamp_blob(canvas, w * 0.5, h * 0.58, 70 * s, 22 * s, _shade(recipe.lip, 0.15), 0.8, 1.6)
    elif prop == "edge_timer":
        _stamp_blob(canvas, w * 0.5, h * 0.5, 120 * s, 120 * s, (24, 18, 20), 0.96, 1.4)
        _stamp_blob(canvas, w * 0.5, h * 0.5, 88 * s, 88 * s, gold, 0.35, 1.7)
        _stamp_capsule(canvas, w * 0.5, h * 0.5, w * 0.5, h * 0.28, 6 * s, (240, 230, 210), 0.92)
        _stamp_capsule(canvas, w * 0.5, h * 0.5, w * 0.72, h * 0.58, 5 * s, recipe.lip, 0.9)
        _stamp_blob(canvas, w * 0.5, h * 0.5, 12 * s, 12 * s, recipe.lip, 0.96, 2.0)
    elif prop == "keyhole_view":
        _stamp_blob(canvas, w * 0.5, h * 0.5, 200 * s, 200 * s, (12, 8, 10), 0.96, 1.2)
        _stamp_blob(canvas, w * 0.5, h * 0.42, 50 * s, 50 * s, recipe.glow, 0.85, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.62, 28 * s, 48 * s, recipe.glow, 0.8, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.44, 22 * s, 28 * s, recipe.lip, 0.55, 1.7)
    elif prop == "compact_mirror":
        _stamp_blob(canvas, w * 0.38, h * 0.52, 90 * s, 90 * s, gold, 0.96, 1.4)
        _stamp_blob(canvas, w * 0.38, h * 0.52, 62 * s, 62 * s, (180, 200, 210), 0.75, 1.6)
        _stamp_blob(canvas, w * 0.7, h * 0.58, 70 * s, 40 * s, recipe.cloth_rgb, 0.9, 1.5)
        _stamp_blob(canvas, w * 0.7, h * 0.52, 40 * s, 16 * s, recipe.lip, 0.7, 1.8)
    elif prop == "feather":
        _stamp_capsule(canvas, w * 0.28, h * 0.72, w * 0.72, h * 0.22, 7 * s, (40, 24, 20), 0.9)
        for i in range(10):
            _stamp_capsule(
                canvas, w * (0.4 + i * 0.03), h * (0.55 - i * 0.03),
                w * (0.55 + i * 0.03), h * (0.35 - i * 0.02), 8 * s, recipe.cloth_rgb, 0.55,
            )
        _stamp_blob(canvas, w * 0.26, h * 0.74, 18 * s, 16 * s, gold, 0.85, 1.8)
    elif prop == "satin_pillow":
        _stamp_blob(canvas, w * 0.5, h * 0.58, 200 * s, 90 * s, recipe.cloth_rgb, 0.92, 1.35)
        _stamp_blob(canvas, w * 0.42, h * 0.5, 80 * s, 40 * s, _tint(recipe.cloth_rgb, 0.2), 0.45, 1.6)
        _stamp_blob(canvas, w * 0.62, h * 0.64, 50 * s, 24 * s, gold, 0.28, 1.7)
        _stamp_blob(canvas, w * 0.3, h * 0.62, 30 * s, 16 * s, recipe.lip, 0.25, 1.8)
    elif prop == "toy_silhouette":
        _stamp_blob(canvas, w * 0.5, h * 0.42, 40 * s, 36 * s, recipe.cloth_rgb, 0.96, 1.45)
        _stamp_capsule(canvas, w * 0.5, h * 0.48, w * 0.5, h * 0.78, 22 * s, recipe.cloth_rgb, 0.96)
        _stamp_blob(canvas, w * 0.5, h * 0.82, 36 * s, 20 * s, gold, 0.7, 1.7)
        _stamp_blob(canvas, w * 0.42, h * 0.38, 12 * s, 10 * s, (255, 220, 220), 0.4, 1.9)
    elif prop == "worship_chalice":
        _stamp_blob(canvas, w * 0.5, h * 0.38, 80 * s, 36 * s, gold, 0.96, 1.45)
        _stamp_capsule(canvas, w * 0.5, h * 0.42, w * 0.5, h * 0.7, 14 * s, gold, 0.92)
        _stamp_blob(canvas, w * 0.5, h * 0.78, 50 * s, 16 * s, gold, 0.96, 1.8)
        _stamp_blob(canvas, w * 0.5, h * 0.34, 50 * s, 18 * s, recipe.lip, 0.55, 1.6)
    elif prop == "blindfold_silk":
        _stamp_capsule(canvas, w * 0.16, h * 0.48, w * 0.84, h * 0.48, 22 * s, recipe.cloth_rgb, 0.96)
        _stamp_blob(canvas, w * 0.78, h * 0.62, 40 * s, 70 * s, recipe.cloth_rgb, 0.88, 1.5)
        _stamp_blob(canvas, w * 0.5, h * 0.48, 20 * s, 10 * s, gold, 0.4, 1.8)
    elif prop == "glove_pair":
        for x in (0.36, 0.64):
            _stamp_capsule(canvas, w * x, h * 0.28, w * x, h * 0.7, 22 * s, (18, 12, 16), 0.96)
            _stamp_blob(canvas, w * x, h * 0.76, 32 * s, 28 * s, (18, 12, 16), 0.96, 1.55)
            _stamp_blob(canvas, w * (x + 0.06), h * 0.8, 12 * s, 22 * s, (18, 12, 16), 0.9, 1.7)
        _stamp_blob(canvas, w * 0.5, h * 0.4, 16 * s, 16 * s, gold, 0.7, 2.0)
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
        _px_fill(a, 0, 0, 128, 18, (12, 16, 22))
        _px_fill(a, 0, 110, 128, 18, (18, 22, 28))
        for gx in range(0, 128, 8):
            _px_fill(a, gx, 110, 1, 18, (30, 36, 44))
        _px_fill(a, 0, 18, 14, 92, (22, 28, 34))
        _px_fill(a, 114, 18, 14, 92, (22, 28, 34))
        _px_fill(a, 22, 22, 84, 84, (36, 48, 56))
        _px_disc(a, 64, 64, 36, (58, 72, 80))
        _px_disc(a, 64, 64, 24, (14, 16, 20))
        _px_disc(a, 64, 64, 8, gold)
        for i in range(8):
            ang = i / 8 * 6.28
            _px_fill(a, int(64 + np.cos(ang) * 28), int(64 + np.sin(ang) * 28), 6, 6, gold)
        _px_fill(a, 20, 40, 88, 2, (80, 255, 220))
        _px_fill(a, 24, 86, 80, 2, (80, 255, 220))
        _px_fill(a, 48, 100, 14, 16, (12, 10, 14))
        _px_person(a, 4, 74, (150, 110, 90), (12, 12, 16), (16, 12, 12))
        _px_fill(a, 6, 80, 10, 5, (8, 8, 10))
        _px_fill(a, 108, 96, 14, 10, gold)
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
    elif scene == "private_booth":
        _px_fill(a, 0, 0, 18, 128, cloth)
        _px_fill(a, 110, 0, 18, 128, cloth)
        _px_fill(a, 18, 90, 92, 38, (40, 16, 22))
        _px_fill(a, 26, 82, 76, 16, (80, 24, 36))
        _px_person(a, 40, 48, (210, 170, 140), (140, 30, 50), (80, 20, 28))
        _px_person(a, 70, 52, (176, 132, 104), (20, 12, 16), (28, 18, 16))
        _px_fill(a, 48, 16, 32, 10, gold)
        _px_disc(a, 64, 22, 8, (255, 180, 80))
    elif scene == "group_floor":
        _px_fill(a, 0, 88, 128, 40, (50, 18, 24))
        skins = ((200, 160, 130), (160, 110, 90), (210, 176, 150), (140, 96, 70), (186, 148, 118), (176, 120, 96))
        for i, sk in enumerate(skins):
            _px_person(a, 8 + i * 20, 50 + (i % 2) * 6, sk, (80, 20, 30) if i % 2 else (30, 16, 22), (24, 14, 14))
        _px_disc(a, 64, 28, 16, gold)
        _px_fill(a, 20, 108, 88, 10, (30, 12, 16))
    elif scene == "altar_kneel":
        _px_fill(a, 24, 86, 80, 22, gold)
        _px_fill(a, 40, 54, 48, 34, (180, 140, 50))
        _px_disc(a, 64, 44, 14, gold)
        _px_person(a, 56, 70, (210, 170, 140), (90, 16, 28), (40, 12, 18))
        _px_fill(a, 18, 20, 8, 70, (255, 160, 60))
        _px_fill(a, 102, 20, 8, 70, (255, 160, 60))
    elif scene == "aftercare_bed":
        _px_fill(a, 8, 70, 112, 50, (210, 170, 160))
        _px_fill(a, 16, 64, 96, 18, (230, 200, 190))
        _px_disc(a, 48, 60, 10, (220, 176, 150))
        _px_disc(a, 72, 58, 10, (186, 140, 112))
        _px_fill(a, 20, 40, 28, 16, (240, 230, 220))
        _px_fill(a, 88, 36, 16, 20, gold)
    elif scene == "toy_drawer":
        _px_fill(a, 10, 20, 108, 90, (60, 36, 28))
        _px_fill(a, 16, 26, 96, 78, (90, 50, 40))
        for i in range(3):
            _px_fill(a, 24 + i * 30, 40, 18, 40, cloth if i != 1 else gold)
            _px_disc(a, 33 + i * 30, 36, 7, (20, 12, 14))
        _px_fill(a, 20, 88, 88, 8, (40, 24, 20))
    elif scene == "voyeur_window":
        _px_fill(a, 0, 0, 128, 128, (16, 12, 18))
        _px_fill(a, 28, 18, 72, 88, (80, 28, 40))
        _px_person(a, 48, 40, (210, 170, 140), (140, 24, 40), (90, 16, 24))
        _px_fill(a, 28, 18, 6, 88, (40, 30, 36))
        _px_fill(a, 94, 18, 6, 88, (40, 30, 36))
        _px_fill(a, 28, 58, 72, 6, (40, 30, 36))
        _px_disc(a, 20, 100, 8, gold)
    elif scene == "cabaret_stage":
        _px_fill(a, 0, 96, 128, 32, (40, 16, 20))
        _px_fill(a, 16, 88, 96, 12, gold)
        _px_person(a, 56, 48, (220, 176, 150), (160, 20, 40), (100, 16, 28))
        _px_fill(a, 20, 8, 16, 24, (255, 80, 80))
        _px_fill(a, 92, 8, 16, 24, (80, 180, 255))
        _px_disc(a, 64, 20, 12, (255, 220, 100))
        _px_fill(a, 8, 110, 8, 8, gold)
        _px_fill(a, 112, 110, 8, 8, gold)
    elif scene == "denial_clock":
        _px_disc(a, 64, 56, 40, (30, 22, 24))
        _px_disc(a, 64, 56, 32, gold)
        _px_fill(a, 62, 30, 4, 26, (20, 12, 14))
        _px_fill(a, 64, 56, 22, 4, (160, 20, 36))
        _px_person(a, 16, 84, (186, 140, 112), (40, 16, 22), (28, 16, 16))
        _px_fill(a, 96, 92, 18, 22, cloth)
    elif scene == "encore_spot":
        _px_fill(a, 40, 8, 48, 70, (255, 210, 120))
        _px_person(a, 56, 48, (220, 176, 148), (140, 16, 32), (88, 14, 24))
        _px_fill(a, 0, 100, 128, 28, (20, 10, 14))
        for i in range(6):
            _px_fill(a, 12 + i * 20, 108, 8, 8, gold)
        _px_fill(a, 20, 16, 10, 10, (255, 80, 120))
        _px_fill(a, 98, 16, 10, 10, (255, 80, 120))
    elif scene == "rope_room":
        _px_fill(a, 0, 0, 128, 128, (36, 16, 20))
        for i in range(5):
            _px_fill(a, 18 + i * 20, 8, 4, 110, cloth)
        _px_person(a, 52, 54, (210, 168, 140), (20, 10, 14), (60, 16, 22))
        _px_fill(a, 48, 48, 24, 4, gold)
        _px_fill(a, 48, 72, 24, 4, gold)
    elif scene == "lap_booth":
        _px_fill(a, 8, 70, 112, 50, (90, 24, 36))
        _px_person(a, 36, 48, (164, 120, 92), (24, 16, 18), (20, 14, 12))
        _px_person(a, 64, 40, (220, 176, 150), (160, 30, 50), (90, 18, 28))
        _px_fill(a, 20, 16, 88, 8, gold)
        _px_disc(a, 64, 20, 6, (255, 200, 80))
    elif scene == "bath_steam":
        _px_fill(a, 16, 70, 96, 40, (80, 120, 140))
        _px_disc(a, 48, 56, 12, (220, 176, 150))
        _px_disc(a, 72, 54, 12, (186, 140, 112))
        for i in range(8):
            _px_disc(a, 30 + i * 10, 40 - (i % 3) * 6, 6, (200, 210, 220))
        _px_fill(a, 20, 100, 20, 8, gold)
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


def recipe_fingerprint(recipe: CardRecipe) -> bytes:
    """Stable hash of silhouette/palette/prop choices — not the RNG grain."""
    blob = (
        recipe.kind, recipe.body, recipe.hair, recipe.hair_rgb, recipe.skin,
        recipe.lip, recipe.eye, recipe.clothing, recipe.cloth_rgb, recipe.accent,
        recipe.bg, recipe.bg_top, recipe.bg_bot, recipe.glow, recipe.pose,
        recipe.extras, recipe.props, recipe.mood_asset, recipe.scene,
    )
    return hashlib.sha256(repr(blob).encode()).digest()


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

