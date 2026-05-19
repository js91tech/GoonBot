"""Summoner penalty helpers."""

from __future__ import annotations

import unittest

import config
from utils.summoner_penalty import (
    apply_summoner_attack_debuff,
    apply_summoner_counter_damage,
    is_summoner_debuffed,
)


class SummonerPenaltyTests(unittest.TestCase):
    def test_debuffed_only_for_summoner(self) -> None:
        row = {"summoner_id": 42}
        self.assertTrue(is_summoner_debuffed(row, 42))
        self.assertFalse(is_summoner_debuffed(row, 99))

    def test_attack_debuff(self) -> None:
        self.assertEqual(
            apply_summoner_attack_debuff(100),
            int(100 * config.SUMMONER_DEBUFF_ATK_DEF_RETENTION),
        )

    def test_counter_multiplier(self) -> None:
        self.assertEqual(apply_summoner_counter_damage(50), 100)


if __name__ == "__main__":
    unittest.main()
