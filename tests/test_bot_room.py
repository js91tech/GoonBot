"""Bot-room lock — GoonBot only types in NuggetIvitesBot-style channel."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

import config
from database import Database
from utils import age_gate, bot_room
from utils.helpers import resolve_bot_announcement_channel, resolve_main_channel


class BotRoomNameTests(unittest.TestCase):
    def test_matches_nuggetivitesbot_names(self) -> None:
        self.assertTrue(
            bot_room.channel_matches_bot_room_name(
                SimpleNamespace(name="nuggetivitesbot"),
            ),
        )
        self.assertTrue(
            bot_room.channel_matches_bot_room_name(
                SimpleNamespace(name="Nugget-Ivites-Bot-room"),
            ),
        )
        self.assertTrue(
            bot_room.channel_matches_bot_room_name(SimpleNamespace(name="goonbot-room")),
        )
        self.assertFalse(
            bot_room.channel_matches_bot_room_name(SimpleNamespace(name="general")),
        )


class BotRoomResolverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "room.sqlite3"))
        await self.db.connect()
        await self.db.init_schema()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_resolvers_use_designated_when_bot_room_only(self) -> None:
        await self.db.set_designated_channel_id(1, 555)
        await self.db.set_main_channel_id(1, 555)
        await self.db.set_config_value(1, "bot_room_only", 1.0)

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 555
        channel.permissions_for.return_value = SimpleNamespace(send_messages=True)

        guild = MagicMock(spec=discord.Guild)
        guild.id = 1
        guild.me = MagicMock()
        guild.get_channel.return_value = channel
        guild.text_channels = [channel]
        guild.system_channel = None

        main = await resolve_main_channel(guild, self.db)
        announce = await resolve_bot_announcement_channel(guild, self.db)
        self.assertIs(main, channel)
        self.assertIs(announce, channel)

    async def test_no_fallback_when_bot_room_only_unset(self) -> None:
        await self.db.set_config_value(2, "bot_room_only", 1.0)
        other = MagicMock(spec=discord.TextChannel)
        other.id = 999
        other.name = "general"
        other.permissions_for.return_value = SimpleNamespace(send_messages=True)

        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()
        guild.get_channel.return_value = None
        guild.text_channels = [other]
        guild.system_channel = other

        self.assertIsNone(await resolve_main_channel(guild, self.db))


class BotRoomGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocks_commands_outside_bot_room(self) -> None:
        db = MagicMock()
        db.get_config_value = AsyncMock(side_effect=lambda gid, key: {
            "nsfw_channel_only": 0.0,
            "bot_room_only": 1.0,
        }[key])
        db.get_age_verified = AsyncMock(return_value=True)
        db.get_designated_channel_id = AsyncMock(return_value=555)
        db.get_main_channel_id = AsyncMock(return_value=555)

        bot_ch = MagicMock(spec=discord.TextChannel)
        bot_ch.id = 555
        bot_ch.permissions_for.return_value = SimpleNamespace(send_messages=True)

        guild = MagicMock(spec=discord.Guild)
        guild.id = 10
        guild.me = MagicMock()
        guild.get_channel.return_value = bot_ch
        guild.text_channels = [bot_ch]

        interaction = MagicMock()
        interaction.guild_id = 10
        interaction.guild = guild
        interaction.type = discord.InteractionType.application_command
        interaction.channel = SimpleNamespace(id=111, nsfw=True, parent=None)
        interaction.user = SimpleNamespace(
            id=7,
            guild_permissions=SimpleNamespace(administrator=False),
        )
        interaction.response.send_message = AsyncMock()

        ok = await age_gate.check_interaction(interaction, db)
        self.assertFalse(ok)
        msg = interaction.response.send_message.await_args.args[0]
        self.assertIn("only runs", msg.lower())


if __name__ == "__main__":
    unittest.main()
