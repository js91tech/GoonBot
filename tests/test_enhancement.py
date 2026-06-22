"""BDO-style enhancement costs, repair, and roll outcomes."""

from __future__ import annotations

import unittest

import config
from items import get_item
from utils.enhancement import (
    display_level,
    enhance_attempt_cost,
    material_for_target_level,
    nugget_cost_for_attempt,
    repair_nugget_cost,
    roll_enhancement,
    stat_multiplier_for_level,
)


class EnhancementCostTests(unittest.TestCase):
    def test_nugget_anchors(self) -> None:
        self.assertAlmostEqual(nugget_cost_for_attempt(10), config.ENHANCE_NUGGET_COST_AT_PLUS_10, delta=1.0)
        self.assertAlmostEqual(nugget_cost_for_attempt(15), config.ENHANCE_NUGGET_COST_AT_PLUS_15, delta=1.0)
        self.assertAlmostEqual(nugget_cost_for_attempt(20), config.ENHANCE_NUGGET_COST_AT_PENTA, delta=1.0)

    def test_material_tiers(self) -> None:
        self.assertEqual(material_for_target_level(5), "alchemy_scrap")
        self.assertEqual(material_for_target_level(12), "void_hardener")
        self.assertEqual(material_for_target_level(17), "celestial_shard")

    def test_repair_is_ten_percent_base_price(self) -> None:
        blade = get_item("iron_sword")
        assert blade is not None
        expected = max(1.0, blade.price * config.ENHANCE_REPAIR_NUGGET_FACTOR)
        self.assertAlmostEqual(repair_nugget_cost("iron_sword"), expected)

    def test_display_levels(self) -> None:
        self.assertEqual(display_level(7), "+7")
        self.assertEqual(display_level(16), "PRI")
        self.assertEqual(display_level(20), "PENTA")

    def test_max_level_has_no_cost(self) -> None:
        self.assertIsNone(enhance_attempt_cost(config.ENHANCE_MAX_LEVEL))

    def test_stat_multiplier_grows(self) -> None:
        self.assertGreater(stat_multiplier_for_level(10), stat_multiplier_for_level(1))
        self.assertGreater(stat_multiplier_for_level(16), stat_multiplier_for_level(15))


class EnhancementRollTests(unittest.TestCase):
    def test_roll_at_max_is_noop(self) -> None:
        result = roll_enhancement(config.ENHANCE_MAX_LEVEL)
        self.assertFalse(result.success)
        self.assertEqual(result.new_level, config.ENHANCE_MAX_LEVEL)


if __name__ == "__main__":
    unittest.main()
