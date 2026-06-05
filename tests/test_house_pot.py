"""House pot funding and coin drop recycling tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database


class HousePotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 901

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_credit_and_debit_house_pot(self) -> None:
        await self.db.credit_house_pot(self.guild_id, 500.0)
        self.assertAlmostEqual(await self.db.get_house_pot(self.guild_id), 500.0)
        taken = await self.db.debit_house_pot(self.guild_id, 200.0)
        self.assertAlmostEqual(taken, 200.0)
        self.assertAlmostEqual(await self.db.get_house_pot(self.guild_id), 300.0)

    async def test_debit_empty_pot_returns_zero(self) -> None:
        taken = await self.db.debit_house_pot(self.guild_id, 100.0)
        self.assertAlmostEqual(taken, 0.0)

    async def test_expired_drop_returns_to_pot(self) -> None:
        await self.db.credit_house_pot(self.guild_id, 100.0)
        taken = await self.db.debit_house_pot(self.guild_id, 50.0)
        self.assertAlmostEqual(taken, 50.0)
        await self.db.credit_house_pot(self.guild_id, taken)
        self.assertAlmostEqual(await self.db.get_house_pot(self.guild_id), 100.0)
