from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from items import get_item
from utils.alchemy import RECIPE_MAP, RECIPES
from utils.helpers import fmt_amount, guild_only_message


class Alchemy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="alchemy", description="Craft consumables from alchemy scrap.")
    @app_commands.describe(
        action="List recipes or craft one",
        recipe="Recipe id from list",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="List recipes", value="list"),
            app_commands.Choice(name="Craft", value="craft"),
        ],
        recipe=[app_commands.Choice(name=r.name, value=r.recipe_id) for r in RECIPES],
    )
    @app_commands.guild_only()
    async def alchemy(
        self,
        interaction: discord.Interaction,
        action: str,
        recipe: str | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        guild_id = interaction.guild_id
        uid = interaction.user.id

        if action == "list":
            lines = []
            scrap_qty = await self.bot.db.get_inventory_quantity(
                uid, guild_id, "alchemy_scrap",
            )
            for r in RECIPES:
                lines.append(
                    f"**{r.name}** (`{r.recipe_id}`) — {r.scrap_cost} scrap + "
                    f"{fmt_amount(r.nugget_cost)} → `{r.output_item_id}`\n_{r.description}_"
                )
            await interaction.response.send_message(
                f"You have **{scrap_qty}** alchemy scrap.\n\n" + "\n\n".join(lines),
                ephemeral=True,
            )
            return

        if action == "craft":
            if not recipe or recipe not in RECIPE_MAP:
                await interaction.response.send_message(
                    "Pick a recipe.", ephemeral=True,
                )
                return
            r = RECIPE_MAP[recipe]
            scrap_have = await self.bot.db.get_inventory_quantity(
                uid, guild_id, "alchemy_scrap",
            )
            if scrap_have < r.scrap_cost:
                await interaction.response.send_message(
                    f"Need **{r.scrap_cost}** alchemy scrap (you have {scrap_have}).",
                    ephemeral=True,
                )
                return
            if not await self.bot.db.debit_wallet(uid, guild_id, r.nugget_cost):
                await interaction.response.send_message(
                    f"Need **{fmt_amount(r.nugget_cost)}**.", ephemeral=True,
                )
                return
            for _ in range(r.scrap_cost):
                if not await self.bot.db.consume_inventory_item(
                    uid, guild_id, "alchemy_scrap",
                ):
                    await self.bot.db.credit_wallet(uid, guild_id, r.nugget_cost)
                    await interaction.response.send_message(
                        "Craft failed — scrap refunded.", ephemeral=True,
                    )
                    return
            await self.bot.db.grant_item(uid, guild_id, r.output_item_id)
            out = get_item(r.output_item_id)
            await interaction.response.send_message(
                f"Crafted **{out.name if out else r.output_item_id}**!",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Unknown action.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Alchemy(bot))
