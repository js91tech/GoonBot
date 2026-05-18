"""Loadout slot resolution for dual-wield."""

from __future__ import annotations

import unittest

from items import get_item
from utils.loadout import equip_target_slot, parse_loadout, resolve_primary_off_hand


class EquipTargetSlotTests(unittest.TestCase):
    def test_gun_goes_off_hand_with_sword(self) -> None:
        sword = get_item("iron_sword")
        gun = get_item("iron_pistol")
        assert sword is not None and gun is not None
        slot = equip_target_slot(gun, {"weapon": sword.id})
        self.assertEqual(slot, "off_hand")

    def test_gun_goes_off_hand_when_main_has_gun(self) -> None:
        cap = get_item("cap_gun")
        pistol = get_item("iron_pistol")
        assert cap is not None and pistol is not None
        slot = equip_target_slot(pistol, {"weapon": cap.id})
        self.assertEqual(slot, "off_hand")

    def test_gun_goes_main_hand_when_empty(self) -> None:
        gun = get_item("cap_gun")
        assert gun is not None
        slot = equip_target_slot(gun, {})
        self.assertEqual(slot, "weapon")

    def test_dual_gun_loadout_resolves(self) -> None:
        cap = get_item("cap_gun")
        pistol = get_item("iron_pistol")
        assert cap is not None and pistol is not None
        loadout = parse_loadout({"weapon": cap.id, "off_hand": pistol.id})
        self.assertEqual(loadout.primary.id, pistol.id)
        self.assertEqual(loadout.off_hand.id, cap.id)


if __name__ == "__main__":
    unittest.main()
