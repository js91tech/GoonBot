from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from items import ShopItem, get_item
from utils.helpers import fmt_amount, guild_only_message

BOSS_NAME = "Hannah"


class Boss(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.auto_spawn.start()

    def cog_unload(self) -> None:
        self.auto_spawn.cancel()

    async def _boss_hp(self, guild_id: int, variant: str) -> float:
        circulation = await self.bot.db.total_circulation(guild_id)
        scale_factor = await self.bot.db.get_config_value(guild_id, "boss_health_scale_factor")
        base_hp = max(config.BOSS_MIN_HP, circulation * scale_factor)
        return base_hp * float(config.BOSS_VARIANTS[variant]["multiplier"])

    async def _spawn_boss(self, guild_id: int, variant: str) -> float:
        hp = await self._boss_hp(guild_id, variant)
        await self.bot.db.replace_boss(guild_id, BOSS_NAME, variant, hp)
        return hp

    async def _gear(self, user_id: int, guild_id: int) -> tuple[ShopItem | None, ShopItem | None]:
        equipment = await self.bot.db.get_equipment(user_id, guild_id)
        weapon = get_item(equipment["weapon"]) if "weapon" in equipment else None
        armor = get_item(equipment["armor"]) if "armor" in equipment else None
        return weapon, armor

    async def _max_hp(self, user_id: int, guild_id: int) -> float:
        _, armor = await self._gear(user_id, guild_id)
        return float(config.PLAYER_BASE_HP + (armor.hp_bonus if armor is not None else 0))

    @staticmethod
    def _attack_roll(weapon: ShopItem | None) -> tuple[int, bool, str]:
        damage = random.randint(config.BOSS_ATTACK_MIN, config.BOSS_ATTACK_MAX)
        verb = "hits"
        crit_chance = 0.03
        if weapon is not None:
            damage += weapon.power
            verb = random.choice(weapon.verbs or ("strikes",))
            crit_chance += weapon.crit_chance
        critical = random.random() < crit_chance
        if critical:
            damage = int(damage * 1.6)
        return damage, critical, verb

    @staticmethod
    def _counter_roll(variant: str, armor: ShopItem | None) -> tuple[int, int, bool, str]:
        variant_config = config.BOSS_VARIANTS[variant]
        low, high = variant_config["counter_damage"]
        raw_damage = random.randint(int(low), int(high))
        critical = random.random() < float(variant_config["crit_chance"])
        if critical:
            raw_damage = int(raw_damage * 1.75)
        blocked = armor.power if armor is not None else 0
        damage = max(1, raw_damage - blocked)
        moves = {
            "normal": ("backhands", "shoulder-checks", "bonks"),
            "enraged": ("rage-smashes", "uppercuts", "body-slams"),
            "shadow": ("void-crushes", "shadow-rakes", "ambushes"),
            "celestial": ("meteor-crits", "starfalls onto", "supernovas"),
        }
        return damage, blocked, critical, random.choice(moves[variant])

    @tasks.loop(seconds=config.BOSS_AUTO_SPAWN_SECONDS)
    async def auto_spawn(self) -> None:
        for guild in self.bot.guilds:
            if await self.bot.db.get_active_boss(guild.id) is not None:
                continue
            variant = random.choice(tuple(config.BOSS_VARIANTS))
            hp = await self._spawn_boss(guild.id, variant)
            channel = guild.system_channel
            if channel is not None:
                await channel.send(
                    f"A {variant} {BOSS_NAME} has appeared with {fmt_amount(hp)} HP!"
                )

    @auto_spawn.before_loop
    async def before_auto_spawn(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="summon", description="Admin only: force-spawn a boss.")
    @app_commands.describe(variant="Boss variant")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def summon(self, interaction: discord.Interaction, variant: str = "normal") -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        normalized = variant.lower().strip()
        if normalized not in config.BOSS_VARIANTS:
            choices = ", ".join(config.BOSS_VARIANTS)
            await interaction.response.send_message(
                f"Unknown variant. Choose one of: {choices}.",
                ephemeral=True,
            )
            return

        hp = await self._spawn_boss(interaction.guild_id, normalized)
        await interaction.response.send_message(
            f"Summoned a {normalized} {BOSS_NAME} with {fmt_amount(hp)} HP."
        )

    @app_commands.command(name="boss", description="Check boss status.")
    @app_commands.guild_only()
    async def boss(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        boss = await self.bot.db.get_active_boss(interaction.guild_id)
        if boss is None:
            await interaction.response.send_message("No boss is active right now.")
            return

        await interaction.response.send_message(
            f"{boss['variant'].title()} {boss['name']}: "
            f"{fmt_amount(float(boss['hp']))}/{fmt_amount(float(boss['max_hp']))} HP"
        )

    @app_commands.command(name="attack", description="Attack the active boss.")
    @app_commands.guild_only()
    async def attack(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        if await self.bot.db.is_restricted(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message("You cannot attack right now.", ephemeral=True)
            return

        boss = await self.bot.db.get_active_boss(interaction.guild_id)
        if boss is None:
            await interaction.response.send_message("No boss is active right now.", ephemeral=True)
            return

        weapon, _ = await self._gear(interaction.user.id, interaction.guild_id)
        damage, attack_critical, attack_verb = self._attack_roll(weapon)
        updated = await self.bot.db.damage_boss(interaction.guild_id, interaction.user.id, damage)
        if updated is None:
            await interaction.response.send_message("No boss is active right now.", ephemeral=True)
            return

        if float(updated["hp"]) <= 0:
            await self._finish_boss(interaction)
            return

        counter_text = ""
        variant = str(updated["variant"])
        if random.random() < float(config.BOSS_VARIANTS[variant]["counter_chance"]):
            damage_rows = await self.bot.db.list_boss_damage(interaction.guild_id)
            if damage_rows:
                victim_id = int(random.choice(damage_rows)["user_id"])
                counter_text = await self._counterattack_text(interaction.guild_id, victim_id, variant)

        weapon_text = f" with **{weapon.name}**" if weapon is not None else ""
        crit_text = " **Critical hit!**" if attack_critical else ""
        await interaction.response.send_message(
            f"{interaction.user.mention} {attack_verb} {BOSS_NAME}{weapon_text} "
            f"for {damage} damage.{crit_text} "
            f"HP: {fmt_amount(float(updated['hp']))}.{counter_text}",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _counterattack_text(self, guild_id: int, victim_id: int, variant: str) -> str:
        _, armor = await self._gear(victim_id, guild_id)
        max_hp = await self._max_hp(victim_id, guild_id)
        await self.bot.db.sync_combat_hp(victim_id, guild_id, max_hp)
        damage, blocked, critical, move = self._counter_roll(variant, armor)
        hp, max_hp = await self.bot.db.damage_player(victim_id, guild_id, damage, max_hp)
        armor_text = f" {armor.name} blocks {blocked}." if armor is not None and blocked else ""
        crit_text = " Critical blow!" if critical else ""
        threat = int(config.BOSS_VARIANTS[variant]["threat"])
        if hp <= 0:
            downed_seconds = await self.bot.db.get_config_value(guild_id, "boss_downed_seconds")
            await self.bot.db.set_downed_until(victim_id, guild_id, time.time() + downed_seconds)
            return (
                f"\nThreat {threat} {BOSS_NAME} {move} <@{victim_id}> for {damage} damage."
                f"{crit_text}{armor_text} They are downed!"
            )
        return (
            f"\nThreat {threat} {BOSS_NAME} {move} <@{victim_id}> for {damage} damage."
            f"{crit_text}{armor_text} HP: {int(hp)}/{int(max_hp)}."
        )

    async def _finish_boss(self, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        assert interaction.guild is not None
        boss = await self.bot.db.get_active_boss(interaction.guild_id)
        if boss is None:
            await interaction.response.send_message("The boss was already defeated.", ephemeral=True)
            return

        rows = await self.bot.db.list_boss_damage(interaction.guild_id)
        total_damage = sum(float(row["damage"]) for row in rows)
        if total_damage <= 0:
            await self.bot.db.clear_boss(interaction.guild_id)
            await interaction.response.send_message(f"{BOSS_NAME} vanished without any rewards.")
            return

        max_hp = float(boss["max_hp"])
        reward_lines = []
        for row in rows:
            user_id = int(row["user_id"])
            reward = max_hp * (float(row["damage"]) / total_damage)
            await self.bot.db.credit_wallet(user_id, interaction.guild_id, reward)
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            reward_lines.append(f"{name}: {fmt_amount(reward)}")

        await self.bot.db.clear_boss(interaction.guild_id)
        await interaction.response.send_message(
            f"{BOSS_NAME} was defeated! Rewards:\n" + "\n".join(reward_lines[:10])
        )

    @app_commands.command(name="heal", description="Revive a downed teammate.")
    @app_commands.describe(target="Downed user to heal")
    @app_commands.guild_only()
    async def heal(self, interaction: discord.Interaction, target: discord.Member) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("Bots do not need healing.", ephemeral=True)
            return
        if not await self.bot.db.is_downed(target.id, interaction.guild_id):
            await interaction.response.send_message("That user is not downed.", ephemeral=True)
            return

        await self.bot.db.set_downed_until(target.id, interaction.guild_id, 0)
        await self.bot.db.restore_player_hp(
            target.id,
            interaction.guild_id,
            await self._max_hp(target.id, interaction.guild_id),
        )
        await self.bot.db.record_heal(interaction.guild_id, interaction.user.id, target.id)
        await interaction.response.send_message(
            f"{interaction.user.mention} revived {target.mention}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Boss(bot))
