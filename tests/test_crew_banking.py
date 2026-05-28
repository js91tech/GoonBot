"""Crew banking helpers and joinable crew listing."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database
from utils.crew_banking import heist_same_crew_bonus, max_loan_amount


class CrewBankingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_heist_same_crew_bonus_stacks_and_caps(self) -> None:
        ids = [1, 2, 3]
        crews = {1: "Raiders", 2: "Raiders", 3: "Other"}
        bonus = heist_same_crew_bonus(ids, crews)
        self.assertAlmostEqual(bonus, 0.05)

        crews_both = {1: "Raiders", 2: "Raiders", 3: "Raiders"}
        capped = heist_same_crew_bonus(ids, crews_both)
        self.assertAlmostEqual(capped, 0.10)

    def test_max_loan_amount_scales_with_level(self) -> None:
        low = max_loan_amount(1000.0, 1)
        high = max_loan_amount(1000.0, 5)
        self.assertGreater(high, low)

    async def test_list_joinable_crews_returns_member_counts(self) -> None:
        guild_id = 9
        await self.db.join_crew(501, guild_id, "Alpha")
        await self.db.join_crew(502, guild_id, "Alpha")
        crews = await self.db.list_joinable_crews(guild_id)
        alpha = next((c for c in crews if c[0] == "Alpha"), None)
        self.assertIsNotNone(alpha)
        assert alpha is not None
        self.assertEqual(alpha[1], 2)


if __name__ == "__main__":
    unittest.main()
