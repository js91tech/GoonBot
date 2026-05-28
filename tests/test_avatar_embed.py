"""Avatar files for duel/boss embeds."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database
from utils.avatars import build_avatar_embed_files, resolve_equipped_avatar_id


class AvatarEmbedTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_catalog_avatar_builds_files(self) -> None:
        files, victory_name, portrait_name = await build_avatar_embed_files(
            self.db,
            "duel_champion",
            guild_id=1,
            user_id=1,
        )
        self.assertGreaterEqual(len(files), 1)
        self.assertIsNotNone(victory_name)
        self.assertTrue(victory_name.startswith("victory_"))

    async def test_custom_avatar_from_db(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
        await self.db.save_custom_avatar_assets(1, 42, data, ".png")
        aid = resolve_equipped_avatar_id("custom_42")
        files, victory_name, _ = await build_avatar_embed_files(
            self.db, aid, guild_id=1, user_id=42,
        )
        self.assertEqual(len(files), 2)
        self.assertEqual(victory_name, "victory_custom_42.png")


if __name__ == "__main__":
    unittest.main()
