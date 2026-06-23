from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config
from items import ShopItem, accessory_equip_slot, get_item, is_accessory
from utils.enhancement import AccessoryBonuses, EffectiveGear, accessory_bonuses_from_gear, resolve_effective_gear


@dataclass(frozen=True)
class PlayerLoadout:
    """Resolved combat loadout with enhancement and accessories."""

    primary: EffectiveGear | None
    off_hand: EffectiveGear | None
    armor: EffectiveGear | None
    ring: EffectiveGear | None
    amulet: EffectiveGear | None

    @property
    def accessory_bonuses(self) -> AccessoryBonuses:
        return accessory_bonuses_from_gear(self.ring, self.amulet)


def _resolve_slot_gear(
    item_id: str | None,
    instance_id: int | None,
    instances: dict[int, Any],
    *,
    slot_unstable: bool,
) -> EffectiveGear | None:
    if slot_unstable or not item_id:
        return None
    item = get_item(item_id)
    if item is None:
        return None
    level = 0
    broken = False
    if instance_id is not None and instance_id in instances:
        row = instances[instance_id]
        level = int(row["enhancement_level"])
        broken = bool(int(row["is_broken"]))
    elif instance_id is None and item.category in ("weapon", "gun", "armor", "accessory"):
        broken = False
    return resolve_effective_gear(item, enhancement_level=level, is_broken=broken)


def parse_resolved_loadout(
    equipment_records: dict[str, dict[str, str | int | None]],
    *,
    instances: dict[int, Any],
    unstable_slots: set[str] | None = None,
) -> PlayerLoadout:
    unstable = unstable_slots or set()

    def rec(slot: str) -> tuple[str | None, int | None]:
        data = equipment_records.get(slot)
        if not data:
            return None, None
        inst = data.get("gear_instance_id")
        return str(data["item_id"]), int(inst) if inst is not None else None

    weapon_id, weapon_inst = rec("weapon")
    off_id, off_inst = rec("off_hand")
    armor_id, armor_inst = rec("armor")
    ring_id, ring_inst = rec("ring")
    amulet_id, amulet_inst = rec("amulet")

    weapon_slot = _resolve_slot_gear(
        weapon_id, weapon_inst, instances, slot_unstable="weapon" in unstable,
    )
    off_slot = _resolve_slot_gear(
        off_id, off_inst, instances, slot_unstable="off_hand" in unstable,
    )
    armor = _resolve_slot_gear(
        armor_id, armor_inst, instances, slot_unstable="armor" in unstable,
    )
    ring = _resolve_slot_gear(
        ring_id, ring_inst, instances, slot_unstable="ring" in unstable,
    )
    amulet = _resolve_slot_gear(
        amulet_id, amulet_inst, instances, slot_unstable="amulet" in unstable,
    )
    primary, off_hand = resolve_primary_off_hand(weapon_slot, off_slot)
    return PlayerLoadout(
        primary=primary,
        off_hand=off_hand,
        armor=armor,
        ring=ring,
        amulet=amulet,
    )


def parse_loadout(
    equipment: dict[str, str],
    *,
    unstable_slots: set[str] | None = None,
) -> PlayerLoadout:
    records = {
        slot: {"item_id": item_id, "gear_instance_id": None}
        for slot, item_id in equipment.items()
    }
    return parse_resolved_loadout(records, instances={}, unstable_slots=unstable_slots)


def resolve_primary_off_hand(
    weapon_slot: EffectiveGear | None,
    off_slot: EffectiveGear | None,
) -> tuple[EffectiveGear | None, EffectiveGear | None]:
    if weapon_slot is None and off_slot is None:
        return None, None
    if weapon_slot is not None and off_slot is not None:
        if weapon_slot.category == "weapon" and off_slot.category == "gun":
            return weapon_slot, off_slot
        if weapon_slot.category == "gun" and off_slot.category == "weapon":
            return off_slot, weapon_slot
        if off_slot.power > weapon_slot.power:
            return off_slot, weapon_slot
        return weapon_slot, off_slot
    return weapon_slot, off_slot


def off_hand_power_bonus(off_hand: EffectiveGear | None) -> int:
    if off_hand is None:
        return 0
    return int(round(off_hand.power * config.OFF_HAND_DAMAGE_FACTOR))


def off_hand_crit_bonus(off_hand: EffectiveGear | None) -> float:
    if off_hand is None:
        return 0.0
    return off_hand.crit_chance * config.OFF_HAND_CRIT_FACTOR


def effective_attack_power(primary: EffectiveGear | None, off_hand: EffectiveGear | None) -> int:
    if primary is None:
        return 0
    return primary.power + off_hand_power_bonus(off_hand)


def equip_target_slot(item: ShopItem, equipment: dict[str, str]) -> str:
    if is_accessory(item):
        return accessory_equip_slot(item)
    if item.category == "armor":
        return "armor"
    if item.category == "gun":
        weapon_id = equipment.get("weapon")
        weapon_item = get_item(weapon_id) if weapon_id else None
        if weapon_item is not None:
            if weapon_item.category == "weapon":
                return "off_hand"
            if weapon_item.category == "gun":
                return "off_hand"
        return "weapon"
    return "weapon"
