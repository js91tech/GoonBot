"""Bot-room lock — GoonBot only types in NuggetIvitesBot-style channel."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_matches_yappinmain_names(self) -> None:
        self.assertTrue(
            bot_room.channel_matches_main_channel_name(
                SimpleNamespace(name="yappinmain"),
            ),
        )
        self.assertTrue(
            bot_room.channel_matches_main_channel_name(
                SimpleNamespace(name="Yappin-Main"),
            ),
        )
        self.assertFalse(
            bot_room.channel_matches_main_channel_name(SimpleNamespace(name="general")),
        )
        self.assertFalse(
            bot_room.channel_matches_main_channel_name(
                SimpleNamespace(name="nuggetivitesbot"),
            ),
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


class LoreChannelResolverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "lore.sqlite3"))
        await self.db.connect()
        await self.db.init_schema()

        self.bot_ch = MagicMock(spec=discord.TextChannel)
        self.bot_ch.id = 555
        self.bot_ch.name = "nuggetivitesbot"
        self.bot_ch.permissions_for.return_value = SimpleNamespace(send_messages=True)

        self.main_ch = MagicMock(spec=discord.TextChannel)
        self.main_ch.id = 777
        self.main_ch.name = "yappinmain"
        self.main_ch.permissions_for.return_value = SimpleNamespace(send_messages=True)

        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = 1
        self.guild.me = MagicMock()
        self.guild.get_channel.side_effect = lambda cid: {
            555: self.bot_ch,
            777: self.main_ch,
        }.get(cid)
        self.guild.text_channels = [self.bot_ch, self.main_ch]
        self.guild.system_channel = None

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_prefers_yappinmain_when_main_synced_to_bot_room(self) -> None:
        await self.db.set_designated_channel_id(1, 555)
        await self.db.set_main_channel_id(1, 555)
        await self.db.set_config_value(1, "bot_room_only", 1.0)

        lore = await bot_room.resolve_lore_channel(self.guild, self.db, self.bot_ch)
        self.assertIs(lore, self.main_ch)

    async def test_uses_stored_main_when_distinct_from_bot_room(self) -> None:
        await self.db.set_designated_channel_id(1, 555)
        await self.db.set_main_channel_id(1, 777)
        await self.db.set_config_value(1, "bot_room_only", 1.0)

        lore = await bot_room.resolve_lore_channel(self.guild, self.db)
        self.assertIs(lore, self.main_ch)

    async def test_falls_back_to_bot_room_without_yappinmain(self) -> None:
        await self.db.set_designated_channel_id(1, 555)
        await self.db.set_main_channel_id(1, 555)
        await self.db.set_config_value(1, "bot_room_only", 1.0)
        self.guild.text_channels = [self.bot_ch]
        self.guild.get_channel.side_effect = lambda cid: {555: self.bot_ch}.get(cid)

        lore = await bot_room.resolve_lore_channel(self.guild, self.db)
        self.assertIs(lore, self.bot_ch)


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


class BotRoomPublicSendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.bot_ch = MagicMock(spec=discord.TextChannel)
        self.bot_ch.id = 555
        self.bot_ch.name = "nuggetivitesbot"
        self.bot_ch.permissions_for.return_value = SimpleNamespace(send_messages=True)

        self.other_ch = MagicMock(spec=discord.TextChannel)
        self.other_ch.id = 111
        self.other_ch.name = "general"
        self.other_ch.permissions_for.return_value = SimpleNamespace(send_messages=True)

        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = 42
        self.guild.me = MagicMock()
        self.guild.get_channel.side_effect = lambda cid: {
            555: self.bot_ch,
            111: self.other_ch,
        }.get(cid)
        self.guild.text_channels = [self.bot_ch, self.other_ch]

        self.db = MagicMock()
        self.db.get_config_value = AsyncMock(return_value=1.0)
        self.db.get_designated_channel_id = AsyncMock(return_value=555)
        self.db.get_main_channel_id = AsyncMock(return_value=555)

    async def test_resolve_public_channel_redirects_when_locked(self) -> None:
        resolved = await bot_room.resolve_public_channel(
            self.guild,
            self.db,
            self.other_ch,
        )
        self.assertIs(resolved, self.bot_ch)

    async def test_send_bot_room_message_redirects_when_locked(self) -> None:
        bot = MagicMock()
        bot.outbound_gate = None
        sent = MagicMock(spec=discord.Message)
        with patch(
            "utils.discord_api.safe_channel_send",
            new_callable=AsyncMock,
            return_value=sent,
        ) as mock_send:
            result = await bot_room.send_bot_room_message(
                bot,
                self.guild,
                self.db,
                self.other_ch,
                content="hello",
            )
        self.assertIs(result, sent)
        mock_send.assert_awaited_once()
        self.assertIs(mock_send.await_args.args[0], self.bot_ch)

    async def test_message_allowed_for_gameplay_blocks_outside_bot_room(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.guild = self.guild
        message.channel = self.other_ch
        allowed = await bot_room.message_allowed_for_gameplay(message, self.db)
        self.assertFalse(allowed)

    async def test_message_allowed_for_gameplay_allows_bot_room(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.guild = self.guild
        message.channel = self.bot_ch
        allowed = await bot_room.message_allowed_for_gameplay(message, self.db)
        self.assertTrue(allowed)

    async def test_message_allowed_for_trivia_allows_yappinmain(self) -> None:
        self.db.get_main_channel_id = AsyncMock(return_value=555)
        self.other_ch.name = "yappinmain"
        self.guild.text_channels = [self.bot_ch, self.other_ch]
        message = MagicMock(spec=discord.Message)
        message.guild = self.guild
        message.channel = self.other_ch
        allowed = await bot_room.message_allowed_for_trivia(message, self.db)
        self.assertTrue(allowed)

    async def test_message_allowed_for_trivia_blocks_unrelated_channel(self) -> None:
        self.other_ch.name = "general"
        message = MagicMock(spec=discord.Message)
        message.guild = self.guild
        message.channel = self.other_ch
        allowed = await bot_room.message_allowed_for_trivia(message, self.db)
        self.assertFalse(allowed)

    async def test_send_channel_message_does_not_redirect(self) -> None:
        bot = MagicMock()
        bot.outbound_gate = None
        sent = MagicMock(spec=discord.Message)
        with patch(
            "utils.discord_api.safe_channel_send",
            new_callable=AsyncMock,
            return_value=sent,
        ) as mock_send:
            result = await bot_room.send_channel_message(
                bot,
                self.other_ch,
                content="lore",
            )
        self.assertIs(result, sent)
        mock_send.assert_awaited_once()
        self.assertIs(mock_send.await_args.args[0], self.other_ch)

    async def test_drops_send_when_bot_room_unset_and_locked(self) -> None:
        self.db.get_designated_channel_id = AsyncMock(return_value=None)
        self.db.get_main_channel_id = AsyncMock(return_value=None)
        self.guild.get_channel = MagicMock(return_value=None)
        self.guild.text_channels = [self.other_ch]
        self.other_ch.name = "general"

        with patch.object(config, "BOT_CHANNEL_ID", None):
            resolved = await bot_room.resolve_public_channel(
                self.guild,
                self.db,
                self.other_ch,
            )
            self.assertIsNone(resolved)

            bot = MagicMock()
            bot.outbound_gate = None
            with patch(
                "utils.discord_api.safe_channel_send",
                new_callable=AsyncMock,
            ) as mock_send:
                result = await bot_room.send_bot_room_message(
                    bot,
                    self.guild,
                    self.db,
                    self.other_ch,
                    content="should not send",
                )
            self.assertIsNone(result)
            mock_send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
