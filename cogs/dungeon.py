from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.combat_engine import AttackContext, roll_player_damage
from utils.helpers import fmt_amount, guild_only_message, valid_amount
from utils.loadout import parse_loadout
from utils.quests import record_quest_event


class Dungeon(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _player_max_hp(self, user_id: int, guild_id: int) -> float:
        equipment = await self.bot.db.get_equipment(user_id, guild_id)
        loadout = parse_loadout(equipment)
        hp = float(config.PLAYER_BASE_HP)
        if loadout.armor:
            hp += float(loadout.armor.hp_bonus)
        return hp

    @app_commands.command(name="dungeon", description="Solo dungeon run — 5 rooms, loot at the end.")
    @app_commands.describe(
        action="Start, fight, or flee",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Status", value="status"),
            app_commands.Choice(name="Start run", value="start"),
            app_commands.Choice(name="Fight room", value="fight"),
            app_commands.Choice(name="Flee", value="flee"),
        ],
    )
    @app_commands.guild_only()
    async def dungeon(self, interaction: discord.Interaction, action: str) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        guild_id = interaction.guild_id
        uid = interaction.user.id

        run = await self.bot.db.get_dungeon_run(uid, guild_id)

        if action == "flee":
            if run is None:
                await interaction.response.send_message(
                    "No active dungeon.", ephemeral=True,
                )
                return
            await self.bot.db.clear_dungeon_run(uid, guild_id)
            await interaction.response.send_message(
                "You fled the dungeon empty-handed.", ephemeral=True,
            )
            return

        if action == "status":
            if run is None:
                await interaction.response.send_message(
                    "No active run. **Start run** costs "
                    f"{fmt_amount(config.DUNGEON_ENTRY_COST)}.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"Room **{int(run['room'])}/{config.DUNGEON_ROOMS}** · "
                f"Your HP **{int(float(run['player_hp']))}**/{int(float(run['max_hp']))} · "
                f"Enemy HP **{int(float(run['enemy_hp']))}**",
                ephemeral=True,
            )
            return

        if action == "start":
            if run is not None:
                await interaction.response.send_message(
                    "Finish or flee your current run first.", ephemeral=True,
                )
                return
            if await self.bot.db.is_restricted(uid, guild_id):
                await interaction.response.send_message(
                    "You cannot enter a dungeon while arrested or downed.",
                    ephemeral=True,
                )
                return
            cost = config.DUNGEON_ENTRY_COST
            if not await self.bot.db.debit_wallet(uid, guild_id, cost):
                await interaction.response.send_message(
                    f"Entry costs **{fmt_amount(cost)}**.", ephemeral=True,
                )
                return
            max_hp = await self._player_max_hp(uid, guild_id)
            enemy_hp = random.uniform(80, 140)
            await self.bot.db.start_dungeon_run(uid, guild_id, max_hp, max_hp, enemy_hp)
            await interaction.response.send_message(
                f"Entered the dungeon (-{fmt_amount(cost)}). "
                f"Room 1 — enemy HP **{int(enemy_hp)}**. Use **Fight room**.",
                ephemeral=True,
            )
            return

        if action == "fight":
            if run is None:
                await interaction.response.send_message(
                    "Start a run first.", ephemeral=True,
                )
                return
            equipment = await self.bot.db.get_equipment(uid, guild_id)
            loadout = parse_loadout(equipment)
            progress = await self.bot.db.get_user_progress(uid, guild_id)
            ctx = AttackContext(prestige_level=int(progress["prestige_level"]))
            damage, critical, verb = roll_player_damage(
                loadout.primary,
                off_hand=loadout.off_hand,
                ctx=ctx,
            )
            player_hp = float(run["player_hp"])
            enemy_hp = float(run["enemy_hp"]) - damage
            room = int(run["room"])
            crit_note = " **CRIT!**" if critical else ""
            lines = [f"You **{verb}** for **{damage}** damage.{crit_note}"]

            if enemy_hp > 0:
                counter = random.randint(12, 28)
                player_hp = max(0.0, player_hp - counter)
                lines.append(f"Enemy hits back for **{counter}**.")
                if player_hp <= 0:
                    await self.bot.db.clear_dungeon_run(uid, guild_id)
                    await interaction.response.send_message(
                        "\n".join(lines) + "\nYou were defeated.",
                        ephemeral=True,
                    )
                    return
                await self.bot.db.update_dungeon_run(
                    uid, guild_id, room=room, player_hp=player_hp, enemy_hp=enemy_hp,
                )
                await interaction.response.send_message("\n".join(lines), ephemeral=True)
                return

            reward = config.DUNGEON_ROOM_REWARD
            if room >= config.DUNGEON_ROOMS:
                reward += config.DUNGEON_CLEAR_BONUS
                await self.bot.db.clear_dungeon_run(uid, guild_id)
                await self.bot.db.credit_wallet(uid, guild_id, reward)
                await self.bot.db.increment_progress(
                    uid, guild_id, dungeons_cleared=1,
                )
                await record_quest_event(self.bot.db, guild_id, uid, "dungeon_clear")
                await interaction.response.send_message(
                    "\n".join(lines)
                    + f"\n**Dungeon cleared!** +{fmt_amount(reward)}",
                    ephemeral=True,
                )
                return

            next_room = room + 1
            next_enemy = random.uniform(90 + next_room * 15, 130 + next_room * 20)
            await self.bot.db.update_dungeon_run(
                uid,
                guild_id,
                room=next_room,
                player_hp=player_hp,
                enemy_hp=next_enemy,
            )
            await self.bot.db.credit_wallet(uid, guild_id, reward)
            await interaction.response.send_message(
                "\n".join(lines)
                + f"\nRoom cleared (+{fmt_amount(reward)}). "
                f"Room **{next_room}** — enemy HP **{int(next_enemy)}**.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Unknown action.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dungeon(bot))
