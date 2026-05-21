from __future__ import annotations

import random
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class AspectDefinition:
    id: str
    name: str
    description: str
    effect: str  # damage, crit, mitigation, vitality, boss_slayer


ASPECT_DEFINITIONS: tuple[AspectDefinition, ...] = (
    AspectDefinition(
        "aspect_ravager",
        "Ravager's Echo",
        "Increases damage dealt in combat.",
        "damage",
    ),
    AspectDefinition(
        "aspect_keeneye",
        "Keeneye Sigil",
        "Sharpens critical strike chance.",
        "crit",
    ),
    AspectDefinition(
        "aspect_bulwark",
        "Bulwark Imprint",
        "Improves armor mitigation.",
        "mitigation",
    ),
    AspectDefinition(
        "aspect_vitality",
        "Vitality Thread",
        "Bolsters maximum HP.",
        "vitality",
    ),
    AspectDefinition(
        "aspect_slayer",
        "Slayer's Mark",
        "Amplifies damage against bosses.",
        "boss_slayer",
    ),
)

ASPECT_MAP: dict[str, AspectDefinition] = {a.id: a for a in ASPECT_DEFINITIONS}


@dataclass(frozen=True)
class AspectInstance:
    instance_id: int
    aspect_id: str
    roll_pct: float
    name: str
    effect: str


@dataclass(frozen=True)
class AspectCombatBonuses:
    damage_mult: float = 1.0
    extra_crit: float = 0.0
    mitigation_bonus: float = 0.0
    hp_bonus: int = 0
    boss_damage_mult: float = 1.0


def get_aspect(aspect_id: str) -> AspectDefinition | None:
    return ASPECT_MAP.get(aspect_id)


def roll_pct_for_threat(threat: int) -> float:
    """Boss threat tier (1–5) sets how strong a dropped aspect roll can be."""
    ranges = {
        1: (3.0, 8.0),
        2: (5.0, 12.0),
        3: (8.0, 18.0),
        4: (12.0, 28.0),
        5: (18.0, 40.0),
    }
    low, high = ranges.get(max(1, min(5, threat)), ranges[1])
    return round(random.uniform(low, high), 1)


def roll_pct_shop() -> float:
    """Purchased aspects roll in a mid band (no boss-tier jackpots)."""
    return round(random.uniform(4.0, 14.0), 1)


def random_aspect_definition() -> AspectDefinition:
    return random.choice(ASPECT_DEFINITIONS)


def instance_from_row(row) -> AspectInstance:
    aspect_id = str(row["aspect_id"])
    defn = get_aspect(aspect_id)
    name = defn.name if defn else aspect_id
    effect = defn.effect if defn else "damage"
    return AspectInstance(
        instance_id=int(row["instance_id"]),
        aspect_id=aspect_id,
        roll_pct=float(row["roll_pct"]),
        name=name,
        effect=effect,
    )


def combat_bonuses_from_instance(instance: AspectInstance | None) -> AspectCombatBonuses:
    if instance is None:
        return AspectCombatBonuses()
    pct = instance.roll_pct / 100.0
    if instance.effect == "damage":
        return AspectCombatBonuses(damage_mult=1.0 + pct)
    if instance.effect == "crit":
        return AspectCombatBonuses(extra_crit=pct)
    if instance.effect == "mitigation":
        return AspectCombatBonuses(mitigation_bonus=pct)
    if instance.effect == "vitality":
        return AspectCombatBonuses(hp_bonus=int(round(config.PLAYER_BASE_HP * pct)))
    if instance.effect == "boss_slayer":
        return AspectCombatBonuses(boss_damage_mult=1.0 + pct)
    return AspectCombatBonuses()


def format_aspect_line(instance: AspectInstance, *, equipped: bool = False) -> str:
    tag = " *(equipped)*" if equipped else ""
    effect_label = {
        "damage": "damage",
        "crit": "crit chance",
        "mitigation": "mitigation",
        "vitality": "max HP",
        "boss_slayer": "boss damage",
    }.get(instance.effect, instance.effect)
    return (
        f"**{instance.name}** — **{instance.roll_pct:g}%** {effect_label}{tag}\n"
        f"└ `aspect#{instance.instance_id}`"
    )


def format_aspect_effect(instance: AspectInstance) -> str:
    effect_label = {
        "damage": "damage dealt",
        "crit": "crit chance",
        "mitigation": "damage blocked",
        "vitality": "max HP",
        "boss_slayer": "boss damage",
    }.get(instance.effect, instance.effect)
    return f"**{instance.roll_pct:g}%** {effect_label}"
