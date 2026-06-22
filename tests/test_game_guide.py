"""Tests for /guide content and embed limits."""
from __future__ import annotations

import unittest

from utils.game_guide import (
    GUIDE_SECTIONS,
    GUIDE_SECTION_MAP,
    build_guide_embed,
    guide_section_options,
)


class GameGuideTests(unittest.TestCase):
    def test_sections_cover_core_topics(self) -> None:
        ids = {section.section_id for section in GUIDE_SECTIONS}
        expected = {
            "overview",
            "economy",
            "boss",
            "dungeon",
            "pvp",
            "character",
            "enhancement",
            "accessories",
            "weapons",
            "guns",
            "armor",
            "consumables",
            "chaos",
            "progression",
            "aspects",
        }
        self.assertTrue(expected.issubset(ids))

    def test_select_options_match_sections(self) -> None:
        options = guide_section_options()
        self.assertEqual(len(options), len(GUIDE_SECTIONS))
        self.assertEqual({opt[0] for opt in options}, set(GUIDE_SECTION_MAP))

    def test_all_embeds_within_discord_limits(self) -> None:
        for section in GUIDE_SECTIONS:
            for page_index in range(len(section.pages)):
                embed, _, _ = build_guide_embed(section.section_id, page_index)
                desc = embed.description or ""
                self.assertLessEqual(
                    len(desc),
                    4096,
                    msg=f"{section.section_id} page {page_index}",
                )
                for field in embed.fields:
                    self.assertLessEqual(len(field.value), 1024)

    def test_unknown_section_not_in_map(self) -> None:
        with self.assertRaises(KeyError):
            build_guide_embed("not_a_real_section", 0)


if __name__ == "__main__":
    unittest.main()
