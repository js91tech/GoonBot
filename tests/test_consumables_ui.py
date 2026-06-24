"""Tests for /use panel and player max HP helper."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database


class UsePanelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        self.guild_id = 1
        self.user_id = 50

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_player_max_hp_does_not_crash(self) -> None:
        from utils.drug_ui import player_max_hp

        await self.db.ensure_user(self.user_id, self.guild_id)
        await self.db.grant_item(self.user_id, self.guild_id, "iron_sword", equip_slot="weapon")
        await self.db.grant_item(self.user_id, self.guild_id, "leather_armor", equip_slot="armor")

        class FakeCog:
            def __init__(self, bot: object) -> None:
                self.bot = bot

        cog = FakeCog(self)
        max_hp = await player_max_hp(cog, self.user_id, self.guild_id)
        self.assertGreater(max_hp, 0)

    async def test_execute_use_drug(self) -> None:
        from utils.consumables_ui import execute_use

        await self.db.ensure_user(self.user_id, self.guild_id)
        await self.db.conn.execute(
            """
            INSERT INTO drug_inventory (user_id, guild_id, drug_id, quantity)
            VALUES (?, ?, ?, ?)
            """,
            (self.user_id, self.guild_id, "blue_dream", 1),
        )
        await self.db.conn.commit()

        class FakeCog:
            def __init__(self, bot: object) -> None:
                self.bot = bot

        cog = FakeCog(self)
        err, message = await execute_use(cog, self.user_id, self.guild_id, "blue_dream")
        self.assertIsNone(err)
        self.assertIsNotNone(message)
        assert message is not None
        self.assertIn("Blue Dream", message)

    async def test_execute_use_energy_drink(self) -> None:
        from utils.consumables_ui import execute_use

        await self.db.ensure_user(self.user_id, self.guild_id)
        await self.db.grant_item(self.user_id, self.guild_id, "energy_drink")

        class FakeCog:
            def __init__(self, bot: object) -> None:
                self.bot = bot

        cog = FakeCog(self)
        err, message = await execute_use(cog, self.user_id, self.guild_id, "energy_drink")
        self.assertIsNone(err)
        self.assertIn("Energy Drink", message or "")


if __name__ == "__main__":
    unittest.main()
