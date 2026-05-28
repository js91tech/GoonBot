"""Database duel settlement and Postgres SQL compatibility."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database, PostgresConnection


class PostgresInsertOrIgnoreTests(unittest.TestCase):
    def test_duel_elo_converts_to_on_conflict(self) -> None:
        sql = """
            INSERT OR IGNORE INTO duel_elo (guild_id, user_id, rating, wins, losses)
            VALUES (?, ?, ?, 0, 0)
        """
        out = PostgresConnection._normalize_query(sql)
        assert out is not None
        self.assertNotIn("OR IGNORE", out.upper())
        self.assertIn("ON CONFLICT (guild_id, user_id) DO NOTHING", out)

    def test_player_avatar_unlocks_converts(self) -> None:
        sql = """
            INSERT OR IGNORE INTO player_avatar_unlocks
                (guild_id, user_id, avatar_id, unlocked_at)
            VALUES (?, ?, ?, ?)
        """
        out = PostgresConnection._normalize_query(sql)
        assert out is not None
        self.assertIn("ON CONFLICT (guild_id, user_id, avatar_id) DO NOTHING", out)


class DuelExecuteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_execute_duel_records_elo_and_wins(self) -> None:
        guild_id = 9001
        attacker_id = 101
        defender_id = 202
        for uid, wallet in ((attacker_id, 500.0), (defender_id, 1_000.0)):
            await self.db.ensure_user(uid, guild_id)
            await self.db.credit_wallet(uid, guild_id, wallet)

        result = await self.db.execute_duel(
            guild_id,
            attacker_id,
            defender_id,
            attacker_id,
            loss_fraction=0.1,
            same_target_cooldown_seconds=300.0,
            max_attacks_per_hour=10,
        )
        self.assertIsNotNone(result)
        loot, _ = result  # type: ignore[misc]
        self.assertAlmostEqual(loot, 100.0)

        rating, wins, losses = await self.db.get_duel_elo(attacker_id, guild_id)
        self.assertGreater(rating, 1000)
        self.assertEqual(wins, 1)
        _, def_rating, def_losses = await self.db.get_duel_elo(defender_id, guild_id)
        del def_rating
        self.assertEqual(def_losses, 1)

        progress = await self.db.get_user_progress(attacker_id, guild_id)
        self.assertEqual(int(progress["duel_wins"]), 1)


if __name__ == "__main__":
    unittest.main()
