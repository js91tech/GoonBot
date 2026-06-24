from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from items import GIFTABLE_ITEM_IDS, get_item
from utils.bot_players import pvp_target_error
from utils.consumables_ui import (
    build_use_embed,
    execute_use,
    list_useable_entries,
    send_use_panel,
    use_error_message,
    UsePanelView,
)
from utils.helpers import fmt_amount, guild_only_message


class Consumables(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def use_item_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        entries = await list_useable_entries(
            self, interaction.user.id, interaction.guild_id,
        )
        needle = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for entry_id, label, qty in entries:
            if needle and needle not in entry_id and needle not in label.lower():
                continue
            choices.append(
                app_commands.Choice(name=f"{label} x{qty}"[:100], value=entry_id),
            )
            if len(choices) >= 25:
                break
        return choices

    async def gift_item_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        rows = await self.bot.db.get_inventory(interaction.user.id, interaction.guild_id)
        needle = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for row in rows:
            item_id = str(row["item_id"])
            if item_id not in GIFTABLE_ITEM_IDS:
                continue
            item = get_item(item_id)
            if item is None:
                continue
            if needle and needle not in item_id and needle not in item.name.lower():
                continue
            choices.append(
                app_commands.Choice(
                    name=f"{item.name} x{int(row['quantity'])}",
                    value=item_id,
                ),
            )
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(
        name="use",
        description="Open the consumables panel — use shop items or harvested drugs.",
    )
    @app_commands.describe(item="Optional: use directly without opening the panel")
    @app_commands.autocomplete(item=use_item_autocomplete)
    @app_commands.guild_only()
    async def use_item(self, interaction: discord.Interaction, item: str | None = None) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        if item is None:
            await send_use_panel(interaction, self)
            return

        await interaction.response.defer(ephemeral=True)
        err, message = await execute_use(
            self, interaction.user.id, interaction.guild_id, item.strip().lower(),
        )
        if err:
            await interaction.followup.send(use_error_message(err), ephemeral=True)
            return
        view = await UsePanelView.build(self, interaction.guild_id, interaction.user.id)
        embed = await build_use_embed(self, interaction.user.id, interaction.guild_id)
        embed.description = message
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="gift",
        description="Gift chia seeds (or other giftable items) from your inventory.",
    )
    @app_commands.describe(
        user="Player to receive the gift",
        item="Item to gift (buy Chia Seeds from /shop first)",
        quantity="How many to send (1–99)",
    )
    @app_commands.autocomplete(item=gift_item_autocomplete)
    @app_commands.guild_only()
    async def gift(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        item: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        gift_err = pvp_target_error(user, interaction.user.id)
        if gift_err:
            await interaction.response.send_message(gift_err, ephemeral=True)
            return
        item_id = item.strip()
        shop_item = get_item(item_id)
        if shop_item is None or item_id not in GIFTABLE_ITEM_IDS:
            await interaction.response.send_message(
                "That item cannot be gifted. Buy **Chia Seeds** from `/shop` consumables.",
                ephemeral=True,
            )
            return
        guild_id = interaction.guild_id
        sender_id = interaction.user.id
        qty = int(quantity)
        err = await self.bot.db.gift_inventory_item(
            sender_id, user.id, guild_id, item_id, qty,
        )
        if err == "insufficient_items":
            await interaction.response.send_message(
                f"You need **{qty}×** **{shop_item.name}** in your inventory "
                f"(buy with `/buy chia_seeds`).",
                ephemeral=True,
            )
            return
        if err == "self_gift":
            await interaction.response.send_message(
                "Gift them to someone else!", ephemeral=True,
            )
            return
        if err:
            await interaction.response.send_message(
                "Could not complete the gift.", ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"{interaction.user.mention} gifted **{qty}×** **{shop_item.name}** "
            f"to {user.mention}! 🌱",
            allowed_mentions=discord.AllowedMentions(users=True),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Consumables(bot))
