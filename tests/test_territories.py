"""Territory control income, guards, and sieges."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import config
from database import Database
from utils.territories import TERRITORY_IDS, guard_cost_per_unit, territory_by_id
from utils.territory_ui import TerritoryMapView, zone_select_options_from_rows


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

    async def test_buy_guards_from_treasury(self) -> None:
        guild_id, uid = 4, 400
        defn = territory_by_id("docks")
        assert defn is not None
        await self.db.ensure_user(uid, guild_id)
        await self.db.join_crew(uid, guild_id, "TreasuryCrew")
        await self.db.start_territory_siege(uid, guild_id, defn.territory_id)
        await self.db.credit_crew_treasury_no_wallet(guild_id, "TreasuryCrew", 10_000.0)
        err = await self.db.buy_territory_guards(
            uid, guild_id, defn.territory_id, 1, pay_from="treasury",
        )
        self.assertIsNone(err)
        row = await self.db.get_territory_row(guild_id, defn.territory_id)
        assert row is not None
        self.assertEqual(int(row["guards"]), 1)

    def test_perks_from_held(self) -> None:
        from utils.territories import perks_from_held

        perks = perks_from_held({"market", "docks"})
        self.assertAlmostEqual(perks.sell_mult, 1.05)
        self.assertAlmostEqual(perks.heist_loot_mult, 1.05)

    async def test_guard_cost_scales_by_tier(self) -> None:
        docks = territory_by_id("docks")
        citadel = territory_by_id("citadel")
        assert docks is not None and citadel is not None
        self.assertLess(guard_cost_per_unit(docks), guard_cost_per_unit(citadel))

    async def test_map_view_always_includes_zone_select(self) -> None:
        from unittest.mock import MagicMock

        guild_id = 5
        rows = await self.db.list_territory_rows(guild_id)
        options = zone_select_options_from_rows(rows)
        self.assertEqual(len(options), len(TERRITORY_IDS))

        cog = MagicMock()
        view = TerritoryMapView(
            cog, guild_id, 500, territory_rows=rows, in_crew=True,
        )
        select_items = [c for c in view.children if c.__class__.__name__ == "TerritoryZoneSelect"]
        self.assertEqual(len(select_items), 1)

if __name__ == "__main__":
    unittest.main()
