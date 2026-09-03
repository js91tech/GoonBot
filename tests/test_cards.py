"""Tests for GoonCards catalog, packs, market, and trade escrow."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import Database
from utils.card_ai import maybe_backfill_missing_portrait, portrait_path
from utils.card_canvas import (
    BINDER_PER_PAGE,
    load_portrait,
    render_binder_page,
    render_card_png,
    render_pack_reveal,
    render_procedural_portrait,
    write_procedural_portrait,
)
from utils.cards import (
    CARD_DEFINITIONS,
    PACK_WEIGHTS,
    SET_ORDER,
    card_by_id,
    cards_for_rarity,
    npc_sell_value,
    rarity_counts,
    roll_pack,
)


class CardCatalogTests(unittest.TestCase):
    def test_launch_catalog_is_48(self) -> None:
        self.assertEqual(len(CARD_DEFINITIONS), 48)
        self.assertEqual(len({c.card_id for c in CARD_DEFINITIONS.values()}), 48)

    def test_sets_are_eight_each(self) -> None:
        for set_id in SET_ORDER:
            count = sum(1 for c in CARD_DEFINITIONS.values() if c.set_id == set_id)
            self.assertEqual(count, 8, set_id)

    def test_rarity_split(self) -> None:
        self.assertEqual(
            rarity_counts(),
            {
                "common": 18,
                "uncommon": 12,
                "rare": 6,
                "epic": 6,
                "legendary": 4,
                "mythic": 2,
            },
        )

    def test_pack_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(sum(PACK_WEIGHTS.values()), 1.0)

    def test_every_rarity_has_cards(self) -> None:
        for rarity in PACK_WEIGHTS:
            self.assertGreater(len(cards_for_rarity(rarity)), 0, rarity)

    def test_roll_pack_size(self) -> None:
        import random

        pack = roll_pack(3, random.Random(0))
        self.assertEqual(len(pack), 3)

    def test_npc_value_scales(self) -> None:
        card = next(c for c in CARD_DEFINITIONS.values() if c.rarity == "common")
        self.assertGreater(npc_sell_value(card, 0.5), 0)

    def test_portrait_prompt_present(self) -> None:
        for card in CARD_DEFINITIONS.values():
            self.assertIn("portrait bust", card.portrait_prompt)
            self.assertIn("no watermark", card.portrait_prompt)


class CardCanvasTests(unittest.TestCase):
    def test_procedural_and_framed_png(self) -> None:
        card = card_by_id("card_velvet_vixen")
        assert card is not None
        portrait = render_procedural_portrait(card)
        self.assertEqual(portrait.size[0], portrait.size[1])
        png = render_card_png(card, print_number=7)
        self.assertTrue(png.startswith(b"\x89PNG"))
        binder = render_binder_page([(card, 1, 2)])
        self.assertTrue(binder.startswith(b"\x89PNG"))
        pack = render_pack_reveal([card], [1])
        self.assertTrue(pack.startswith(b"\x89PNG"))

    def test_load_portrait_fallback(self) -> None:
        card = card_by_id("card_hostess")
        assert card is not None
        path = portrait_path(card.card_id)
        existed = path.is_file()
        if existed:
            img = load_portrait(card)
            self.assertGreater(img.size[0], 0)
        else:
            img = load_portrait(card)
            self.assertGreater(img.size[0], 0)

    def test_write_procedural_roundtrip(self) -> None:
        card = card_by_id("card_talent")
        assert card is not None
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "card.png"
            write_procedural_portrait(card, dest)
            self.assertTrue(dest.is_file())

    def test_binder_page_size(self) -> None:
        self.assertEqual(BINDER_PER_PAGE, 6)


class CardAiTests(unittest.IsolatedAsyncioTestCase):
    async def test_backfill_skips_unknown(self) -> None:
        self.assertFalse(await maybe_backfill_missing_portrait("not_a_card"))

    async def test_backfill_noop_without_key(self) -> None:
        with patch("utils.card_ai.config.AI_API_KEY", ""):
            card = next(iter(CARD_DEFINITIONS))
            path = portrait_path(card)
            if path.is_file():
                self.assertTrue(await maybe_backfill_missing_portrait(card))
            else:
                self.assertFalse(await maybe_backfill_missing_portrait(card))


class CardDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        self.guild_id = 9
        self.user_a = 101
        self.user_b = 202
        await self.db.ensure_user(self.user_a, self.guild_id)
        await self.db.ensure_user(self.user_b, self.guild_id)

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_grant_print_numbers_increment(self) -> None:
        first = await self.db.grant_card(self.user_a, self.guild_id, "card_hostess")
        second = await self.db.grant_card(self.user_a, self.guild_id, "card_hostess")
        assert first is not None and second is not None
        self.assertEqual(first["print_number"], 1)
        self.assertEqual(second["print_number"], 2)
        total, unique = await self.db.count_owned_cards(self.user_a, self.guild_id)
        self.assertEqual(total, 2)
        self.assertEqual(unique, 1)

    async def test_museum_tracks_uniques(self) -> None:
        await self.db.grant_card(self.user_a, self.guild_id, "card_hostess")
        await self.db.grant_card(self.user_a, self.guild_id, "card_hostess")
        await self.db.grant_card(self.user_a, self.guild_id, "card_velvet_vixen")
        counts = await self.db.get_museum_counts(self.user_a, self.guild_id)
        self.assertEqual(int(counts.get("cards", 0)), 2)

    async def test_open_pack_requires_funds(self) -> None:
        result = await self.db.open_card_pack(self.user_a, self.guild_id)
        self.assertEqual(result["error"], "insufficient_funds")
        await self.db.credit_wallet(self.user_a, self.guild_id, 50_000.0, apply_bonuses=False)
        result = await self.db.open_card_pack(self.user_a, self.guild_id)
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["granted"]), 3)

    async def test_npc_sell_and_locked_copy(self) -> None:
        granted = await self.db.grant_card(self.user_a, self.guild_id, "card_hostess")
        assert granted is not None
        listing_id, err = await self.db.list_card_on_market(
            self.user_a, self.guild_id, int(granted["instance_id"]), 500.0,
        )
        self.assertIsNone(err)
        locked = await self.db.sell_instances_to_npc(
            self.user_a, self.guild_id, [int(granted["instance_id"])], sell_mult=0.5,
        )
        self.assertEqual(locked["error"], "none_sellable")
        await self.db.cancel_card_listing(self.user_a, self.guild_id, int(listing_id))
        sold = await self.db.sell_instances_to_npc(
            self.user_a, self.guild_id, [int(granted["instance_id"])], sell_mult=0.5,
        )
        self.assertIsNone(sold["error"])
        self.assertEqual(sold["sold"], 1)

    async def test_market_buy_moves_card_and_taxes_house(self) -> None:
        granted = await self.db.grant_card(self.user_a, self.guild_id, "card_tomass")
        assert granted is not None
        listing_id, err = await self.db.list_card_on_market(
            self.user_a, self.guild_id, int(granted["instance_id"]), 1000.0,
        )
        self.assertIsNone(err)
        await self.db.credit_wallet(self.user_b, self.guild_id, 2000.0, apply_bonuses=False)
        result = await self.db.buy_card_listing(self.user_b, self.guild_id, int(listing_id))
        self.assertIsNone(result["error"])
        inst = await self.db.get_card_instance(int(granted["instance_id"]), self.guild_id)
        assert inst is not None
        self.assertEqual(int(inst["user_id"]), self.user_b)
        pot = await self.db.get_house_pot(self.guild_id)
        self.assertGreater(pot, 0)

    async def test_sell_extras_keeps_one(self) -> None:
        for _ in range(3):
            await self.db.grant_card(self.user_a, self.guild_id, "card_edge")
        result = await self.db.sell_extra_copies_to_npc(
            self.user_a, self.guild_id, sell_mult=0.5,
        )
        self.assertEqual(result["sold"], 2)
        total, unique = await self.db.count_owned_cards(self.user_a, self.guild_id)
        self.assertEqual(total, 1)
        self.assertEqual(unique, 1)

    async def test_pull_cooldown(self) -> None:
        first = await self.db.try_card_pull(self.user_a, self.guild_id, now=1_000.0)
        self.assertIsNone(first["error"])
        second = await self.db.try_card_pull(self.user_a, self.guild_id, now=1_010.0)
        self.assertEqual(second["error"], "cooldown")

    async def test_trade_escrow_cards(self) -> None:
        granted = await self.db.grant_card(self.user_a, self.guild_id, "card_fixer")
        assert granted is not None
        await self.db.credit_wallet(self.user_a, self.guild_id, 100.0, apply_bonuses=False)
        trade_id, err = await self.db.create_pending_trade(
            self.user_a,
            self.user_b,
            self.guild_id,
            nuggets=0.0,
            drugs={},
            gear_instance_ids=[],
            card_instance_ids=[int(granted["instance_id"])],
        )
        self.assertIsNone(err)
        inst = await self.db.get_card_instance(int(granted["instance_id"]), self.guild_id)
        assert inst is not None
        self.assertEqual(int(inst["escrow_trade_id"]), trade_id)
        locked_sell = await self.db.sell_instances_to_npc(
            self.user_a, self.guild_id, [int(granted["instance_id"])], sell_mult=0.5,
        )
        self.assertEqual(locked_sell["error"], "none_sellable")
        resolve = await self.db.resolve_trade(int(trade_id), self.guild_id, self.user_b, "accept")
        self.assertIsNone(resolve)
        inst = await self.db.get_card_instance(int(granted["instance_id"]), self.guild_id)
        assert inst is not None
        self.assertEqual(int(inst["user_id"]), self.user_b)
        self.assertTrue(inst["escrow_trade_id"] in (None, 0))

    async def test_trade_decline_returns_card(self) -> None:
        granted = await self.db.grant_card(self.user_a, self.guild_id, "card_host")
        assert granted is not None
        trade_id, err = await self.db.create_pending_trade(
            self.user_a,
            self.user_b,
            self.guild_id,
            nuggets=0.0,
            drugs={},
            gear_instance_ids=[],
            card_instance_ids=[int(granted["instance_id"])],
        )
        self.assertIsNone(err)
        await self.db.resolve_trade(int(trade_id), self.guild_id, self.user_b, "decline")
        inst = await self.db.get_card_instance(int(granted["instance_id"]), self.guild_id)
        assert inst is not None
        self.assertEqual(int(inst["user_id"]), self.user_a)
        self.assertTrue(inst["escrow_trade_id"] in (None, 0))

    async def test_favorite_and_cannot_buy_own_listing(self) -> None:
        granted = await self.db.grant_card(self.user_a, self.guild_id, "card_ruin")
        assert granted is not None
        self.assertTrue(
            await self.db.set_favorite_card(
                self.user_a, self.guild_id, int(granted["instance_id"]),
            ),
        )
        listing_id, err = await self.db.list_card_on_market(
            self.user_a, self.guild_id, int(granted["instance_id"]), 50.0,
        )
        self.assertIsNone(err)
        result = await self.db.buy_card_listing(self.user_a, self.guild_id, int(listing_id))
        self.assertEqual(result["error"], "own_listing")
