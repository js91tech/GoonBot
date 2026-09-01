"""Group goon call scheduling — poll, live chatters, Velvet art, no silent skip."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import config
from cogs.goon import Goon
from database import Database
from utils.goon_group import (
    GroupCallState,
    call_body,
    group_call_skip_reason,
    group_goon_call_media,
    group_goon_favor_media,
    pick_velvet_favor,
    prune_chatter_stamps,
    recent_channel_author_stamps,
    round_body,
    velvet_favor_claim_copy,
    velvet_favor_prize_text,
)


class GroupCallHelperTests(unittest.TestCase):
    def test_prune_drops_stale_typers(self) -> None:
        now = 1_000.0
        kept = prune_chatter_stamps({1: 900.0, 2: 100.0}, now, 200.0)
        self.assertEqual(kept, {1: 900.0})

    def test_skip_reasons(self) -> None:
        self.assertEqual(
            group_call_skip_reason(
                channel_ok=False, active=False, due=True, chatter_count=5, min_chatters=2,
            ),
            "no_channel",
        )
        self.assertEqual(
            group_call_skip_reason(
                channel_ok=True, active=True, due=True, chatter_count=5, min_chatters=2,
            ),
            "active_call",
        )
        self.assertEqual(
            group_call_skip_reason(
                channel_ok=True, active=False, due=False, chatter_count=5, min_chatters=2,
            ),
            "not_due",
        )
        self.assertEqual(
            group_call_skip_reason(
                channel_ok=True, active=False, due=True, chatter_count=1, min_chatters=2,
            ),
            "quiet",
        )
        self.assertIsNone(
            group_call_skip_reason(
                channel_ok=True, active=False, due=True, chatter_count=2, min_chatters=2,
            )
        )

    def test_call_body_offers_velvet_not_condoms(self) -> None:
        paid = GroupCallState(guild_id=1, channel_id=2, amount=8000.0, condoms=0)
        free = GroupCallState(guild_id=1, channel_id=2, amount=0.0, condoms=0)
        self.assertIn("8,000", call_body(paid))
        self.assertIn("kisses from Velvet", call_body(paid))
        self.assertIn("go down on you", call_body(paid))
        self.assertNotIn("Condoms", call_body(paid))
        self.assertNotIn("Condoms", call_body(free))
        self.assertIn("kisses from Velvet", call_body(free))

    def test_round_body_says_velvet_took_care(self) -> None:
        state = GroupCallState(
            guild_id=1, channel_id=2, amount=8000.0, condoms=0, host_id=77, phase="round",
        )
        state.joiners.add(77)
        body = round_body(state)
        self.assertIn("Velvet took care", body)
        self.assertNotIn("Condoms", body.split("Join late")[0])

    def test_velvet_favor_copy_and_media(self) -> None:
        self.assertIn("kisses from Velvet", velvet_favor_prize_text())
        kisses = velvet_favor_claim_copy("kisses", 9, 0.0)
        head = velvet_favor_claim_copy("head", 9, 5000.0)
        self.assertIn("<@9>", kisses)
        self.assertIn("kissed", kisses)
        self.assertIn("head from Velvet", head)
        self.assertIn("5,000", head)
        self.assertIn(pick_velvet_favor(), {"kisses", "head"})
        for kind in ("kisses", "head"):
            embed, art = group_goon_favor_media(kind)
            self.assertIsNotNone(embed)
            self.assertIsNotNone(art)
            assert art is not None
            self.assertIn("velvet", art.filename.lower())
            art.close()

    def test_poll_is_far_shorter_than_interval(self) -> None:
        self.assertLess(config.GOON_CALL_POLL_SECONDS, 120)
        self.assertEqual(config.GOON_CALL_INTERVAL_MINUTES, 145)
        self.assertEqual(config.GOON_CALL_INTERVAL_JITTER_MINUTES, 0)

    def test_call_media_attaches_velvet_image(self) -> None:
        embed, art = group_goon_call_media()
        self.assertIsNotNone(embed)
        self.assertIsNotNone(art)
        assert art is not None
        self.assertNotIn("_", art.filename)
        self.assertTrue(
            art.filename.endswith((".png", ".gif", ".webp")),
            art.filename,
        )
        self.assertIn("velvet", art.filename.lower())
        image = embed.to_dict().get("image") or {}
        self.assertEqual(image.get("url"), f"attachment://{art.filename}")
        art.close()


class GroupCallHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_collects_human_authors(self) -> None:
        now = time.time()

        async def _history(*, limit, after):
            del limit, after
            yield SimpleNamespace(
                author=SimpleNamespace(id=11, bot=False),
                created_at=SimpleNamespace(timestamp=lambda: now - 10),
            )
            yield SimpleNamespace(
                author=SimpleNamespace(id=12, bot=True),
                created_at=SimpleNamespace(timestamp=lambda: now - 5),
            )
            yield SimpleNamespace(
                author=SimpleNamespace(id=13, bot=False),
                created_at=SimpleNamespace(timestamp=lambda: now - 3),
            )

        channel = SimpleNamespace(history=_history)
        stamps = await recent_channel_author_stamps(channel, after_ts=now - 60, limit=40)
        self.assertEqual(set(stamps), {11, 13})


class GroupCallPostTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "goon.sqlite3"))
        await self.db.connect()
        await self.db.init_schema()
        self.guild_id = 42
        self.channel_id = 99
        self.bot = SimpleNamespace(
            db=self.db,
            guilds=[],
            user=SimpleNamespace(id=1),
            outbound_gate=None,
        )
        self.cog = Goon(self.bot)  # type: ignore[arg-type]
        self.cog.group_goon_call_tick.cancel()
        self.cog.group_goon_expire_tick.cancel()
        self.guild = MagicMock()
        self.guild.id = self.guild_id
        self.guild.roles = []
        self.channel = MagicMock()
        self.channel.id = self.channel_id
        posted = MagicMock()
        posted.id = 555
        self.posted = posted
        await self.db.credit_house_pot(self.guild_id, 50_000.0)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_quiet_tick_keeps_chatters_and_stays_due(self) -> None:
        now = 10_000.0
        self.cog._call_due_at[self.guild_id] = now - 1
        self.cog._note_chatter(self.guild_id, 7, now=now)
        with (
            patch("cogs.goon.resolve_lore_channel", new_callable=AsyncMock, return_value=self.channel),
            patch("cogs.goon.recent_channel_author_stamps", new_callable=AsyncMock, return_value={}),
            patch("cogs.goon.send_channel_message", new_callable=AsyncMock) as send,
        ):
            await self.cog._maybe_post_group_goon_call(self.guild, now=now)
        send.assert_not_called()
        self.assertIn(7, self.cog.recent_chatters[self.guild_id])
        self.assertLess(self.cog._call_due_at[self.guild_id], now)

    async def test_posts_when_due_with_two_typers(self) -> None:
        now = 10_000.0
        self.cog._call_due_at[self.guild_id] = now - 1
        self.cog._note_chatter(self.guild_id, 7, now=now)
        self.cog._note_chatter(self.guild_id, 8, now=now)
        with (
            patch("cogs.goon.resolve_lore_channel", new_callable=AsyncMock, return_value=self.channel),
            patch("cogs.goon.recent_channel_author_stamps", new_callable=AsyncMock, return_value={}),
            patch("cogs.goon.send_channel_message", new_callable=AsyncMock, return_value=self.posted) as send,
        ):
            await self.cog._maybe_post_group_goon_call(self.guild, now=now)
        send.assert_called_once()
        self.assertIn(self.channel_id, self.cog.active_calls)
        self.assertGreater(self.cog._call_due_at[self.guild_id], now)
        body = send.call_args.args[2]
        self.assertIn("I'm ready", body)
        self.assertIn("Velvet", body)
        self.assertNotIn("Condoms", body)
        self.assertIn("embed", send.call_args.kwargs)
        self.assertIn("file", send.call_args.kwargs)
        art = send.call_args.kwargs["file"]
        self.assertIn("velvet", art.filename.lower())
        art.close()

    async def test_history_typers_can_satisfy_min_chatters(self) -> None:
        now = 10_000.0
        self.cog._call_due_at[self.guild_id] = now - 1
        with (
            patch("cogs.goon.resolve_lore_channel", new_callable=AsyncMock, return_value=self.channel),
            patch(
                "cogs.goon.recent_channel_author_stamps",
                new_callable=AsyncMock,
                return_value={21: now - 5, 22: now - 8},
            ),
            patch("cogs.goon.send_channel_message", new_callable=AsyncMock, return_value=self.posted) as send,
        ):
            await self.cog._maybe_post_group_goon_call(self.guild, now=now)
        send.assert_called_once()
        art = send.call_args.kwargs.get("file")
        if art is not None:
            art.close()

    async def test_empty_pot_still_posts(self) -> None:
        now = 10_000.0
        await self.db.debit_house_pot(self.guild_id, 50_000.0)
        self.assertEqual(await self.db.get_house_pot(self.guild_id), 0.0)
        self.cog._call_due_at[self.guild_id] = now - 1
        self.cog._note_chatter(self.guild_id, 7, now=now)
        self.cog._note_chatter(self.guild_id, 8, now=now)
        with (
            patch("cogs.goon.resolve_lore_channel", new_callable=AsyncMock, return_value=self.channel),
            patch("cogs.goon.recent_channel_author_stamps", new_callable=AsyncMock, return_value={}),
            patch("cogs.goon.send_channel_message", new_callable=AsyncMock, return_value=self.posted) as send,
        ):
            await self.cog._maybe_post_group_goon_call(self.guild, now=now)
        send.assert_called_once()
        self.assertEqual(self.cog.active_calls[self.channel_id].amount, 0.0)
        body = send.call_args.args[2]
        self.assertIn("Velvet", body)
        self.assertNotIn("Condoms", body)
        self.assertIn("file", send.call_args.kwargs)
        send.call_args.kwargs["file"].close()

    async def test_first_claim_sends_velvet_favor_not_condoms(self) -> None:
        now = 10_000.0
        self.cog._call_due_at[self.guild_id] = now - 1
        self.cog._note_chatter(self.guild_id, 7, now=now)
        self.cog._note_chatter(self.guild_id, 8, now=now)
        self.posted.channel = self.channel
        member = MagicMock()
        member.id = 7
        member.bot = False
        member.guild = self.guild
        await self.db.ensure_user(7, self.guild_id)
        with (
            patch("cogs.goon.resolve_lore_channel", new_callable=AsyncMock, return_value=self.channel),
            patch("cogs.goon.recent_channel_author_stamps", new_callable=AsyncMock, return_value={}),
            patch("cogs.goon.send_channel_message", new_callable=AsyncMock, return_value=self.posted) as send,
            patch("cogs.goon.edit_call_message", new_callable=AsyncMock),
        ):
            await self.cog._maybe_post_group_goon_call(self.guild, now=now)
            state = self.cog.active_calls[self.channel_id]
            err = await self.cog._claim_first(member, state)
        self.assertIsNone(err)
        self.assertEqual(state.phase, "round")
        qty = await self.db.get_inventory_quantity(7, self.guild_id, "condoms")
        self.assertEqual(qty, 0)
        self.assertGreaterEqual(send.await_count, 2)
        favor_body = send.call_args.args[2]
        self.assertTrue(
            "kissed" in favor_body or "head from Velvet" in favor_body,
            favor_body,
        )
        self.assertIn("file", send.call_args.kwargs)
        for call in send.call_args_list:
            art = call.kwargs.get("file")
            if art is not None:
                art.close()

    async def test_startup_delay_skips_immediate_boot_tick(self) -> None:
        now = 10_000.0
        self.cog._schedule_next_group_call(self.guild_id, now=now, startup=True)
        self.cog._note_chatter(self.guild_id, 7, now=now)
        self.cog._note_chatter(self.guild_id, 8, now=now)
        with (
            patch("cogs.goon.resolve_lore_channel", new_callable=AsyncMock, return_value=self.channel),
            patch("cogs.goon.send_channel_message", new_callable=AsyncMock) as send,
        ):
            await self.cog._maybe_post_group_goon_call(self.guild, now=now)
        send.assert_not_called()
        due = self.cog._call_due_at[self.guild_id]
        self.assertAlmostEqual(due - now, config.GOON_CALL_STARTUP_DELAY_MINUTES * 60, delta=1)

    async def test_loop_uses_poll_seconds(self) -> None:
        self.assertEqual(self.cog.group_goon_call_tick.seconds, config.GOON_CALL_POLL_SECONDS)


if __name__ == "__main__":
    unittest.main()
