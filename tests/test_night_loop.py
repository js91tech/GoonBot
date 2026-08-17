"""Onboarding night-loop panel tests."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from utils import age_gate, onboarding
from utils.businesses import BUSINESS_TIERS, tier_def
from utils.districts import DISTRICT_MAP
from items import get_item


class OnboardingTests(unittest.IsolatedAsyncioTestCase):
    def test_embed_teaches_night_loop(self) -> None:
        embed = onboarding.onboarding_embed(member_name="Test")
        text = (embed.description or "") + embed.title
        self.assertIn("/daily", text)
        self.assertIn("/jobs", text)
        self.assertIn("/shop", text)
        self.assertIn("/boss", text)
        self.assertIn("/profile", text)
        self.assertIn("goonbux", text.lower())

    async def test_age_confirm_shows_onboarding(self) -> None:
        db = MagicMock()
        db.set_age_verified = AsyncMock()
        view = age_gate.AgeGateView(db, guild_id=1, user_id=7)
        interaction = MagicMock()
        interaction.user = MagicMock(id=7, display_name="Gooner")
        interaction.response.edit_message = AsyncMock()
        confirm_btn = next(
            c for c in view.children
            if getattr(c, "label", None) == "I am 18+ — enter"
        )
        await confirm_btn.callback(interaction)
        db.set_age_verified.assert_awaited_once_with(7, 1, True)
        kwargs = interaction.response.edit_message.await_args.kwargs
        self.assertIn("/daily", kwargs["embed"].description)
        self.assertIsInstance(kwargs["view"], onboarding.NightLoopView)


class NightlifeCatalogTests(unittest.TestCase):
    def test_districts_renamed(self) -> None:
        self.assertEqual(DISTRICT_MAP["downtown"].name, "Red-Light Strip")
        self.assertEqual(DISTRICT_MAP["financial"].name, "Sugar District")
        self.assertEqual(DISTRICT_MAP["industrial"].name, "Studio Row")

    def test_business_display_names(self) -> None:
        self.assertEqual(tier_def(1).tier_id, "lemon_stand")
        self.assertEqual(tier_def(1).name, "Tip Jar Cam")
        self.assertEqual(tier_def(7).name, "Adult Empire HQ")
        self.assertEqual(len(BUSINESS_TIERS), 7)

    def test_shop_flavor(self) -> None:
        self.assertEqual(get_item("twig_sword").name, "Tease Blade")
        self.assertEqual(get_item("iron_sword").name, "Velvet Edge")
        self.assertEqual(get_item("nugget_excalibur").name, "Goon Excalibur")
        self.assertEqual(get_item("training_stick").name, "Practice Crop")


if __name__ == "__main__":
    unittest.main()
