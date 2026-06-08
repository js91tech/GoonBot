from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.character_attributes import (
    STAT_EMOJI,
    STAT_KEYS,
    STAT_LABELS,
    AttributeName,
    CharacterAttributes,
    format_attributes_block,
    stat_cap_for_prestige,
    total_point_pool_cap,
    unspent_attribute_points,
)

if TYPE_CHECKING:
    from cogs.attributes import Attributes


async def build_attributes_embed(
    cog: Attributes,
    member: discord.Member,
    guild_id: int,
) -> discord.Embed:
    row = await cog.bot.db.get_user_character(member.id, guild_id)
    progress = await cog.bot.db.get_user_progress(member.id, guild_id)
    prestige_level = int(progress["prestige_level"])
    attrs = CharacterAttributes.from_row(row, prestige_level=prestige_level)
    class_xp = int(row["class_xp"])
    unspent = unspent_attribute_points(attrs, class_xp, prestige_level)
    stat_cap = stat_cap_for_prestige(prestige_level)
    pool_cap = total_point_pool_cap(prestige_level)

    embed = discord.Embed(
        title=f"{member.display_name}'s Attributes",
        description=format_attributes_block(
            attrs,
            class_xp=class_xp,
            prestige_level=prestige_level,
        ),
        color=discord.Color.blurple(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="Guide",
        value=(
            f"Use **+1** buttons below. Pool **{pool_cap}** total · **{stat_cap}**/stat max.\n"
            "**AGI** cuts stun/root/chill · **DEF** cuts burn/void · **STR/DEX/VIT** boost combat."
        ),
        inline=False,
    )
    footer = f"{unspent} unspent point{'s' if unspent != 1 else ''}"
    if unspent <= 0:
        footer = "No unspent points — earn class XP or prestige up"
    embed.set_footer(text=footer)
    return embed


class AllocateAmountModal(discord.ui.Modal, title="Allocate attribute points"):
    amount = discord.ui.TextInput(
        label="Points",
        placeholder="How many points to add?",
        required=True,
        max_length=3,
        default="5",
    )

    def __init__(
        self,
        cog: Attributes,
        guild_id: int,
        user_id: int,
        stat: AttributeName,
    ) -> None:
        super().__init__(title=f"Add points to {STAT_LABELS[stat]}")
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.stat = stat

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            points = int(str(self.amount.value).strip())
        except ValueError:
            await interaction.response.send_message("Enter a whole number.", ephemeral=True)
            return
        if points <= 0:
            await interaction.response.send_message("Enter at least **1**.", ephemeral=True)
            return
        ok, message = await self.cog.bot.db.allocate_attribute_points(
            self.user_id,
            self.guild_id,
            self.stat,
            points,
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await refresh_attributes_message(interaction, self.cog, self.guild_id, self.user_id)


class AttributesView(discord.ui.View):
    def __init__(self, cog: Attributes, guild_id: int, user_id: int) -> None:
        super().__init__(timeout=180.0)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your attributes panel.", ephemeral=True,
            )
            return False
        return True

    async def _allocate_one(self, interaction: discord.Interaction, stat: AttributeName) -> None:
        ok, message = await self.cog.bot.db.allocate_attribute_points(
            self.user_id,
            self.guild_id,
            stat,
            1,
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await refresh_attributes_message(interaction, self.cog, self.guild_id, self.user_id)

    @discord.ui.button(
        label="STR +1",
        emoji="💪",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def str_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._allocate_one(interaction, "strength")

    @discord.ui.button(
        label="DEX +1",
        emoji="🎯",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def dex_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._allocate_one(interaction, "dexterity")

    @discord.ui.button(
        label="AGI +1",
        emoji="💨",
        style=discord.ButtonStyle.success,
        row=0,
    )
    async def agi_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._allocate_one(interaction, "agility")

    @discord.ui.button(
        label="DEF +1",
        emoji="🛡️",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def def_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._allocate_one(interaction, "defense")

    @discord.ui.button(
        label="VIT +1",
        emoji="❤️",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def vit_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await self._allocate_one(interaction, "vitality")

    @discord.ui.select(
        placeholder="Custom amount…",
        options=[
            discord.SelectOption(
                label=f"{STAT_LABELS[name]} +5",
                emoji=STAT_EMOJI[name],
                value=name,
            )
            for name in STAT_KEYS
        ],
        row=2,
    )
    async def custom_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select,
    ) -> None:
        stat = select.values[0]
        assert stat in STAT_KEYS
        await interaction.response.send_modal(
            AllocateAmountModal(self.cog, self.guild_id, self.user_id, stat),  # type: ignore[arg-type]
        )

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=3)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        await refresh_attributes_message(interaction, self.cog, self.guild_id, self.user_id)


async def refresh_attributes_message(
    interaction: discord.Interaction,
    cog: Attributes,
    guild_id: int,
    user_id: int,
) -> None:
    member = interaction.user
    if not isinstance(member, discord.Member):
        member = interaction.guild.get_member(user_id) if interaction.guild else None
    if member is None:
        await interaction.response.send_message("Updated.", ephemeral=True)
        return
    embed = await build_attributes_embed(cog, member, guild_id)
    view = AttributesView(cog, guild_id, user_id)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


async def send_attributes_panel(
    interaction: discord.Interaction,
    cog: Attributes,
    *,
    target: discord.Member,
) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("Guild only.", ephemeral=True)
        return
    guild_id = interaction.guild_id
    embed = await build_attributes_embed(cog, target, guild_id)
    view = None
    if target.id == interaction.user.id:
        view = AttributesView(cog, guild_id, interaction.user.id)
    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True,
    )
