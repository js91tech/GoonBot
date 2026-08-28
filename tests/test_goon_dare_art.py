"""Dare portraits — girl on screen, not 'the floor'."""
from __future__ import annotations

import unittest

import discord

from utils.goon_dare_art import attach_dare_art, dare_art_paths, pick_dare_art
from utils.goon_session import GOON_DARES, pick_dare


class GoonDareArtTests(unittest.TestCase):
    def test_pack_has_images(self) -> None:
        paths = dare_art_paths()
        self.assertGreaterEqual(len(paths), 3)
        for path in paths:
            self.assertGreater(path.stat().st_size, 20_000, path.name)
            self.assertNotIn("_", path.name)

    def test_pick_returns_pack_file(self) -> None:
        path = pick_dare_art()
        assert path is not None
        self.assertTrue(path.is_file())
        self.assertIn(path, dare_art_paths())

    def test_attach_sets_embed_image_without_underscores(self) -> None:
        embed = discord.Embed(title="dare")
        art = attach_dare_art(embed)
        assert art is not None
        self.assertNotIn("_", art.filename)
        self.assertTrue(art.uri.startswith("attachment://"))
        self.assertEqual(embed.to_dict()["image"]["url"], art.uri)

    def test_prompts_ask_what_youd_let_her_do(self) -> None:
        joined = " ".join(GOON_DARES).lower()
        self.assertNotIn("let the floor do", joined)
        her_lines = [dare for dare in GOON_DARES if "her" in dare.lower()]
        self.assertGreaterEqual(len(her_lines), 8)
        self.assertTrue(any("let her do" in dare.lower() for dare in GOON_DARES))
        self.assertTrue(pick_dare())


if __name__ == "__main__":
    unittest.main()
