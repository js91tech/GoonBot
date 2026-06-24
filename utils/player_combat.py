"""Shared player combat helpers for consumables, drugs, and raids."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord.ext import commands


async def player_max_hp(cog: commands.Cog, user_id: int, guild_id: int) -> float:
    from utils.character_attributes import combat_bonuses_from_attributes
    from utils.classes import get_modifiers
    from utils.combat_engine import max_hp_from_armor

    loadout = await cog.bot.db.get_combat_loadout(user_id, guild_id)
    class_id = await cog.bot.db.get_class_id(user_id, guild_id)
    attrs = await cog.bot.db.get_character_attributes(user_id, guild_id)
    attr_bonuses = combat_bonuses_from_attributes(attrs)
    return float(
        max_hp_from_armor(
            loadout.armor,
            class_modifiers=get_modifiers(class_id),
            attr_hp_bonus=attr_bonuses.hp_bonus,
            accessory_bonuses=loadout.accessory_bonuses,
        ),
    )
