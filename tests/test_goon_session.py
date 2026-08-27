"""Goon session loop — meter, streaks, ruin, dares."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import config
from database import Database
from utils.goon_session import (
    GROUP_GOON_PROMPT,
    blank_lore_line,
    daily_edge_bonus_mult,
    finish_payout,
    is_group_goon_chat_claim,
    is_group_goon_yes,
    meter_bar,
    next_group_goon_call_minutes,
    pick_dare,
    roll_group_goon_reward,
    ruin_cost,
    session_from_row,
    watch_multiplier,
)
from utils.jobs import get_job
from utils.avatars import get_avatar


class GoonSessionMathTests(unittest.TestCase):
    def test_meter_bar_fills(self) -> None:
        self.assertIn("█", meter_bar(100.0))
        self.assertIn("░", meter_bar(0.0))

    def test_finish_payout_scales_with_streak_and_meter(self) -> None:
        dry = finish_payout(0, 0.0)
        self.assertEqual(dry, 0.0)
        low = finish_payout(1, 20.0)
        high = finish_payout(10, 90.0)
        self.assertGreater(low, 0.0)
        self.assertGreater(high, low)

    def test_ruin_cost_scales(self) -> None:
        self.assertGreater(ruin_cost(10), ruin_cost(1))

    def test_daily_bonus_caps(self) -> None:
        self.assertEqual(daily_edge_bonus_mult(0), 1.0)
        self.assertGreater(daily_edge_bonus_mult(5), 1.0)
        self.assertAlmostEqual(
            daily_edge_bonus_mult(999),
            1.0 + config.GOON_DAILY_STREAK_BONUS_CAP,
        )

    def test_watch_multiplier_caps(self) -> None:
        self.assertEqual(watch_multiplier(0), 1.0)
        self.assertGreater(watch_multiplier(3), 1.0)
        self.assertLessEqual(watch_multiplier(99), config.GOON_WATCH_MULT_CAP)

    def test_blank_lore_has_answer(self) -> None:
        prompt, answer = blank_lore_line("Velvet said don't finish until the bass drops.")
        self.assertIn("______", prompt)
        self.assertGreaterEqual(len(answer), 4)
        self.assertNotIn(answer.lower(), prompt.lower())

    def test_dare_deck_nonempty(self) -> None:
        self.assertTrue(pick_dare())

    def test_group_goon_yes_matches_answers(self) -> None:
        self.assertTrue(is_group_goon_yes("yes"))
        self.assertTrue(is_group_goon_yes("Yeah!"))
        self.assertTrue(is_group_goon_yes("yep"))
        self.assertTrue(is_group_goon_yes("I'm ready"))
        self.assertTrue(is_group_goon_yes("lets go"))
        self.assertTrue(is_group_goon_yes("ready"))
        self.assertFalse(is_group_goon_yes(""))
        self.assertFalse(is_group_goon_yes("no"))
        self.assertFalse(is_group_goon_yes("yesterday we raided"))
        self.assertIn("group goon session", GROUP_GOON_PROMPT.lower())

    def test_group_goon_chat_claim_filters_long_unrelated(self) -> None:
        self.assertTrue(is_group_goon_chat_claim("yes"))
        self.assertTrue(is_group_goon_chat_claim("yeah let's goon"))
        self.assertTrue(
            is_group_goon_chat_claim(
                "yeah that's a long unrelated take about the raid",
                replied_to_prompt=True,
            )
        )
        self.assertFalse(
            is_group_goon_chat_claim(
                "yeah that's a long unrelated take about the raid boss tonight",
            )
        )

    def test_group_goon_interval_and_reward_bounds(self) -> None:
        lo = config.GOON_CALL_INTERVAL_MINUTES - config.GOON_CALL_INTERVAL_JITTER_MINUTES
        hi = config.GOON_CALL_INTERVAL_MINUTES + config.GOON_CALL_INTERVAL_JITTER_MINUTES
        for _ in range(40):
            mins = next_group_goon_call_minutes()
            self.assertGreaterEqual(mins, lo)
            self.assertLessEqual(mins, hi)
            amount = roll_group_goon_reward()
            self.assertGreaterEqual(amount, config.GOON_CALL_REWARD[0])
            self.assertLessEqual(amount, config.GOON_CALL_REWARD[1])

    def test_condoms_item_is_drop_only(self) -> None:
        from items import get_item
        from utils.consumables_ui import SHOP_USE_IDS

        item = get_item("condoms")
        assert item is not None
        self.assertEqual(item.name, "Condoms")
        self.assertFalse(item.shop_listed)
        self.assertIn("condoms", SHOP_USE_IDS)

    def test_session_from_empty_row(self) -> None:
        state = session_from_row(None)
        self.assertEqual(state.meter, 0.0)
        self.assertEqual(state.streak, 0)

    def test_jobs_are_gooner(self) -> None:
        cave = get_job("miner")
        booth = get_job("floor_host")
        stage = get_job("stage_talent")
        assert cave and booth and stage
        self.assertEqual(cave.name, "Goon Cave Shift")
        self.assertEqual(booth.name, "Private Booth")
        self.assertIn("edge", stage.description.lower())

    def test_default_avatar_renamed(self) -> None:
        av = get_avatar("nugget_raider")
        assert av is not None
        self.assertEqual(av.name, "Goon Cave Regular")


class GoonSessionDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "goon.sqlite3"))
        await self.db.connect()
        await self.db.init_schema()
        self.guild = 42
        self.user = 7
        self.other = 8

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_edge_builds_streak_and_meter(self) -> None:
        now = 1_000.0
        result = await self.db.apply_goon_edge(
            self.user, self.guild, gain=15.0, now=now,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.state.streak, 1)
        self.assertAlmostEqual(result.state.meter, 15.0)
        cooled = await self.db.apply_goon_edge(
            self.user, self.guild, gain=15.0, now=now + 1,
        )
        self.assertFalse(cooled.ok)
        self.assertEqual(cooled.error, "cooldown")
        again = await self.db.apply_goon_edge(
            self.user, self.guild, gain=15.0, now=now + config.GOON_EDGE_COOLDOWN_SECONDS + 1,
        )
        self.assertTrue(again.ok)
        self.assertEqual(again.state.streak, 2)

    async def test_finish_pays_and_resets(self) -> None:
        await self.db.apply_goon_edge(self.user, self.guild, gain=40.0, now=10.0)
        result = await self.db.apply_goon_finish(self.user, self.guild, now=100.0)
        self.assertTrue(result.ok)
        self.assertGreater(result.payout, 0.0)
        wallet = await self.db.get_balance(self.user, self.guild)
        self.assertAlmostEqual(wallet, result.payout)
        state = await self.db.get_goon_session(self.user, self.guild)
        self.assertEqual(state.streak, 0)
        self.assertEqual(state.meter, 0.0)
        self.assertEqual(state.lifetime_finishes, 1)

    async def test_self_ruin_pays_consolation(self) -> None:
        await self.db.apply_goon_edge(self.user, self.guild, gain=50.0, now=10.0)
        result = await self.db.apply_goon_ruin_self(self.user, self.guild, now=20.0)
        self.assertTrue(result.ok)
        self.assertGreater(result.payout, 0.0)
        state = await self.db.get_goon_session(self.user, self.guild)
        self.assertEqual(state.streak, 0)
        self.assertEqual(state.lifetime_ruins, 1)

    async def test_ruin_other_steals(self) -> None:
        await self.db.credit_wallet(self.user, self.guild, 50_000.0, apply_bonuses=False)
        await self.db.apply_goon_edge(self.other, self.guild, gain=80.0, now=10.0)
        result = await self.db.apply_goon_ruin_other(
            self.user, self.other, self.guild, now=20.0,
        )
        self.assertTrue(result.ok)
        self.assertGreater(result.stolen, 0.0)
        target = await self.db.get_goon_session(self.other, self.guild)
        self.assertEqual(target.streak, 0)
        self.assertEqual(target.ruined_by, self.user)
        actor_wallet = await self.db.get_balance(self.user, self.guild)
        self.assertLess(actor_wallet, 50_000.0)

    async def test_tease_pushes_target_meter(self) -> None:
        await self.db.credit_wallet(self.user, self.guild, 1_000.0, apply_bonuses=False)
        result = await self.db.apply_goon_tease(
            self.user, self.other, self.guild, gain=18.0, now=10.0,
        )
        self.assertTrue(result.ok)
        target = await self.db.get_goon_session(self.other, self.guild)
        self.assertAlmostEqual(target.meter, 18.0)

    async def test_hack_ruin_wipes_session(self) -> None:
        await self.db.apply_goon_edge(self.user, self.guild, gain=40.0, now=10.0)
        result = await self.db.ruin_goon_from_hack(self.user, self.guild, now=20.0)
        self.assertTrue(result.ok)
        state = await self.db.get_goon_session(self.user, self.guild)
        self.assertEqual(state.meter, 0.0)
        self.assertEqual(state.streak, 0)

    async def test_passive_tick_respects_cooldown(self) -> None:
        first = await self.db.tick_goon_passive(
            self.user, self.guild, gain=2.0, now=10.0, cooldown=120.0,
        )
        self.assertTrue(first.ok)
        second = await self.db.tick_goon_passive(
            self.user, self.guild, gain=2.0, now=11.0, cooldown=120.0,
        )
        self.assertFalse(second.ok)
        self.assertEqual(second.error, "cooldown")

    async def test_meter_caps_and_leaks(self) -> None:
        result = await self.db.apply_goon_edge(
            self.user, self.guild, gain=150.0, now=10.0,
        )
        self.assertTrue(result.leaked)
        self.assertEqual(result.state.meter, config.GOON_METER_MAX)

    async def test_grant_condoms_stacks(self) -> None:
        await self.db.ensure_user(self.user, self.guild)
        for _ in range(config.GOON_CALL_CONDOMS):
            await self.db.grant_item(self.user, self.guild, "condoms")
        qty = await self.db.get_inventory_quantity(self.user, self.guild, "condoms")
        self.assertEqual(qty, config.GOON_CALL_CONDOMS)


class GoonLoreFallbackTests(unittest.TestCase):
    def test_trivia_fallback_always_works(self) -> None:
        for _ in range(20):
            prompt, answer = blank_lore_line()
            self.assertTrue(prompt)
            self.assertTrue(answer)


if __name__ == "__main__":
    unittest.main()
