"""Persona display names — no raw Vanguard/Mogul/Shade titles in UI helpers."""
from __future__ import annotations

import unittest

from utils.classes import (
    STARTER_IDS,
    format_master_roots,
    get_class,
    starter_display_name,
    starter_names_list,
)


class PersonaDisplayTests(unittest.TestCase):
    def test_starters_are_nightlife_names(self) -> None:
        names = [starter_display_name(s) for s in STARTER_IDS]
        self.assertEqual(names, ["Talent", "Host", "Fixer"])
        joined = starter_names_list()
        self.assertIn("Talent", joined)
        self.assertNotIn("Vanguard", joined)
        self.assertNotIn("Mogul", joined)
        self.assertNotIn("Shade", joined)

    def test_master_roots_use_labels(self) -> None:
        text = format_master_roots({"vanguard", "shade"})
        self.assertEqual(text, "Fixer, Talent")

    def test_hybrids_named(self) -> None:
        self.assertEqual(get_class("warlord").name, "Circuit Boss")
        self.assertEqual(get_class("archon").name, "House Idol")

    def test_fantasy_master_names_gone(self) -> None:
        for class_id, cls in __import__("utils.classes", fromlist=["CLASS_MAP"]).CLASS_MAP.items():
            self.assertNotEqual(cls.name, "Incursor")
            self.assertNotEqual(cls.name, "Nightshade")
            self.assertNotEqual(cls.name, "Wraith")
            self.assertNotIn("Vanguard", cls.name)


if __name__ == "__main__":
    unittest.main()
