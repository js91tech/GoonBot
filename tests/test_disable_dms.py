"""GoonBot must not DM players unless DM_NOTIFICATIONS_ENABLED is on."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

import config
from cogs.retention import Retention
from utils.notify_prefs import effective_notify_flags
from utils.notify_ui import build_notify_embed


class DisableDmTests(unittest.IsolatedAsyncioTestCase):
    def test_dms_off_by_default(self) -> None:
        self.assertFalse(config.DM_NOTIFICATIONS_ENABLED)
        self.assertEqual(config.NOTIFY_ELIGIBLE_DEFAULT_FLAGS, 0)

    async def test_effective_flags_zero_when_disabled(self) -> None:
        db = MagicMock()
        db.get_notify_flags = AsyncMock(
            return_value=config.NOTIFY_BOSS | config.NOTIFY_USER_CONFIGURED,
        )
        self.assertEqual(await effective_notify_flags(db, 1, 2), 0)

    def test_notify_panel_says_no_dms(self) -> None:
        embed = build_notify_embed(0, configured=False, eligible=True)
        self.assertIn("does not send DMs", embed.description)

    async def test_maybe_dm_does_not_send(self) -> None:
        bot = MagicMock()
        bot.db = MagicMock()
        cog = Retention.__new__(Retention)
        cog.bot = bot
        member = MagicMock()
        member.bot = False
        member.send = AsyncMock()
        guild = MagicMock()
        guild.get_member.return_value = member
        guild.name = "Goon"
        bot.get_guild.return_value = guild
        await Retention._maybe_dm(
            cog,
            1,
            2,
            flag=config.NOTIFY_BOSS,
            notify_key="boss:1",
            body="raid",
        )
        member.send.assert_not_called()
        bot.db.record_notify_sent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
