"""Unique default avatar generation and assignment."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database
from utils.avatar_generate import (
    default_assets_ready,
    ensure_default_avatar_assets,
    traits_for_user,
    unique_default_avatar_id,
)
from utils.avatars import (
    build_victory_attachment,
    get_avatar,
    is_unique_default_avatar_id,
    portrait_path,
    resolve_equipped_avatar_id,
)


class UniqueDefaultAvatarTests(unittest.TestCase):
    def test_unique_id_is_stable(self) -> None:
        a = unique_default_avatar_id(42, 9001)
        b = unique_default_avatar_id(42, 9001)
        c = unique_default_avatar_id(42, 9002)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(is_unique_default_avatar_id(a))

    def test_traits_vary_by_user(self) -> None:
        t1 = traits_for_user(1, 100)
        t2 = traits_for_user(2, 100)
        self.assertNotEqual(t1.accent, t2.accent)

    def test_generate_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "defaults"
            import utils.avatar_generate as gen

            original = gen.DEFAULT_ASSETS_ROOT
            gen.DEFAULT_ASSETS_ROOT = root
            try:
                ensure_default_avatar_assets(7, 88)
                self.assertTrue(default_assets_ready(88, 7))
                aid = unique_default_avatar_id(7, 88)
                files, name = build_victory_attachment(
                    aid,
                    guild_id=88,
                    user_id=7,
                )
                self.assertEqual(len(files), 1)
                self.assertIsNotNone(name)
            finally:
                gen.DEFAULT_ASSETS_ROOT = original

    def test_get_avatar_unique_default(self) -> None:
        aid = unique_default_avatar_id(5, 10)
        defn = get_avatar(aid)
        self.assertIsNotNone(defn)
        assert defn is not None
        self.assertEqual(defn.price, 0.0)
        self.assertEqual(defn.name, "Raid Mascot")


class UniqueDefaultDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 500
        self.user_id = 12345
        self.tmp = tempfile.TemporaryDirectory()
        import utils.avatar_generate as gen

        self._orig_root = gen.DEFAULT_ASSETS_ROOT
        gen.DEFAULT_ASSETS_ROOT = Path(self.tmp.name) / "defaults"

    async def asyncTearDown(self) -> None:
        import utils.avatar_generate as gen

        gen.DEFAULT_ASSETS_ROOT = self._orig_root
        self.tmp.cleanup()
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_ensure_assigns_unique_default(self) -> None:
        aid = await self.db.ensure_unique_default_avatar(self.user_id, self.guild_id)
        self.assertTrue(is_unique_default_avatar_id(aid))
        equipped = await self.db.get_equipped_avatar_id(self.user_id, self.guild_id)
        self.assertEqual(equipped, aid)
        self.assertEqual(resolve_equipped_avatar_id(equipped), aid)
        self.assertTrue(
            portrait_path(aid, guild_id=self.guild_id, user_id=self.user_id).is_file(),
        )


if __name__ == "__main__":
    unittest.main()
