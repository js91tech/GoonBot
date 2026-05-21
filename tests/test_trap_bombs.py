"""Trap bomb proc chance and damage."""

from __future__ import annotations

import unittest

from utils.trap_bombs import trap_proc_chance, try_trap_proc


class TrapBombTests(unittest.TestCase):
    def test_zero_bombs_no_chance(self) -> None:
        self.assertEqual(trap_proc_chance(0), 0.0)

    def test_chance_scales_with_inventory(self) -> None:
        self.assertLess(trap_proc_chance(1), trap_proc_chance(5))
        self.assertLessEqual(trap_proc_chance(50), 0.75)

    def test_proc_returns_damage(self) -> None:
        proc = try_trap_proc(10)
        if proc is not None:
            self.assertGreater(proc.damage, 0)
            self.assertEqual(proc.bombs_remaining, 9)


if __name__ == "__main__":
    unittest.main()
