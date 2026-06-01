from __future__ import annotations

import random

import config


def threat_for_variant(variant: str) -> int:
    return int(config.BOSS_VARIANTS.get(variant, {}).get("threat", 1))


def compute_boss_hp(
    circulation: float,
    scale_factor: float,
    variant: str,
    *,
    hp_multiplier: float = 1.0,
    mirrored_variant: str | None = None,
) -> float:
    if variant == "tomass":
        mirror = mirrored_variant or "enraged"
        scaled_hp = max(config.BOSS_MIN_HP, circulation * scale_factor)
        base_hp = min(config.BOSS_HP_CAP, scaled_hp)
        mirror_mult = float(config.BOSS_VARIANTS[mirror]["multiplier"])
        strength = float(config.BOSS_VARIANTS["tomass"]["mirrored_strength_mult"])
        hp = base_hp * mirror_mult * strength
        threat = threat_for_variant(variant)
        hp *= 1.0 + (threat - 1) * config.BOSS_THREAT_HP_BONUS_PER_TIER
        return hp * hp_multiplier

    variant_cfg = config.BOSS_VARIANTS[variant]
    fixed = variant_cfg.get("fixed_hp")
    if fixed is not None:
        hp = float(fixed)
    else:
        scaled_hp = max(config.BOSS_MIN_HP, circulation * scale_factor)
        base_hp = min(config.BOSS_HP_CAP, scaled_hp)
        hp = base_hp * float(variant_cfg["multiplier"])
        threat = threat_for_variant(variant)
        hp *= 1.0 + (threat - 1) * config.BOSS_THREAT_HP_BONUS_PER_TIER
    return hp * hp_multiplier


def passive_decay_rate_for_variant(variant: str) -> float:
    threat = threat_for_variant(variant)
    return config.BOSS_PASSIVE_DECAY_BY_THREAT.get(
        threat,
        config.BOSS_PASSIVE_HP_DECAY_FRACTION_PER_MINUTE,
    )


def reward_mult_for_variant(variant: str) -> float:
    threat = threat_for_variant(variant)
    return config.BOSS_REWARD_MULT_BY_THREAT.get(threat, 1.0)


def raider_damage_mult(distinct_raiders: int) -> float:
    if distinct_raiders >= 4:
        return 1.0
    return config.BOSS_RAIDER_DAMAGE_MULT.get(distinct_raiders, 1.0)


def scale_counter_damage(
    raw_damage: int,
    variant: str,
    *,
    hp_ratio: float,
) -> int:
    threat = threat_for_variant(variant)
    mult = 1.0 + (threat - 1) * config.BOSS_COUNTER_THREAT_SCALE
    if hp_ratio <= config.BOSS_ENRAGE_HP_THRESHOLD:
        mult *= config.BOSS_ENRAGE_COUNTER_MULT
    return max(1, int(round(raw_damage * mult)))


def roll_counter_damage(variant: str, *, hp_ratio: float) -> int:
    low, high = config.BOSS_VARIANTS[variant]["counter_damage"]
    raw = random.randint(int(low), int(high))
    return scale_counter_damage(raw, variant, hp_ratio=hp_ratio)


def boss_expires_at(spawn_ts: float, variant: str) -> float | None:
    despawn = config.BOSS_VARIANTS.get(variant, {}).get("despawn_seconds")
    if despawn is None:
        return None
    return spawn_ts + float(despawn)
