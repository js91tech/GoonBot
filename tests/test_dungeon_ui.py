"""Dungeon panel embed and energy gate tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import config
from cogs.dungeon import Dungeon
from database import Database


class DungeonPanelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.connect()
        await self.db.init_schema()
        self.bot = SimpleNamespace(db=self.db)
        self.cog = Dungeon(self.bot)  # type: ignore[arg-type]
        self.guild_id = 9001
        self.user_id = 42

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_build_embed_no_run_shows_energy_cost(self) -> None:
        embed, has_run = await self.cog.build_dungeon_embed(self.guild_id, self.user_id)
        self.assertFalse(has_run)
        self.assertIn("Delver's Depths", embed.title)
        cost_field = next(f for f in embed.fields if f.name == "Entry cost")
        self.assertIn(str(config.DUNGEON_ENERGY_COST), cost_field.value)

    async def test_build_embed_active_run_shows_hp(self) -> None:
        await self.db.start_dungeon_run(self.user_id, self.guild_id, 100.0, 100.0, 80.0)
        embed, has_run = await self.cog.build_dungeon_embed(self.guild_id, self.user_id)
        self.assertTrue(has_run)
        self.assertIn("Room 1/", embed.title)
        hp_field = next(f for f in embed.fields if f.name == "Your HP")
        self.assertIn("100", hp_field.value)

    async def test_start_rejects_insufficient_energy(self) -> None:
        char = await self.db.get_user_character(self.user_id, self.guild_id)
        cap = int(char["energy_cap"])
        ok, _ = await self.db.spend_job_energy(self.user_id, self.guild_id, cap)
        self.assertTrue(ok)
        result = await self.cog.execute_dungeon_start(self.guild_id, self.user_id)
        self.assertIsNotNone(result.error)
        assert result.error is not None
        self.assertIn("Not enough energy", result.error)
        run = await self.db.get_dungeon_run(self.user_id, self.guild_id)
        self.assertIsNone(run)

    async def test_start_spends_energy_and_creates_run(self) -> None:
        result = await self.cog.execute_dungeon_start(self.guild_id, self.user_id)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.embed)
        run = await self.db.get_dungeon_run(self.user_id, self.guild_id)
        self.assertIsNotNone(run)
        char = await self.db.get_user_character(self.user_id, self.guild_id)
        expected = int(char["energy_cap"]) - config.DUNGEON_ENERGY_COST
        self.assertEqual(int(char["energy"]), expected)


if __name__ == "__main__":
    unittest.main()
