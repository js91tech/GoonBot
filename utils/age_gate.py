"""18+ age confirmation and NSFW channel gates for GoonBot."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord

from utils.goon_theme import brand_color, danger_color
from utils.onboarding import NightLoopView, onboarding_embed

if TYPE_CHECKING:
    from database import Database

AGE_GATE_TITLE = "GoonBot — 18+ confirmation"
AGE_GATE_BODY = (
    "**GoonBot is an explicit adult Discord economy RPG.**\n\n"
    "By continuing you confirm that you are **at least 18 years old** "
    "and consent to erotic / NSFW game content.\n\n"
    "Sexual content involving minors is never allowed. "
    "If you are under 18, press **I am under 18** and leave."
)
REFUSAL_UNDERAGE = (
    "Access denied. GoonBot is **18+ only**. "
    "If you are under 18, do not use this bot."
)
NSFW_CHANNEL_REQUIRED = (
    "This server requires GoonBot commands in a **Discord NSFW channel**. "
    "Ask an admin to mark a channel NSFW, or disable the NSFW-channel gate "
    "(`nsfw_channel_only` guild setting)."
)


class AgeGateView(discord.ui.View):
    def __init__(self, db: Database, guild_id: int, user_id: int) -> None:
        super().__init__(timeout=180)
        self.db = db
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This confirmation is only for you.", ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="I am 18+ — enter", style=discord.ButtonStyle.success, row=0)
    async def confirm_adult(
        self, interaction: discord.Interaction, _button: discord.ui.Button,
    ) -> None:
        await self.db.set_age_verified(self.user_id, self.guild_id, True)
        member_name = getattr(interaction.user, "display_name", None)
        embed = onboarding_embed(member_name=member_name)
        view = NightLoopView()
        self.stop()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="I am under 18", style=discord.ButtonStyle.danger, row=0)
    async def refuse_underage(
        self, interaction: discord.Interaction, _button: discord.ui.Button,
    ) -> None:
        await self.db.set_age_verified(self.user_id, self.guild_id, False)
        embed = discord.Embed(
            title="Access denied",
            description=REFUSAL_UNDERAGE,
            color=danger_color(),
        )
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)


def age_gate_embed() -> discord.Embed:
    return discord.Embed(
        title=AGE_GATE_TITLE,
        description=AGE_GATE_BODY,
        color=brand_color(),
    )


async def is_age_verified(db: Database, user_id: int, guild_id: int) -> bool:
    return await db.get_age_verified(user_id, guild_id)


async def nsfw_channel_required(db: Database, guild_id: int) -> bool:
    try:
        value = await db.get_config_value(guild_id, "nsfw_channel_only")
    except KeyError:
        return True
    return float(value) >= 1.0


def channel_is_nsfw(channel: Any) -> bool:
    return bool(getattr(channel, "nsfw", False) or getattr(channel, "is_nsfw", lambda: False)())


def _interaction_command_name(interaction: discord.Interaction) -> str:
    cmd = getattr(interaction, "command", None)
    if cmd is not None:
        qualified = getattr(cmd, "qualified_name", None)
        if qualified:
            return str(qualified)
        name = getattr(cmd, "name", None)
        if name:
            return str(name)
    data = getattr(interaction, "data", None) or {}
    if isinstance(data, dict):
        return str(data.get("name") or "")
    return str(getattr(data, "name", "") or "")


async def check_interaction(interaction: discord.Interaction, db: Database) -> bool:
    """Tree interaction_check: NSFW channel + bot room + age gate. Returns False to block."""
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "GoonBot only works inside a server.", ephemeral=True,
        )
        return False

    # Allow the age-gate button callbacks (component interactions on our view)
    # App commands still go through here.
    if interaction.type == discord.InteractionType.component:
        return True

    channel = interaction.channel
    if await nsfw_channel_required(db, interaction.guild_id):
        if channel is not None and not channel_is_nsfw(channel):
            # DMs / threads inherit; threads may not have nsfw — check parent
            parent = getattr(channel, "parent", None)
            if parent is not None and channel_is_nsfw(parent):
                pass
            elif getattr(interaction.user, "guild_permissions", None) and (
                interaction.user.guild_permissions.administrator
            ):
                # Admins may configure from any channel for setup convenience
                pass
            else:
                await interaction.response.send_message(
                    NSFW_CHANNEL_REQUIRED, ephemeral=True,
                )
                return False

    # Bot-room lock — players may only use commands in the designated bot room.
    # Exception: /trivia (Lore Roulette) is also allowed in the main channel (yappinmain).
    from utils.bot_room import (
        bot_room_only_enabled,
        bot_room_required_message,
        channel_is_allowed_bot_room,
        channel_is_allowed_lore,
        resolve_bot_room,
    )

    is_admin = bool(
        getattr(interaction.user, "guild_permissions", None)
        and interaction.user.guild_permissions.administrator
    )
    if (
        interaction.guild is not None
        and await bot_room_only_enabled(db, interaction.guild_id)
        and not is_admin
        and not await channel_is_allowed_bot_room(interaction.guild, db, channel)
    ):
        trivia_in_main = (
            _interaction_command_name(interaction) == "trivia"
            and await channel_is_allowed_lore(interaction.guild, db, channel)
        )
        if not trivia_in_main:
            bot_room = await resolve_bot_room(interaction.guild, db)
            await interaction.response.send_message(
                bot_room_required_message(bot_room),
                ephemeral=True,
            )
            return False

    if await is_age_verified(db, interaction.user.id, interaction.guild_id):
        return True

    view = AgeGateView(db, interaction.guild_id, interaction.user.id)
    await interaction.response.send_message(
        embed=age_gate_embed(), view=view, ephemeral=True,
    )
    return False
