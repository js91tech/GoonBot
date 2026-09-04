"""GoonCards hub — binder, packs, market, and collection tabs."""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any

import discord

from utils.card_announce import announce_granted_cards, interaction_channel
from utils.card_canvas import (
    BINDER_PER_PAGE,
    render_binder_page,
    render_card_png,
)
from utils.cards import (
    CARD_DEFINITIONS,
    RARITY_COLOR,
    RARITY_EMOJI,
    RARITY_LABELS,
    RARITY_ORDER,
    SET_EMOJI,
    SET_LABELS,
    SET_ORDER,
    card_by_id,
    format_card_line,
    format_pack_odds,
)
from utils.goon_theme import branded_embed, panel_title
from utils.helpers import fmt_amount, guild_only_message

if TYPE_CHECKING:
    from discord.ext import commands

logger = logging.getLogger(__name__)

TABS = ("binder", "packs", "market", "collection")
TAB_LABELS = {
    "binder": "Binder",
    "packs": "Packs",
    "market": "Market",
    "collection": "Collection",
}


def _filter_key(set_id: str | None, rarity: str | None) -> str:
    return f"{set_id or 'all'}|{rarity or 'all'}"


def _parse_filter(value: str) -> tuple[str | None, str | None]:
    set_id, rarity = value.split("|", 1)
    return (None if set_id == "all" else set_id, None if rarity == "all" else rarity)


async def _sell_mult(cog: commands.Cog, guild_id: int) -> float:
    return float(await cog.bot.db.get_config_value(guild_id, "card_npc_sell_mult"))


class CardsTabSelect(discord.ui.Select):
    def __init__(self, current: str) -> None:
        options = [
            discord.SelectOption(
                label=TAB_LABELS[tab],
                value=tab,
                default=tab == current,
            )
            for tab in TABS
        ]
        super().__init__(placeholder="Choose a tab…", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: CardsHubView = self.view  # type: ignore[assignment]
        view.tab = self.values[0]
        view.page = 0
        view.selected_instance_id = None
        view.pending_extras_confirm = False
        await view.refresh(interaction)


class BinderFilterSelect(discord.ui.Select):
    def __init__(self, current: str) -> None:
        options = [discord.SelectOption(label="All cards", value="all|all", default=current == "all|all")]
        for set_id in SET_ORDER:
            value = f"{set_id}|all"
            options.append(
                discord.SelectOption(
                    label=f"{SET_EMOJI[set_id]} {SET_LABELS[set_id]}",
                    value=value,
                    default=current == value,
                ),
            )
        for rarity in RARITY_ORDER:
            value = f"all|{rarity}"
            options.append(
                discord.SelectOption(
                    label=f"{RARITY_EMOJI[rarity]} {RARITY_LABELS[rarity]}",
                    value=value,
                    default=current == value,
                ),
            )
        super().__init__(placeholder="Filter binder…", options=options[:25], row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: CardsHubView = self.view  # type: ignore[assignment]
        view.set_id, view.rarity = _parse_filter(self.values[0])
        view.page = 0
        view.selected_instance_id = None
        await view.refresh(interaction)


class BinderCardSelect(discord.ui.Select):
    def __init__(self, groups: list[dict[str, Any]], selected: int | None) -> None:
        options: list[discord.SelectOption] = []
        for bucket in groups:
            defn = card_by_id(str(bucket["card_id"]))
            if defn is None:
                continue
            iid = int(bucket["showcase_instance_id"])
            label = f"{defn.emoji} {defn.name} ×{bucket['count']}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(iid),
                    description=f"{defn.rarity_label} · #{int(bucket['lowest_print']):04d}"[:100],
                    default=selected == iid,
                ),
            )
        if not options:
            options.append(discord.SelectOption(label="Binder empty", value="_none"))
        super().__init__(
            placeholder="Select a card…",
            options=options[:25],
            disabled=options[0].value == "_none",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: CardsHubView = self.view  # type: ignore[assignment]
        if self.values[0] == "_none":
            await interaction.response.defer()
            return
        view.selected_instance_id = int(self.values[0])
        await view.refresh(interaction)


class MarketListingSelect(discord.ui.Select):
    def __init__(self, listings: list[dict[str, Any]], selected: int | None) -> None:
        options: list[discord.SelectOption] = []
        for row in listings:
            defn = card_by_id(str(row["card_id"]))
            name = defn.name if defn else str(row["card_id"])
            emoji = defn.emoji if defn else "🃏"
            lid = int(row["listing_id"])
            options.append(
                discord.SelectOption(
                    label=f"{emoji} {name} #{int(row['print_number']):04d}"[:100],
                    value=str(lid),
                    description=fmt_amount(float(row["price"]))[:100],
                    default=selected == lid,
                ),
            )
        if not options:
            options.append(discord.SelectOption(label="No listings", value="_none"))
        super().__init__(
            placeholder="Pick a market listing…",
            options=options[:25],
            disabled=options[0].value == "_none",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: CardsHubView = self.view  # type: ignore[assignment]
        if self.values[0] == "_none":
            await interaction.response.defer()
            return
        view.selected_listing_id = int(self.values[0])
        await view.refresh(interaction)


class CollectionHuntSelect(discord.ui.Select):
    def __init__(self, current: str) -> None:
        options = [
            discord.SelectOption(
                label=f"{SET_EMOJI[set_id]} {SET_LABELS[set_id]}"[:100],
                value=set_id,
                default=set_id == current,
            )
            for set_id in SET_ORDER
        ]
        super().__init__(placeholder="Holes in which set…", options=options, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: CardsHubView = self.view  # type: ignore[assignment]
        view.hunt_set_id = self.values[0]
        await view.refresh(interaction)


class ListCardSelect(discord.ui.Select):
    def __init__(self, instances: list[dict[str, Any]]) -> None:
        options: list[discord.SelectOption] = []
        for row in instances[:24]:
            defn = card_by_id(str(row["card_id"]))
            name = defn.name if defn else str(row["card_id"])
            options.append(
                discord.SelectOption(
                    label=f"{name} #{int(row['print_number']):04d}"[:100],
                    value=str(int(row["instance_id"])),
                ),
            )
        if not options:
            options.append(discord.SelectOption(label="Nothing to list", value="_none"))
        super().__init__(
            placeholder="List a card for sale…",
            options=options,
            disabled=options[0].value == "_none",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: CardsHubView = self.view  # type: ignore[assignment]
        if self.values[0] == "_none":
            await interaction.response.defer()
            return
        await interaction.response.send_modal(ListPriceModal(view, int(self.values[0])))


class ListPriceModal(discord.ui.Modal, title="List GoonCard"):
    def __init__(self, view: CardsHubView, instance_id: int) -> None:
        super().__init__()
        self._view = view
        self._instance_id = instance_id
        self.price = discord.ui.TextInput(
            label="Price in goonbux",
            placeholder="1000",
            max_length=12,
        )
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.price.value.strip().replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            await interaction.response.send_message("Enter a valid price.", ephemeral=True)
            return
        _, err = await self._view.cog.bot.db.list_card_on_market(
            self._view.user_id, self._view.guild_id, self._instance_id, value,
        )
        errors = {
            "invalid_price": "Price must be greater than 0.",
            "not_found": "Card not found.",
            "locked": "That copy is listed or in a trade.",
        }
        if err:
            await interaction.response.send_message(errors.get(err, "Could not list."), ephemeral=True)
            return
        self._view.tab = "market"
        await self._view.refresh(interaction)


class CardsHubView(discord.ui.View):
    def __init__(
        self,
        cog: commands.Cog,
        guild_id: int,
        user_id: int,
        *,
        tab: str = "binder",
    ) -> None:
        super().__init__(timeout=180.0)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.tab = tab
        self.set_id: str | None = None
        self.rarity: str | None = None
        self.page = 0
        self.selected_instance_id: int | None = None
        self.selected_listing_id: int | None = None
        self.note: str | None = None
        self.hunt_set_id: str | None = None
        self.pending_extras_confirm = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your GoonCards panel.", ephemeral=True)
            return False
        return True

    def _add_binder_buttons(self, page_count: int) -> None:
        prev_btn = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary, row=3, disabled=self.page <= 0)
        next_btn = discord.ui.Button(
            label="Next", style=discord.ButtonStyle.secondary, row=3, disabled=self.page >= page_count - 1,
        )
        inspect_btn = discord.ui.Button(label="Inspect", style=discord.ButtonStyle.primary, row=3)
        fav_btn = discord.ui.Button(label="Favorite", style=discord.ButtonStyle.success, row=4)
        sell_btn = discord.ui.Button(label="Sell copy", style=discord.ButtonStyle.danger, row=4)
        extras_btn = discord.ui.Button(
            label="Confirm extras" if self.pending_extras_confirm else "Sell extras",
            style=discord.ButtonStyle.danger,
            row=4,
        )

        async def prev_cb(interaction: discord.Interaction) -> None:
            self.page = max(0, self.page - 1)
            await self.refresh(interaction)

        async def next_cb(interaction: discord.Interaction) -> None:
            self.page += 1
            await self.refresh(interaction)

        async def inspect_cb(interaction: discord.Interaction) -> None:
            await self._inspect(interaction)

        async def fav_cb(interaction: discord.Interaction) -> None:
            if self.selected_instance_id is None:
                await interaction.response.send_message("Select a card first.", ephemeral=True)
                return
            ok = await self.cog.bot.db.set_favorite_card(
                self.user_id, self.guild_id, self.selected_instance_id,
            )
            self.note = "Favorite updated." if ok else "Could not favorite that copy."
            await self.refresh(interaction)

        async def sell_cb(interaction: discord.Interaction) -> None:
            if self.selected_instance_id is None:
                await interaction.response.send_message("Select a card first.", ephemeral=True)
                return
            row = await self.cog.bot.db.get_card_instance(self.selected_instance_id, self.guild_id)
            if row is None or int(row["user_id"]) != self.user_id:
                await interaction.response.send_message("Card not found.", ephemeral=True)
                return
            card_id = str(row["card_id"])
            copies = await self.cog.bot.db.count_owned_copies(
                self.user_id, self.guild_id, card_id,
            )
            if copies <= 1:
                defn = card_by_id(card_id)
                name = defn.name if defn else card_id
                await interaction.response.send_message(
                    f"That's your last **{name}**. Selling it would drop it from your dex. "
                    "Sell extras only dumps duplicates.",
                    ephemeral=True,
                )
                return
            self.pending_extras_confirm = False
            mult = await _sell_mult(self.cog, self.guild_id)
            result = await self.cog.bot.db.sell_instances_to_npc(
                self.user_id, self.guild_id, [self.selected_instance_id], sell_mult=mult,
            )
            if result["error"]:
                await interaction.response.send_message("That copy cannot be sold.", ephemeral=True)
                return
            self.selected_instance_id = None
            self.note = f"Sold for {fmt_amount(float(result['payout']))}."
            await self.refresh(interaction)

        async def extras_cb(interaction: discord.Interaction) -> None:
            mult = await _sell_mult(self.cog, self.guild_id)
            if not self.pending_extras_confirm:
                preview = await self.cog.bot.db.preview_extra_copies_to_npc(
                    self.user_id, self.guild_id, sell_mult=mult,
                )
                if int(preview["sold"]) <= 0:
                    await interaction.response.send_message("No extra copies to sell.", ephemeral=True)
                    return
                self.pending_extras_confirm = True
                self.note = (
                    f"Sell **{preview['sold']}** extra"
                    f"{'s' if int(preview['sold']) != 1 else ''} "
                    f"for {fmt_amount(float(preview['payout']))}? "
                    "Click **Confirm extras** to dump duplicates (lowest prints stay)."
                )
                await self.refresh(interaction)
                return
            self.pending_extras_confirm = False
            result = await self.cog.bot.db.sell_extra_copies_to_npc(
                self.user_id, self.guild_id, sell_mult=mult,
            )
            if result["error"] or int(result["sold"]) <= 0:
                await interaction.response.send_message("No extra copies to sell.", ephemeral=True)
                return
            self.note = (
                f"Sold **{result['sold']}** extra{'s' if int(result['sold']) != 1 else ''} "
                f"for {fmt_amount(float(result['payout']))}."
            )
            await self.refresh(interaction)

        prev_btn.callback = prev_cb
        next_btn.callback = next_cb
        inspect_btn.callback = inspect_cb
        fav_btn.callback = fav_cb
        sell_btn.callback = sell_cb
        extras_btn.callback = extras_cb
        for item in (prev_btn, next_btn, inspect_btn, fav_btn, sell_btn, extras_btn):
            self.add_item(item)

    def _add_pack_buttons(self) -> None:
        buy_btn = discord.ui.Button(label="Buy pack", style=discord.ButtonStyle.success, row=1)
        pull_btn = discord.ui.Button(label="Free pull", style=discord.ButtonStyle.primary, row=1)

        async def buy_cb(interaction: discord.Interaction) -> None:
            result = await self.cog.bot.db.open_card_pack(self.user_id, self.guild_id)
            if result["error"] == "insufficient_funds":
                await interaction.response.send_message(
                    f"Need {fmt_amount(float(result['price']))} for a pack.",
                    ephemeral=True,
                )
                return
            granted = result.get("granted") or []
            self.note = (
                "Opened a pack:\n"
                + "\n".join(format_card_line(row) for row in granted)
            ) if granted else "Empty pack."
            await self.refresh(interaction)
            await announce_granted_cards(
                self.cog.bot,
                interaction_channel(interaction),
                user=interaction.user,
                granted_rows=granted,
                title="Pack opened",
                content=f"{interaction.user.mention} opened a GoonCards pack.",
            )

        async def pull_cb(interaction: discord.Interaction) -> None:
            result = await self.cog.bot.db.try_card_pull(self.user_id, self.guild_id)
            if result["error"] == "cooldown":
                remaining = int(float(result["remaining"]))
                minutes = remaining // 60
                seconds = remaining % 60
                await interaction.response.send_message(
                    f"Pull is cooling down — **{minutes}m {seconds}s** left.",
                    ephemeral=True,
                )
                return
            granted = result.get("granted") or {}
            defn = card_by_id(str(granted.get("card_id", "")))
            if defn is None:
                await interaction.response.send_message("Pull failed.", ephemeral=True)
                return
            self.note = "Free pull:\n" + format_card_line(granted)
            await self.refresh(interaction)
            await announce_granted_cards(
                self.cog.bot,
                interaction_channel(interaction),
                user=interaction.user,
                granted_rows=[granted],
                title="Free pull",
                content=f"{interaction.user.mention} hit a free GoonCards pull.",
            )

        buy_btn.callback = buy_cb
        pull_btn.callback = pull_cb
        self.add_item(buy_btn)
        self.add_item(pull_btn)

    def _add_market_buttons(self) -> None:
        buy_btn = discord.ui.Button(label="Buy listing", style=discord.ButtonStyle.success, row=3)
        cancel_btn = discord.ui.Button(label="Cancel mine", style=discord.ButtonStyle.secondary, row=3)

        async def buy_cb(interaction: discord.Interaction) -> None:
            if self.selected_listing_id is None:
                await interaction.response.send_message("Pick a listing first.", ephemeral=True)
                return
            result = await self.cog.bot.db.buy_card_listing(
                self.user_id, self.guild_id, self.selected_listing_id,
            )
            err = result.get("error")
            messages = {
                "not_found": "Listing gone.",
                "own_listing": "That's your listing.",
                "insufficient_funds": f"Need {fmt_amount(float(result.get('total') or 0))}.",
            }
            if err:
                await interaction.response.send_message(messages.get(str(err), "Buy failed."), ephemeral=True)
                return
            defn = card_by_id(str(result["card_id"]))
            name = defn.name if defn else result["card_id"]
            self.selected_listing_id = None
            self.note = (
                f"Bought **{name}** #{int(result['print_number']):04d} "
                f"for {fmt_amount(float(result['total']))}."
            )
            await self.refresh(interaction)
            await announce_granted_cards(
                self.cog.bot,
                interaction_channel(interaction),
                user=interaction.user,
                granted_rows=[result],
                title="Market buy",
                content=(
                    f"{interaction.user.mention} bought **{name}** "
                    f"#{int(result['print_number']):04d} "
                    f"for {fmt_amount(float(result['total']))}."
                ),
            )

        async def cancel_cb(interaction: discord.Interaction) -> None:
            if self.selected_listing_id is None:
                await interaction.response.send_message("Pick your listing first.", ephemeral=True)
                return
            err = await self.cog.bot.db.cancel_card_listing(
                self.user_id, self.guild_id, self.selected_listing_id,
            )
            if err:
                await interaction.response.send_message("Could not cancel that listing.", ephemeral=True)
                return
            self.selected_listing_id = None
            self.note = "Listing cancelled."
            await self.refresh(interaction)

        buy_btn.callback = buy_cb
        cancel_btn.callback = cancel_cb
        self.add_item(buy_btn)
        self.add_item(cancel_btn)

    async def _inspect(self, interaction: discord.Interaction) -> None:
        if self.selected_instance_id is None:
            await interaction.response.send_message("Select a card first.", ephemeral=True)
            return
        row = await self.cog.bot.db.get_card_instance(self.selected_instance_id, self.guild_id)
        if row is None or int(row["user_id"]) != self.user_id:
            await interaction.response.send_message("Card not found.", ephemeral=True)
            return
        defn = card_by_id(str(row["card_id"]))
        if defn is None:
            await interaction.response.send_message("Unknown card.", ephemeral=True)
            return
        png = render_card_png(defn, print_number=int(row["print_number"]))
        embed = branded_embed(
            panel_title(defn.name),
            description=f"{defn.description}\n\n{defn.set_name} · {defn.rarity_label}",
            color=discord.Color(RARITY_COLOR[defn.rarity]),
        )
        embed.set_image(url="attachment://inspect.png")
        file = discord.File(io.BytesIO(png), filename="inspect.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    async def build_payload(self) -> tuple[discord.Embed, discord.File | None]:
        self.clear_items()
        self.add_item(CardsTabSelect(self.tab))
        note = self.note
        self.note = None
        if self.tab == "binder":
            return await self._build_binder(note)
        if self.tab == "packs":
            return await self._build_packs(note)
        if self.tab == "market":
            return await self._build_market(note)
        return await self._build_collection(note), None

    async def _build_binder(self, note: str | None) -> tuple[discord.Embed, discord.File | None]:
        groups = await self.cog.bot.db.binder_grouped(
            self.user_id, self.guild_id, set_id=self.set_id, rarity=self.rarity,
        )
        total, unique = await self.cog.bot.db.count_owned_cards(self.user_id, self.guild_id)
        page_count = max(1, (len(groups) + BINDER_PER_PAGE - 1) // BINDER_PER_PAGE)
        self.page = min(self.page, page_count - 1)
        start = self.page * BINDER_PER_PAGE
        page_groups = groups[start:start + BINDER_PER_PAGE]
        self.add_item(BinderFilterSelect(_filter_key(self.set_id, self.rarity)))
        self.add_item(BinderCardSelect(page_groups, self.selected_instance_id))
        self._add_binder_buttons(page_count)
        entries = []
        for bucket in page_groups:
            defn = card_by_id(str(bucket["card_id"]))
            if defn is None:
                continue
            entries.append((defn, int(bucket["lowest_print"]), int(bucket["count"])))
        png = render_binder_page(entries)
        embed = branded_embed(
            panel_title("GoonCards Binder"),
            description=(
                f"**{unique}** / **{len(CARD_DEFINITIONS)}** unique · "
                f"**{total}** copies · page {self.page + 1}/{page_count}"
            ),
        )
        if note:
            embed.add_field(name="Update", value=note, inline=False)
        embed.set_image(url="attachment://binder.png")
        return embed, discord.File(io.BytesIO(png), filename="binder.png")

    async def _build_packs(self, note: str | None) -> tuple[discord.Embed, discord.File | None]:
        self._add_pack_buttons()
        price = await self.cog.bot.db.get_config_value(self.guild_id, "card_pack_price")
        size = int(await self.cog.bot.db.get_config_value(self.guild_id, "card_pack_size"))
        cooldown = int(await self.cog.bot.db.get_config_value(self.guild_id, "card_pull_cooldown_seconds"))
        wallet = await self.cog.bot.db.get_balance(self.user_id, self.guild_id)
        remaining = await self.cog.bot.db.card_pull_remaining(self.user_id, self.guild_id)
        if remaining > 0:
            minutes = int(remaining) // 60
            seconds = int(remaining) % 60
            pull_line = f"Free pull ready in **{minutes}m {seconds}s**."
        else:
            pull_line = "Free pull is **ready**."
        embed = branded_embed(
            panel_title("GoonCards Packs"),
            description=(
                f"Booster packs are **{size}** cards. {pull_line}\n"
                f"Pack price **{fmt_amount(price)}** · your pocket **{fmt_amount(wallet)}**\n"
                f"Pull cooldown **{cooldown // 60}m**.\n"
                f"Odds: {format_pack_odds()}"
            ),
        )
        if note:
            embed.add_field(name="Update", value=note[:1024], inline=False)
        return embed, None

    async def _build_market(self, note: str | None) -> tuple[discord.Embed, discord.File | None]:
        listings = await self.cog.bot.db.list_card_market(self.guild_id, limit=20)
        mine = await self.cog.bot.db.list_user_card_listings(self.user_id, self.guild_id)
        tradeable = await self.cog.bot.db.list_tradeable_card_instances(self.user_id, self.guild_id)
        self.add_item(MarketListingSelect(listings, self.selected_listing_id))
        self.add_item(ListCardSelect(tradeable))
        self._add_market_buttons()
        lines = []
        for row in listings[:8]:
            defn = card_by_id(str(row["card_id"]))
            name = defn.name if defn else str(row["card_id"])
            emoji = defn.emoji if defn else "🃏"
            lines.append(
                f"{emoji} **{name}** #{int(row['print_number']):04d} — "
                f"{fmt_amount(float(row['price']))} · <@{int(row['seller_id'])}>"
            )
        embed = branded_embed(
            panel_title("GoonCards Market"),
            description="\n".join(lines) if lines else "No listings. List a copy from the menu.",
        )
        embed.add_field(name="Your listings", value=str(len(mine)), inline=True)
        if note:
            embed.add_field(name="Update", value=note, inline=False)
        return embed, None

    async def _build_collection(self, note: str | None) -> discord.Embed:
        owned = await self.cog.bot.db.collection_owned_ids(self.user_id, self.guild_id)
        completed = await self.cog.bot.db.list_completed_card_sets(self.user_id, self.guild_id)
        set_reward = float(await self.cog.bot.db.get_config_value(
            self.guild_id, "card_set_complete_reward",
        ))
        lines = []
        finished = 0
        for set_id in SET_ORDER:
            cards = [c for c in CARD_DEFINITIONS.values() if c.set_id == set_id]
            have = sum(1 for c in cards if c.card_id in owned)
            bar = "█" * have + "░" * (len(cards) - have)
            mark = "✅" if have >= len(cards) else SET_EMOJI[set_id]
            extra = ""
            if have >= len(cards):
                finished += 1
                extra = " · complete"
                if set_id in completed and set_reward > 0:
                    extra += f" ({fmt_amount(set_reward)})"
            lines.append(f"{mark} **{SET_LABELS[set_id]}** `{bar}` {have}/{len(cards)}{extra}")
        if self.hunt_set_id is None:
            self.hunt_set_id = SET_ORDER[0]
            for set_id in SET_ORDER:
                set_cards = [c for c in CARD_DEFINITIONS.values() if c.set_id == set_id]
                if any(c.card_id not in owned for c in set_cards):
                    self.hunt_set_id = set_id
                    break
        self.add_item(CollectionHuntSelect(self.hunt_set_id))
        holes = [
            c for c in CARD_DEFINITIONS.values()
            if c.set_id == self.hunt_set_id and c.card_id not in owned
        ]
        hunt_name = SET_LABELS[self.hunt_set_id] if self.hunt_set_id in SET_LABELS else self.hunt_set_id
        if holes:
            hunt_value = ", ".join(f"{c.emoji} {c.name}" for c in holes)
        else:
            hunt_value = "Complete — nothing missing."
        embed = branded_embed(
            panel_title("GoonCards Collection"),
            description="\n".join(lines),
        )
        embed.add_field(
            name="Dex",
            value=f"**{len(owned)}** / **{len(CARD_DEFINITIONS)}** unique · **{finished}** sets done",
            inline=True,
        )
        embed.add_field(
            name="Earn more",
            value=(
                "First **two** on a group session get a card. Trivia winners get one. "
                f"Finish a set for **{fmt_amount(set_reward)}** (once)."
            ),
            inline=False,
        )
        embed.add_field(
            name=f"Still hunting · {hunt_name}",
            value=hunt_value[:1024],
            inline=False,
        )
        if note:
            embed.add_field(name="Update", value=note, inline=False)
        return embed

    async def refresh(self, interaction: discord.Interaction) -> None:
        embed, attachment = await self.build_payload()
        kwargs: dict[str, Any] = {"embed": embed, "view": self}
        if attachment is not None:
            kwargs["attachments"] = [attachment]
        else:
            kwargs["attachments"] = []
        if interaction.response.is_done():
            await interaction.edit_original_response(**kwargs)
        else:
            await interaction.response.edit_message(**kwargs)


async def send_cards_hub(
    cog: commands.Cog,
    interaction: discord.Interaction,
    *,
    tab: str = "binder",
) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message(guild_only_message(), ephemeral=True)
        return
    view = CardsHubView(cog, interaction.guild_id, interaction.user.id, tab=tab)
    try:
        embed, attachment = await view.build_payload()
    except Exception:
        logger.exception("Failed to open GoonCards hub for user %s", interaction.user.id)
        msg = "Could not open GoonCards. Try again in a moment."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return
    files = [attachment] if attachment is not None else []
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, files=files, ephemeral=True)
        return
    if interaction.type == discord.InteractionType.component:
        kwargs: dict[str, object] = {"embed": embed, "view": view, "content": None}
        if attachment is not None:
            kwargs["attachments"] = [attachment]
        else:
            kwargs["attachments"] = []
        await interaction.response.edit_message(**kwargs)
        return
    await interaction.response.send_message(
        embed=embed, view=view, files=files, ephemeral=True,
    )
