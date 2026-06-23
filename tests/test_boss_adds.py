"""Raid add spawn rules and loot tables."""

from __future__ import annotations

import unittest

from utils.boss_adds import (
    FORBIDDEN_ADD_DROPS,
    add_max_hp,
    pick_add_type,
    roll_add_loot,
    should_spawn_add,
)


class BossAddTests(unittest.TestCase):
    def test_loot_never_includes_celestial_shard(self) -> None:
        for add_type in ("henchman", "court_jester"):
            for variant in ("normal", "enraged", "shadow", "celestial", "mythic", "zz_wrath"):
                for _ in range(50):
                    drops = roll_add_loot(add_type, variant)
                    for item_id, _qty in drops:
                        self.assertNotIn(item_id, FORBIDDEN_ADD_DROPS)

    def test_henchman_drops_scrap(self) -> None:
        drops = roll_add_loot("henchman", "enraged")
        self.assertTrue(drops)
        self.assertEqual(drops[0][0], "alchemy_scrap")
        self.assertGreaterEqual(drops[0][1], 1)

    def test_jester_drops_hardener(self) -> None:
        drops = roll_add_loot("court_jester", "shadow")
        self.assertTrue(drops)
        self.assertEqual(drops[0][0], "void_hardener")

    def test_add_hp_scales_with_boss(self) -> None:
        low = add_max_hp(10_000.0, 1)
        high = add_max_hp(10_000.0, 5)
        self.assertGreater(high, low)

    def test_spawn_blocked_above_half_hp(self) -> None:
        self.assertFalse(should_spawn_add(boss_hp_ratio=0.75, phase_crossed=False))

    def test_pick_add_type_returns_valid(self) -> None:
        for variant in ("enraged", "shadow", "mythic"):
            add_type = pick_add_type(variant)
            self.assertIn(add_type, ("henchman", "court_jester"))


if __name__ == "__main__":
    unittest.main()
