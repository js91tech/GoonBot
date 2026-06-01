"""Boss elemental counter effect tests."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from database import Database
from utils.boss_element_effects import (
    element_hazard_text,
    extra_attack_cooldown_for_status,
    roll_element_proc,
)


class BossElementEffectUtilTests(unittest.TestCase):
    def test_element_hazard_text_known_elements(self) -> None:
        self.assertIn("Frost", element_hazard_text("frost") or "")
        self.assertIn("Fire", element_hazard_text("fire") or "")
        self.assertIn("Storm", element_hazard_text("storm") or "")

    def test_extra_cooldown_stacks_frost_and_verdant(self) -> None:
        now = 1000.0
        extra = extra_attack_cooldown_for_status(
            attack_slow_until=now + 10,
            verdant_root_until=now + 5,
            now=now,
        )
        self.assertEqual(extra, 5)

    @patch("utils.boss_element_effects.random.random", return_value=0.0)
    def test_roll_frost_proc(self, _random: object) -> None:
        proc = roll_element_proc("frost", now=100.0)
        self.assertIn("Chilled", proc.note)
        self.assertIsNotNone(proc.frost_slow_until)


class BossElementDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 7001
        self.user_id = 99
        await self.db.replace_boss(self.guild_id, "Hannah", "normal", 5000.0, element="frost")

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_frost_slow_extends_attack_cooldown(self) -> None:
        now = time.time()
        await self.db.record_boss_attack_time(self.guild_id, self.user_id, now)
        await self.db.apply_boss_element_status(
            self.guild_id,
            self.user_id,
            frost_slow_until=now + 30,
        )
        remaining = await self.db.boss_attack_cooldown_remaining(
            self.guild_id,
            self.user_id,
            at=now + 1,
        )
        self.assertIsNotNone(remaining)
        assert remaining is not None
        self.assertGreater(remaining, 3.0)

    async def test_fire_dot_ticks_damage(self) -> None:
        max_hp = 200.0
        await self.db.sync_combat_hp(self.user_id, self.guild_id, max_hp)
        now = time.time()
        await self.db.apply_boss_element_status(
            self.guild_id,
            self.user_id,
            fire_burn=(15.0, 2, now - 1),
        )
        result = await self.db.process_boss_fire_dot(
            self.user_id,
            self.guild_id,
            max_hp,
            at=now,
        )
        self.assertIsNotNone(result)
        assert result is not None
        hp, _, tick_damage, ticks_left = result
        self.assertEqual(tick_damage, 15.0)
        self.assertEqual(ticks_left, 1)
        self.assertLess(hp, max_hp)

    async def test_debuff_summary_lists_active_effects(self) -> None:
        now = time.time()
        await self.db.apply_boss_element_status(
            self.guild_id,
            self.user_id,
            frost_slow_until=now + 20,
            fire_burn=(10.0, 3, now + 5),
        )
        summary = await self.db.boss_raider_debuff_summary(
            self.guild_id,
            self.user_id,
            at=now,
        )
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertIn("Chilled", summary)
        self.assertIn("Burning", summary)


if __name__ == "__main__":
    unittest.main()
