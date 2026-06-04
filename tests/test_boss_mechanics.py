"""Boss HP and raid damage scaling tests."""
from __future__ import annotations

import unittest

import config
from utils.boss_mechanics import boss_raid_damage_bonus, compute_boss_hp


class BossMechanicsTests(unittest.TestCase):
    def test_mythic_hp_uses_standard_multiplier(self) -> None:
        circulation = 5_000_000.0
        scale = config.BOSS_CIRCULATION_HP_FACTOR
        expected = (
            min(config.BOSS_HP_CAP, circulation * scale)
            * 4.5
            * (1 + 4 * config.BOSS_THREAT_HP_BONUS_PER_TIER)
        )
        self.assertAlmostEqual(compute_boss_hp(circulation, scale, "mythic"), expected)

    def test_mythic_damage_bonus_helps_raid_dps(self) -> None:
        self.assertEqual(boss_raid_damage_bonus("normal"), 1.0)
        self.assertGreater(boss_raid_damage_bonus("mythic"), 1.0)
        self.assertEqual(
            boss_raid_damage_bonus("mythic"),
            config.BOSS_RAID_DAMAGE_BONUS_BY_THREAT[5],
        )


if __name__ == "__main__":
    unittest.main()
