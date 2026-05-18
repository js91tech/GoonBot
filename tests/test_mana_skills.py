from __future__ import annotations

import unittest

import config
from utils.classes import is_healer_class
from utils.mana import mana_from_damage
from utils.skills import get_skill, skill_kit_id, skills_for_class


class TestManaSkills(unittest.TestCase):
    def test_healer_warden(self) -> None:
        self.assertTrue(is_healer_class("vanguard_warden"))
        self.assertTrue(is_healer_class("vanguard_warden_sentinel"))
        self.assertFalse(is_healer_class("vanguard_slayer"))

    def test_mana_from_damage_non_healer(self) -> None:
        gain = mana_from_damage(100, is_healer=False)
        self.assertEqual(gain, int(100 * config.MANA_ON_DAMAGE_PCT))

    def test_mana_from_damage_healer_lower(self) -> None:
        nh = mana_from_damage(100, is_healer=False)
        h = mana_from_damage(100, is_healer=True)
        self.assertLess(h, nh)

    def test_vanguard_slayer_has_skills(self) -> None:
        skills = skills_for_class("vanguard_slayer_reaper")
        self.assertGreaterEqual(len(skills), 2)
        self.assertEqual(skill_kit_id("vanguard_slayer_reaper"), "vanguard_slayer")

    def test_skill_lookup(self) -> None:
        skill = get_skill("vgs_rend")
        self.assertIsNotNone(skill)
        assert skill is not None
        self.assertEqual(skill.mana_cost, 20)


if __name__ == "__main__":
    unittest.main()
