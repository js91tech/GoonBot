from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import discord

import config
from cogs.trivia import (
    Trivia,
    TriviaRound,
    format_trivia_window,
    normalize_trivia_guess,
    roll_trivia_drug,
    trivia_drug_chance,
    trivia_speed_fraction,
    trivia_speed_multiplier,
)
from database import Database


class TriviaRewardMathTests(unittest.TestCase):
    def test_window_is_three_minutes(self) -> None:
        self.assertEqual(config.TRIVIA_SECONDS, 180)
        self.assertEqual(format_trivia_window(), "3 minutes")

    def test_faster_answers_pay_more(self) -> None:
        instant = trivia_speed_multiplier(config.TRIVIA_SECONDS)
        mid = trivia_speed_multiplier(config.TRIVIA_SECONDS / 2)
        late = trivia_speed_multiplier(0.0)
        self.assertAlmostEqual(instant, config.TRIVIA_SPEED_MAX_MULT)
        self.assertAlmostEqual(late, config.TRIVIA_SPEED_MIN_MULT)
        self.assertGreater(instant, mid)
        self.assertGreater(mid, late)

    def test_speed_fraction_clamps(self) -> None:
        self.assertEqual(trivia_speed_fraction(-5), 0.0)
        self.assertEqual(trivia_speed_fraction(config.TRIVIA_SECONDS * 2), 1.0)

    def test_faster_answers_raise_drug_chance(self) -> None:
        instant = trivia_drug_chance(config.TRIVIA_SECONDS)
        late = trivia_drug_chance(0.0)
        self.assertAlmostEqual(late, config.TRIVIA_DRUG_CHANCE)
        self.assertAlmostEqual(
            instant,
            config.TRIVIA_DRUG_CHANCE + config.TRIVIA_DRUG_FAST_BONUS,
        )
        self.assertGreater(instant, late)

    def test_roll_trivia_drug_returns_catalog_id(self) -> None:
        with mock.patch(
            "cogs.trivia.random.choices",
            return_value=[type("D", (), {"drug_id": "blue_dream"})()],
        ):
            self.assertEqual(roll_trivia_drug(), "blue_dream")

    def test_trivia_drug_display_is_goonbot_named(self) -> None:
        from utils.drugs import drug_by_id

        defn = drug_by_id("blue_dream")
        assert defn is not None
        self.assertEqual(defn.name, "Velvet Dream")
        self.assertNotIn("nugget", defn.name.lower())
        self.assertNotEqual(defn.name, "Blue Dream")

    def test_normalize_strips_punctuation(self) -> None:
        self.assertEqual(normalize_trivia_guess("Hello!"), "hello")
        self.assertEqual(normalize_trivia_guess("  goonbux. "), "goonbux")


class TriviaPayoutTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "trivia.sqlite3"))
        await self.db.connect()
        await self.db.init_schema()
        self.bot = SimpleNamespace(db=self.db)
        self.cog = Trivia(self.bot)  # type: ignore[arg-type]
        self.cog.trivia_event_tick.cancel()

    async def asyncTearDown(self) -> None:
        self.cog.cog_unload()
        await self.db.close()
        self.tmp.cleanup()

    async def test_reward_debits_house_pot(self) -> None:
        guild = SimpleNamespace(id=42)
        user = SimpleNamespace(id=7, mention="<@7>")
        await self.db.credit_house_pot(42, 10_000.0)
        before = await self.db.get_house_pot(42)
        with mock.patch("cogs.trivia.random.random", return_value=1.0):
            text = await self.cog._reward_correct_answer(
                guild,  # type: ignore[arg-type]
                user,  # type: ignore[arg-type]
                "test",
                expires_at=9999999999.0,
                started_at=0.0,
            )
        after = await self.db.get_house_pot(42)
        self.assertLess(after, before)
        self.assertIn("Prize:", text)
        wallet = await self.db.get_balance(7, 42)
        self.assertGreater(wallet, 0)

    async def test_reward_drops_a_gooncard(self) -> None:
        guild = SimpleNamespace(id=42)
        user = SimpleNamespace(id=7, mention="<@7>")
        await self.db.ensure_user(7, 42)
        with mock.patch("cogs.trivia.random.random", return_value=1.0):
            text = await self.cog._reward_correct_answer(
                guild,  # type: ignore[arg-type]
                user,  # type: ignore[arg-type]
                "test",
                expires_at=9999999999.0,
                started_at=0.0,
            )
        count, unique = await self.db.count_owned_cards(7, 42)
        self.assertEqual(count, 1)
        self.assertEqual(unique, 1)
        self.assertIn("Trivia GoonCard", text)

    async def test_stale_round_id_rejected(self) -> None:
        self.cog.active_rounds[99] = TriviaRound(
            round_id="abc",
            answer="hello",
            expires_at=9999999999.0,
            started_at=0.0,
        )
        self.assertTrue(self.cog._round_is_active(99, "abc"))
        self.assertFalse(self.cog._round_is_active(99, "zzz"))

    async def test_start_round_posts_in_yappinmain(self) -> None:
        await self.db.set_designated_channel_id(42, 555)
        await self.db.set_main_channel_id(42, 555)
        await self.db.set_config_value(42, "bot_room_only", 1.0)

        bot_ch = mock.MagicMock(spec=discord.TextChannel)
        bot_ch.id = 555
        bot_ch.name = "nuggetivitesbot"
        bot_ch.permissions_for.return_value = SimpleNamespace(send_messages=True)

        main_ch = mock.MagicMock(spec=discord.TextChannel)
        main_ch.id = 777
        main_ch.name = "yappinmain"
        main_ch.permissions_for.return_value = SimpleNamespace(send_messages=True)

        guild = mock.MagicMock(spec=discord.Guild)
        guild.id = 42
        guild.me = mock.MagicMock()
        guild.get_channel.side_effect = lambda cid: {555: bot_ch, 777: main_ch}.get(cid)
        guild.text_channels = [bot_ch, main_ch]

        sent = mock.MagicMock(spec=discord.Message)
        sent.guild = guild
        with (
            mock.patch.object(
                self.cog,
                "_make_puzzle",
                new=mock.AsyncMock(return_value=("foo _____ bar", "missing")),
            ),
            mock.patch(
                "cogs.trivia.send_channel_message",
                new_callable=mock.AsyncMock,
                return_value=sent,
            ) as mock_send,
        ):
            started = await self.cog._start_round(guild, bot_ch, announce_prefix=True)

        self.assertTrue(started)
        self.assertIn(777, self.cog.active_rounds)
        self.assertNotIn(555, self.cog.active_rounds)
        mock_send.assert_awaited_once()
        self.assertIs(mock_send.await_args.args[1], main_ch)
        round_state = self.cog.active_rounds[777]
        if round_state.end_task is not None:
            round_state.end_task.cancel()


if __name__ == "__main__":
    unittest.main()
