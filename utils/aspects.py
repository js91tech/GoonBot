from __future__ import annotations

import random
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class AspectDefinition:
    id: str
    name: str
    description: str
    effect: str


ASPECT_DEFINITIONS: tuple[AspectDefinition, ...] = (
    # Combat
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
    AspectDefinition(
        "aspect_second_wind",
        "Second Wind",
        "Chance to survive a duel killing blow at 1 HP.",
        "second_wind",
    ),
    # Utility
    AspectDefinition(
        "aspect_duelist",
        "Duelist's Gambit",
        "More duels per hour and faster rematch cooldown vs the same player.",
        "duelist",
    ),
    AspectDefinition(
        "aspect_grafter",
        "Grafter's Contract",
        "Multiplies /work payouts (up to 3× at high rolls).",
        "grafter",
    ),
    AspectDefinition(
        "aspect_overclock",
        "Overclock Coil",
        "Faster energy regen — more shifts per session.",
        "overclock",
    ),
    AspectDefinition(
        "aspect_plunder",
        "Plunderer's Seal",
        "Steal extra nuggets when you win duels.",
        "plunder",
    ),
    AspectDefinition(
        "aspect_windfall",
        "Windfall Charm",
        "Boosts daily claims and passive chat earnings.",
        "windfall",
    ),
    AspectDefinition(
        "aspect_midas",
        "Midas Touch",
        "Job payouts and trivia-style luck on coin drops (chat rewards).",
        "midas",
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
class AspectBonuses:
    """All bonuses from one equipped aspect instance."""

    damage_mult: float = 1.0
    extra_crit: float = 0.0
    mitigation_bonus: float = 0.0
    hp_bonus: int = 0
    boss_damage_mult: float = 1.0
    second_wind_chance: float = 0.0
    extra_duels_per_hour: int = 0
    duel_cooldown_mult: float = 1.0
    work_income_mult: float = 1.0
    energy_regen_mult: float = 1.0
    energy_regen_flat: int = 0
    duel_loot_mult: float = 1.0
    daily_reward_mult: float = 1.0
    passive_income_mult: float = 1.0


# Back-compat alias used by duel/boss combat code paths
AspectCombatBonuses = AspectBonuses


def get_aspect(aspect_id: str) -> AspectDefinition | None:
    return ASPECT_MAP.get(aspect_id)


def roll_pct_for_threat(threat: int) -> float:
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


def bonuses_from_instance(instance: AspectInstance | None) -> AspectBonuses:
    if instance is None:
        return AspectBonuses()
    pct = instance.roll_pct
    r = pct / 100.0
    effect = instance.effect

    if effect == "damage":
        return AspectBonuses(damage_mult=1.0 + r)
    if effect == "crit":
        return AspectBonuses(extra_crit=r)
    if effect == "mitigation":
        return AspectBonuses(mitigation_bonus=r)
    if effect == "vitality":
        return AspectBonuses(hp_bonus=int(round(config.PLAYER_BASE_HP * r)))
    if effect == "boss_slayer":
        return AspectBonuses(boss_damage_mult=1.0 + r)
    if effect == "second_wind":
        return AspectBonuses(second_wind_chance=min(0.45, r * 0.9))
    if effect == "duelist":
        extra = min(4, max(1, int(round(pct / 8.0))))
        cooldown_mult = max(0.35, 1.0 - pct / 85.0)
        return AspectBonuses(
            extra_duels_per_hour=extra,
            duel_cooldown_mult=cooldown_mult,
        )
    if effect == "grafter":
        return AspectBonuses(work_income_mult=1.0 + min(2.0, pct * 0.05))
    if effect == "overclock":
        return AspectBonuses(
            energy_regen_mult=1.0 + pct / 40.0,
            energy_regen_flat=max(0, int(pct // 8)),
        )
    if effect == "plunder":
        return AspectBonuses(duel_loot_mult=1.0 + pct / 45.0)
    if effect == "windfall":
        return AspectBonuses(
            daily_reward_mult=1.0 + pct / 22.0,
            passive_income_mult=1.0 + pct / 40.0,
        )
    if effect == "midas":
        return AspectBonuses(
            work_income_mult=1.0 + min(1.5, pct * 0.035),
            passive_income_mult=1.0 + pct / 35.0,
        )
    return AspectBonuses()


def combat_bonuses_from_instance(instance: AspectInstance | None) -> AspectBonuses:
    return bonuses_from_instance(instance)


def effective_energy_regen_per_tick(base: int, bonuses: AspectBonuses) -> int:
    boosted = int(round(base * bonuses.energy_regen_mult)) + bonuses.energy_regen_flat
    return max(1, boosted)


EFFECT_LABELS: dict[str, str] = {
    "damage": "damage",
    "crit": "crit chance",
    "mitigation": "mitigation",
    "vitality": "max HP",
    "boss_slayer": "boss damage",
    "second_wind": "lethal-save chance",
    "duelist": "duel limits",
    "grafter": "work income",
    "overclock": "energy regen",
    "plunder": "duel loot",
    "windfall": "daily & passive",
    "midas": "work & chat gold",
}


def format_aspect_line(instance: AspectInstance, *, equipped: bool = False) -> str:
    tag = " *(equipped)*" if equipped else ""
    return (
        f"**{instance.name}** — **{instance.roll_pct:g}%** "
        f"{EFFECT_LABELS.get(instance.effect, instance.effect)}{tag}\n"
        f"└ `aspect#{instance.instance_id}` · {format_aspect_effect(instance)}"
    )


def format_aspect_effect(instance: AspectInstance) -> str:
    b = bonuses_from_instance(instance)
    pct = instance.roll_pct
    effect = instance.effect
    if effect == "damage":
        return f"+{pct:g}% damage dealt"
    if effect == "crit":
        return f"+{pct:g}% crit chance"
    if effect == "mitigation":
        return f"+{pct:g}% damage blocked"
    if effect == "vitality":
        return f"+{b.hp_bonus} max HP"
    if effect == "boss_slayer":
        return f"+{pct:g}% boss damage"
    if effect == "second_wind":
        return f"{int(round(b.second_wind_chance * 100))}% chance to survive a lethal duel hit at 1 HP"
    if effect == "duelist":
        return (
            f"+{b.extra_duels_per_hour} duels/hr · "
            f"{int(round((1.0 - b.duel_cooldown_mult) * 100))}% faster same-target cooldown"
        )
    if effect == "grafter":
        return f"×{b.work_income_mult:.2f} /work payouts (up to 3× at 40% roll)"
    if effect == "overclock":
        return (
            f"×{b.energy_regen_mult:.2f} energy regen "
            f"(+{b.energy_regen_flat} per tick)"
        )
    if effect == "plunder":
        return f"×{b.duel_loot_mult:.2f} nuggets stolen on duel wins"
    if effect == "windfall":
        return (
            f"×{b.daily_reward_mult:.2f} daily · "
            f"×{b.passive_income_mult:.2f} chat drip"
        )
    if effect == "midas":
        return (
            f"×{b.work_income_mult:.2f} jobs · "
            f"×{b.passive_income_mult:.2f} chat rewards"
        )
    return f"{pct:g}% power"
