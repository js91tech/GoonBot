"""Crew treasury deposit and joinable crew listing."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database


class CrewTreasuryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_deposit_credits_full_amount(self) -> None:
        guild_id = 1
        uid = 100
        await self.db.ensure_user(uid, guild_id)
        await self.db.credit_wallet(uid, guild_id, 500.0)
        await self.db.join_crew(uid, guild_id, "Raiders")

        err = await self.db.deposit_crew_treasury(uid, guild_id, 250.0)
        self.assertIsNone(err)

        stats = await self.db.get_crew_stats(guild_id, "Raiders")
        assert stats is not None
        self.assertAlmostEqual(float(stats["treasury"]), 250.0)
        self.assertAlmostEqual(await self.db.get_balance(uid, guild_id), 250.0)

    async def test_list_joinable_crews_excludes_full(self) -> None:
        guild_id = 2
        await self.db.join_crew(1000, guild_id, "FullCrew")
        for i in range(1, 8):
            await self.db.join_crew(1000 + i, guild_id, "FullCrew")
        names = await self.db.list_joinable_crew_names(guild_id)
        self.assertNotIn("FullCrew", names)

        await self.db.join_crew(2000, guild_id, "OpenCrew")
        names = await self.db.list_joinable_crew_names(guild_id)
        self.assertIn("OpenCrew", names)


if __name__ == "__main__":
    unittest.main()
