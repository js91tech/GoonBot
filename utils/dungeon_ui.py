from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

import config
from utils.dungeon_tiers import NORMAL_TIER, VAULT_TIER
from utils.helpers import fmt_amount

if TYPE_CHECKING:
    from cogs.dungeon import Dungeon


@dataclass
class DungeonActionResult:
    embed: discord.Embed | None = None
    message: str | None = None
    finished: bool = False
    error: str | None = None


class DungeonView(discord.ui.View):
    """Interactive solo dungeon panel — tier select, fight, flee, unlock."""

    def __init__(
        self,
        cog: Dungeon,
        guild_id: int,
        user_id: int,
        *,
        has_run: bool,
        vault_unlocked: bool,
    ) -> None:
        super().__init__(timeout=300.0)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.vault_unlocked = vault_unlocked
        self._configure_buttons(has_run)

    def _configure_buttons(self, has_run: bool) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            cid = child.custom_id or ""
            if cid == "dungeon:start:normal":
                child.disabled = has_run
            elif cid == "dungeon:party:vault":
                child.disabled = has_run or not self.vault_unlocked
            elif cid == "dungeon:unlock:vault":
                child.disabled = has_run or self.vault_unlocked
            elif cid in {"dungeon:fight", "dungeon:flee"}:
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
        embed, has_run, vault_unlocked = await self.cog.build_dungeon_embed(
            self.guild_id,
            self.user_id,
        )
        self.vault_unlocked = vault_unlocked
        self._configure_buttons(has_run)
        if defer:
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def _apply_result(
        self,
        interaction: discord.Interaction,
        result: DungeonActionResult,
    ) -> None:
        if result.error:
            await interaction.followup.send(result.error, ephemeral=True)
            return
        if result.embed is not None:
            _, has_run, vault_unlocked = await self.cog.build_dungeon_embed(
                self.guild_id,
                self.user_id,
            )
            self.vault_unlocked = vault_unlocked
            self._configure_buttons(has_run)
            await interaction.edit_original_response(embed=result.embed, view=self)
        if result.message:
            await interaction.followup.send(result.message, ephemeral=True)

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
        await self._apply_result(interaction, result)

    @discord.ui.button(
        label="🕳️ Delver's Depths",
        style=discord.ButtonStyle.success,
        custom_id="dungeon:start:normal",
        row=1,
    )
    async def start_normal_button(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        del button
        await interaction.response.defer()
        result = await self.cog.execute_dungeon_start(
            self.guild_id, self.user_id, tier_id=NORMAL_TIER.tier_id,
        )
        await self._apply_result(interaction, result)

    @discord.ui.button(
        label="🏛️ Vault party",
        style=discord.ButtonStyle.primary,
        custom_id="dungeon:party:vault",
        row=1,
    )
    async def vault_party_button(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        del button
        await interaction.response.defer()
        result = await self.cog.execute_party_create(
            self.guild_id, self.user_id, tier_id=VAULT_TIER.tier_id,
        )
        if result.error:
            await interaction.followup.send(result.error, ephemeral=True)
            return
        if result.message:
            await interaction.followup.send(result.message, ephemeral=True)

    @discord.ui.button(
        label="Unlock Vault",
        style=discord.ButtonStyle.secondary,
        custom_id="dungeon:unlock:vault",
        row=2,
    )
    async def unlock_vault_button(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        del button
        button.label = f"Unlock Vault ({fmt_amount(config.DUNGEON_VAULT_UNLOCK_COST)})"
        await interaction.response.defer()
        result = await self.cog.execute_dungeon_unlock_vault(self.guild_id, self.user_id)
        if result.error:
            await interaction.followup.send(result.error, ephemeral=True)
            return
        if result.embed is not None:
            self.vault_unlocked = True
            self._configure_buttons(has_run=False)
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
        await self._apply_result(interaction, result)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=2)
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

    embed, has_run, vault_unlocked = await cog.build_dungeon_embed(
        interaction.guild_id,
        interaction.user.id,
    )
    view = DungeonView(
        cog,
        interaction.guild_id,
        interaction.user.id,
        has_run=has_run,
        vault_unlocked=vault_unlocked,
    )
    for child in view.children:
        if isinstance(child, discord.ui.Button) and child.custom_id == "dungeon:unlock:vault":
            child.label = f"Unlock Vault ({fmt_amount(config.DUNGEON_VAULT_UNLOCK_COST)})"
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
