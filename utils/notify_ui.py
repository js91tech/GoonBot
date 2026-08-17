"""Opt-in DM notification preferences."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

import config
from utils.notify_prefs import NOTIFY_CATEGORY_MASK, panel_notify_flags

if TYPE_CHECKING:
    from discord.ext import commands

NOTIFY_OPTIONS: tuple[tuple[str, int, str], ...] = (
    ("crops", config.NOTIFY_CROPS, "Lab crops ready to harvest"),
    ("boss", config.NOTIFY_BOSS, "Boss raid spawned"),
    ("business", config.NOTIFY_BUSINESS, "Business vault nearly full"),
    ("defense", config.NOTIFY_DEFENSE, "Business under attack — defend window"),
)


def build_notify_embed(flags: int, *, configured: bool, eligible: bool) -> discord.Embed:
    if not config.DM_NOTIFICATIONS_ENABLED:
        intro = (
            "**GoonBot does not send DMs.** Reminder categories below are saved "
            "but will not message you until an admin re-enables `DM_NOTIFICATIONS_ENABLED`."
        )
    elif configured:
        intro = "Your saved reminder preferences. Uncheck everything to opt out of all DMs."
    elif eligible:
        intro = (
            "Reminders stay **off** unless you opt in below. "
            "Toggle categories to enable DMs."
        )
    else:
        intro = (
            "Reminders are **off** until you opt in. Select categories below to enable DMs."
        )
    embed = discord.Embed(
        title="🔔 Notification preferences",
        description=intro,
        color=discord.Color.blurple(),
    )
    for _key, flag, label in NOTIFY_OPTIONS:
        on = "✅ On" if flags & flag else "❌ Off"
        embed.add_field(name=label, value=on, inline=False)
    embed.set_footer(text="Changes save instantly · Every DM includes how to opt out")
    return embed


class NotifyToggleSelect(discord.ui.Select):
    def __init__(self, view: "NotifyView", flags: int) -> None:
        self._view = view
        options = [
            discord.SelectOption(
                label=label[:100],
                value=str(flag),
                description="On" if flags & flag else "Off",
                default=bool(flags & flag),
            )
            for _key, flag, label in NOTIFY_OPTIONS
        ]
        super().__init__(
            placeholder="Toggle categories…",
            min_values=0,
            max_values=len(options),
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = {int(v) for v in self.values}
        flags = config.NOTIFY_USER_CONFIGURED
        for _key, flag, _label in NOTIFY_OPTIONS:
            if flag in selected:
                flags |= flag
        await self._view.cog.bot.db.set_notify_flags(
            self._view.user_id, self._view.guild_id, flags,
        )
        display = flags & NOTIFY_CATEGORY_MASK
        new_view = NotifyView(
            self._view.cog,
            self._view.user_id,
            self._view.guild_id,
            display,
            configured=True,
            eligible=self._view.eligible,
        )
        await interaction.response.edit_message(
            embed=build_notify_embed(display, configured=True, eligible=self._view.eligible),
            view=new_view,
        )


class NotifyView(discord.ui.View):
    def __init__(
        self,
        cog: commands.Cog,
        user_id: int,
        guild_id: int,
        flags: int,
        *,
        configured: bool,
        eligible: bool,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.flags = flags
        self.configured = configured
        self.eligible = eligible
        self.add_item(NotifyToggleSelect(self, flags))


async def send_notify_panel(
    cog: commands.Cog, interaction: discord.Interaction,
) -> None:
    if interaction.guild_id is None:
        return
    flags, configured, eligible = await panel_notify_flags(
        cog.bot.db, interaction.user.id, interaction.guild_id,
    )
    view = NotifyView(
        cog, interaction.user.id, interaction.guild_id, flags,
        configured=configured, eligible=eligible,
    )
    await interaction.response.send_message(
        embed=build_notify_embed(flags, configured=configured, eligible=eligible),
        view=view,
        ephemeral=True,
    )
