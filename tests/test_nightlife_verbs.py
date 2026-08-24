"""Nightlife verbs: heat/VIP, persona floors, Velvet Walks In."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import config
from database import Database
from utils.heat import (
    gambling_max_bet,
    heat_tier_for_spend,
    next_heat_tier,
    slots_max_bet,
)
from utils.jobs import get_job
from utils.persona_floors import available_jobs, job_unlocked, starter_root_for
from utils.velvet_night import velvet_night_active_now


class HeatTests(unittest.TestCase):
    def test_tiers_scale_with_spend(self) -> None:
        self.assertEqual(heat_tier_for_spend(0).name, "Guest")
        self.assertEqual(heat_tier_for_spend(config.HEAT_TIER_REGULAR_SPEND).name, "Regular")
        self.assertEqual(heat_tier_for_spend(config.HEAT_TIER_VIP_SPEND).name, "VIP")
        self.assertEqual(heat_tier_for_spend(config.HEAT_TIER_BOOTH_SPEND).name, "Booth")
        self.assertIsNone(next_heat_tier(config.HEAT_TIER_BOOTH_SPEND))

    def test_table_limits_rise(self) -> None:
        guest = gambling_max_bet(0)
        booth = gambling_max_bet(config.HEAT_TIER_BOOTH_SPEND)
        self.assertGreater(booth, guest)
        self.assertGreater(
            slots_max_bet(config.HEAT_TIER_VIP_SPEND),
            config.SLOTS_MAX_BET,
        )


class PersonaFloorTests(unittest.TestCase):
    def test_exclusive_jobs_gate_by_root(self) -> None:
        stage = get_job("stage_talent")
        host = get_job("floor_host")
        fixer = get_job("backroom_fixer")
        assert stage and host and fixer
        self.assertTrue(job_unlocked(stage, "vanguard"))
        self.assertFalse(job_unlocked(stage, "mogul"))
        self.assertTrue(job_unlocked(host, "mogul"))
        self.assertTrue(job_unlocked(fixer, "shade"))
        open_floor = available_jobs("vanguard")
        self.assertIn(stage, open_floor)
        self.assertNotIn(host, open_floor)

    def test_open_jobs_always_available(self) -> None:
        lounge = get_job("miner")
        assert lounge is not None
        self.assertTrue(job_unlocked(lounge, None))
        self.assertTrue(job_unlocked(lounge, "shade"))

    def test_starter_root_resolves(self) -> None:
        self.assertEqual(starter_root_for("vanguard"), "vanguard")
        self.assertEqual(starter_root_for("mogul"), "mogul")


class VelvetNightTests(unittest.TestCase):
    def test_admin_event_forces_active(self) -> None:
        event = {"event_type": "velvet_night", "multiplier": 1.5}
        self.assertTrue(velvet_night_active_now(event))

    def test_utc_window(self) -> None:
        with patch("utils.velvet_night.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            self.assertTrue(velvet_night_active_now(None))
        with patch("utils.velvet_night.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            self.assertFalse(velvet_night_active_now(None))


class HeatSpendDbTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "heat.sqlite3"))
        await self.db.connect()
        await self.db.init_schema()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_debit_tracks_spend_and_buy_boost(self) -> None:
        await self.db.credit_wallet(1, 9, 200_000.0, apply_bonuses=False)
        ok = await self.db.debit_wallet(1, 9, 25_000.0)
        self.assertTrue(ok)
        spent = await self.db.get_goonbux_spent(1, 9)
        self.assertAlmostEqual(spent, 25_000.0)
        self.assertEqual(heat_tier_for_spend(spent).name, "Regular")
        err, cost = await self.db.buy_heat_boost(1, 9)
        self.assertIsNone(err)
        self.assertGreater(cost, 0)
        spent2 = await self.db.get_goonbux_spent(1, 9)
        self.assertEqual(heat_tier_for_spend(spent2).name, "VIP")


if __name__ == "__main__":
    unittest.main()
