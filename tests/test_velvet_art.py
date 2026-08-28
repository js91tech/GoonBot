from __future__ import annotations

import hashlib
import unittest
from unittest import mock

import discord

import config
from utils import boss_art


class VelvetArtTests(unittest.TestCase):
    def test_both_style_packs_exist(self) -> None:
        for variant in ("normal", "enraged", "shadow", "celestial", "mythic"):
            name = f"velvet_vixen_{variant}.png"
            self.assertTrue((boss_art.GLAM_ROOT / name).is_file(), name)
            self.assertTrue((boss_art.ARMORED_ROOT / name).is_file(), name)

    def test_glam_and_armored_pixels_differ(self) -> None:
        """Guard against copying one pack over the other (NuggetBot Hannah regression)."""
        for variant in ("normal", "enraged", "shadow", "celestial", "mythic"):
            name = f"velvet_vixen_{variant}.png"
            glam = hashlib.md5((boss_art.GLAM_ROOT / name).read_bytes()).digest()
            armored = hashlib.md5((boss_art.ARMORED_ROOT / name).read_bytes()).digest()
            self.assertNotEqual(glam, armored, name)

    def test_named_boss_portraits_exist(self) -> None:
        for filename in ("tomass.png", "zz_wrath.png"):
            path = boss_art.ASSETS_ROOT / filename
            self.assertTrue(path.is_file(), filename)
            self.assertGreater(path.stat().st_size, 50_000, filename)

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

    def test_attachment_filenames_avoid_underscores(self) -> None:
        with mock.patch.object(config, "VELVET_VIXEN_ART_STYLE", "glam"):
            embed = discord.Embed(title="spawn")
            art = boss_art.attach_boss_art(embed, "normal")
            assert art is not None
            self.assertNotIn("_", art.filename)
            self.assertEqual(embed.to_dict()["image"]["url"], art.uri)
            self.assertTrue(art.uri.startswith("attachment://"))
            self.assertIn("velvet-vixen-normal", art.filename)

    def test_moment_art_filenames_avoid_underscores(self) -> None:
        embed = discord.Embed(title="nikki")
        art = boss_art.attach_boss_moment_art(embed, "freaky_nikki", "spawn")
        assert art is not None
        self.assertNotIn("_", art.filename)
        self.assertEqual(embed.to_dict()["image"]["url"], art.uri)

    def test_hannah_stored_name_is_rewritten(self) -> None:
        from cogs.boss import Boss

        self.assertEqual(Boss._boss_display_name("normal", "Hannah"), "Velvet Vixen")
        self.assertEqual(Boss._boss_display_name("enraged", "Hannah Hentai"), "Velvet Vixen")
        self.assertEqual(Boss._boss_display_name("shadow", "Velvet Vixen"), "Velvet Vixen")
        self.assertEqual(Boss._boss_display_name("tomass", "Hannah"), "TomAss")


if __name__ == "__main__":
    unittest.main()
