"""Gift commands reject restricted players."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from cogs.consumables import Consumables
from cogs.drugs import Drugs
from database import Database


class GiftRestrictedTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        self.guild_id = 1
        self.sender_id = 100
        self.receiver_id = 200

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    def _interaction(self) -> MagicMock:
        interaction = MagicMock()
        interaction.guild_id = self.guild_id
        interaction.user.id = self.sender_id
        interaction.response.send_message = AsyncMock()
        return interaction

    def _member(self, user_id: int) -> MagicMock:
        member = MagicMock()
        member.id = user_id
        member.bot = False
        return member

    async def test_drugs_gift_blocked_when_restricted(self) -> None:
        await self.db.ensure_user(self.sender_id, self.guild_id)
        await self.db.grant_drug_units(self.sender_id, self.guild_id, "blue_dream", 3)
        await self.db.set_arrested_until(
            self.sender_id, self.guild_id, time.time() + 3600,
        )
        bot = MagicMock()
        bot.db = self.db
        cog = Drugs(bot)
        interaction = self._interaction()
        await Drugs.gift.callback(
            cog,
            interaction,
            self._member(self.receiver_id),
            "blue_dream",
            1,
        )
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args
        self.assertIn("cannot gift", args[0].lower())
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_gift_item_blocked_when_restricted(self) -> None:
        await self.db.ensure_user(self.sender_id, self.guild_id)
        await self.db.grant_item(self.sender_id, self.guild_id, "chia_seeds")
        await self.db.set_arrested_until(
            self.sender_id, self.guild_id, time.time() + 3600,
        )
        bot = MagicMock()
        bot.db = self.db
        cog = Consumables(bot)
        interaction = self._interaction()
        await Consumables.gift.callback(
            cog,
            interaction,
            self._member(self.receiver_id),
            "chia_seeds",
            1,
        )
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args
        self.assertIn("cannot gift", args[0].lower())
        self.assertTrue(kwargs.get("ephemeral"))


if __name__ == "__main__":
    unittest.main()
