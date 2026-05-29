"""Territory control income, guards, and sieges."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import config
from database import Database
from utils.territories import TERRITORY_IDS, guard_cost_per_unit, territory_by_id


class TerritoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_ensure_territories_seeds_five(self) -> None:
        guild_id = 1
        rows = await self.db.list_territory_rows(guild_id)
        self.assertEqual(len(rows), len(TERRITORY_IDS))

    async def test_claim_neutral_and_income(self) -> None:
        guild_id, uid = 2, 200
        await self.db.ensure_user(uid, guild_id)
        await self.db.join_crew(uid, guild_id, "Owners")
        result = await self.db.start_territory_siege(uid, guild_id, "docks")
        self.assertEqual(result, "claimed_neutral")
        row = await self.db.get_territory_row(guild_id, "docks")
        assert row is not None
        self.assertEqual(str(row["owner_crew_name"]), "Owners")
        import time

        await self.db.conn.execute(
            """
            UPDATE territory_control SET last_income_at = ?
            WHERE guild_id = ? AND territory_id = 'docks'
            """,
            (time.time() - config.TERRITORY_HOURLY_TICK_SECONDS - 1, guild_id),
        )
        await self.db.conn.commit()
        paid = await self.db.process_territory_hourly_income(guild_id)
        self.assertGreater(paid, 0.0)
        stats = await self.db.get_crew_stats(guild_id, "Owners")
        assert stats is not None
        self.assertGreater(float(stats["treasury"]), 0.0)

    async def test_buy_guards_respects_cap(self) -> None:
        guild_id, uid = 3, 300
        defn = territory_by_id("market")
        assert defn is not None
        await self.db.ensure_user(uid, guild_id)
        await self.db.credit_wallet(uid, guild_id, 50_000.0)
        await self.db.join_crew(uid, guild_id, "Guards")
        self.assertEqual(
            await self.db.start_territory_siege(uid, guild_id, defn.territory_id),
            "claimed_neutral",
        )
        err = await self.db.buy_territory_guards(
            uid, guild_id, defn.territory_id, defn.max_guards + 5,
        )
        self.assertEqual(err, "guard_cap")

    async def test_guard_cost_scales_by_tier(self) -> None:
        docks = territory_by_id("docks")
        citadel = territory_by_id("citadel")
        assert docks is not None and citadel is not None
        self.assertLess(guard_cost_per_unit(docks), guard_cost_per_unit(citadel))


if __name__ == "__main__":
    unittest.main()
