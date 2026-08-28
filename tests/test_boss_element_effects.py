"""Boss elemental counter effect tests."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from database import Database
from utils.boss_element_effects import (
    attack_cooldown_while_debuffed,
    debuff_duration_range_for_threat,
    element_hazard_text,
    roll_debuff_attack_cooldown,
    roll_debuff_duration_for_threat,
    roll_element_proc,
)


class BossElementEffectUtilTests(unittest.TestCase):
    def test_element_hazard_text_known_elements(self) -> None:
        self.assertIsNone(element_hazard_text("frost"))
        self.assertIsNone(element_hazard_text("storm"))
        self.assertIsNone(element_hazard_text("verdant"))
        fire = element_hazard_text("fire") or ""
        void = element_hazard_text("void") or ""
        self.assertIn("Fire", fire)
        self.assertIn("burn", fire.lower())
        self.assertIn("Void", void)
        self.assertNotIn("chill", fire.lower())
        self.assertNotIn("stun", void.lower())

    def test_debuff_attack_cooldown_in_range(self) -> None:
        lo, hi = config.BOSS_DEBUFF_ATTACK_COOLDOWN_SECONDS
        for _ in range(20):
            cd = roll_debuff_attack_cooldown()
            self.assertGreaterEqual(cd, lo)
            self.assertLessEqual(cd, hi)

    def test_debuff_duration_never_exceeds_max(self) -> None:
        for threat in range(1, 8):
            for _ in range(50):
                duration = roll_debuff_duration_for_threat(threat)
                self.assertLessEqual(duration, config.BOSS_DEBUFF_MAX_SECONDS)

    def test_debuff_duration_scales_with_threat(self) -> None:
        lo, hi = debuff_duration_range_for_threat(1)
        self.assertEqual(lo, config.BOSS_DEBUFF_DURATION_BASE_SECONDS[0])
        self.assertEqual(hi, config.BOSS_DEBUFF_DURATION_BASE_SECONDS[1])

        tier6_lo, tier6_hi = debuff_duration_range_for_threat(6)
        self.assertGreaterEqual(tier6_lo, lo)
        self.assertGreater(tier6_hi, hi)

        for threat in (1, 3, 6):
            t_lo, t_hi = debuff_duration_range_for_threat(threat)
            for _ in range(20):
                duration = roll_debuff_duration_for_threat(threat)
                self.assertGreaterEqual(duration, t_lo)
                self.assertLessEqual(duration, t_hi)

    def test_attack_cooldown_while_debuffed_ignores_leftover_cc(self) -> None:
        now = 1000.0
        cd = attack_cooldown_while_debuffed(
            attack_slow_until=now + 10,
            verdant_root_until=now + 10,
            debuff_attack_cooldown=9.0,
            now=now,
        )
        self.assertIsNone(cd)

    @patch("utils.boss_element_effects.random.random", return_value=0.0)
    def test_frost_storm_verdant_do_not_apply_cc(self, _random: object) -> None:
        for element in ("frost", "storm", "verdant"):
            proc = roll_element_proc(element, now=100.0, threat=6)
            self.assertEqual(proc.note, "")
            self.assertIsNone(proc.fire_burn)
            self.assertIsNone(proc.void_mana_drain)

    @patch("utils.boss_element_effects.random.random", return_value=0.0)
    def test_roll_fire_burn_still_applies(self, _random: object) -> None:
        proc = roll_element_proc("fire", now=100.0, threat=3)
        self.assertIn("Burning", proc.note)
        self.assertIsNotNone(proc.fire_burn)

    @patch("utils.boss_element_effects.random.random", return_value=0.0)
    def test_roll_void_drain_still_applies(self, _random: object) -> None:
        proc = roll_element_proc("void", now=100.0, threat=3)
        self.assertIn("Void", proc.note)
        self.assertIsNotNone(proc.void_mana_drain)


class BossElementDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 7001
        self.user_id = 99
        await self.db.replace_boss(self.guild_id, "Velvet Vixen", "normal", 5000.0, element="frost")

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_leftover_frost_does_not_extend_attack_cooldown(self) -> None:
        now = time.time()
        await self.db.record_boss_attack_time(self.guild_id, self.user_id, now)
        remaining_before = await self.db.boss_attack_cooldown_remaining(
            self.guild_id,
            self.user_id,
            at=now + 1,
        )
        await self.db.apply_boss_element_status(
            self.guild_id,
            self.user_id,
            frost_slow_until=now + 30,
            debuff_attack_cooldown=2.0,
        )
        remaining_after = await self.db.boss_attack_cooldown_remaining(
            self.guild_id,
            self.user_id,
            at=now + 1,
        )
        self.assertIsNone(remaining_before)
        self.assertIsNone(remaining_after)

    async def test_record_boss_attack_has_no_cooldown(self) -> None:
        now = time.time()
        await self.db.record_boss_attack_time(self.guild_id, self.user_id, now)
        remaining = await self.db.boss_attack_cooldown_remaining(
            self.guild_id,
            self.user_id,
            at=now,
        )
        self.assertIsNone(remaining)
        self.assertEqual(config.BOSS_ATTACK_COOLDOWN_MAX_SECONDS, 0)

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

    async def test_debuff_summary_lists_burn_not_leftover_chill(self) -> None:
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
        self.assertNotIn("Chilled", summary)
        self.assertNotIn("Rooted", summary)
        self.assertIn("Burning", summary)


if __name__ == "__main__":
    unittest.main()
