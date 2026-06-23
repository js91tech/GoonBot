"""Combat engine with enhancement and accessory bonuses."""

from __future__ import annotations

import unittest

from items import get_item
from utils.combat_engine import max_hp_from_armor, roll_player_damage
from utils.enhancement import AccessoryBonuses, resolve_effective_gear


class CombatEngineEnhancementTests(unittest.TestCase):
    def test_enhanced_weapon_increases_damage_range(self) -> None:
        base = get_item("iron_sword")
        assert base is not None
        plain = resolve_effective_gear(base, enhancement_level=0)
        enhanced = resolve_effective_gear(base, enhancement_level=10)
        assert plain is not None and enhanced is not None
        self.assertGreater(enhanced.power, plain.power)

    def test_accessory_flat_damage_applies(self) -> None:
        weapon = get_item("iron_sword")
        assert weapon is not None
        gear = resolve_effective_gear(weapon)
        assert gear is not None
        acc = AccessoryBonuses(flat_damage=10)
        damages = [
            roll_player_damage(gear, accessory_bonuses=acc)[0]
            for _ in range(30)
        ]
        self.assertTrue(all(d >= 10 for d in damages))

    def test_accessory_flat_hp_in_max_hp(self) -> None:
        armor = get_item("bronze_vest")
        assert armor is not None
        gear = resolve_effective_gear(armor)
        assert gear is not None
        base_hp = max_hp_from_armor(gear)
        bonus_hp = max_hp_from_armor(gear, accessory_bonuses=AccessoryBonuses(flat_hp=25))
        self.assertEqual(bonus_hp, base_hp + 25)


if __name__ == "__main__":
    unittest.main()
