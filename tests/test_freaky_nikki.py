"""Freaky Nikki boss moment art and reward tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

import config
from cogs.boss import Boss
from database import Database
from utils.boss_art import attach_boss_moment_art, moment_for_move


class FreakyNikkiMomentTests(unittest.TestCase):
    def test_moment_for_move_maps_obsession_verbs(self) -> None:
        self.assertEqual(moment_for_move("obsessive-stares at"), "obsessive_stare")
        self.assertEqual(moment_for_move("unhinged-whispers to"), "whisper")
        self.assertEqual(moment_for_move("restraining-grabs"), "grab")
        self.assertEqual(moment_for_move("psyche-twists"), "psyche_twist")
        self.assertEqual(moment_for_move("freak-out-slaps"), "slap")

    def test_moment_for_move_unknown_defaults_spawn(self) -> None:
        self.assertEqual(moment_for_move("unknown-move"), "spawn")

    def test_attach_moment_art_returns_file_for_spawn(self) -> None:
        embed = discord.Embed()
        art = attach_boss_moment_art(embed, "freaky_nikki", "spawn")
        self.assertIsNotNone(art)
        assert art is not None
        self.assertTrue(art.filename.endswith(".png"))
        self.assertIn("attachment://", embed.image.url or "")

    def test_attach_moment_art_graceful_for_missing_variant(self) -> None:
        embed = discord.Embed()
        art = attach_boss_moment_art(embed, "nonexistent_boss", "spawn")
        self.assertIsNone(art)


class FreakyNikkiRewardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.connect()
        await self.db.init_schema()
        self.bot = SimpleNamespace(db=self.db)
        self.cog = Boss(self.bot)  # type: ignore[arg-type]
        self.cog.auto_spawn.cancel()
        self.cog.passive_boss_decay_tick.cancel()
        self.guild_id = 9010
        self.guild = SimpleNamespace(id=self.guild_id, get_member=lambda _uid: None)
        await self.db.ensure_user(1, self.guild_id)
        await self.db.ensure_user(2, self.guild_id)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_grant_bonuses_gives_scrap_to_all_contributors(self) -> None:
        with patch("cogs.boss.random.randint", side_effect=[3, 4]), patch(
            "cogs.boss.random.random",
            return_value=1.0,
        ):
            lines = await self.cog._grant_freaky_nikki_bonuses(
                self.guild,
                self.guild_id,
                [1, 2],
            )
        self.assertEqual(len(lines), 2)
        scrap1 = await self.db.get_inventory_quantity(1, self.guild_id, "alchemy_scrap")
        scrap2 = await self.db.get_inventory_quantity(2, self.guild_id, "alchemy_scrap")
        self.assertEqual(scrap1, 3)
        self.assertEqual(scrap2, 4)
        self.assertTrue(all("scrap" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
