from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from items import GIFTABLE_ITEM_IDS, get_item
from utils.bot_players import pvp_target_error
from utils.drug_ui import player_max_hp
from utils.drugs import drug_by_id, format_consume_message
from utils.helpers import guild_only_message
from utils.quests import record_quest_event


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
        from items import CONSUMABLE_USE_IDS

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
        if len(choices) < 25:
            drug_inv = await self.bot.db.get_drug_inventory(
                interaction.user.id, interaction.guild_id,
            )
            for drug_id, qty in drug_inv.items():
                if qty <= 0:
                    continue
                defn = drug_by_id(drug_id)
                if defn is None:
                    continue
                label = f"{defn.emoji} {defn.name} x{qty}"
                if needle and needle not in drug_id and needle not in defn.name.lower():
                    continue
                choices.append(
                    app_commands.Choice(name=label[:100], value=drug_id),
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
        description="Use a consumable from your inventory or harvested product from your stash.",
    )
    @app_commands.describe(item="Consumable or drug product to use")
    @app_commands.autocomplete(item=use_item_autocomplete)
    @app_commands.guild_only()
    async def use_item(self, interaction: discord.Interaction, item: str) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        guild_id = interaction.guild_id
        uid = interaction.user.id
        item_id = item.strip().lower()

        drug = drug_by_id(item_id)
        if drug is not None:
            stash_qty = (await self.bot.db.get_drug_inventory(uid, guild_id)).get(drug.drug_id, 0)
            if stash_qty <= 0:
                await interaction.response.send_message(
                    "You don't have that product in your stash.", ephemeral=True,
                )
                return
            max_hp = await player_max_hp(self, uid, guild_id)
            result = await self.bot.db.consume_drug(uid, guild_id, drug.drug_id, max_hp=max_hp)
            if result.get("error"):
                messages = {
                    "invalid_drug": "Unknown product.",
                    "insufficient_product": "You don't have any of that left.",
                }
                await interaction.response.send_message(
                    messages.get(str(result["error"]), "Could not use that product."),
                    ephemeral=True,
                )
                return
            await record_quest_event(self.bot.db, guild_id, uid, "drug_use")
            await interaction.response.send_message(
                format_consume_message(result), ephemeral=True,
            )
            return

        from items import CONSUMABLE_USE_IDS

        shop_item = get_item(item_id)
        if shop_item is None or item_id not in CONSUMABLE_USE_IDS:
            await interaction.response.send_message(
                "That item cannot be used with /use.", ephemeral=True,
            )
            return
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

        if item_id in {"jail_key", "pick_key"}:
            if not await self.bot.db.is_arrested(uid, guild_id):
                await interaction.response.send_message(
                    "You are not in jail — save this for when you get arrested.",
                    ephemeral=True,
                )
                return
            if not await self.bot.db.consume_inventory_item(uid, guild_id, item_id):
                await interaction.response.send_message(
                    "Could not consume item.", ephemeral=True,
                )
                return
            if item_id == "jail_key":
                await self.bot.db.clear_arrested(uid, guild_id)
                await interaction.response.send_message(
                    f"**{shop_item.name}** — the cell door swings open. You are free!",
                    ephemeral=True,
                )
                return
            if random.random() < config.PICK_KEY_ESCAPE_CHANCE:
                await self.bot.db.clear_arrested(uid, guild_id)
                await interaction.response.send_message(
                    f"**{shop_item.name}** — the lock clicks. You slip out into the night!",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"**{shop_item.name}** — the pick snaps. Guards drag you back to your cell.",
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
