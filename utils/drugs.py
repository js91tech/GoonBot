"""Drug trade catalog and pricing math.

A risky, high-reward economy layer: grow product in a lab over time, then sell
it on the street (volatile prices, raid risk) or to other players. Products can
also be consumed for gameplay effects.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import config

DRUG_EFFECT_DURATION_MIN_SECONDS = 30.0
DRUG_EFFECT_DURATION_MAX_SECONDS = 180.0

# Legacy fictional ids mapped to current catalog entries (player stash migration).
_LEGACY_DRUG_ALIASES: dict[str, str] = {
    "greenleaf": "blue_dream",
    "bluecrystal": "crystal_meth",
    "whitedust": "cocaine",
    "goldenpoppy": "heroin",
}


@dataclass(frozen=True, slots=True)
class DrugDef:
    drug_id: str
    name: str
    emoji: str
    category: str
    seed_cost: float
    grow_seconds: int
    yield_min: int
    yield_max: int
    street_price: float  # base goonbux per unit
    effect_summary: str
    effect_energy: int = 0
    effect_heal_pct: float = 0.0
    effect_damage_pct: float = 0.0
    effect_boss_mult: float = 1.0
    effect_duel_mult: float = 1.0
    effect_cc_immunity: bool = False
    effect_attack_hp_risk_chance: float = 0.0
    effect_attack_hp_risk_pct: float = 0.0
    overdose_chance: float = 0.0
    overdose_damage_pct: float = 0.0


DRUGS: tuple[DrugDef, ...] = (
    # --- Cannabis (THC strains) ---
    DrugDef(
        "blue_dream", "Velvet Dream", "💋", "cannabis",
        200.0, 30 * 60, 4, 8, 120.0,
        "Relaxed focus — +10 energy, heal 5% HP.",
        effect_energy=10, effect_heal_pct=0.05,
    ),
    DrugDef(
        "og_kush", "Afterhours Kush", "🌙", "cannabis",
        350.0, 45 * 60, 4, 7, 180.0,
        "Heavy indica — heal 10% HP.",
        effect_heal_pct=0.10,
    ),
    DrugDef(
        "girl_scout_cookies", "Stage-Door Cookies", "🍪", "cannabis",
        600.0, 60 * 60, 3, 7, 280.0,
        "Sweet hybrid — next **/attack** deals +15% boss damage.",
        effect_boss_mult=1.15,
    ),
    DrugDef(
        "purple_haze", "Club Haze", "💜", "cannabis",
        900.0, 75 * 60, 3, 6, 420.0,
        "Psychedelic sativa — next **/duel** deals +15% strike damage.",
        effect_duel_mult=1.15,
    ),
    DrugDef(
        "sour_diesel", "Floor Diesel", "⛽", "cannabis",
        1_200.0, 90 * 60, 3, 6, 550.0,
        "Energizing diesel — +20 energy.",
        effect_energy=20,
    ),
    DrugDef(
        "gorilla_glue", "Booth Glue", "🖤", "cannabis",
        1_800.0, 2 * 3600, 3, 5, 750.0,
        "Sticky knockout — heal 15% HP and +10 energy.",
        effect_heal_pct=0.15, effect_energy=10,
    ),
    DrugDef(
        "white_widow", "White Heat", "🔥", "cannabis",
        2_500.0, 3 * 3600, 2, 5, 950.0,
        "Balanced classic — +5 energy, next **/attack** +10% damage.",
        effect_energy=5, effect_boss_mult=1.10,
    ),
    # --- Stimulants ---
    DrugDef(
        "cocaine", "Cocaine", "❄️", "stimulant",
        5_000.0, 3 * 3600, 2, 5, 2_500.0,
        "Pure stim — +25 energy, next **/duel** +20% damage.",
        effect_energy=25, effect_duel_mult=1.20,
    ),
    DrugDef(
        "crystal_meth", "Crystal Meth", "💎", "stimulant",
        8_000.0, 4 * 3600, 2, 4, 4_000.0,
        "Hard stim — next **/attack** +25% damage, but costs 5% HP.",
        effect_boss_mult=1.25, effect_damage_pct=0.05,
    ),
    DrugDef(
        "mdma", "MDMA", "💊", "stimulant",
        6_500.0, 3 * 3600, 2, 5, 3_200.0,
        "Euphoria — +15 energy, **/duel** +15% damage for the high.",
        effect_energy=15, effect_duel_mult=1.15,
    ),
    DrugDef(
        "addies", "Addies (Adderall IR)", "🧠", "stimulant",
        4_500.0, 2 * 3600 + 30 * 60, 2, 5, 2_200.0,
        "Study grind — +22 energy, **/duel** +15% strike damage for the high.",
        effect_energy=22, effect_duel_mult=1.15,
    ),
    DrugDef(
        "adderall_xr", "Adderall XR", "⏳", "stimulant",
        7_000.0, 3 * 3600 + 30 * 60, 2, 4, 3_400.0,
        "Extended focus — +18 energy, **/attack** +12% boss damage for the high.",
        effect_energy=18, effect_boss_mult=1.12,
    ),
    DrugDef(
        "vyvanse", "Vyvanse", "⚡", "stimulant",
        9_500.0, 4 * 3600, 2, 4, 4_500.0,
        "Pharma-grade focus — +28 energy, **/duel** +18% damage, costs 3% HP.",
        effect_energy=28, effect_duel_mult=1.18, effect_damage_pct=0.03,
    ),
    # --- Codeine ---
    DrugDef(
        "tylenol_3", "Tylenol #3", "💊", "codeine",
        4_000.0, 2 * 3600, 3, 6, 1_800.0,
        "Light script — heal 6% HP, -5 energy.",
        effect_heal_pct=0.06, effect_energy=-5,
    ),
    DrugDef(
        "codeine_pills", "Codeine Pills", "💊", "codeine",
        5_500.0, 2 * 3600 + 30 * 60, 3, 5, 2_600.0,
        "Pharmacy codeine — heal 10% HP, -8 energy.",
        effect_heal_pct=0.10, effect_energy=-8,
    ),
    DrugDef(
        "robitussin_ac", "Robitussin AC", "🍯", "codeine",
        6_500.0, 3 * 3600, 2, 5, 3_000.0,
        "Cough syrup cut — heal 8% HP, +5 energy.",
        effect_heal_pct=0.08, effect_energy=5,
    ),
    DrugDef(
        "prometh_codeine", "Promethazine-Codeine", "🩺", "codeine",
        8_000.0, 3 * 3600 + 30 * 60, 2, 4, 3_800.0,
        "Classic script base — heal 12% HP, **/duel** +8% damage for the high.",
        effect_heal_pct=0.12, effect_duel_mult=1.08,
    ),
    # --- Lean (syrup brands) ---
    DrugDef(
        "hi_tech", "Hi-Tech Lean", "🍼", "lean",
        9_500.0, 3 * 3600 + 30 * 60, 2, 4, 4_200.0,
        "Purple pint — heal 14% HP, **/attack** +10% boss damage for the high.",
        effect_heal_pct=0.14, effect_boss_mult=1.10,
    ),
    DrugDef(
        "wockhardt", "Wockhardt Lean", "🍼", "lean",
        11_000.0, 4 * 3600, 2, 4, 5_200.0,
        "Wock lean — heal 16% HP, **/duel** +12% strike damage for the high.",
        effect_heal_pct=0.16, effect_duel_mult=1.12,
    ),
    DrugDef(
        "tris", "Tris Lean", "🥤", "lean",
        12_000.0, 4 * 3600 + 30 * 60, 2, 4, 5_600.0,
        "Tris pint — heal 16% HP, **/attack** +12% boss damage for the high.",
        effect_heal_pct=0.16, effect_boss_mult=1.12,
    ),
    DrugDef(
        "par", "PAR Lean", "🥤", "lean",
        13_000.0, 5 * 3600, 2, 3, 6_200.0,
        "PAR pharma — heal 18% HP, **/duel** +10% damage, -10 energy.",
        effect_heal_pct=0.18, effect_duel_mult=1.10, effect_energy=-10,
    ),
    DrugDef(
        "quagen", "Quagen Lean", "🍇", "lean",
        14_000.0, 5 * 3600 + 30 * 60, 2, 3, 6_800.0,
        "Quagen cut — heal 17% HP, **/attack** and **/duel** +10% for the high.",
        effect_heal_pct=0.17, effect_boss_mult=1.10, effect_duel_mult=1.10,
    ),
    DrugDef(
        "actavis", "Actavis (OG)", "👑", "lean",
        17_000.0, 6 * 3600, 1, 3, 8_500.0,
        "Legendary OG pint — heal 22% HP, immune to stun/freeze/root; 10% per attack to lose 2% HP.",
        effect_heal_pct=0.22,
        effect_cc_immunity=True,
        effect_attack_hp_risk_chance=0.10,
        effect_attack_hp_risk_pct=0.02,
    ),
    # --- Depressants / opioids ---
    DrugDef(
        "heroin", "Heroin", "🌺", "opioid",
        15_000.0, 6 * 3600, 2, 4, 7_000.0,
        "Numbing high — heal 20% HP, immune to stun/freeze/root for duration; 15% per attack to lose 3% HP.",
        effect_heal_pct=0.20, effect_energy=-15,
        effect_cc_immunity=True,
        effect_attack_hp_risk_chance=0.15,
        effect_attack_hp_risk_pct=0.03,
    ),
    DrugDef(
        "fentanyl", "Fentanyl", "☠️", "opioid",
        25_000.0, 8 * 3600, 1, 3, 12_000.0,
        "Extreme opioid — heal 25% HP, immune to stun/freeze/root for duration; 15% per attack to lose 3% HP.",
        effect_heal_pct=0.25,
        effect_cc_immunity=True,
        effect_attack_hp_risk_chance=0.15,
        effect_attack_hp_risk_pct=0.03,
    ),
    # --- Psychedelics ---
    DrugDef(
        "lsd", "LSD", "🌈", "psychedelic",
        10_000.0, 5 * 3600, 2, 4, 5_500.0,
        "Trip — random combat buff: +20% boss or duel damage.",
        effect_boss_mult=1.20, effect_duel_mult=1.20,
    ),
    DrugDef(
        "shrooms", "Magic Mushrooms", "🍄", "psychedelic",
        4_000.0, 2 * 3600, 3, 6, 2_000.0,
        "Mellow trip — heal 8% HP, +8 energy.",
        effect_heal_pct=0.08, effect_energy=8,
    ),
)

DRUGS_BY_ID: dict[str, DrugDef] = {d.drug_id: d for d in DRUGS}

DRUG_BUFF_PREFIX = "drug_buff:"


def normalize_drug_id(drug_id: str) -> str:
    key = drug_id.strip().lower()
    return _LEGACY_DRUG_ALIASES.get(key, key)


def drug_by_id(drug_id: str) -> DrugDef | None:
    return DRUGS_BY_ID.get(normalize_drug_id(drug_id))


def drug_effect_duration(defn: DrugDef) -> float:
    """Tier-scaled active effect window: 30s (entry strains) up to 3 minutes (top tier)."""
    if len(DRUGS) <= 1:
        return DRUG_EFFECT_DURATION_MIN_SECONDS
    try:
        idx = next(i for i, drug in enumerate(DRUGS) if drug.drug_id == defn.drug_id)
    except StopIteration:
        return DRUG_EFFECT_DURATION_MIN_SECONDS
    tier_frac = idx / (len(DRUGS) - 1)
    span = DRUG_EFFECT_DURATION_MAX_SECONDS - DRUG_EFFECT_DURATION_MIN_SECONDS
    return DRUG_EFFECT_DURATION_MIN_SECONDS + tier_frac * span


def drug_has_timed_effect(defn: DrugDef) -> bool:
    return (
        defn.effect_boss_mult > 1.0
        or defn.effect_duel_mult > 1.0
        or defn.effect_cc_immunity
    )


def legacy_ids_for_canonical(canonical_id: str) -> tuple[str, ...]:
    return tuple(k for k, v in _LEGACY_DRUG_ALIASES.items() if v == canonical_id)


def inventory_lookup_ids(defn: DrugDef) -> tuple[str, ...]:
    keys = (defn.drug_id, *legacy_ids_for_canonical(defn.drug_id))
    return tuple(dict.fromkeys(keys))


def drug_buff_key(drug_id: str, variant: str | None = None) -> str:
    base = f"{DRUG_BUFF_PREFIX}{normalize_drug_id(drug_id)}"
    return f"{base}:{variant}" if variant else base


def parse_drug_buff_key(pending: str | None) -> str | None:
    if not pending or not str(pending).startswith(DRUG_BUFF_PREFIX):
        return None
    raw = str(pending)[len(DRUG_BUFF_PREFIX):]
    drug_id = raw.split(":", 1)[0]
    return drug_id if drug_by_id(drug_id) else None


def roll_yield(defn: DrugDef, *, yield_bonus: float = 0.0, rng: random.Random | None = None) -> int:
    """Harvest yield, including any district/equipment bonus."""
    r = rng or random
    base = r.randint(defn.yield_min, defn.yield_max)
    return max(1, int(round(base * (1.0 + max(0.0, yield_bonus)))))


def street_price(defn: DrugDef, *, rng: random.Random | None = None) -> float:
    """Current street price with random volatility around the base."""
    r = rng or random
    variance = config.DRUG_STREET_PRICE_VARIANCE
    factor = 1.0 + r.uniform(-variance, variance)
    return max(1.0, defn.street_price * factor)


def sale_total(defn: DrugDef, quantity: int, *, rng: random.Random | None = None) -> float:
    return street_price(defn, rng=rng) * max(0, int(quantity))


def format_drug_effect(defn: DrugDef) -> str:
    return defn.effect_summary


def format_consume_message(result: dict[str, object]) -> str:
    parts = [f"{result['emoji']} **{result['name']}** — {result['effect_summary']}"]
    if result.get("overdosed"):
        parts.append(f"☠️ **Overdose!** Took **{int(result['damage_amount'])}** damage.")
    else:
        if float(result.get("heal_amount") or 0) > 0:
            parts.append(f"❤️ Healed **{int(result['heal_amount'])}** HP.")
        if float(result.get("damage_amount") or 0) > 0:
            parts.append(f"💔 Took **{int(result['damage_amount'])}** damage.")
    energy_delta = int(result.get("energy_delta") or 0)
    if energy_delta > 0:
        parts.append(f"⚡ +**{energy_delta}** energy.")
    elif energy_delta < 0:
        parts.append(f"⚡ **{energy_delta}** energy.")
    if result.get("boss_buff"):
        pct = int((float(result["boss_buff"]) - 1.0) * 100)
        secs = int(float(result.get("buff_duration") or DRUG_EFFECT_DURATION_MIN_SECONDS))
        parts.append(f"**/attack** +**{pct}%** boss damage for **{secs}s**.")
    if result.get("duel_buff"):
        pct = int((float(result["duel_buff"]) - 1.0) * 100)
        secs = int(float(result.get("buff_duration") or DRUG_EFFECT_DURATION_MIN_SECONDS))
        parts.append(f"**/duel** +**{pct}%** strike damage for **{secs}s**.")
    if result.get("cc_immunity"):
        secs = int(float(result.get("buff_duration") or DRUG_EFFECT_DURATION_MIN_SECONDS))
        parts.append(
            f"Immune to **stun/freeze/root** for **{secs}s** "
            f"({int(float(result.get('attack_hp_risk_chance') or 0) * 100)}% per attack: "
            f"-{int(float(result.get('attack_hp_risk_pct') or 0) * 100)}% HP)."
        )
    return "💨 " + " ".join(parts)


def drugs_by_category() -> dict[str, list[DrugDef]]:
    grouped: dict[str, list[DrugDef]] = {}
    for defn in DRUGS:
        grouped.setdefault(defn.category, []).append(defn)
    return grouped


DRUG_CATEGORY_LABELS: dict[str, str] = {
    "cannabis": "🌿 Cannabis",
    "stimulant": "⚡ Stimulants",
    "codeine": "💊 Codeine",
    "lean": "🍇 Lean",
    "opioid": "💉 Opioids",
    "psychedelic": "🌈 Psychedelics",
}


def drugs_for_category(category: str) -> list[DrugDef]:
    return drugs_by_category().get(category, [])
