"""Onboarding night-loop panel tests."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

import config
from utils import age_gate, onboarding
from utils.businesses import BUSINESS_TIERS, tier_def, tier_def_by_id
from utils.districts import DISTRICT_MAP
from items import get_item


class OnboardingTests(unittest.IsolatedAsyncioTestCase):
    def test_embed_teaches_night_loop(self) -> None:
        embed = onboarding.onboarding_embed(member_name="Test")
        text = (embed.description or "") + embed.title
        self.assertIn("/daily", text)
        self.assertIn("/class choose", text)
        self.assertIn("/jobs", text)
        self.assertIn("/boss", text)
        self.assertIn("/profile", text)
        self.assertIn("persona", text.lower())
        self.assertIn("goonbux", text.lower())
        self.assertIn("guest list", text.lower())

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
        self.assertEqual(tier_def(1).tier_id, "tip_jar_cam")
        self.assertEqual(tier_def(1).name, "Tip Jar Cam")
        self.assertEqual(tier_def(7).tier_id, "adult_empire_hq")
        self.assertEqual(tier_def(7).name, "Adult Empire HQ")
        self.assertEqual(len(BUSINESS_TIERS), 7)
        self.assertEqual(tier_def_by_id("lemon_stand").tier_id, "tip_jar_cam")

    def test_shop_flavor(self) -> None:
        self.assertEqual(get_item("twig_sword").name, "Tease Blade")
        self.assertEqual(get_item("iron_sword").name, "Velvet Edge")
        self.assertEqual(get_item("nugget_excalibur").name, "Goon Excalibur")
        self.assertEqual(get_item("training_stick").name, "Practice Crop")

    def test_business_art_is_nightlife_not_lemonade(self) -> None:
        from pathlib import Path

        from utils.achievements import ACHIEVEMENTS
        from utils.business_art import ASSET_DIR
        from utils.business_competition import action_by_id
        from utils.mega_projects import mega_project_by_id

        leftover_ids = {
            "lemon_stand",
            "food_cart",
            "coffee_shop",
            "restaurant",
            "chain_restaurant",
            "factory",
            "corporation",
        }
        live_ids = {defn.tier_id for defn in BUSINESS_TIERS}
        self.assertTrue(live_ids.isdisjoint(leftover_ids))
        for defn in BUSINESS_TIERS:
            self.assertTrue(
                (ASSET_DIR / f"{defn.tier_id}.png").is_file(),
                f"missing nightlife art for {defn.tier_id}",
            )
        from utils.districts import ASSET_DIR as DISTRICT_ASSET_DIR, DISTRICT_IDS

        for district_id in DISTRICT_IDS:
            self.assertTrue(
                (DISTRICT_ASSET_DIR / f"{district_id}.png").is_file(),
                f"missing nightlife district art for {district_id}",
            )
        for leftover in leftover_ids:
            self.assertFalse((ASSET_DIR / f"{leftover}.png").is_file(), leftover)

        self.assertEqual(ACHIEVEMENTS["corporation_owner"].name, "Empire Owner")
        self.assertIn("Adult Empire HQ", ACHIEVEMENTS["corporation_owner"].description)
        self.assertEqual(action_by_id("marketing_campaign").name, "Floor Promo")
        self.assertEqual(action_by_id("price_war").name, "Cover Charge War")
        self.assertEqual(mega_project_by_id("space_program").name, "Satellite Cam Grid")
        self.assertEqual(mega_project_by_id("world_expo").name, "World Afterparty")
        self.assertEqual(config.BOSS_ATTACK_COOLDOWN_MAX_SECONDS, 0)
        self.assertEqual(config.BOSS_ATTACK_COOLDOWN_MIN_SECONDS, 0)
        art_src = Path(__file__).resolve().parents[1] / "utils" / "business_art.py"
        self.assertNotIn("lemonade", art_src.read_text().lower())
        self.assertNotIn("lemon stand", art_src.read_text().lower())


if __name__ == "__main__":
    unittest.main()
