"""Character attribute and debuff resistance tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from database import Database
from utils.character_attributes import (
    CharacterAttributes,
    apply_cc_duration,
    combat_bonuses_from_attributes,
    debuff_resistance_from_attributes,
    total_attribute_points_earned,
    unspent_attribute_points,
)
from utils.boss_element_effects import roll_element_proc


class CharacterAttributeUtilTests(unittest.TestCase):
    def test_points_earned_from_class_xp(self) -> None:
        self.assertEqual(total_attribute_points_earned(0), 0)
        self.assertEqual(total_attribute_points_earned(250), 2)
        self.assertEqual(total_attribute_points_earned(99999), config.ATTR_MAX_TOTAL_POINTS)

    def test_unspent_points(self) -> None:
        attrs = CharacterAttributes(agility=15)
        self.assertEqual(unspent_attribute_points(attrs, 1000), 5)

    def test_agi_reduces_cc_duration(self) -> None:
        base_attrs = CharacterAttributes()
        high_agi = CharacterAttributes(agility=50)
        base_resist = debuff_resistance_from_attributes(base_attrs)
        high_resist = debuff_resistance_from_attributes(high_agi)
        self.assertLess(high_resist.cc_duration_mult, base_resist.cc_duration_mult)
        reduced = apply_cc_duration(20.0, high_resist)
        self.assertLess(reduced, 20.0)
        self.assertGreaterEqual(reduced, config.ATTR_MIN_DEBUFF_SECONDS)

    def test_def_boosts_mitigation_and_dot_resist(self) -> None:
        attrs = CharacterAttributes(defense=40)
        combat = combat_bonuses_from_attributes(attrs)
        resist = debuff_resistance_from_attributes(attrs)
        self.assertGreater(combat.mitigation_bonus, 0.0)
        self.assertLess(resist.dot_damage_mult, 1.0)

    def test_str_and_vit_combat_bonuses(self) -> None:
        attrs = CharacterAttributes(strength=30, vitality=25)
        combat = combat_bonuses_from_attributes(attrs)
        self.assertGreater(combat.damage_mult, 1.0)
        self.assertGreater(combat.hp_bonus, 0)


class CharacterAttributeDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 8001
        self.user_id = 42

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_allocate_attribute_points(self) -> None:
        await self.db.add_class_xp(self.user_id, self.guild_id, 500)
        ok, msg = await self.db.allocate_attribute_points(
            self.user_id, self.guild_id, "agility", 3,
        )
        self.assertTrue(ok, msg)
        attrs = await self.db.get_character_attributes(self.user_id, self.guild_id)
        self.assertEqual(attrs.agility, config.ATTR_BASE_VALUE + 3)

    async def test_allocate_rejects_over_cap(self) -> None:
        await self.db.add_class_xp(self.user_id, self.guild_id, 5000)
        ok, _ = await self.db.allocate_attribute_points(
            self.user_id, self.guild_id, "agility", config.ATTR_MAX_VALUE,
        )
        self.assertFalse(ok)


class BossDebuffResistanceTests(unittest.TestCase):
    @patch("utils.boss_element_effects.random.random", return_value=0.0)
    @patch("utils.boss_element_effects.roll_debuff_duration_for_threat", return_value=20.0)
    def test_high_agi_shortens_storm_stun(self, _duration: object, _random: object) -> None:
        high_agi = debuff_resistance_from_attributes(CharacterAttributes(agility=50))
        proc = roll_element_proc("storm", now=100.0, threat=6, resistance=high_agi)
        assert proc.storm_stun_seconds is not None
        self.assertLess(proc.storm_stun_seconds, 20.0)
        self.assertGreaterEqual(proc.storm_stun_seconds, config.ATTR_MIN_DEBUFF_SECONDS)


if __name__ == "__main__":
    unittest.main()
