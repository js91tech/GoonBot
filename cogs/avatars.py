from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.avatars import (
    AVATARS,
    AVATAR_MAP,
    build_portrait_attachment,
    build_victory_attachment,
    get_avatar,
)
from utils.helpers import fmt_amount, guild_only_message


class Avatars(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def avatar_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        unlocked = await self.bot.db.list_unlocked_avatar_ids(
            interaction.user.id,
            interaction.guild_id,
        )
        needle = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for avatar in AVATARS:
            if avatar.id not in unlocked:
                continue
            if needle and needle not in avatar.id and needle not in avatar.name.lower():
                continue
            choices.append(app_commands.Choice(name=avatar.name, value=avatar.id))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(
        name="avatar",
        description="Choose your raid avatar and victory pose art.",
    )
    @app_commands.describe(
        action="What to do",
        avatar="Avatar to equip or buy (autocomplete)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="List avatars", value="list"),
            app_commands.Choice(name="Equip", value="equip"),
            app_commands.Choice(name="Buy unlock", value="buy"),
            app_commands.Choice(name="Preview victory pose", value="preview"),
        ],
    )
    @app_commands.autocomplete(avatar=avatar_autocomplete)
    @app_commands.guild_only()
    async def avatar(
        self,
        interaction: discord.Interaction,
        action: str,
        avatar: str | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        guild_id = interaction.guild_id
        user_id = interaction.user.id
        unlocked = await self.bot.db.list_unlocked_avatar_ids(user_id, guild_id)
        equipped = await self.bot.db.get_equipped_avatar_id(user_id, guild_id)

        if action == "list":
            lines = []
            for defn in AVATARS:
                owned = defn.id in unlocked
                mark = "✅" if owned else "🔒"
                eq = " **(equipped)**" if defn.id == equipped else ""
                price = "Free" if defn.price <= 0 else fmt_amount(defn.price)
                lines.append(
                    f"{mark} {defn.emoji} **{defn.name}** (`{defn.id}`) — {price}{eq}\n"
                    f"_{defn.description}_"
                )
            embed = discord.Embed(
                title="Raid avatars",
                description="\n\n".join(lines),
                color=discord.Color.gold(),
            )
            embed.set_footer(
                text="Use /avatar action:Equip · Buy unlock · Preview victory pose"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if action == "preview":
            if not avatar:
                await interaction.response.send_message(
                    "Pick an avatar you own from autocomplete.",
                    ephemeral=True,
                )
                return
            if avatar not in unlocked:
                await interaction.response.send_message(
                    "You have not unlocked that avatar yet. Use **Buy unlock** or earn free ones.",
                    ephemeral=True,
                )
                return
            defn = get_avatar(avatar)
            files, filename = build_victory_attachment(avatar)
            embed = discord.Embed(
                title=f"{defn.name if defn else avatar} — victory pose",
                description="This art appears when you win duels or land the boss killing blow.",
                color=discord.Color.green(),
            )
            if filename:
                embed.set_image(url=f"attachment://{filename}")
            await interaction.response.send_message(
                embed=embed,
                files=files or None,
                ephemeral=True,
            )
            return

        if action == "buy":
            if not avatar or avatar not in AVATAR_MAP:
                await interaction.response.send_message(
                    "Pick an avatar from autocomplete.",
                    ephemeral=True,
                )
                return
            defn = AVATAR_MAP[avatar]
            if defn.price <= 0:
                await self.bot.db.unlock_avatar(user_id, guild_id, avatar)
                await interaction.response.send_message(
                    f"**{defn.name}** is free — unlocked!",
                    ephemeral=True,
                )
                return
            err = await self.bot.db.buy_avatar_unlock(
                user_id, guild_id, avatar, defn.price
            )
            if err == "already_owned":
                await interaction.response.send_message(
                    f"You already own **{defn.name}**.",
                    ephemeral=True,
                )
                return
            if err == "insufficient_funds":
                await interaction.response.send_message(
                    f"**{defn.name}** costs {fmt_amount(defn.price)}.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"Unlocked **{defn.name}**! Use `/avatar` → Equip to wear it.",
                ephemeral=True,
            )
            return

        if action == "equip":
            if not avatar or avatar not in AVATAR_MAP:
                await interaction.response.send_message(
                    "Pick an unlocked avatar from autocomplete.",
                    ephemeral=True,
                )
                return
            err = await self.bot.db.set_equipped_avatar(user_id, guild_id, avatar)
            if err == "locked":
                defn = AVATAR_MAP[avatar]
                price = fmt_amount(defn.price) if defn.price > 0 else "free"
                await interaction.response.send_message(
                    f"**{defn.name}** is locked. Buy unlock for {price} first.",
                    ephemeral=True,
                )
                return
            defn = AVATAR_MAP[avatar]
            files, thumb_name = build_portrait_attachment(avatar)
            embed = discord.Embed(
                title="Avatar equipped",
                description=f"You are now **{defn.emoji} {defn.name}**.",
                color=discord.Color.blue(),
            )
            if thumb_name:
                embed.set_thumbnail(url=f"attachment://{thumb_name}")
            await interaction.response.send_message(
                embed=embed,
                files=files or None,
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Unknown action.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Avatars(bot))
