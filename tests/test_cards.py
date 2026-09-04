"""Tests for GoonCards catalog, packs, market, and trade escrow."""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np

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
from utils.card_announce import (
    announce_granted_cards,
    build_card_event_payload,
    cards_from_granted,
)
from utils.cards import (
    CARD_DEFINITIONS,
    PACK_WEIGHTS,
    SET_ORDER,
    card_by_id,
    cards_for_rarity,
    cards_for_set,
    format_card_drop,
    format_pack_odds,
    npc_sell_value,
    rarity_counts,
    roll_card_prefer_unowned,
    roll_pack,
)


class CardCatalogTests(unittest.TestCase):
    def test_launch_catalog_is_148(self) -> None:
        self.assertEqual(len(CARD_DEFINITIONS), 148)
        self.assertEqual(len({c.card_id for c in CARD_DEFINITIONS.values()}), 148)

    def test_original_48_ids_untouched(self) -> None:
        from utils.cards import ORIGINAL_CARD_IDS

        self.assertEqual(len(ORIGINAL_CARD_IDS), 48)
        self.assertTrue(ORIGINAL_CARD_IDS <= set(CARD_DEFINITIONS))
        original = [CARD_DEFINITIONS[cid] for cid in ORIGINAL_CARD_IDS]
        self.assertEqual(
            {
                "common": sum(1 for c in original if c.rarity == "common"),
                "uncommon": sum(1 for c in original if c.rarity == "uncommon"),
                "rare": sum(1 for c in original if c.rarity == "rare"),
                "epic": sum(1 for c in original if c.rarity == "epic"),
                "legendary": sum(1 for c in original if c.rarity == "legendary"),
                "mythic": sum(1 for c in original if c.rarity == "mythic"),
            },
            {
                "common": 18,
                "uncommon": 12,
                "rare": 6,
                "epic": 6,
                "legendary": 4,
                "mythic": 2,
            },
        )

    def test_sets_match_catalog_structure(self) -> None:
        from utils.cards import ORIGINAL_CARD_IDS

        original_sets = ("velvet", "floor", "personas", "hustle", "lounge", "reliquary")
        expansion_sets = (
            "edge", "booth", "heat", "kink", "aftercare",
            "cabaret", "peek", "denial", "worship", "encore",
        )
        self.assertEqual(SET_ORDER[:6], original_sets)
        self.assertEqual(SET_ORDER[6:], expansion_sets)
        for set_id in original_sets:
            count = sum(1 for c in CARD_DEFINITIONS.values() if c.set_id == set_id)
            self.assertEqual(count, 8, set_id)
        for set_id in expansion_sets:
            count = sum(1 for c in CARD_DEFINITIONS.values() if c.set_id == set_id)
            self.assertEqual(count, 10, set_id)
        self.assertEqual(len(CARD_DEFINITIONS) - len(ORIGINAL_CARD_IDS), 100)

    def test_rarity_split(self) -> None:
        self.assertEqual(
            rarity_counts(),
            {
                "common": 56,
                "uncommon": 37,
                "rare": 20,
                "epic": 18,
                "legendary": 11,
                "mythic": 6,
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

    def test_prefer_unowned_fills_the_last_gap(self) -> None:
        import random

        missing = "card_velvet_vixen"
        owned = {cid for cid in CARD_DEFINITIONS if cid != missing}
        card = roll_card_prefer_unowned(owned, random.Random(1))
        self.assertEqual(card.card_id, missing)

    def test_format_card_drop(self) -> None:
        line = format_card_drop(
            {
                "card_id": "card_hostess",
                "print_number": 7,
                "set_complete": "velvet",
                "set_reward": 15000,
            }
        )
        self.assertIn("Lounge Hostess", line)
        self.assertIn("#0007", line)
        self.assertIn("15,000", line)

    def test_format_card_drop_marks_new_and_duplicate(self) -> None:
        fresh = format_card_drop(
            {"card_id": "card_hostess", "print_number": 1, "new_unique": True},
        )
        self.assertIn("**NEW**", fresh)
        self.assertNotIn("duplicate", fresh)
        dupe = format_card_drop(
            {"card_id": "card_hostess", "print_number": 2, "new_unique": False},
        )
        self.assertIn("duplicate", dupe)
        self.assertNotIn("**NEW**", dupe)

    def test_format_pack_odds_lists_rarities(self) -> None:
        odds = format_pack_odds()
        self.assertIn("Common 55%", odds)
        self.assertIn("Mythic 0.2%", odds)

    def test_public_card_payload_attaches_portrait(self) -> None:
        card = card_by_id("card_hostess")
        assert card is not None
        embed, file, name = build_card_event_payload(
            title="Free pull", cards=[card], prints=[7],
        )
        self.assertEqual(name, "card.png")
        self.assertEqual(file.filename, "card.png")
        self.assertEqual(embed.image.url, "attachment://card.png")
        self.assertIn("Lounge Hostess", embed.description or "")
        self.assertIn("#0007", embed.description or "")
        file.close()

    def test_public_card_payload_marks_new_unique(self) -> None:
        card = card_by_id("card_hostess")
        assert card is not None
        embed, file, _name = build_card_event_payload(
            title="Free pull",
            cards=[card],
            prints=[7],
            granted_rows=[{"card_id": "card_hostess", "print_number": 7, "new_unique": True}],
        )
        self.assertIn("**NEW**", embed.description or "")
        file.close()

    def test_public_pack_payload_uses_pack_sheet(self) -> None:
        hostess = card_by_id("card_hostess")
        edge = card_by_id("card_edge")
        assert hostess is not None and edge is not None
        embed, file, name = build_card_event_payload(
            title="Pack opened",
            cards=[hostess, edge],
            prints=[1, 2],
        )
        self.assertEqual(name, "pack.png")
        self.assertEqual(embed.image.url, "attachment://pack.png")
        self.assertIn("Lounge Hostess", embed.description or "")
        self.assertIn("On the Edge", embed.description or "")
        file.close()

    def test_cards_from_granted_skips_unknown(self) -> None:
        cards, prints = cards_from_granted(
            [
                {"card_id": "card_hostess", "print_number": 3},
                {"card_id": "not_a_card", "print_number": 1},
            ]
        )
        self.assertEqual([c.card_id for c in cards], ["card_hostess"])
        self.assertEqual(prints, [3])

    def test_npc_value_scales(self) -> None:
        card = next(c for c in CARD_DEFINITIONS.values() if c.rarity == "common")
        self.assertGreater(npc_sell_value(card, 0.5), 0)

    def test_portrait_prompt_present(self) -> None:
        for card in CARD_DEFINITIONS.values():
            self.assertIn("portrait bust", card.portrait_prompt)
            self.assertIn("no watermark", card.portrait_prompt)


class CardAnnounceTests(unittest.IsolatedAsyncioTestCase):
    async def test_announce_posts_to_channel_not_ephemeral(self) -> None:
        user = SimpleNamespace(id=1, mention="<@1>")
        with patch("utils.card_announce.send_channel_message", new_callable=AsyncMock) as send:
            send.return_value = object()
            await announce_granted_cards(
                SimpleNamespace(),
                object(),
                user=user,  # type: ignore[arg-type]
                granted_rows=[{"card_id": "card_hostess", "print_number": 1}],
                title="Pack opened",
                content="<@1> opened a GoonCards pack.",
            )
        send.assert_awaited_once()
        kwargs = send.await_args.kwargs
        self.assertIn("embed", kwargs)
        self.assertIn("file", kwargs)
        self.assertNotIn("ephemeral", kwargs)
        self.assertTrue(kwargs["allowed_mentions"].users)
        kwargs["file"].close()


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

    def test_portraits_are_unique_original_plates(self) -> None:
        from utils.card_art import CARD_RECIPES, recipe_fingerprint

        self.assertEqual(set(CARD_RECIPES), set(CARD_DEFINITIONS))
        fingerprints = {recipe_fingerprint(CARD_RECIPES[cid]) for cid in CARD_DEFINITIONS}
        self.assertEqual(len(fingerprints), 148)
        hashes: set[bytes] = set()
        for card in CARD_DEFINITIONS.values():
            portrait = render_procedural_portrait(card)
            self.assertEqual(portrait.size, (512, 512), card.card_id)
            hashes.add(hashlib.sha256(portrait.tobytes()).digest())
        self.assertEqual(len(hashes), 148)

    def test_named_cards_are_distinct_from_each_other(self) -> None:
        ids = (
            "card_velvet_vixen",
            "card_tomass",
            "card_freaky_nikki",
            "card_zz_wrath",
            "card_kisses_velvet",
            "card_shadow_velvet",
            "card_hostess",
            "card_house_idol",
        )
        blobs = []
        for card_id in ids:
            img = render_procedural_portrait(CARD_DEFINITIONS[card_id])
            blobs.append(img.tobytes())
        self.assertEqual(len(set(blobs)), len(ids))

    def test_portraits_are_not_copied_boss_files(self) -> None:
        from utils.card_ai import portrait_path as shipped

        boss_dir = Path(__file__).resolve().parent.parent / "assets"
        sources = []
        for rel in (
            "bosses/tomass.png",
            "bosses/zz_wrath.png",
            "bosses/glam/velvet_vixen_mythic.png",
            "bosses/glam/velvet_vixen_shadow.png",
            "brand/goonbot-icon-explicit.png",
            "brand/goonbot-banner-explicit.png",
            "drugs/grow_lab.png",
        ):
            path = boss_dir / rel
            if path.is_file():
                sources.append(path.read_bytes())
        for card_id in CARD_DEFINITIONS:
            dest = shipped(card_id)
            if not dest.is_file():
                continue
            data = dest.read_bytes()
            for source in sources:
                self.assertNotEqual(data, source, card_id)

    def test_renderer_does_not_crop_house_art(self) -> None:
        src = Path(__file__).resolve().parent.parent / "utils" / "card_art.py"
        text = src.read_text()
        self.assertNotIn(".crop(", text)
        self.assertIn("resize((8, 8)", text)
        self.assertIn("Never crops a boss/brand file", text)

    def test_procedural_plates_are_not_cover_crops(self) -> None:
        from PIL import Image

        def ahash(im: Image.Image, size: int = 16) -> np.ndarray:
            gray = im.convert("L").resize((size, size), Image.Resampling.BOX)
            arr = np.asarray(gray, dtype=np.float32)
            return arr > arr.mean()

        root = Path(__file__).resolve().parent.parent / "assets"
        crops: list[tuple[str, np.ndarray]] = []
        for rel in (
            "bosses/tomass.png",
            "bosses/glam/velvet_vixen_mythic.png",
            "brand/goonbot-icon-explicit.png",
            "brand/goonbot-banner-explicit.png",
            "districts/financial.png",
            "districts/industrial.png",
            "drugs/grow_lab.png",
        ):
            path = root / rel
            if not path.is_file():
                continue
            im = Image.open(path).convert("RGB")
            if getattr(im, "n_frames", 1) > 1:
                im.seek(0)
                im = im.convert("RGB")
            w, h = im.size
            side = min(w, h)
            left = (w - side) // 2
            top = max(0, (h - side) // 3)
            crop = im.crop((left, top, left + side, top + side)).resize(
                (512, 512), Image.Resampling.LANCZOS,
            )
            crops.append((rel, ahash(crop)))
        self.assertTrue(crops)
        for card in CARD_DEFINITIONS.values():
            plate = ahash(render_procedural_portrait(card).convert("RGB"))
            for rel, crop in crops:
                dist = int(np.count_nonzero(plate != crop))
                self.assertGreater(
                    dist, 32, f"{card.card_id} aHash too close to cover-crop of {rel} ({dist})",
                )

    def test_load_portrait_fallback(self) -> None:
        card = card_by_id("card_hostess")
        assert card is not None
        img = load_portrait(card)
        self.assertGreater(img.size[0], 0)

    def test_write_procedural_roundtrip(self) -> None:
        card = card_by_id("card_talent")
        assert card is not None
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "card.png"
            write_procedural_portrait(card, dest)
            self.assertTrue(dest.is_file())
            self.assertGreater(dest.stat().st_size, 40_000)

    def test_shipped_portraits_not_tiny_placeholders(self) -> None:
        missing = [cid for cid in CARD_DEFINITIONS if not portrait_path(cid).is_file()]
        if missing:
            self.skipTest(f"portraits not generated yet: {missing[:3]}")
        hashes: set[bytes] = set()
        for card_id in CARD_DEFINITIONS:
            path = portrait_path(card_id)
            self.assertGreater(path.stat().st_size, 40_000, card_id)
            hashes.add(hashlib.sha256(path.read_bytes()).digest())
        self.assertEqual(len(hashes), 148)

    def test_original_shipped_portraits_still_present(self) -> None:
        from utils.cards import ORIGINAL_CARD_IDS

        for card_id in ORIGINAL_CARD_IDS:
            path = portrait_path(card_id)
            self.assertTrue(path.is_file(), card_id)
            self.assertGreater(path.stat().st_size, 40_000, card_id)

    def test_binder_page_size(self) -> None:
        self.assertEqual(BINDER_PER_PAGE, 6)


class CardAiTests(unittest.IsolatedAsyncioTestCase):
    async def test_backfill_skips_unknown(self) -> None:
        self.assertFalse(await maybe_backfill_missing_portrait("not_a_card"))

    async def test_backfill_writes_unique_plate_without_key(self) -> None:
        with patch("utils.card_ai.config.AI_API_KEY", ""):
            card = next(iter(CARD_DEFINITIONS))
            self.assertTrue(await maybe_backfill_missing_portrait(card))
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "missing.png"
                with patch("utils.card_ai.portrait_path", return_value=dest):
                    self.assertTrue(await maybe_backfill_missing_portrait(card))
                self.assertTrue(dest.is_file())
                self.assertGreater(dest.stat().st_size, 40_000)


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
        self.assertTrue(result["new_unique"])

    async def test_sell_extras_keeps_one(self) -> None:
        for _ in range(3):
            await self.db.grant_card(self.user_a, self.guild_id, "card_edge")
        preview = await self.db.preview_extra_copies_to_npc(
            self.user_a, self.guild_id, sell_mult=0.5,
        )
        self.assertEqual(preview["sold"], 2)
        self.assertGreater(preview["payout"], 0)
        result = await self.db.sell_extra_copies_to_npc(
            self.user_a, self.guild_id, sell_mult=0.5,
        )
        self.assertEqual(result["sold"], 2)
        self.assertEqual(result["payout"], preview["payout"])
        total, unique = await self.db.count_owned_cards(self.user_a, self.guild_id)
        self.assertEqual(total, 1)
        self.assertEqual(unique, 1)
        self.assertEqual(
            await self.db.count_owned_copies(self.user_a, self.guild_id, "card_edge"),
            1,
        )

    async def test_pull_cooldown(self) -> None:
        self.assertEqual(
            await self.db.card_pull_remaining(self.user_a, self.guild_id, now=1_000.0),
            0.0,
        )
        first = await self.db.try_card_pull(self.user_a, self.guild_id, now=1_000.0)
        self.assertIsNone(first["error"])
        remaining = await self.db.card_pull_remaining(
            self.user_a, self.guild_id, now=1_010.0,
        )
        self.assertGreater(remaining, 0)
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

    async def test_set_complete_pays_once(self) -> None:
        velvet = cards_for_set("velvet")
        for card in velvet[:-1]:
            granted = await self.db.grant_card(self.user_a, self.guild_id, card.card_id)
            assert granted is not None
            self.assertIsNone(granted.get("set_complete"))
        before = await self.db.get_balance(self.user_a, self.guild_id)
        last = await self.db.grant_card(self.user_a, self.guild_id, velvet[-1].card_id)
        assert last is not None
        self.assertEqual(last["set_complete"], "velvet")
        self.assertGreater(float(last["set_reward"]), 0)
        after = await self.db.get_balance(self.user_a, self.guild_id)
        self.assertAlmostEqual(after - before, float(last["set_reward"]))
        completed = await self.db.list_completed_card_sets(self.user_a, self.guild_id)
        self.assertIn("velvet", completed)
        dup = await self.db.grant_card(self.user_a, self.guild_id, velvet[-1].card_id)
        assert dup is not None
        self.assertIsNone(dup.get("set_complete"))
        self.assertAlmostEqual(await self.db.get_balance(self.user_a, self.guild_id), after)
