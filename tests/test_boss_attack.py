"""Boss attack integration tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from cogs.boss import Boss
from database import Database


class BossTomassAttackTests(unittest.IsolatedAsyncioTestCase):
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
        self.guild_id = 9002
        self.user_id = 501
        await self.db.ensure_user(self.user_id, self.guild_id)
        await self.db.replace_boss(
            self.guild_id,
            "TomAss",
            "tomass",
            8000.0,
            element="fire",
            mirrored_variant="enraged",
        )

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_attack_tomass_succeeds(self) -> None:
        guild = MagicMock()
        guild.id = self.guild_id
        member = MagicMock()
        member.id = self.user_id
        member.display_name = "Raider"

        result = await self.cog.execute_boss_attack(member, guild)
        self.assertIsNone(result.error, msg=result.error)
        self.assertIsNotNone(result.embed)

    async def test_counter_roll_tomass_no_name_error(self) -> None:
        damage, mitigated, critical, move = Boss._counter_roll(
            "tomass",
            None,
            hp_ratio=0.8,
        )
        self.assertGreater(damage, 0)
        self.assertIn("ass", move)


if __name__ == "__main__":
    unittest.main()
