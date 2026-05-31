from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from cogs.dungeon import Dungeon


@dataclass
class DungeonActionResult:
    embed: discord.Embed | None = None
    message: str | None = None
    finished: bool = False
    error: str | None = None


class DungeonView(discord.ui.View):
    """Interactive solo dungeon panel — start, fight, flee, refresh."""

    def __init__(self, cog: Dungeon, guild_id: int, user_id: int, *, has_run: bool) -> None:
        super().__init__(timeout=300.0)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self._configure_buttons(has_run)

    def _configure_buttons(self, has_run: bool) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "dungeon:start":
                child.disabled = has_run
            elif child.custom_id in {"dungeon:fight", "dungeon:flee"}:
                child.disabled = not has_run

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Open your own dungeon panel with `/dungeon`.", ephemeral=True,
            )
            return False
        return True

    async def _refresh_panel(
        self,
        interaction: discord.Interaction,
        *,
        defer: bool = False,
    ) -> None:
        if defer:
            await interaction.response.defer()
        embed, has_run = await self.cog.build_dungeon_embed(
            self.guild_id,
            self.user_id,
        )
        self._configure_buttons(has_run)
        if defer:
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="⚔️ Fight",
        style=discord.ButtonStyle.danger,
        custom_id="dungeon:fight",
        row=0,
    )
    async def fight_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await interaction.response.defer()
        result = await self.cog.execute_dungeon_fight(self.guild_id, self.user_id)
        if result.error:
            await interaction.followup.send(result.error, ephemeral=True)
            return
        if result.finished:
            for child in self.children:
                child.disabled = True
        if result.embed is not None:
            has_run = not result.finished
            self._configure_buttons(has_run)
            await interaction.edit_original_response(embed=result.embed, view=self)
        if result.message:
            await interaction.followup.send(result.message, ephemeral=True)

    @discord.ui.button(
        label="Enter dungeon",
        style=discord.ButtonStyle.success,
        custom_id="dungeon:start",
        row=0,
    )
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await interaction.response.defer()
        result = await self.cog.execute_dungeon_start(self.guild_id, self.user_id)
        if result.error:
            await interaction.followup.send(result.error, ephemeral=True)
            return
        if result.embed is not None:
            self._configure_buttons(has_run=True)
            await interaction.edit_original_response(embed=result.embed, view=self)
        if result.message:
            await interaction.followup.send(result.message, ephemeral=True)

    @discord.ui.button(
        label="Flee",
        style=discord.ButtonStyle.secondary,
        custom_id="dungeon:flee",
        row=0,
    )
    async def flee_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await interaction.response.defer()
        result = await self.cog.execute_dungeon_flee(self.guild_id, self.user_id)
        if result.error:
            await interaction.followup.send(result.error, ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        if result.embed is not None:
            await interaction.edit_original_response(embed=result.embed, view=self)
        if result.message:
            await interaction.followup.send(result.message, ephemeral=True)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._refresh_panel(interaction)


async def send_dungeon_panel(
    interaction: discord.Interaction,
    cog: Dungeon,
) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("Guild only.", ephemeral=True)
        return

    embed, has_run = await cog.build_dungeon_embed(
        interaction.guild_id,
        interaction.user.id,
    )
    view = DungeonView(cog, interaction.guild_id, interaction.user.id, has_run=has_run)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
