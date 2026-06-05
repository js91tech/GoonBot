"""Boss auto-spawn scheduling tests."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import config
from cogs.boss import Boss
from database import Database


class BossAutoSpawnTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.connect()
        await self.db.init_schema()
        self.bot = SimpleNamespace(db=self.db, guilds=[], outbound_gate=None)
        self.cog = Boss(self.bot)  # type: ignore[arg-type]
        self.cog.auto_spawn.cancel()
        self.cog.passive_boss_decay_tick.cancel()
        self.guild_id = 9003
        self.guild = MagicMock()
        self.guild.id = self.guild_id
        self.bot.guilds = [self.guild]
        await self.db.ensure_user(1, self.guild_id)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_zz_wrath_spawn_succeeds(self) -> None:
        with (
            patch("cogs.boss.random.random", return_value=0.0),
            patch(
                "cogs.boss.resolve_bot_announcement_channel",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            await self.cog._try_auto_spawn_guild(self.guild)
        boss = await self.db.get_active_boss(self.guild_id)
        self.assertIsNotNone(boss)
        assert boss is not None
        self.assertEqual(str(boss["variant"]), "zz_wrath")
        self.assertGreater(float(boss["hp"]), 0)

    async def test_spawn_scheduled_every_40_minutes(self) -> None:
        now = time.time()
        self.cog._schedule_next_auto_spawn(self.guild_id, now=now)
        due = self.cog._auto_spawn_due_at[self.guild_id]
        delay = due - now
        self.assertAlmostEqual(delay, config.BOSS_AUTO_SPAWN_MIN_SECONDS, delta=1.0)
        self.assertEqual(
            config.BOSS_AUTO_SPAWN_MIN_SECONDS,
            config.BOSS_AUTO_SPAWN_MAX_SECONDS,
        )

    async def test_skips_when_boss_active(self) -> None:
        await self.db.replace_boss(self.guild_id, "Hannah", "normal", 5000.0)
        self.cog._send_boss_spawn_embed = AsyncMock()  # type: ignore[method-assign]
        await self.cog._try_auto_spawn_guild(self.guild)
        self.cog._send_boss_spawn_embed.assert_not_called()

    async def test_despawns_expired_boss_before_skipping(self) -> None:
        past = time.time() - 3600
        await self.db.replace_boss(
            self.guild_id,
            "Hannah",
            "mythic",
            5000.0,
            spawned_at=past,
        )
        self.cog._despawn_boss_timeout = AsyncMock()  # type: ignore[method-assign]
        self.cog._send_boss_spawn_embed = AsyncMock()  # type: ignore[method-assign]
        with patch("cogs.boss.random.random", return_value=0.99):
            await self.cog._try_auto_spawn_guild(self.guild)
        self.cog._despawn_boss_timeout.assert_awaited_once()
        self.cog._send_boss_spawn_embed.assert_awaited()


if __name__ == "__main__":
    unittest.main()
