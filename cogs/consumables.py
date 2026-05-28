from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from items import CONSUMABLE_USE_IDS, get_item
from utils.helpers import guild_only_message


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
        rows = await self.bot.db.get_inventory(interaction.user.id, interaction.guild_id)
        needle = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for row in rows:
            item_id = str(row["item_id"])
            if item_id not in CONSUMABLE_USE_IDS:
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

    @app_commands.command(name="use", description="Use a consumable from your inventory.")
    @app_commands.describe(item="Consumable to use")
    @app_commands.autocomplete(item=use_item_autocomplete)
    @app_commands.guild_only()
    async def use_item(self, interaction: discord.Interaction, item: str) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        item_id = item.strip()
        shop_item = get_item(item_id)
        if shop_item is None or item_id not in CONSUMABLE_USE_IDS:
            await interaction.response.send_message(
                "That item cannot be used with /use.", ephemeral=True,
            )
            return
        guild_id = interaction.guild_id
        uid = interaction.user.id
        qty = await self.bot.db.get_inventory_quantity(uid, guild_id, item_id)
        if qty <= 0:
            await interaction.response.send_message(
                "You do not have that item.", ephemeral=True,
            )
            return

        if item_id == "energy_drink":
            if not await self.bot.db.consume_inventory_item(uid, guild_id, item_id):
                await interaction.response.send_message(
                    "Could not consume item.", ephemeral=True,
                )
                return
            new_energy = await self.bot.db.add_energy(uid, guild_id, 15)
            await interaction.response.send_message(
                f"**Energy Drink** — energy restored to **{new_energy}**.",
                ephemeral=True,
            )
            return

        if not await self.bot.db.consume_inventory_item(uid, guild_id, item_id):
            await interaction.response.send_message(
                "Could not consume item.", ephemeral=True,
            )
            return
        await self.bot.db.set_pending_consumable(uid, guild_id, item_id)
        hint = {
            "raid_potion": "Next **/attack** deals +20% boss damage.",
            "duel_scroll": "Your next **/duel** deals +15% strike damage.",
        }.get(item_id, "Buff active.")
        await interaction.response.send_message(
            f"Used **{shop_item.name}**. {hint} (5 min window)",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Consumables(bot))
