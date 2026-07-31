from __future__ import annotations

import unittest
from unittest import mock

import config
from cogs.trivia import (
    format_trivia_window,
    roll_trivia_drug,
    trivia_drug_chance,
    trivia_speed_fraction,
    trivia_speed_multiplier,
)


class TriviaRewardMathTests(unittest.TestCase):
    def test_window_is_three_minutes(self) -> None:
        self.assertEqual(config.TRIVIA_SECONDS, 180)
        self.assertEqual(format_trivia_window(), "3 minutes")

    def test_faster_answers_pay_more(self) -> None:
        instant = trivia_speed_multiplier(config.TRIVIA_SECONDS)
        mid = trivia_speed_multiplier(config.TRIVIA_SECONDS / 2)
        late = trivia_speed_multiplier(0.0)
        self.assertAlmostEqual(instant, config.TRIVIA_SPEED_MAX_MULT)
        self.assertAlmostEqual(late, config.TRIVIA_SPEED_MIN_MULT)
        self.assertGreater(instant, mid)
        self.assertGreater(mid, late)

    def test_speed_fraction_clamps(self) -> None:
        self.assertEqual(trivia_speed_fraction(-5), 0.0)
        self.assertEqual(trivia_speed_fraction(config.TRIVIA_SECONDS * 2), 1.0)

    def test_faster_answers_raise_drug_chance(self) -> None:
        instant = trivia_drug_chance(config.TRIVIA_SECONDS)
        late = trivia_drug_chance(0.0)
        self.assertAlmostEqual(late, config.TRIVIA_DRUG_CHANCE)
        self.assertAlmostEqual(
            instant,
            config.TRIVIA_DRUG_CHANCE + config.TRIVIA_DRUG_FAST_BONUS,
        )
        self.assertGreater(instant, late)

    def test_roll_trivia_drug_returns_catalog_id(self) -> None:
        with mock.patch("cogs.trivia.random.choices", return_value=[type("D", (), {"drug_id": "blue_dream"})()]):
            self.assertEqual(roll_trivia_drug(), "blue_dream")


if __name__ == "__main__":
    unittest.main()
