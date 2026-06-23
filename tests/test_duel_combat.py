"""Duel combat loadout and simulation."""

from __future__ import annotations

import unittest

from utils.duel_combat import fighter_from_equipment, simulate_duel


class DuelCombatTests(unittest.TestCase):
    def test_fighter_from_equipment_dual_wield(self) -> None:
        fighter = fighter_from_equipment(
            1,
            "Tester",
            {"weapon": "iron_sword", "off_hand": "iron_pistol"},
            prestige_level=0,
        )
        self.assertEqual(fighter.weapon.base.id, "iron_sword")
        self.assertEqual(fighter.off_hand.base.id, "iron_pistol")
        self.assertGreater(fighter.max_hp, 0)
        self.assertEqual(fighter.hp, fighter.max_hp)

    def test_simulate_duel_produces_winner(self) -> None:
        a = fighter_from_equipment(1, "A", {"weapon": "iron_sword"}, prestige_level=0)
        b = fighter_from_equipment(2, "B", {"weapon": "twig_sword"}, prestige_level=0)
        result = simulate_duel(a, b)
        self.assertIn(result.winner_id, (1, 2))
        self.assertTrue(result.strikes)


if __name__ == "__main__":
    unittest.main()
