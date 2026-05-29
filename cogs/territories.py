from __future__ import annotations

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.helpers import fmt_amount, guild_only_message, send_error
from utils.territories import (
    TERRITORY_MAP,
    guard_cost_per_unit,
    territory_by_id,
)

logger = logging.getLogger(__name__)


class Territories(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.territory_income_tick.start()
        self.territory_siege_tick.start()

    def cog_unload(self) -> None:
        self.territory_income_tick.cancel()
        self.territory_siege_tick.cancel()

    async def territory_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        needle = (current or "").strip().lower()
        choices: list[app_commands.Choice[str]] = []
        for defn in TERRITORY_MAP.values():
            if needle and needle not in defn.name.lower() and needle not in defn.territory_id:
                continue
            label = f"{defn.name} ({fmt_amount(defn.income_per_hour)}/hr)"
            choices.append(app_commands.Choice(name=label[:100], value=defn.territory_id))
        return choices[:25]

    @app_commands.command(
        name="territory",
        description="Control zones: map, attack, buy guards, abandon. Income goes to crew treasury.",
    )
    @app_commands.describe(
        action="What to do",
        zone="Territory (Docks, Market, Foundry, Vault, Citadel)",
        amount="Guards to buy (1–20) for Buy guards",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Map / status", value="map"),
            app_commands.Choice(name="Attack / claim", value="attack"),
            app_commands.Choice(name="Buy guards", value="guards"),
            app_commands.Choice(name="Abandon", value="abandon"),
        ],
    )
    @app_commands.autocomplete(zone=territory_autocomplete)
    @app_commands.guild_only()
    async def territory(
        self,
        interaction: discord.Interaction,
        action: str,
        zone: str | None = None,
        amount: app_commands.Range[int, 1, 20] | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        guild_id = interaction.guild_id
        uid = interaction.user.id

        if action == "map":
            await self._send_map(interaction, guild_id, uid)
            return

        if not zone:
            await interaction.response.send_message(
                "Pick a **zone** for this action.", ephemeral=True,
            )
            return
        defn = territory_by_id(zone)
        if defn is None:
            await interaction.response.send_message(
                "Unknown territory. Use autocomplete.", ephemeral=True,
            )
            return

        if action == "attack":
            await interaction.response.defer(ephemeral=True)
            try:
                err = await self.bot.db.start_territory_siege(uid, guild_id, defn.territory_id)
                msgs = {
                    "not_in_crew": "Join a crew first (`/crew` → Join crew).",
                    "crew_too_small": (
                        f"Need at least {config.TERRITORY_MIN_CREW_MEMBERS_TO_ATTACK} "
                        "crew members to attack."
                    ),
                    "own_territory": "Your crew already holds this zone.",
                    "already_under_siege": "This zone is already under siege.",
                    "siege_cooldown": "This zone was attacked recently. Try again later.",
                    "max_territories": (
                        f"Your crew already holds {config.TERRITORY_MAX_HELD_PER_CREW} zones."
                    ),
                    "invalid_territory": "Unknown territory.",
                }
                if err == "claimed_neutral":
                    await interaction.followup.send(
                        f"**{defn.name}** is unclaimed — your crew **{await self.bot.db.get_crew_membership(uid, guild_id)}** now holds it!",
                        ephemeral=True,
                    )
                    return
                if err:
                    await interaction.followup.send(msgs.get(err, err), ephemeral=True)
                    return
                mins = int(config.TERRITORY_SIEGE_DURATION_SECONDS // 60)
                await interaction.followup.send(
                    f"Siege started on **{defn.name}**! Battle resolves in **{mins}** minutes. "
                    "Defenders: buy **guards** to improve hold chance.",
                    ephemeral=True,
                )
            except Exception:
                logger.exception("territory attack failed")
                await send_error(interaction, "Something went wrong starting the siege.")
            return

        if action == "guards":
            if amount is None:
                await interaction.response.send_message(
                    "Set **amount** (how many guards to hire).", ephemeral=True,
                )
                return
            await interaction.response.defer(ephemeral=True)
            unit = guard_cost_per_unit(defn)
            try:
                err = await self.bot.db.buy_territory_guards(
                    uid, guild_id, defn.territory_id, int(amount),
                )
                msgs = {
                    "not_in_crew": "Join a crew first.",
                    "not_owner": "Only the holding crew can buy guards here.",
                    "under_siege": "Cannot hire guards during an active siege.",
                    "guard_cap": f"Max **{defn.max_guards}** guards at {defn.name}.",
                    "insufficient_funds": (
                        f"Need **{fmt_amount(unit * int(amount))}** "
                        f"({fmt_amount(unit)} each)."
                    ),
                    "invalid_territory": "Unknown territory.",
                }
                if err:
                    await interaction.followup.send(msgs.get(err, err), ephemeral=True)
                    return
                row = await self.bot.db.get_territory_row(guild_id, defn.territory_id)
                guards = int(row["guards"]) if row is not None else int(amount)
                await interaction.followup.send(
                    f"Hired **{int(amount)}** guard(s) at **{defn.name}** "
                    f"({guards}/{defn.max_guards}).",
                    ephemeral=True,
                )
            except Exception:
                logger.exception("territory guards failed")
                await send_error(interaction, "Something went wrong buying guards.")
            return

        if action == "abandon":
            await interaction.response.defer(ephemeral=True)
            try:
                err = await self.bot.db.abandon_territory(uid, guild_id, defn.territory_id)
                msgs = {
                    "not_in_crew": "Join a crew first.",
                    "not_owner": "Your crew does not hold this zone.",
                    "invalid_territory": "Unknown territory.",
                }
                if err:
                    await interaction.followup.send(msgs.get(err, err), ephemeral=True)
                    return
                await interaction.followup.send(
                    f"Your crew abandoned **{defn.name}**. It is now neutral.",
                    ephemeral=True,
                )
            except Exception:
                logger.exception("territory abandon failed")
                await send_error(interaction, "Something went wrong.")
            return

        await interaction.response.send_message("Unknown action.", ephemeral=True)

    async def _send_map(
        self, interaction: discord.Interaction, guild_id: int, uid: int,
    ) -> None:
        crew = await self.bot.db.get_crew_membership(uid, guild_id)
        rows = await self.bot.db.list_territory_rows(guild_id)
        now = time.time()
        lines: list[str] = []
        for row in rows:
            tid = str(row["territory_id"])
            defn = TERRITORY_MAP.get(tid)
            if defn is None:
                continue
            owner = row["owner_crew_name"]
            guards = int(row["guards"])
            owner_text = f"**{owner}**" if owner else "_Neutral_"
            siege = row["siege_ends_at"]
            extra = ""
            if siege is not None and float(siege) > now:
                attacker = row["siege_attacker_crew"]
                left = int((float(siege) - now) // 60) + 1
                extra = f" · ⚔️ Siege by **{attacker}** ({left}m)"
            lines.append(
                f"**{defn.name}** — {owner_text} · "
                f"{fmt_amount(defn.income_per_hour)}/hr · "
                f"Guards {guards}/{defn.max_guards}{extra}",
            )
        embed = discord.Embed(
            title="Territory map",
            description="\n".join(lines) if lines else "_No zones configured_",
            color=discord.Color.dark_green(),
        )
        if crew:
            held = await self.bot.db.count_crew_territories(guild_id, crew)
            embed.set_footer(
                text=(
                    f"Your crew: {crew} · Holds {held}/{config.TERRITORY_MAX_HELD_PER_CREW} · "
                    "Income → crew treasury hourly"
                ),
            )
        else:
            embed.set_footer(text="Join a crew to attack or claim zones.")
        await interaction.response.send_message(embed=embed)

    @tasks.loop(seconds=config.TERRITORY_HOURLY_TICK_SECONDS)
    async def territory_income_tick(self) -> None:
        for guild in self.bot.guilds:
            try:
                await self.bot.db.process_territory_hourly_income(guild.id)
            except Exception:
                logger.exception("territory income tick failed guild=%s", guild.id)

    @territory_income_tick.before_loop
    async def before_territory_income_tick(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=60)
    async def territory_siege_tick(self) -> None:
        for guild in self.bot.guilds:
            try:
                results = await self.bot.db.resolve_territory_sieges(guild.id)
            except Exception:
                logger.exception("territory siege tick failed guild=%s", guild.id)
                continue
            if not results:
                continue
            channel = guild.system_channel
            if channel is None:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break
            if channel is None:
                continue
            for item in results:
                name = str(item["name"])
                if item["won"]:
                    body = (
                        f"**{item['attacker']}** captured **{name}** "
                        f"from **{item['defender']}**!"
                    )
                else:
                    body = (
                        f"**{item['defender']}** held **{name}** against "
                        f"**{item['attacker']}**."
                    )
                try:
                    await channel.send(body)
                except discord.HTTPException:
                    logger.exception("territory siege announce failed")

    @territory_siege_tick.before_loop
    async def before_territory_siege_tick(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Territories(bot))
