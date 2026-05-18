from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.duel_combat import (
    DuelFighter,
    fighter_from_equipment,
    format_strike_line,
    simulate_duel,
)
from utils.helpers import fmt_amount, guild_only_message
from utils.skills import get_skill, spell_buff_from_skill
from utils.spell_effects import combat_state_from_spell


class Duels(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _duel_settings(self, guild_id: int) -> tuple[float, float, int]:
        loss_fraction = await self.bot.db.get_config_value(guild_id, "duel_loss_fraction")
        cooldown = await self.bot.db.get_config_value(guild_id, "duel_same_target_cooldown_seconds")
        max_per_hour = int(
            await self.bot.db.get_config_value(guild_id, "duel_max_attacks_per_hour")
        )
        return loss_fraction, cooldown, max_per_hour

    @app_commands.command(
        name="duel",
        description="Challenge a player to a gear-based fight. Loser pays a % of their wallet to the winner.",
    )
    @app_commands.describe(opponent="Player to challenge")
    @app_commands.guild_only()
    async def duel(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return

        attacker = interaction.user
        if not isinstance(attacker, discord.Member):
            await interaction.response.send_message("Invalid attacker.", ephemeral=True)
            return
        if opponent.bot or opponent.id == attacker.id:
            await interaction.response.send_message("Pick another non-bot player.", ephemeral=True)
            return

        guild_id = interaction.guild_id
        if await self.bot.db.is_restricted(attacker.id, guild_id):
            await interaction.response.send_message(
                "You cannot duel while arrested or downed.",
                ephemeral=True,
            )
            return
        if await self.bot.db.is_restricted(opponent.id, guild_id):
            await interaction.response.send_message(
                "That player cannot be dueled right now.",
                ephemeral=True,
            )
            return

        loss_fraction, cooldown_seconds, max_per_hour = await self._duel_settings(guild_id)
        remaining_target = await self.bot.db.duel_same_target_cooldown_remaining(
            guild_id,
            attacker.id,
            opponent.id,
            cooldown_seconds,
        )
        if remaining_target is not None:
            mins = int(remaining_target // 60)
            secs = int(remaining_target % 60)
            await interaction.response.send_message(
                f"You already dueled {opponent.display_name} recently. "
                f"Try again in **{mins}m {secs}s**.",
                ephemeral=True,
            )
            return

        attacks_last_hour = await self.bot.db.duel_attacks_in_last_hour(guild_id, attacker.id)
        if attacks_last_hour >= max_per_hour:
            await interaction.response.send_message(
                f"You can only start **{max_per_hour}** duels per hour. Try again later.",
                ephemeral=True,
            )
            return

        attacker_equipment = await self.bot.db.get_equipment(attacker.id, guild_id)
        defender_equipment = await self.bot.db.get_equipment(opponent.id, guild_id)
        attacker_progress = await self.bot.db.get_user_progress(attacker.id, guild_id)
        defender_progress = await self.bot.db.get_user_progress(opponent.id, guild_id)
        await self.bot.db.ensure_jester_class(attacker.id, guild_id)
        await self.bot.db.ensure_jester_class(opponent.id, guild_id)
        attacker_class = await self.bot.db.get_class_id(attacker.id, guild_id)
        defender_class = await self.bot.db.get_class_id(opponent.id, guild_id)

        attacker_fighter = fighter_from_equipment(
            attacker.id,
            attacker.display_name,
            attacker_equipment,
            prestige_level=int(attacker_progress["prestige_level"]),
            class_id=attacker_class,
        )
        defender_fighter = fighter_from_equipment(
            opponent.id,
            opponent.display_name,
            defender_equipment,
            prestige_level=int(defender_progress["prestige_level"]),
            class_id=defender_class,
        )
        for fighter, uid in (
            (attacker_fighter, attacker.id),
            (defender_fighter, opponent.id),
        ):
            skill_id = await self.bot.db.consume_pending_spell(uid, guild_id)
            if skill_id:
                skill = get_skill(skill_id)
                if skill is not None:
                    fighter.spell_state = combat_state_from_spell(spell_buff_from_skill(skill))

        result = simulate_duel(attacker_fighter, defender_fighter)
        fighters: dict[int, DuelFighter] = {
            attacker_fighter.user_id: attacker_fighter,
            defender_fighter.user_id: defender_fighter,
        }

        settlement = await self.bot.db.execute_duel(
            guild_id,
            attacker.id,
            opponent.id,
            result.winner_id,
            loss_fraction=loss_fraction,
            same_target_cooldown_seconds=cooldown_seconds,
            max_attacks_per_hour=max_per_hour,
        )
        if settlement is None:
            await interaction.response.send_message(
                "Duel blocked by cooldown limits. Please try again.",
                ephemeral=True,
            )
            return

        xp_win = config.CLASS_XP_DUEL_WIN
        xp_loss = config.CLASS_XP_DUEL_LOSS
        await self.bot.db.add_class_xp(
            result.winner_id,
            guild_id,
            xp_win,
        )
        await self.bot.db.add_class_xp(result.loser_id, guild_id, xp_loss)

        jester_lines: list[str] = []
        for jester_id, victim_id, _ in result.jester_steals:
            steal = await self.bot.db.jester_steal_wallet(victim_id, jester_id, guild_id)
            if steal > 0:
                jester_lines.append(
                    f"**who me?** <@{jester_id}> pockets **{fmt_amount(steal)}** from <@{victim_id}>!"
                )

        loot, _ = settlement
        winner = attacker if result.winner_id == attacker.id else opponent
        loser = opponent if result.winner_id == attacker.id else attacker
        loss_pct = int(round(loss_fraction * 100))

        log_lines = [format_strike_line(s, fighters) for s in result.strikes[:12]]
        if len(result.strikes) > 12:
            log_lines.append(f"_…and {len(result.strikes) - 12} more exchanges_")

        embed = discord.Embed(
            title="Duel resolved",
            description=(
                f"**{winner.display_name}** defeats **{loser.display_name}**!\n"
                f"**{fmt_amount(loot)}** ({loss_pct}% of {loser.display_name}'s wallet) "
                f"transferred to the winner."
            ),
            color=discord.Color.red() if result.winner_id == attacker.id else discord.Color.blue(),
        )
        embed.add_field(
            name="Final HP",
            value=(
                f"{attacker_fighter.display_name}: **{attacker_fighter.hp}**/{attacker_fighter.max_hp}\n"
                f"{defender_fighter.display_name}: **{defender_fighter.hp}**/{defender_fighter.max_hp}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Battle log",
            value="\n".join(log_lines) if log_lines else "No strikes recorded.",
            inline=False,
        )
        embed.set_footer(
            text=(
                f"Limits: {max_per_hour}/hr · {int(cooldown_seconds // 60)}m cooldown vs same player"
            )
        )

        await interaction.response.send_message(
            content=f"{attacker.mention} vs {opponent.mention}",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=[attacker, opponent]),
        )
        for line in jester_lines:
            await interaction.followup.send(
                line,
                allowed_mentions=discord.AllowedMentions.users,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Duels(bot))
