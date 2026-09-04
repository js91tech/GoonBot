"""Database mixin for GoonCards collect / buy / sell / trade."""
from __future__ import annotations

import time
from typing import Any

import aiosqlite

from utils.cards import (
    CARD_DEFINITIONS,
    card_by_id,
    cards_for_set,
    npc_sell_value,
    roll_card,
    roll_card_prefer_unowned,
    roll_pack,
)


class DatabaseCardsMixin:
    """Card instances, marketplace, pulls, and pack opens."""

    async def _migrate_cards(self) -> None:
        pk = "SERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS card_instances (
                instance_id {pk},
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                card_id TEXT NOT NULL,
                print_number INTEGER NOT NULL,
                created_at REAL NOT NULL,
                escrow_trade_id INTEGER,
                market_listing_id INTEGER
            )
            """,
        )
        await self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_card_instances_owner
            ON card_instances(guild_id, user_id, card_id)
            """,
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_print_counters (
                guild_id BIGINT NOT NULL,
                card_id TEXT NOT NULL,
                next_print INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (guild_id, card_id)
            )
            """,
        )
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS card_market_listings (
                listing_id {pk},
                guild_id BIGINT NOT NULL,
                seller_id BIGINT NOT NULL,
                instance_id INTEGER NOT NULL,
                price REAL NOT NULL CHECK (price > 0),
                created_at REAL NOT NULL
            )
            """,
        )
        await self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_card_market_guild
            ON card_market_listings(guild_id, created_at)
            """,
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_favorites (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                instance_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """,
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_pull_cooldown (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                last_pull_at REAL NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """,
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_set_completions (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                set_id TEXT NOT NULL,
                completed_at REAL NOT NULL,
                reward REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, set_id)
            )
            """,
        )
        await self._ensure_column(
            "pending_trades",
            "offer_cards",
            "TEXT NOT NULL DEFAULT '[]'",
        )
        await self.conn.commit()

    async def _ensure_column(self, table: str, column: str, typedef: str) -> None:
        if self.is_postgres:
            cursor = await self.conn.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = ANY (current_schemas(true))
                  AND table_name = ? AND column_name = ?
                """,
                (table, column),
            )
            if await cursor.fetchone() is None:
                await self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {typedef}",
                )
            return
        cursor = await self.conn.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in await cursor.fetchall()}
        if column not in existing:
            await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")

    async def _next_card_print_no_lock(self, guild_id: int, card_id: str) -> int:
        cursor = await self.conn.execute(
            """
            SELECT next_print FROM card_print_counters
            WHERE guild_id = ? AND card_id = ?
            """,
            (guild_id, card_id),
        )
        row = await cursor.fetchone()
        if row is None:
            await self.conn.execute(
                """
                INSERT INTO card_print_counters (guild_id, card_id, next_print)
                VALUES (?, ?, 2)
                """,
                (guild_id, card_id),
            )
            return 1
        print_number = int(row["next_print"])
        await self.conn.execute(
            """
            UPDATE card_print_counters SET next_print = next_print + 1
            WHERE guild_id = ? AND card_id = ?
            """,
            (guild_id, card_id),
        )
        return print_number

    async def _unique_card_count_no_lock(self, user_id: int, guild_id: int) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COUNT(DISTINCT card_id) AS n FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        row = await cursor.fetchone()
        return int(row["n"]) if row is not None else 0

    async def _bump_cards_museum_no_lock(
        self, guild_id: int, user_id: int, unique_before: int,
    ) -> None:
        unique_after = await self._unique_card_count_no_lock(user_id, guild_id)
        if unique_after <= unique_before:
            return
        delta = unique_after - unique_before
        await self.conn.execute(
            """
            INSERT INTO museum_counts (guild_id, user_id, category, count)
            VALUES (?, ?, 'cards', ?)
            ON CONFLICT (guild_id, user_id, category) DO UPDATE SET
                count = museum_counts.count + excluded.count
            """,
            (guild_id, user_id, delta),
        )

    async def _owned_card_ids_no_lock(self, user_id: int, guild_id: int) -> set[str]:
        cursor = await self.conn.execute(
            """
            SELECT DISTINCT card_id FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        return {str(r["card_id"]) for r in await cursor.fetchall()}

    async def _mark_set_complete_no_lock(
        self,
        user_id: int,
        guild_id: int,
        set_id: str,
        reward: float,
        now: float,
    ) -> bool:
        cursor = await self.conn.execute(
            """
            INSERT INTO card_set_completions (
                guild_id, user_id, set_id, completed_at, reward
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, user_id, set_id) DO NOTHING
            """,
            (guild_id, user_id, set_id, now, reward),
        )
        return int(getattr(cursor, "rowcount", 0) or 0) > 0

    async def _grant_card_no_lock(
        self,
        user_id: int,
        guild_id: int,
        card_id: str,
        *,
        created_at: float | None = None,
    ) -> dict[str, Any] | None:
        if card_id not in CARD_DEFINITIONS:
            return None
        await self._ensure_user_no_lock(user_id, guild_id)
        unique_before = await self._unique_card_count_no_lock(user_id, guild_id)
        owned = await self._owned_card_ids_no_lock(user_id, guild_id)
        print_number = await self._next_card_print_no_lock(guild_id, card_id)
        now = created_at if created_at is not None else time.time()
        cursor = await self.conn.execute(
            """
            INSERT INTO card_instances (
                guild_id, user_id, card_id, print_number, created_at,
                escrow_trade_id, market_listing_id
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
            RETURNING instance_id
            """,
            (guild_id, user_id, card_id, print_number, now),
        )
        row = await cursor.fetchone()
        if row is None:
            instance_id = await self._last_insert_id_no_lock("card_instances", "instance_id")
        else:
            instance_id = int(row["instance_id"])
        await self._bump_cards_museum_no_lock(guild_id, user_id, unique_before)
        set_complete = None
        set_reward = 0.0
        defn = CARD_DEFINITIONS[card_id]
        if card_id not in owned:
            set_cards = cards_for_set(defn.set_id)
            have = sum(1 for c in set_cards if c.card_id in owned) + 1
            if have >= len(set_cards):
                reward = float(await self.get_config_value(guild_id, "card_set_complete_reward"))
                if await self._mark_set_complete_no_lock(
                    user_id, guild_id, defn.set_id, reward, now,
                ):
                    set_complete = defn.set_id
                    set_reward = reward
                    if reward > 0:
                        await self.conn.execute(
                            """
                            UPDATE users
                            SET wallet = wallet + ?,
                                total_earned = total_earned + ?
                            WHERE user_id = ? AND guild_id = ?
                            """,
                            (reward, reward, user_id, guild_id),
                        )
        return {
            "instance_id": instance_id,
            "card_id": card_id,
            "print_number": print_number,
            "new_unique": card_id not in owned,
            "set_complete": set_complete,
            "set_reward": set_reward,
        }

    async def grant_card(
        self, user_id: int, guild_id: int, card_id: str,
    ) -> dict[str, Any] | None:
        async with self._write_lock:
            granted = await self._grant_card_no_lock(user_id, guild_id, card_id)
            await self.conn.commit()
        return granted

    async def grant_engagement_card(
        self, user_id: int, guild_id: int,
    ) -> dict[str, Any] | None:
        """Grant one rarity-weighted card, preferring a missing dex entry."""
        owned = await self.collection_owned_ids(user_id, guild_id)
        card = roll_card_prefer_unowned(owned)
        return await self.grant_card(user_id, guild_id, card.card_id)

    async def list_completed_card_sets(
        self, user_id: int, guild_id: int,
    ) -> set[str]:
        cursor = await self.conn.execute(
            """
            SELECT set_id FROM card_set_completions
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        return {str(r["set_id"]) for r in await cursor.fetchall()}

    async def get_card_instance(
        self, instance_id: int, guild_id: int,
    ) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT * FROM card_instances
            WHERE instance_id = ? AND guild_id = ?
            """,
            (instance_id, guild_id),
        )
        return await cursor.fetchone()

    async def list_binder(
        self,
        user_id: int,
        guild_id: int,
        *,
        set_id: str | None = None,
        rarity: str | None = None,
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT instance_id, card_id, print_number, created_at,
                   escrow_trade_id, market_listing_id
            FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            ORDER BY card_id ASC, print_number ASC
            """,
            (guild_id, user_id),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        filtered: list[dict[str, Any]] = []
        for row in rows:
            defn = card_by_id(str(row["card_id"]))
            if defn is None:
                continue
            if set_id and defn.set_id != set_id:
                continue
            if rarity and defn.rarity != rarity:
                continue
            row["rarity"] = defn.rarity
            row["set_id"] = defn.set_id
            row["name"] = defn.name
            filtered.append(row)
        return filtered

    async def binder_grouped(
        self,
        user_id: int,
        guild_id: int,
        *,
        set_id: str | None = None,
        rarity: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = await self.list_binder(user_id, guild_id, set_id=set_id, rarity=rarity)
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            card_id = str(row["card_id"])
            bucket = grouped.setdefault(
                card_id,
                {
                    "card_id": card_id,
                    "name": row["name"],
                    "rarity": row["rarity"],
                    "set_id": row["set_id"],
                    "count": 0,
                    "available": 0,
                    "lowest_print": int(row["print_number"]),
                    "showcase_instance_id": int(row["instance_id"]),
                    "instances": [],
                },
            )
            bucket["count"] += 1
            listed = row["market_listing_id"] not in (None, 0)
            escrowed = row["escrow_trade_id"] not in (None, 0)
            if not listed and not escrowed:
                bucket["available"] += 1
            print_number = int(row["print_number"])
            if print_number < int(bucket["lowest_print"]):
                bucket["lowest_print"] = print_number
                bucket["showcase_instance_id"] = int(row["instance_id"])
            bucket["instances"].append(row)
        return list(grouped.values())

    async def count_owned_cards(self, user_id: int, guild_id: int) -> tuple[int, int]:
        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) AS n, COUNT(DISTINCT card_id) AS unique_n
            FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return 0, 0
        return int(row["n"]), int(row["unique_n"])

    async def count_owned_copies(
        self, user_id: int, guild_id: int, card_id: str,
    ) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) AS n FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND card_id = ?
            """,
            (guild_id, user_id, card_id),
        )
        row = await cursor.fetchone()
        return int(row["n"]) if row is not None else 0

    async def card_pull_remaining(
        self, user_id: int, guild_id: int, *, now: float | None = None,
    ) -> float:
        cooldown = float(await self.get_config_value(guild_id, "card_pull_cooldown_seconds"))
        stamp = now if now is not None else time.time()
        cursor = await self.conn.execute(
            """
            SELECT last_pull_at FROM card_pull_cooldown
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        row = await cursor.fetchone()
        last = float(row["last_pull_at"]) if row is not None else 0.0
        if last <= 0:
            return 0.0
        return max(0.0, (last + cooldown) - stamp)

    async def collection_owned_ids(self, user_id: int, guild_id: int) -> set[str]:
        cursor = await self.conn.execute(
            """
            SELECT DISTINCT card_id FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        return {str(r["card_id"]) for r in await cursor.fetchall()}

    async def get_favorite_card(
        self, user_id: int, guild_id: int,
    ) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT c.* FROM card_favorites f
            JOIN card_instances c ON c.instance_id = f.instance_id
            WHERE f.guild_id = ? AND f.user_id = ?
            """,
            (guild_id, user_id),
        )
        return await cursor.fetchone()

    async def set_favorite_card(
        self, user_id: int, guild_id: int, instance_id: int,
    ) -> bool:
        async with self._write_lock:
            cursor = await self.conn.execute(
                """
                SELECT instance_id FROM card_instances
                WHERE instance_id = ? AND guild_id = ? AND user_id = ?
                """,
                (instance_id, guild_id, user_id),
            )
            if await cursor.fetchone() is None:
                await self.conn.commit()
                return False
            await self.conn.execute(
                """
                INSERT INTO card_favorites (guild_id, user_id, instance_id)
                VALUES (?, ?, ?)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET
                    instance_id = excluded.instance_id
                """,
                (guild_id, user_id, instance_id),
            )
            await self.conn.commit()
        return True

    def _instance_locked(self, row: object) -> bool:
        listed = row["market_listing_id"] not in (None, 0)  # type: ignore[index]
        escrowed = row["escrow_trade_id"] not in (None, 0)  # type: ignore[index]
        return bool(listed or escrowed)

    async def sell_instances_to_npc(
        self,
        user_id: int,
        guild_id: int,
        instance_ids: list[int],
        *,
        sell_mult: float,
    ) -> dict[str, Any]:
        if not instance_ids:
            return {"error": "empty", "sold": 0, "payout": 0.0}
        unique_ids = list(dict.fromkeys(int(i) for i in instance_ids))
        async with self._write_lock:
            payout = 0.0
            sold_ids: list[int] = []
            for instance_id in unique_ids:
                cursor = await self.conn.execute(
                    """
                    SELECT * FROM card_instances
                    WHERE instance_id = ? AND guild_id = ? AND user_id = ?
                    """,
                    (instance_id, guild_id, user_id),
                )
                row = await cursor.fetchone()
                if row is None or self._instance_locked(row):
                    continue
                defn = card_by_id(str(row["card_id"]))
                if defn is None:
                    continue
                payout += npc_sell_value(defn, sell_mult)
                await self.conn.execute(
                    "DELETE FROM card_favorites WHERE instance_id = ? AND guild_id = ?",
                    (instance_id, guild_id),
                )
                await self.conn.execute(
                    "DELETE FROM card_instances WHERE instance_id = ?",
                    (instance_id,),
                )
                sold_ids.append(instance_id)
            if not sold_ids:
                await self.conn.commit()
                return {"error": "none_sellable", "sold": 0, "payout": 0.0}
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users SET wallet = wallet + ?, total_earned = total_earned + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (payout, payout, user_id, guild_id),
            )
            await self.conn.commit()
        return {"error": None, "sold": len(sold_ids), "payout": payout, "instance_ids": sold_ids}

    def _extra_copies_from_grouped(
        self, grouped: list[dict[str, Any]],
    ) -> list[tuple[int, str]]:
        extras: list[tuple[int, str]] = []
        for bucket in grouped:
            available_rows = [
                inst for inst in bucket["instances"]
                if inst["market_listing_id"] in (None, 0)
                and inst["escrow_trade_id"] in (None, 0)
            ]
            if len(available_rows) <= 1:
                continue
            keep = min(available_rows, key=lambda r: int(r["print_number"]))
            keep_id = int(keep["instance_id"])
            card_id = str(bucket["card_id"])
            for inst in available_rows:
                if int(inst["instance_id"]) != keep_id:
                    extras.append((int(inst["instance_id"]), card_id))
        return extras

    async def preview_extra_copies_to_npc(
        self, user_id: int, guild_id: int, *, sell_mult: float,
    ) -> dict[str, Any]:
        grouped = await self.binder_grouped(user_id, guild_id)
        extras = self._extra_copies_from_grouped(grouped)
        payout = 0.0
        for _instance_id, card_id in extras:
            defn = card_by_id(card_id)
            if defn is not None:
                payout += npc_sell_value(defn, sell_mult)
        return {"sold": len(extras), "payout": payout}

    async def sell_extra_copies_to_npc(
        self, user_id: int, guild_id: int, *, sell_mult: float,
    ) -> dict[str, Any]:
        grouped = await self.binder_grouped(user_id, guild_id)
        extras = [iid for iid, _card_id in self._extra_copies_from_grouped(grouped)]
        return await self.sell_instances_to_npc(
            user_id, guild_id, extras, sell_mult=sell_mult,
        )

    async def list_card_on_market(
        self,
        user_id: int,
        guild_id: int,
        instance_id: int,
        price: float,
    ) -> tuple[int | None, str | None]:
        if price <= 0:
            return None, "invalid_price"
        async with self._write_lock:
            cursor = await self.conn.execute(
                """
                SELECT * FROM card_instances
                WHERE instance_id = ? AND guild_id = ? AND user_id = ?
                """,
                (instance_id, guild_id, user_id),
            )
            row = await cursor.fetchone()
            if row is None:
                await self.conn.commit()
                return None, "not_found"
            if self._instance_locked(row):
                await self.conn.commit()
                return None, "locked"
            await self.conn.execute(
                """
                INSERT INTO card_market_listings (
                    guild_id, seller_id, instance_id, price, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, instance_id, price, time.time()),
            )
            listing_id = await self._last_insert_id_no_lock("card_market_listings", "listing_id")
            await self.conn.execute(
                """
                UPDATE card_instances SET market_listing_id = ?
                WHERE instance_id = ?
                """,
                (listing_id, instance_id),
            )
            await self.conn.commit()
        return int(listing_id), None

    async def list_card_market(
        self, guild_id: int, *, limit: int = 20, offset: int = 0,
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT l.listing_id, l.seller_id, l.instance_id, l.price, l.created_at,
                   c.card_id, c.print_number
            FROM card_market_listings l
            JOIN card_instances c ON c.instance_id = l.instance_id
            WHERE l.guild_id = ?
            ORDER BY l.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (guild_id, limit, offset),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def list_user_card_listings(
        self, user_id: int, guild_id: int,
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT l.listing_id, l.instance_id, l.price, c.card_id, c.print_number
            FROM card_market_listings l
            JOIN card_instances c ON c.instance_id = l.instance_id
            WHERE l.guild_id = ? AND l.seller_id = ?
            ORDER BY l.listing_id DESC
            """,
            (guild_id, user_id),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def cancel_card_listing(
        self, user_id: int, guild_id: int, listing_id: int,
    ) -> str | None:
        async with self._write_lock:
            cursor = await self.conn.execute(
                """
                SELECT seller_id, instance_id FROM card_market_listings
                WHERE listing_id = ? AND guild_id = ?
                """,
                (listing_id, guild_id),
            )
            listing = await cursor.fetchone()
            if listing is None:
                await self.conn.commit()
                return "not_found"
            if int(listing["seller_id"]) != user_id:
                await self.conn.commit()
                return "not_owner"
            instance_id = int(listing["instance_id"])
            await self.conn.execute(
                "DELETE FROM card_market_listings WHERE listing_id = ?",
                (listing_id,),
            )
            await self.conn.execute(
                """
                UPDATE card_instances SET market_listing_id = NULL
                WHERE instance_id = ?
                """,
                (instance_id,),
            )
            await self.conn.commit()
        return None

    async def buy_card_listing(
        self, user_id: int, guild_id: int, listing_id: int,
    ) -> dict[str, Any]:
        async with self._write_lock:
            cursor = await self.conn.execute(
                """
                SELECT l.seller_id, l.instance_id, l.price, c.card_id, c.print_number
                FROM card_market_listings l
                JOIN card_instances c ON c.instance_id = l.instance_id
                WHERE l.listing_id = ? AND l.guild_id = ?
                """,
                (listing_id, guild_id),
            )
            listing = await cursor.fetchone()
            if listing is None:
                await self.conn.commit()
                return {"error": "not_found"}
            seller_id = int(listing["seller_id"])
            if seller_id == user_id:
                await self.conn.commit()
                return {"error": "own_listing"}
            price = float(listing["price"])
            instance_id = int(listing["instance_id"])
            await self._ensure_user_no_lock(user_id, guild_id)
            wallet_cursor = await self.conn.execute(
                "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            wallet_row = await wallet_cursor.fetchone()
            if wallet_row is None or float(wallet_row["wallet"]) < price:
                await self.conn.commit()
                return {"error": "insufficient_funds", "total": price}
            tax_rate = float(await self.get_config_value(guild_id, "card_market_tax"))
            tax = max(0.0, price * tax_rate)
            proceeds = price - tax
            unique_before = await self._unique_card_count_no_lock(user_id, guild_id)
            buyer_owned = await self._owned_card_ids_no_lock(user_id, guild_id)
            new_unique = str(listing["card_id"]) not in buyer_owned
            await self.conn.execute(
                "UPDATE users SET wallet = wallet - ? WHERE user_id = ? AND guild_id = ?",
                (price, user_id, guild_id),
            )
            await self._ensure_progress_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE user_progress SET goonbux_spent = goonbux_spent + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (price, user_id, guild_id),
            )
            await self._ensure_user_no_lock(seller_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users SET wallet = wallet + ?, total_earned = total_earned + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (proceeds, proceeds, seller_id, guild_id),
            )
            if tax > 0:
                await self.conn.execute(
                    """
                    INSERT INTO guild_house_pot (guild_id, balance)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        balance = guild_house_pot.balance + excluded.balance
                    """,
                    (guild_id, tax),
                )
            await self.conn.execute(
                "DELETE FROM card_favorites WHERE instance_id = ? AND guild_id = ?",
                (instance_id, guild_id),
            )
            await self.conn.execute(
                """
                UPDATE card_instances
                SET user_id = ?, market_listing_id = NULL, escrow_trade_id = NULL
                WHERE instance_id = ?
                """,
                (user_id, instance_id),
            )
            await self.conn.execute(
                "DELETE FROM card_market_listings WHERE listing_id = ?",
                (listing_id,),
            )
            await self._bump_cards_museum_no_lock(guild_id, user_id, unique_before)
            await self.conn.commit()
        return {
            "error": None,
            "total": price,
            "tax": tax,
            "instance_id": instance_id,
            "card_id": str(listing["card_id"]),
            "print_number": int(listing["print_number"]),
            "new_unique": new_unique,
        }

    async def _debit_for_cards_no_lock(
        self, user_id: int, guild_id: int, amount: float,
    ) -> bool:
        if amount <= 0:
            return True
        await self._ensure_user_no_lock(user_id, guild_id)
        cursor = await self.conn.execute(
            "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = await cursor.fetchone()
        if row is None or float(row["wallet"]) < amount:
            return False
        await self.conn.execute(
            "UPDATE users SET wallet = wallet - ? WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id),
        )
        await self._ensure_progress_no_lock(user_id, guild_id)
        await self.conn.execute(
            """
            UPDATE user_progress SET goonbux_spent = goonbux_spent + ?
            WHERE user_id = ? AND guild_id = ?
            """,
            (amount, user_id, guild_id),
        )
        return True

    async def open_card_pack(
        self, user_id: int, guild_id: int,
    ) -> dict[str, Any]:
        price = float(await self.get_config_value(guild_id, "card_pack_price"))
        size = int(await self.get_config_value(guild_id, "card_pack_size"))
        cards = roll_pack(size)
        async with self._write_lock:
            if not await self._debit_for_cards_no_lock(user_id, guild_id, price):
                await self.conn.commit()
                return {"error": "insufficient_funds", "price": price, "granted": []}
            granted = []
            for card in cards:
                row = await self._grant_card_no_lock(user_id, guild_id, card.card_id)
                if row is not None:
                    granted.append(row)
            await self.conn.commit()
        return {"error": None, "price": price, "granted": granted}

    async def try_card_pull(
        self, user_id: int, guild_id: int, *, now: float | None = None,
    ) -> dict[str, Any]:
        cooldown = float(await self.get_config_value(guild_id, "card_pull_cooldown_seconds"))
        stamp = now if now is not None else time.time()
        card = roll_card()
        async with self._write_lock:
            cursor = await self.conn.execute(
                """
                SELECT last_pull_at FROM card_pull_cooldown
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            )
            row = await cursor.fetchone()
            last = float(row["last_pull_at"]) if row is not None else 0.0
            remaining = (last + cooldown) - stamp if last > 0 else -1.0
            if remaining > 0:
                await self.conn.commit()
                return {"error": "cooldown", "remaining": remaining}
            granted = await self._grant_card_no_lock(user_id, guild_id, card.card_id)
            await self.conn.execute(
                """
                INSERT INTO card_pull_cooldown (guild_id, user_id, last_pull_at)
                VALUES (?, ?, ?)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET
                    last_pull_at = excluded.last_pull_at
                """,
                (guild_id, user_id, stamp),
            )
            await self.conn.commit()
        return {"error": None, "granted": granted, "remaining": cooldown}

    async def try_card_drop(
        self, user_id: int, guild_id: int, chance: float,
    ) -> dict[str, Any] | None:
        import random

        if chance <= 0 or random.random() >= chance:
            return None
        card = roll_card()
        return await self.grant_card(user_id, guild_id, card.card_id)

    async def list_tradeable_card_instances(
        self, user_id: int, guild_id: int,
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT instance_id, card_id, print_number
            FROM card_instances
            WHERE guild_id = ? AND user_id = ?
              AND (escrow_trade_id IS NULL OR escrow_trade_id = 0)
              AND (market_listing_id IS NULL OR market_listing_id = 0)
            ORDER BY card_id ASC, print_number ASC
            LIMIT 25
            """,
            (guild_id, user_id),
        )
        return [dict(r) for r in await cursor.fetchall()]
