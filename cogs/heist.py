from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.achievements import evaluate_unlocks, format_unlock_message
from utils.crew_banking import heist_same_crew_bonus
from utils.gear_sets import heist_intimidation_bonus
from utils.helpers import fmt_amount, guild_only_message
from utils.loadout import parse_loadout


class Heist(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.pending_arrests: dict[tuple[int, int], tuple[int, float]] = {}

    @app_commands.command(name="heist", description="Attempt to rob a user.")
    @app_commands.describe(target="Robbery target", crew1="Optional crew member", crew2="Optional crew member")
    @app_commands.guild_only()
    async def heist(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        crew1: discord.Member | None = None,
        crew2: discord.Member | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        participants = [interaction.user]
        for member in (crew1, crew2):
            if member is not None:
                participants.append(member)

        participant_ids = {member.id for member in participants}
        if len(participant_ids) != len(participants):
            await interaction.response.send_message("Crew members must be unique.", ephemeral=True)
            return
        if target.bot or target.id in participant_ids or any(member.bot for member in participants):
            await interaction.response.send_message(
                "Choose non-bot users and do not target yourself or crew.",
                ephemeral=True,
            )
            return

        current = time.time()
        thief_row = await self.bot.db.get_user(interaction.user.id, interaction.guild_id)
        heist_cooldown = await self.bot.db.get_config_value(
            interaction.guild_id,
            "heist_cooldown_seconds",
        )
        cooldown_remaining = (float(thief_row["last_heist"]) + heist_cooldown) - current
        if cooldown_remaining > 0:
            await interaction.response.send_message(
                f"Your crew needs {int(cooldown_remaining // 60) + 1} more minutes to regroup.",
                ephemeral=True,
            )
            return

        for member in participants:
            if await self.bot.db.is_restricted(member.id, interaction.guild_id, current):
                await interaction.response.send_message(
                    f"{member.display_name} cannot join a heist right now.",
                    ephemeral=True,
                )
                return

        target_balance = await self.bot.db.get_balance(target.id, interaction.guild_id)
        if target_balance <= 0:
            await interaction.response.send_message("That user has no nuggets to steal.", ephemeral=True)
            return

        await self.bot.db.set_last_heist(interaction.user.id, interaction.guild_id, current)
        base_success = await self.bot.db.get_config_value(interaction.guild_id, "heist_base_success")
        equipment = await self.bot.db.get_equipment(interaction.user.id, interaction.guild_id)
        loadout = parse_loadout(equipment)
        intimidation = heist_intimidation_bonus(loadout.primary, off_hand=loadout.off_hand)
        from utils.classes import get_modifiers

        class_id = await self.bot.db.get_class_id(interaction.user.id, interaction.guild_id)
        class_mod = get_modifiers(class_id)
        spell_heist = await self.bot.db.take_heist_spell_bonus(
            interaction.user.id,
            interaction.guild_id,
        )
        crew_by_user: dict[int, str | None] = {}
        for member in participants:
            crew_by_user[member.id] = await self.bot.db.get_crew_membership(
                member.id,
                interaction.guild_id,
            )
        persistent_crew_bonus = heist_same_crew_bonus(
            [member.id for member in participants],
            crew_by_user,
        )
        leader_crew = crew_by_user.get(participants[0].id)
        held = await self.bot.db.get_crew_territory_perk_ids(
            interaction.guild_id, leader_crew,
        )
        vault_bonus = (
            config.TERRITORY_PERK_VAULT_HEIST_SUCCESS if "vault" in held else 0.0
        )
        success_chance = min(
            config.HEIST_MAX_SUCCESS,
            base_success
            + (len(participants) - 1) * config.HEIST_CREW_BONUS
            + intimidation
            + class_mod.heist_success_bonus
            + spell_heist
            + persistent_crew_bonus
            + vault_bonus
            - class_mod.heist_success_penalty,
        )

        if random.random() > success_chance:
            self.pending_arrests[(interaction.guild_id, interaction.user.id)] = (
                target.id,
                current + config.HEIST_ARREST_WINDOW_SECONDS,
            )
            await interaction.response.send_message(
                f"The heist failed. {target.mention} can use `/arrest` for the next 5 minutes.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        loot_frac = config.HEIST_LOOT_FRACTION
        if "docks" in held:
            loot_frac *= 1.0 + config.TERRITORY_PERK_DOCKS_HEIST_LOOT
        stolen = await self.bot.db.remove_up_to_balance(
            target.id,
            interaction.guild_id,
            target_balance * loot_frac,
        )
        split = stolen / len(participants)
        for member in participants:
            await self.bot.db.credit_wallet(member.id, interaction.guild_id, split)
        await self.bot.db.increment_progress(
            interaction.user.id,
            interaction.guild_id,
            heists_won=1,
        )

        crew_names = ", ".join(member.mention for member in participants)
        await interaction.response.send_message(
            f"Heist success! {crew_names} stole {fmt_amount(stolen)} from {target.mention}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        unlocked = await evaluate_unlocks(
            self.bot.db,
            interaction.guild_id,
            interaction.user.id,
        )
        unlock_msg = format_unlock_message(unlocked)
        if unlock_msg:
            await interaction.followup.send(unlock_msg, ephemeral=True)

    @app_commands.command(name="arrest", description="Arrest a thief after a failed heist.")
    @app_commands.describe(thief="The failed thief")
    @app_commands.guild_only()
    async def arrest(self, interaction: discord.Interaction, thief: discord.Member) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        if thief.bot:
            await interaction.response.send_message("Bots cannot be arrested.", ephemeral=True)
            return

        key = (interaction.guild_id, thief.id)
        pending = self.pending_arrests.get(key)
        current = time.time()
        if pending is None or pending[1] <= current:
            self.pending_arrests.pop(key, None)
            await interaction.response.send_message("There is no arrest window for that thief.", ephemeral=True)
            return
        if pending[0] != interaction.user.id:
            await interaction.response.send_message("Only the heist target can arrest that thief.", ephemeral=True)
            return

        arrest_seconds = await self.bot.db.get_config_value(
            interaction.guild_id,
            "arrest_lockout_seconds",
        )
        await self.bot.db.set_arrested_until(
            thief.id,
            interaction.guild_id,
            current + arrest_seconds,
        )
        self.pending_arrests.pop(key, None)
        minutes = int(arrest_seconds // 60)
        await interaction.response.send_message(
            f"{thief.mention} has been arrested for {minutes} minute(s).",
            allowed_mentions=discord.AllowedMentions.none(),
        )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Heist(bot))
