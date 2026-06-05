"""Bodyguard hiring and defeat-chance calibration tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import config
from database import Database
from utils.bodyguards import bodyguard_defeat_chance


class BodyguardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 800
        self.uid = 5
        await self.db.ensure_user(self.uid, self.guild_id)
        await self.db.credit_wallet(self.uid, self.guild_id, 500_000.0)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_hire_bodyguard_debits_wallet(self) -> None:
        cost = float(config.BODYGUARD_TIERS[1]["cost"])
        err = await self.db.hire_bodyguard(self.uid, self.guild_id, 1)
        self.assertIsNone(err)
        guards = await self.db.get_bodyguards(self.uid, self.guild_id)
        self.assertEqual(guards[1], 1)
        wallet = await self.db.get_balance(self.uid, self.guild_id)
        self.assertAlmostEqual(wallet, 500_000.0 - cost)

    async def test_hire_cap_at_five(self) -> None:
        for _ in range(config.BODYGUARD_MAX_TOTAL):
            err = await self.db.hire_bodyguard(self.uid, self.guild_id, 1)
            self.assertIsNone(err)
        err = await self.db.hire_bodyguard(self.uid, self.guild_id, 1)
        self.assertEqual(err, "max_guards")

    async def test_insufficient_funds(self) -> None:
        poor = 99
        await self.db.ensure_user(poor, self.guild_id)
        err = await self.db.hire_bodyguard(poor, self.guild_id, 3)
        self.assertEqual(err, "insufficient_funds")

    def test_defeat_chance_max_gear_full_t3_guards(self) -> None:
        guards = {3: 5}
        power = config.BODYGUARD_REFERENCE_POWER
        self.assertAlmostEqual(bodyguard_defeat_chance(power, 1, guards), 0.80)
        self.assertAlmostEqual(bodyguard_defeat_chance(power, 2, guards), 0.75)
        self.assertAlmostEqual(bodyguard_defeat_chance(power, 3, guards), 0.60)

    def test_no_guards_always_passes(self) -> None:
        self.assertEqual(bodyguard_defeat_chance(0, 3, {}), 1.0)
