"""Boss HP and raid damage scaling tests."""
from __future__ import annotations

import unittest

import config
from utils.boss_mechanics import boss_raid_damage_retention, compute_boss_hp


class BossMechanicsTests(unittest.TestCase):
    def test_mythic_hp_higher_than_before_rebalance(self) -> None:
        circulation = 5_000_000.0
        scale = config.BOSS_CIRCULATION_HP_FACTOR
        old_hp = min(config.BOSS_HP_CAP, circulation * scale) * 4.5 * (1 + 4 * 0.10)
        new_hp = compute_boss_hp(circulation, scale, "mythic")
        self.assertGreater(new_hp, old_hp * 1.35)

    def test_mythic_damage_retention_reduces_raid_damage(self) -> None:
        self.assertEqual(boss_raid_damage_retention("normal"), 1.0)
        self.assertLess(boss_raid_damage_retention("mythic"), 0.90)
        self.assertEqual(
            boss_raid_damage_retention("mythic"),
            config.BOSS_RAID_DAMAGE_RETENTION_BY_THREAT[5],
        )


if __name__ == "__main__":
    unittest.main()
