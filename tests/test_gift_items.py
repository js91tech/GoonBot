"""Gift inventory items between players."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database


class GiftItemTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_gift_chia_seeds_transfers_quantity(self) -> None:
        guild_id = 1
        sender, receiver = 100, 200
        await self.db.ensure_user(sender, guild_id)
        await self.db.ensure_user(receiver, guild_id)
        await self.db.grant_item(sender, guild_id, "chia_seeds")
        await self.db.grant_item(sender, guild_id, "chia_seeds")
        await self.db.grant_item(sender, guild_id, "chia_seeds")

        err = await self.db.gift_inventory_item(
            sender, receiver, guild_id, "chia_seeds", 2,
        )
        self.assertIsNone(err)
        self.assertEqual(
            await self.db.get_inventory_quantity(sender, guild_id, "chia_seeds"),
            1,
        )
        self.assertEqual(
            await self.db.get_inventory_quantity(receiver, guild_id, "chia_seeds"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
