"""Jail escape consumable tests."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from database import Database


class JailEscapeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 700
        self.uid = 42
        await self.db.ensure_user(self.uid, self.guild_id)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def _jail_user(self) -> None:
        await self.db.set_arrested_until(
            self.uid,
            self.guild_id,
            time.time() + 3600,
        )

    async def test_jail_key_clears_arrest(self) -> None:
        await self._jail_user()
        await self.db.grant_item(self.uid, self.guild_id, "jail_key")
        self.assertTrue(await self.db.is_arrested(self.uid, self.guild_id))
        await self.db.consume_inventory_item(self.uid, self.guild_id, "jail_key")
        await self.db.clear_arrested(self.uid, self.guild_id)
        self.assertFalse(await self.db.is_arrested(self.uid, self.guild_id))

    async def test_pick_key_escape_chance_config(self) -> None:
        self.assertAlmostEqual(config.PICK_KEY_ESCAPE_CHANCE, 0.15)

    async def test_pick_key_success_clears_arrest(self) -> None:
        await self._jail_user()
        await self.db.grant_item(self.uid, self.guild_id, "pick_key")
        with patch("random.random", return_value=0.0):
            escaped = 0.0 < config.PICK_KEY_ESCAPE_CHANCE
        self.assertTrue(escaped)
        if escaped:
            await self.db.clear_arrested(self.uid, self.guild_id)
        self.assertFalse(await self.db.is_arrested(self.uid, self.guild_id))

    async def test_pick_key_fail_keeps_jailed(self) -> None:
        await self._jail_user()
        with patch("random.random", return_value=0.99):
            escaped = 0.99 < config.PICK_KEY_ESCAPE_CHANCE
        self.assertFalse(escaped)
        self.assertTrue(await self.db.is_arrested(self.uid, self.guild_id))
