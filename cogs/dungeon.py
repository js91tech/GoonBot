from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.combat_engine import AttackContext, roll_player_damage
from utils.dungeon_ui import DungeonActionResult, send_dungeon_panel
from utils.energy import format_energy_display
from utils.helpers import fmt_amount, guild_only_message
from utils.quests import record_quest_event
from utils.stats import hp_bar


class Dungeon(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _player_max_hp(self, user_id: int, guild_id: int) -> float:
        loadout = await self.bot.db.get_combat_loadout(user_id, guild_id)
        hp = float(config.PLAYER_BASE_HP)
        if loadout.armor:
            hp += float(loadout.armor.hp_bonus)
        return hp

    async def _energy_display(self, user_id: int, guild_id: int) -> tuple[str, int, int]:
        row = await self.bot.db.get_user_character(user_id, guild_id)
        regen_per_tick = int(
            await self.bot.db.get_config_value(guild_id, "energy_regen_per_tick")
        )
        tick_seconds = int(
            await self.bot.db.get_config_value(guild_id, "energy_regen_interval_seconds")
        )
        return format_energy_display(
            int(row["energy"]),
            int(row["energy_cap"]),
            int(row["cap_upgrades"]),
            float(row["energy_updated_at"]),
            regen_per_tick=regen_per_tick,
            tick_seconds=tick_seconds,
        )

    async def build_dungeon_embed(
        self,
        guild_id: int,
        user_id: int,
    ) -> tuple[discord.Embed, bool]:
        run = await self.bot.db.get_dungeon_run(user_id, guild_id)
        energy_text, current_energy, cap = await self._energy_display(user_id, guild_id)

        if run is None:
            embed = discord.Embed(
                title="Dungeon — Delver's Depths",
                description=(
                    f"**{config.DUNGEON_ROOMS} rooms** of PvE combat.\n"
                    f"Clear rooms for nuggets; finish for a bonus and alchemy scrap."
                ),
                color=discord.Color.dark_purple(),
            )
            embed.add_field(
                name="Entry cost",
                value=f"**{config.DUNGEON_ENERGY_COST}** energy per run",
                inline=True,
            )
            embed.add_field(
                name="Room reward",
                value=fmt_amount(config.DUNGEON_ROOM_REWARD),
                inline=True,
            )
            embed.add_field(
                name="Clear bonus",
                value=(
                    f"{fmt_amount(config.DUNGEON_CLEAR_BONUS)} + "
                    f"{config.DUNGEON_SCRAP_PER_CLEAR} scrap"
                ),
                inline=True,
            )
            embed.add_field(name="Your energy", value=energy_text, inline=False)
            can_start = current_energy >= config.DUNGEON_ENERGY_COST
            embed.set_footer(
                text=(
                    "Press Enter dungeon to begin"
                    if can_start
                    else f"Need {config.DUNGEON_ENERGY_COST} energy ({current_energy}/{cap})"
                ),
            )
            return embed, False

        room = int(run["room"])
        player_hp = float(run["player_hp"])
        max_hp = float(run["max_hp"])
        enemy_hp = float(run["enemy_hp"])
        embed = discord.Embed(
            title=f"Dungeon — Room {room}/{config.DUNGEON_ROOMS}",
            description="Fight through the room or flee empty-handed.",
            color=discord.Color.dark_purple(),
        )
        embed.add_field(
            name="Your HP",
            value=(
                f"`{hp_bar(player_hp, max_hp)}` "
                f"**{int(player_hp)}/{int(max_hp)}**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Enemy HP",
            value=f"`{hp_bar(enemy_hp, max(enemy_hp, 1))}` **{int(enemy_hp)}**",
            inline=False,
        )
        embed.add_field(name="Energy", value=energy_text, inline=False)
        embed.set_footer(text="⚔️ Fight · Flee · Refresh")
        return embed, True

    async def execute_dungeon_start(
        self,
        guild_id: int,
        user_id: int,
    ) -> DungeonActionResult:
        run = await self.bot.db.get_dungeon_run(user_id, guild_id)
        if run is not None:
            return DungeonActionResult(error="Finish or flee your current run first.")

        if await self.bot.db.is_restricted(user_id, guild_id):
            return DungeonActionResult(
                error="You cannot enter a dungeon while arrested or downed.",
            )

        ok, err = await self.bot.db.spend_job_energy(
            user_id,
            guild_id,
            config.DUNGEON_ENERGY_COST,
        )
        if not ok:
            if err == "energy":
                energy_text, current, cap = await self._energy_display(user_id, guild_id)
                return DungeonActionResult(
                    error=(
                        f"Not enough energy. Need **{config.DUNGEON_ENERGY_COST}**, "
                        f"you have **{current}/{cap}**.\n{energy_text}"
                    ),
                )
            return DungeonActionResult(error="Could not start that run.")

        max_hp = await self._player_max_hp(user_id, guild_id)
        enemy_hp = random.uniform(80, 140)
        await self.bot.db.start_dungeon_run(user_id, guild_id, max_hp, max_hp, enemy_hp)
        embed, _ = await self.build_dungeon_embed(guild_id, user_id)
        return DungeonActionResult(
            embed=embed,
            message=(
                f"Entered the dungeon (-**{config.DUNGEON_ENERGY_COST}** energy). "
                f"Room 1 — enemy HP **{int(enemy_hp)}**."
            ),
        )

    async def execute_dungeon_flee(
        self,
        guild_id: int,
        user_id: int,
    ) -> DungeonActionResult:
        run = await self.bot.db.get_dungeon_run(user_id, guild_id)
        if run is None:
            return DungeonActionResult(error="No active dungeon run.")

        await self.bot.db.clear_dungeon_run(user_id, guild_id)
        embed, _ = await self.build_dungeon_embed(guild_id, user_id)
        return DungeonActionResult(
            embed=embed,
            message="You fled the dungeon empty-handed.",
            finished=True,
        )

    async def execute_dungeon_fight(
        self,
        guild_id: int,
        user_id: int,
    ) -> DungeonActionResult:
        run = await self.bot.db.get_dungeon_run(user_id, guild_id)
        if run is None:
            return DungeonActionResult(error="Start a run first.")

        loadout = await self.bot.db.get_combat_loadout(user_id, guild_id)
        progress = await self.bot.db.get_user_progress(user_id, guild_id)
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
                await self.bot.db.clear_dungeon_run(user_id, guild_id)
                embed, _ = await self.build_dungeon_embed(guild_id, user_id)
                return DungeonActionResult(
                    embed=embed,
                    message="\n".join(lines) + "\nYou were defeated.",
                    finished=True,
                )
            await self.bot.db.update_dungeon_run(
                user_id, guild_id, room=room, player_hp=player_hp, enemy_hp=enemy_hp,
            )
            embed, _ = await self.build_dungeon_embed(guild_id, user_id)
            return DungeonActionResult(embed=embed, message="\n".join(lines))

        reward = config.DUNGEON_ROOM_REWARD
        if room >= config.DUNGEON_ROOMS:
            reward += config.DUNGEON_CLEAR_BONUS
            await self.bot.db.clear_dungeon_run(user_id, guild_id)
            await self.bot.db.credit_wallet(user_id, guild_id, reward)
            await self.bot.db.increment_progress(
                user_id, guild_id, dungeons_cleared=1,
            )
            await record_quest_event(self.bot.db, guild_id, user_id, "dungeon_clear")
            for _ in range(config.DUNGEON_SCRAP_PER_CLEAR):
                await self.bot.db.grant_item(user_id, guild_id, "alchemy_scrap")
            embed, _ = await self.build_dungeon_embed(guild_id, user_id)
            return DungeonActionResult(
                embed=embed,
                message=(
                    "\n".join(lines)
                    + f"\n**Dungeon cleared!** +{fmt_amount(reward)} · "
                    f"+{config.DUNGEON_SCRAP_PER_CLEAR} alchemy scrap"
                ),
                finished=True,
            )

        next_room = room + 1
        next_enemy = random.uniform(90 + next_room * 15, 130 + next_room * 20)
        await self.bot.db.update_dungeon_run(
            user_id,
            guild_id,
            room=next_room,
            player_hp=player_hp,
            enemy_hp=next_enemy,
        )
        await self.bot.db.credit_wallet(user_id, guild_id, reward)
        embed, _ = await self.build_dungeon_embed(guild_id, user_id)
        return DungeonActionResult(
            embed=embed,
            message=(
                "\n".join(lines)
                + f"\nRoom cleared (+{fmt_amount(reward)}). "
                f"Room **{next_room}** — enemy HP **{int(next_enemy)}**."
            ),
        )

    @app_commands.command(
        name="dungeon",
        description="Solo dungeon panel — 5 rooms, loot and alchemy scrap at the end.",
    )
    @app_commands.describe(
        action="Party commands (solo uses the panel buttons)",
        leader="Party leader (for join)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Party — create", value="party-create"),
            app_commands.Choice(name="Party — join", value="party-join"),
            app_commands.Choice(name="Party — leave", value="party-leave"),
            app_commands.Choice(name="Party — status", value="party-status"),
            app_commands.Choice(name="Party — fight", value="party-fight"),
        ],
    )
    @app_commands.guild_only()
    async def dungeon(
        self,
        interaction: discord.Interaction,
        action: str | None = None,
        leader: discord.Member | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        guild_id = interaction.guild_id
        uid = interaction.user.id

        if action is None:
            await send_dungeon_panel(interaction, self)
            return

        if action == "party-create":
            if await self.bot.db.get_party_leader_for_member(guild_id, uid) is not None:
                await interaction.response.send_message(
                    "Leave your current party first.", ephemeral=True,
                )
                return
            ok, err = await self.bot.db.spend_job_energy(
                uid,
                guild_id,
                config.DUNGEON_PARTY_ENERGY_COST,
            )
            if not ok:
                if err == "energy":
                    energy_text, current, cap = await self._energy_display(uid, guild_id)
                    await interaction.response.send_message(
                        f"Not enough energy. Need **{config.DUNGEON_PARTY_ENERGY_COST}**, "
                        f"you have **{current}/{cap}**.\n{energy_text}",
                        ephemeral=True,
                    )
                    return
                await interaction.response.send_message(
                    "Could not start that party.", ephemeral=True,
                )
                return
            max_hp = await self._player_max_hp(uid, guild_id)
            enemy_hp = random.uniform(120, 200)
            await self.bot.db.create_dungeon_party(
                guild_id, uid, max_hp, max_hp, enemy_hp,
            )
            await interaction.response.send_message(
                f"Party created (-**{config.DUNGEON_PARTY_ENERGY_COST}** energy). "
                f"Others use **/dungeon** → **Party — join** with you as leader. "
                f"Enemy HP **{int(enemy_hp)}**.",
                ephemeral=True,
            )
            return

        if action == "party-join":
            if leader is None:
                await interaction.response.send_message(
                    "Pick the **leader** who started the party.", ephemeral=True,
                )
                return
            max_hp = await self._player_max_hp(uid, guild_id)
            err = await self.bot.db.join_dungeon_party(
                guild_id, leader.id, uid, max_hp, max_hp,
            )
            msgs = {
                "no_party": "That player has no active party run.",
                "full": "Party is full (4 raiders).",
                "already_in": "You are already in that party.",
                "in_other_party": "Leave your other party first.",
            }
            if err:
                await interaction.response.send_message(
                    msgs.get(err, err), ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"Joined **{leader.display_name}**'s dungeon party!",
                ephemeral=True,
            )
            return

        if action == "party-leave":
            if await self.bot.db.leave_dungeon_party(guild_id, uid):
                await interaction.response.send_message(
                    "Left the party.", ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "You are not in a party.", ephemeral=True,
                )
            return

        if action == "party-status":
            lid = await self.bot.db.get_party_leader_for_member(guild_id, uid)
            if lid is None:
                await interaction.response.send_message(
                    "You are not in a party.", ephemeral=True,
                )
                return
            party = await self.bot.db.get_dungeon_party(guild_id, lid)
            members = await self.bot.db.list_party_members(guild_id, lid)
            if party is None:
                await interaction.response.send_message(
                    "Party run not found.", ephemeral=True,
                )
                return
            names = []
            if interaction.guild:
                for m in members:
                    mem = interaction.guild.get_member(int(m["user_id"]))
                    hp = int(float(m["player_hp"]))
                    maxh = int(float(m["max_hp"]))
                    names.append(
                        f"{mem.display_name if mem else m['user_id']}: **{hp}/{maxh}** HP"
                    )
            await interaction.response.send_message(
                f"Party leader <@{lid}> · Room **{int(party['room'])}/{config.DUNGEON_ROOMS}** · "
                f"Shared enemy **{int(float(party['enemy_hp']))}** HP\n"
                + "\n".join(names),
                ephemeral=True,
            )
            return

        if action == "party-fight":
            lid = await self.bot.db.get_party_leader_for_member(guild_id, uid)
            if lid is None:
                await interaction.response.send_message(
                    "Join a party first.", ephemeral=True,
                )
                return
            party = await self.bot.db.get_dungeon_party(guild_id, lid)
            if party is None:
                await interaction.response.send_message(
                    "No active party dungeon.", ephemeral=True,
                )
                return
            members = await self.bot.db.list_party_members(guild_id, lid)
            my_row = next((m for m in members if int(m["user_id"]) == uid), None)
            if my_row is None:
                await interaction.response.send_message(
                    "You are not in this party.", ephemeral=True,
                )
                return
            player_hp = float(my_row["player_hp"])
            if player_hp <= 0:
                await interaction.response.send_message(
                    "You are downed and cannot fight.", ephemeral=True,
                )
                return
            loadout = await self.bot.db.get_combat_loadout(uid, guild_id)
            progress = await self.bot.db.get_user_progress(uid, guild_id)
            ctx = AttackContext(prestige_level=int(progress["prestige_level"]))
            damage, critical, verb = roll_player_damage(
                loadout.primary, off_hand=loadout.off_hand, ctx=ctx,
            )
            enemy_hp = float(party["enemy_hp"]) - damage
            room = int(party["room"])
            crit = " **CRIT!**" if critical else ""
            lines = [
                f"**{interaction.user.display_name}** **{verb}** for **{damage}**.{crit}",
            ]
            if enemy_hp > 0:
                counter = random.randint(10, 24)
                player_hp = max(0.0, player_hp - counter)
                lines.append(f"Party takes **{counter}** splash damage on you.")
                await self.bot.db.update_party_member_hp(
                    guild_id, lid, uid, player_hp,
                )
                await self.bot.db.update_dungeon_party_enemy(
                    guild_id, lid, room=room, enemy_hp=enemy_hp,
                )
                if player_hp <= 0:
                    await interaction.response.send_message(
                        "\n".join(lines) + "\nYou were downed.",
                        ephemeral=True,
                    )
                    return
                await interaction.response.send_message(
                    "\n".join(lines) + f"\nEnemy **{int(enemy_hp)}** HP left.",
                    ephemeral=True,
                )
                return
            reward_each = config.DUNGEON_ROOM_REWARD / max(1, len(members))
            if room >= config.DUNGEON_ROOMS:
                reward_each += config.DUNGEON_CLEAR_BONUS / max(1, len(members))
                await self.bot.db.clear_dungeon_party(guild_id, lid)
                for m in members:
                    mid = int(m["user_id"])
                    if float(m["player_hp"]) > 0:
                        await self.bot.db.credit_wallet(
                            mid, guild_id, reward_each,
                        )
                        await self.bot.db.increment_progress(
                            mid, guild_id, dungeons_cleared=1,
                        )
                        for _ in range(config.DUNGEON_SCRAP_PER_CLEAR):
                            await self.bot.db.grant_item(
                                mid, guild_id, "alchemy_scrap",
                            )
                await interaction.response.send_message(
                    "\n".join(lines)
                    + f"\n**Party cleared the dungeon!** "
                    f"+{fmt_amount(reward_each)} each · scrap for survivors.",
                    ephemeral=True,
                )
                return
            next_room = room + 1
            next_enemy = random.uniform(100 + next_room * 20, 160 + next_room * 25)
            await self.bot.db.update_dungeon_party_enemy(
                guild_id, lid, room=next_room, enemy_hp=next_enemy,
            )
            for m in members:
                mid = int(m["user_id"])
                if float(m["player_hp"]) > 0:
                    await self.bot.db.credit_wallet(mid, guild_id, reward_each)
            await interaction.response.send_message(
                "\n".join(lines)
                + f"\nRoom cleared (+{fmt_amount(reward_each)} each). "
                f"Room **{next_room}** — enemy **{int(next_enemy)}** HP.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Unknown action.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dungeon(bot))
