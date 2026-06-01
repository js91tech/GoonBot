from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.avatars import (
    AVATAR_MAP,
    AVATARS,
    attachment_image_ext,
    build_portrait_attachment,
    build_victory_attachment,
    custom_avatar_dir,
    custom_avatar_id,
    get_avatar,
    is_custom_avatar_id,
    is_unique_default_avatar_id,
    is_valid_image_attachment,
    load_avatar_attachment_bytes,
)
from utils.helpers import fmt_amount, guild_only_message, send_error

logger = logging.getLogger(__name__)


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
        try:
            unlocked = await self.bot.db.list_unlocked_avatar_ids(
                interaction.user.id,
                interaction.guild_id,
            )
        except Exception:
            logger.exception("avatar autocomplete failed")
            return []
        needle = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for aid in unlocked:
            if is_custom_avatar_id(aid):
                label = "Custom Avatar"
            else:
                defn = AVATAR_MAP.get(aid)
                if defn is None:
                    continue
                label = defn.name
            if needle and needle not in aid and needle not in label.lower():
                continue
            choices.append(app_commands.Choice(name=label, value=aid))
            if len(choices) >= 25:
                break
        return choices

    async def _save_custom_upload(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
    ) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:
            return
        user_id = interaction.user.id

        max_label = config.custom_avatar_max_size_label()
        if not is_valid_image_attachment(image):
            await interaction.followup.send(
                f"Attach a **PNG, GIF, or WebP** image (max {max_label}).",
                ephemeral=True,
            )
            return
        if image.size and image.size > config.CUSTOM_AVATAR_MAX_BYTES:
            await interaction.followup.send(
                f"Image too large (max {max_label}).", ephemeral=True,
            )
            return

        cost = config.CUSTOM_AVATAR_UPLOAD_COST
        if cost > 0 and not await self.bot.db.debit_wallet(user_id, guild_id, cost):
            await interaction.followup.send(
                f"Upload costs **{fmt_amount(cost)}**.", ephemeral=True,
            )
            return

        data = await image.read()
        if len(data) > config.CUSTOM_AVATAR_MAX_BYTES:
            await interaction.followup.send(
                f"Image too large (max {max_label}).", ephemeral=True,
            )
            return

        ext = attachment_image_ext(image) or ".png"
        await self.bot.db.save_custom_avatar_assets(guild_id, user_id, data, ext)

        folder = custom_avatar_dir(guild_id, user_id)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"victory{ext}").write_bytes(data)
            (folder / f"portrait{ext}").write_bytes(data)
        except OSError:
            pass

        aid = custom_avatar_id(user_id)
        await self.bot.db.unlock_custom_avatar(user_id, guild_id, aid)
        await self.bot.db.set_equipped_avatar(user_id, guild_id, aid)

        files, thumb_name = build_victory_attachment(
            aid, custom_victory=(data, ext),
        )
        embed = discord.Embed(
            title="Custom avatar saved",
            description=(
                f"Equipped as `{aid}`. Victory art shows on duel wins "
                "and boss killing blows."
            ),
            color=discord.Color.green(),
        )
        if thumb_name:
            embed.set_image(url=f"attachment://{thumb_name}")
        await interaction.followup.send(
            embed=embed,
            files=files or None,
            ephemeral=True,
        )

    @app_commands.command(
        name="avatar-upload",
        description="Upload PNG/GIF/WebP for your custom victory pose (saved permanently).",
    )
    @app_commands.describe(image="Your victory pose image")
    @app_commands.guild_only()
    async def avatar_upload(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            await self._save_custom_upload(interaction, image)
        except Exception:
            logger.exception("avatar-upload failed")
            await send_error(
                interaction,
                "Could not save your avatar. Try again in a moment.",
            )

    @app_commands.command(
        name="avatar",
        description="Choose your raid avatar and victory pose art.",
    )
    @app_commands.describe(
        action="What to do",
        avatar="Avatar to equip or buy (autocomplete)",
        image="Image file (required for Upload custom art)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="List avatars", value="list"),
            app_commands.Choice(name="Equip", value="equip"),
            app_commands.Choice(name="Buy unlock", value="buy"),
            app_commands.Choice(name="Preview victory pose", value="preview"),
            app_commands.Choice(name="Upload custom art", value="upload"),
        ],
    )
    @app_commands.autocomplete(avatar=avatar_autocomplete)
    @app_commands.guild_only()
    async def avatar(
        self,
        interaction: discord.Interaction,
        action: str,
        avatar: str | None = None,
        image: discord.Attachment | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        guild_id = interaction.guild_id
        user_id = interaction.user.id

        if action == "upload":
            if image is None:
                await interaction.response.send_message(
                    "Attach an image to this command, or use **`/avatar-upload`** "
                    "with a required image attachment.",
                    ephemeral=True,
                )
                return
            try:
                await interaction.response.defer(ephemeral=True)
                await self._save_custom_upload(interaction, image)
            except Exception:
                logger.exception("avatar upload action failed")
                await send_error(
                    interaction,
                    "Could not save your avatar. Try again in a moment.",
                )
            return

        try:
            await interaction.response.defer(ephemeral=True)

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
                custom_id = custom_avatar_id(user_id)
                if custom_id in unlocked:
                    eq = " **(equipped)**" if custom_id == equipped else ""
                    lines.append(
                        f"✅ 🎨 **Custom Avatar** (`{custom_id}`){eq}\n"
                        f"_Your uploaded victory pose._"
                    )
                embed = discord.Embed(
                    title="Raid avatars",
                    description="\n\n".join(lines),
                    color=discord.Color.gold(),
                )
                embed.set_footer(
                    text="Use /avatar-upload for custom art · /avatar for equip/buy/preview"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if action == "preview":
                if not avatar:
                    await interaction.followup.send(
                        "Pick an avatar you own from autocomplete.",
                        ephemeral=True,
                    )
                    return
                if avatar not in unlocked:
                    await interaction.followup.send(
                        "You have not unlocked that avatar yet. Use **Buy unlock** or earn free ones.",
                        ephemeral=True,
                    )
                    return
                defn = get_avatar(avatar)
                _, custom_victory = await load_avatar_attachment_bytes(
                    self.bot.db, avatar, guild_id=guild_id, user_id=user_id,
                )
                files, filename = build_victory_attachment(
                    avatar,
                    guild_id=guild_id,
                    user_id=user_id,
                    custom_victory=custom_victory,
                )
                embed = discord.Embed(
                    title=f"{defn.name if defn else avatar} — victory pose",
                    description="This art appears when you win duels or land the boss killing blow.",
                    color=discord.Color.green(),
                )
                if filename:
                    embed.set_image(url=f"attachment://{filename}")
                await interaction.followup.send(
                    embed=embed,
                    files=files or None,
                    ephemeral=True,
                )
                return

            if action == "buy":
                if not avatar or avatar not in AVATAR_MAP:
                    await interaction.followup.send(
                        "Pick an avatar from autocomplete.",
                        ephemeral=True,
                    )
                    return
                defn = AVATAR_MAP[avatar]
                if defn.price <= 0:
                    await self.bot.db.unlock_avatar(user_id, guild_id, avatar)
                    await interaction.followup.send(
                        f"**{defn.name}** is free — unlocked!",
                        ephemeral=True,
                    )
                    return
                err = await self.bot.db.buy_avatar_unlock(
                    user_id, guild_id, avatar, defn.price
                )
                if err == "already_owned":
                    await interaction.followup.send(
                        f"You already own **{defn.name}**.",
                        ephemeral=True,
                    )
                    return
                if err == "insufficient_funds":
                    await interaction.followup.send(
                        f"**{defn.name}** costs {fmt_amount(defn.price)}.",
                        ephemeral=True,
                    )
                    return
                await interaction.followup.send(
                    f"Unlocked **{defn.name}**! Use `/avatar` → Equip to wear it.",
                    ephemeral=True,
                )
                return

            if action == "equip":
                if not avatar:
                    await interaction.followup.send(
                        "Pick an unlocked avatar from autocomplete.",
                        ephemeral=True,
                    )
                    return
                err = await self.bot.db.set_equipped_avatar(user_id, guild_id, avatar)
                if err == "locked":
                    defn = get_avatar(avatar)
                    price = (
                        fmt_amount(defn.price)
                        if defn is not None and defn.price > 0
                        else "free"
                    )
                    await interaction.followup.send(
                        f"**{defn.name}** is locked. Buy unlock for {price} first.",
                        ephemeral=True,
                    )
                    return
                defn = get_avatar(avatar)
                custom_portrait, _ = await load_avatar_attachment_bytes(
                    self.bot.db, avatar, guild_id=guild_id, user_id=user_id,
                )
                files, thumb_name = build_portrait_attachment(
                    avatar,
                    guild_id=guild_id,
                    user_id=user_id,
                    custom_portrait=custom_portrait,
                )
                label = f"{defn.emoji} {defn.name}" if defn else avatar
                embed = discord.Embed(
                    title="Avatar equipped",
                    description=f"You are now **{label}**.",
                    color=discord.Color.blue(),
                )
                if thumb_name:
                    embed.set_thumbnail(url=f"attachment://{thumb_name}")
                await interaction.followup.send(
                    embed=embed,
                    files=files or None,
                    ephemeral=True,
                )
                return

            await interaction.followup.send("Unknown action.", ephemeral=True)
        except Exception:
            logger.exception("avatar command failed action=%s", action)
            await send_error(
                interaction,
                "Something went wrong with avatars. Try again in a moment.",
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Avatars(bot))
