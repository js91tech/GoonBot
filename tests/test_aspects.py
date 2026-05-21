"""Aspect rolls and combat bonuses."""

from __future__ import annotations

import unittest

from utils.aspects import (
    combat_bonuses_from_instance,
    instance_from_row,
    roll_pct_for_threat,
    roll_pct_shop,
)


class AspectTests(unittest.TestCase):
    def test_roll_pct_for_threat_in_range(self) -> None:
        for threat in range(1, 6):
            pct = roll_pct_for_threat(threat)
            self.assertGreater(pct, 0.0)

    def test_shop_roll_in_band(self) -> None:
        for _ in range(20):
            pct = roll_pct_shop()
            self.assertGreaterEqual(pct, 4.0)
            self.assertLessEqual(pct, 14.0)

    def test_damage_aspect_bonus(self) -> None:
        row = {"instance_id": 1, "aspect_id": "aspect_ravager", "roll_pct": 10.0}
        inst = instance_from_row(row)
        bonuses = combat_bonuses_from_instance(inst)
        self.assertAlmostEqual(bonuses.damage_mult, 1.1)

    def test_vitality_aspect_hp(self) -> None:
        row = {"instance_id": 2, "aspect_id": "aspect_vitality", "roll_pct": 20.0}
        inst = instance_from_row(row)
        bonuses = combat_bonuses_from_instance(inst)
        self.assertEqual(bonuses.hp_bonus, 20)


if __name__ == "__main__":
    unittest.main()
