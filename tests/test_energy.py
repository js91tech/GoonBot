"""Energy regen and cap upgrades."""

from __future__ import annotations

import time
import unittest

import config
from utils.energy import apply_energy_regen, energy_cap_for_upgrades, energy_snapshot


class EnergyTests(unittest.TestCase):
    def test_regen_ticks(self) -> None:
        cap = 30
        current, at = apply_energy_regen(
            10,
            cap,
            0.0,
            now=600.0,
            regen_per_tick=5,
            tick_seconds=300.0,
        )
        self.assertEqual(current, 20)
        self.assertEqual(at, 600.0)

    def test_regen_clamps_at_cap(self) -> None:
        current, _ = apply_energy_regen(
            28,
            30,
            0.0,
            now=300.0,
            regen_per_tick=5,
            tick_seconds=300.0,
        )
        self.assertEqual(current, 30)

    def test_cap_upgrades(self) -> None:
        self.assertEqual(
            energy_cap_for_upgrades(2),
            config.ENERGY_BASE_CAP + 2 * config.ENERGY_CAP_PER_UPGRADE,
        )

    def test_snapshot_seconds_until_tick(self) -> None:
        snap = energy_snapshot(
            10,
            30,
            0,
            last_tick_at=100.0,
            now=250.0,
            regen_per_tick=5,
            tick_seconds=300,
        )
        self.assertEqual(snap.current, 10)
        self.assertGreater(snap.seconds_until_tick, 0)


if __name__ == "__main__":
    unittest.main()
