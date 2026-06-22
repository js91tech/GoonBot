"""BDO-style gear enhancement: materials, nugget costs, stats, fail/repair."""
from __future__ import annotations

import random
from dataclasses import dataclass

import config
from items import ShopItem, get_item
from utils.gear_sets import craft_base_id


@dataclass(frozen=True)
class EffectiveGear:
    """Combat-ready gear with enhancement applied."""

    base: ShopItem
    power: int
    crit_chance: float
    hp_bonus: int
    enhancement_level: int = 0
    is_broken: bool = False

    @property
    def name(self) -> str:
        return self.base.name

    @property
    def verbs(self) -> tuple[str, ...]:
        return self.base.verbs

    @property
    def category(self) -> str:
        return self.base.category

    @property
    def flat_damage(self) -> int:
        return self.base.flat_damage

    @property
    def flat_hp(self) -> int:
        return self.base.hp_bonus + self.base.flat_hp

    @property
    def flat_crit(self) -> float:
        return self.base.flat_crit

    @property
    def flat_mitigation(self) -> float:
        return self.base.flat_mitigation


@dataclass(frozen=True)
class AccessoryBonuses:
    flat_damage: int = 0
    flat_hp: int = 0
    flat_crit: float = 0.0
    flat_mitigation: float = 0.0

    def merged(self, other: AccessoryBonuses) -> AccessoryBonuses:
        return AccessoryBonuses(
            flat_damage=self.flat_damage + other.flat_damage,
            flat_hp=self.flat_hp + other.flat_hp,
            flat_crit=self.flat_crit + other.flat_crit,
            flat_mitigation=self.flat_mitigation + other.flat_mitigation,
        )


@dataclass(frozen=True)
class EnhanceAttemptCost:
    target_level: int
    material_id: str
    material_qty: int
    nugget_cost: float
    success_rate: float


@dataclass(frozen=True)
class EnhanceResult:
    success: bool
    new_level: int
    broken: bool
    downgraded: bool
    message: str


def _lerp(start: float, end: float, t: float) -> float:
    return start + (end - start) * max(0.0, min(1.0, t))


def display_level(level: int) -> str:
    names = {16: "PRI", 17: "DUO", 18: "TRI", 19: "TET", 20: "PENTA"}
    if level <= 0:
        return "+0"
    if level in names:
        return names[level]
    return f"+{level}"


def material_for_target_level(target: int) -> str:
    if target <= config.ENHANCE_SCRAP_MAX_LEVEL:
        return "alchemy_scrap"
    if target <= config.ENHANCE_HARDENER_MAX_LEVEL:
        return "void_hardener"
    return "celestial_shard"


def material_cost_for_target(target: int) -> int:
    if target <= 3:
        return 1
    if target <= 7:
        return 2
    if target <= 10:
        return 3
    if target <= 13:
        return 2
    if target <= 15:
        return 3
    if target <= 18:
        return 2
    return 3


def nugget_cost_for_attempt(target: int) -> float:
    if target <= 10:
        return _lerp(
            config.ENHANCE_NUGGET_COST_AT_PLUS_1,
            config.ENHANCE_NUGGET_COST_AT_PLUS_10,
            (target - 1) / 9,
        )
    if target <= 15:
        return _lerp(
            config.ENHANCE_NUGGET_COST_AT_PLUS_10 + 2_000,
            config.ENHANCE_NUGGET_COST_AT_PLUS_15,
            (target - 11) / 4,
        )
    return _lerp(
        config.ENHANCE_NUGGET_COST_AT_PRI,
        config.ENHANCE_NUGGET_COST_AT_PENTA,
        (target - 16) / 4,
    )


def success_rate_for_target(target: int) -> float:
    if target <= 5:
        return 0.85 - (target - 1) * 0.05
    if target <= 10:
        return 0.60 - (target - 6) * 0.04
    if target <= 15:
        return 0.35 - (target - 11) * 0.04
    return max(0.03, 0.18 - (target - 16) * 0.03)


def enhance_attempt_cost(current_level: int) -> EnhanceAttemptCost | None:
    if current_level >= config.ENHANCE_MAX_LEVEL:
        return None
    target = current_level + 1
    return EnhanceAttemptCost(
        target_level=target,
        material_id=material_for_target_level(target),
        material_qty=material_cost_for_target(target),
        nugget_cost=nugget_cost_for_attempt(target),
        success_rate=success_rate_for_target(target),
    )


def stat_multiplier_for_level(level: int) -> float:
    if level <= 0:
        return 1.0
    mult = 1.0 + level * config.ENHANCE_POWER_BONUS_PER_LEVEL
    if level >= 16:
        mult *= config.ENHANCE_PRI_BONUS_MULT
    return mult


def resolve_effective_gear(
    item: ShopItem | None,
    *,
    enhancement_level: int = 0,
    is_broken: bool = False,
) -> EffectiveGear | None:
    if item is None or is_broken:
        return None
    mult = stat_multiplier_for_level(enhancement_level)
    return EffectiveGear(
        base=item,
        power=max(1, int(round(item.power * mult))),
        crit_chance=item.crit_chance * mult if item.crit_chance else 0.0,
        hp_bonus=max(0, int(round(item.hp_bonus * mult))),
        enhancement_level=enhancement_level,
        is_broken=False,
    )


def accessory_bonuses_from_gear(*pieces: EffectiveGear | None) -> AccessoryBonuses:
    total = AccessoryBonuses()
    for piece in pieces:
        if piece is None:
            continue
        total = total.merged(
            AccessoryBonuses(
                flat_damage=piece.base.flat_damage,
                flat_hp=piece.base.flat_hp,
                flat_crit=piece.base.flat_crit,
                flat_mitigation=piece.base.flat_mitigation,
            ),
        )
    return total


def repair_nugget_cost(item_id: str) -> float:
    base_id = craft_base_id(item_id) or item_id.removeprefix("boss_weak_")
    item = get_item(base_id) or get_item(item_id)
    if item is None or item.price <= 0:
        return 1.0
    return max(1.0, float(item.price) * config.ENHANCE_REPAIR_NUGGET_FACTOR)


def roll_enhancement(current_level: int) -> EnhanceResult:
    cost = enhance_attempt_cost(current_level)
    if cost is None:
        return EnhanceResult(
            success=False,
            new_level=current_level,
            broken=False,
            downgraded=False,
            message="Already at max enhancement.",
        )
    target = cost.target_level
    if random.random() < cost.success_rate:
        return EnhanceResult(
            success=True,
            new_level=target,
            broken=False,
            downgraded=False,
            message=f"Success! Now **{display_level(target)}**.",
        )
    if target >= config.ENHANCE_FAIL_BREAK_FROM:
        return EnhanceResult(
            success=False,
            new_level=current_level,
            broken=True,
            downgraded=False,
            message=f"Fail! Gear is **broken** — repair with `/repair-gear`.",
        )
    if target >= config.ENHANCE_FAIL_DOWNGRADE_FROM and current_level > 0:
        new_level = current_level - 1
        return EnhanceResult(
            success=False,
            new_level=new_level,
            broken=False,
            downgraded=True,
            message=f"Fail! Downgraded to **{display_level(new_level)}**.",
        )
    return EnhanceResult(
        success=False,
        new_level=current_level,
        broken=False,
        downgraded=False,
        message="Fail! Enhancement level unchanged.",
    )


def format_instance_label(item: ShopItem, instance_id: int, level: int, *, broken: bool) -> str:
    suffix = display_level(level)
    state = " [BROKEN]" if broken else ""
    return f"{item.name} {suffix} (#{instance_id}){state}"
