from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import config
from utils import boss_art


class VelvetArtTests(unittest.TestCase):
    def test_both_style_packs_exist(self) -> None:
        for variant in ("normal", "enraged", "shadow", "celestial", "mythic"):
            name = f"velvet_vixen_{variant}.png"
            self.assertTrue((boss_art.GLAM_ROOT / name).is_file(), name)
            self.assertTrue((boss_art.ARMORED_ROOT / name).is_file(), name)

    def test_resolve_respects_style(self) -> None:
        with mock.patch.object(config, "VELVET_VIXEN_ART_STYLE", "glam"):
            path = boss_art.boss_art_path("normal")
            assert path is not None
            self.assertEqual(path.parent.name, "glam")
        with mock.patch.object(config, "VELVET_VIXEN_ART_STYLE", "armored"):
            path = boss_art.boss_art_path("enraged")
            assert path is not None
            self.assertEqual(path.parent.name, "armored")

    def test_both_picks_from_either_pack(self) -> None:
        with mock.patch.object(config, "VELVET_VIXEN_ART_STYLE", "both"):
            seen = {boss_art.boss_art_path("mythic").parent.name for _ in range(40)}  # type: ignore[union-attr]
            self.assertTrue(seen & {"glam", "armored"})


if __name__ == "__main__":
    unittest.main()
