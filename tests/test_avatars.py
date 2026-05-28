"""Player avatar catalog and asset paths."""
from __future__ import annotations

import unittest

from utils.avatars import (
    DEFAULT_AVATAR_ID,
    build_victory_attachment,
    get_avatar,
    portrait_path,
    resolve_equipped_avatar_id,
    victory_path,
)


class AvatarUtilsTests(unittest.TestCase):
    def test_default_avatar(self) -> None:
        self.assertEqual(resolve_equipped_avatar_id(None), DEFAULT_AVATAR_ID)
        self.assertEqual(resolve_equipped_avatar_id("invalid"), DEFAULT_AVATAR_ID)

    def test_get_avatar(self) -> None:
        raider = get_avatar("nugget_raider")
        self.assertIsNotNone(raider)
        assert raider is not None
        self.assertEqual(raider.price, 0.0)

    def test_assets_exist_for_catalog(self) -> None:
        aid = DEFAULT_AVATAR_ID
        self.assertTrue(portrait_path(aid).is_file(), portrait_path(aid))
        self.assertTrue(victory_path(aid).is_file(), victory_path(aid))

    def test_victory_attachment_builds(self) -> None:
        files, name = build_victory_attachment(DEFAULT_AVATAR_ID)
        self.assertEqual(len(files), 1)
        self.assertIsNotNone(name)
        self.assertTrue(name.endswith(".gif") or name.endswith(".png"))


if __name__ == "__main__":
    unittest.main()
