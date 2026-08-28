"""Group goon call scheduling — poll, live chatters, no silent 2h skip."""
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
    prune_chatter_stamps,
    recent_channel_author_stamps,
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

    def test_call_body_omits_zero_prize(self) -> None:
        paid = GroupCallState(guild_id=1, channel_id=2, amount=8000.0, condoms=3)
        free = GroupCallState(guild_id=1, channel_id=2, amount=0.0, condoms=3)
        self.assertIn("8,000", call_body(paid))
        self.assertNotIn("0", call_body(free).split("Condoms")[0])
        self.assertIn("3× Condoms", call_body(free))

    def test_poll_is_far_shorter_than_interval(self) -> None:
        self.assertLess(config.GOON_CALL_POLL_SECONDS, 120)
        self.assertGreaterEqual(config.GOON_CALL_INTERVAL_MINUTES, 60)


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
        self.assertIn("Condoms", body)

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
        self.assertIn("Condoms", body)

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
