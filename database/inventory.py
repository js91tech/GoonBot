"""Stackable inventory shop operations for Database."""
from __future__ import annotations

import aiosqlite

import config
from database.types import _spendable_cents


class DatabaseInventoryMixin:
    async def buy_item(
        self,
        user_id: int,
        guild_id: int,
        item_id: str,
        unit_price: float,
        quantity: int = 1,
    ) -> bool:
        if unit_price <= 0:
            return False
        qty = max(1, min(int(quantity), config.SHOP_MAX_BUY_QUANTITY))
        total_cents = _spendable_cents(unit_price) * qty
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._ensure_user_no_lock(user_id, guild_id)
                cursor = await self.conn.execute(
                    "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                    (user_id, guild_id),
                )
                row = await cursor.fetchone()
                if row is None or _spendable_cents(row["wallet"]) < total_cents:
                    await self.conn.rollback()
                    return False
                total_price = total_cents / 100.0
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet - ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (total_price, user_id, guild_id),
                )
                await self.conn.execute(
                    """
                    INSERT INTO inventory (guild_id, user_id, item_id, quantity)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id, item_id) DO UPDATE SET
                        quantity = inventory.quantity + excluded.quantity
                    """,
                    (guild_id, user_id, item_id, qty),
                )
                from items import get_item, is_gear_instance_item

                item = get_item(item_id)
                if item is not None and is_gear_instance_item(item):
                    import time

                    now = time.time()
                    for _ in range(qty):
                        await self.conn.execute(
                            """
                            INSERT INTO gear_instances (
                                guild_id, user_id, item_id, enhancement_level, is_broken, created_at
                            )
                            VALUES (?, ?, ?, 0, 0, ?)
                            """,
                            (guild_id, user_id, item_id, now),
                        )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return True

    async def sell_one_item(
        self,
        user_id: int,
        guild_id: int,
        item_id: str,
        unit_refund: float,
        quantity: int = 1,
    ) -> int:
        """Sell up to quantity copies. Returns how many were sold (0 on failure)."""
        if unit_refund <= 0:
            return 0
        want = max(1, min(int(quantity), config.SHOP_MAX_SELL_QUANTITY))
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._ensure_user_no_lock(user_id, guild_id)
                cursor = await self.conn.execute(
                    """
                    SELECT quantity
                    FROM inventory
                    WHERE guild_id = ? AND user_id = ? AND item_id = ?
                    """,
                    (guild_id, user_id, item_id),
                )
                row = await cursor.fetchone()
                if row is None or int(row["quantity"]) <= 0:
                    await self.conn.rollback()
                    return 0
                owned = int(row["quantity"])
                sold = min(want, owned)
                new_qty = owned - sold
                if new_qty <= 0:
                    await self.conn.execute(
                        """
                        DELETE FROM inventory
                        WHERE guild_id = ? AND user_id = ? AND item_id = ?
                        """,
                        (guild_id, user_id, item_id),
                    )
                    await self.conn.execute(
                        """
                        DELETE FROM equipment
                        WHERE guild_id = ? AND user_id = ? AND item_id = ?
                        """,
                        (guild_id, user_id, item_id),
                    )
                else:
                    await self.conn.execute(
                        """
                        UPDATE inventory
                        SET quantity = ?
                        WHERE guild_id = ? AND user_id = ? AND item_id = ?
                        """,
                        (new_qty, guild_id, user_id, item_id),
                    )
                total_refund = unit_refund * sold
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet + ?,
                        total_earned = total_earned + ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (total_refund, total_refund, user_id, guild_id),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return sold

    async def get_inventory(self, user_id: int, guild_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT item_id, quantity
            FROM inventory
            WHERE guild_id = ? AND user_id = ? AND quantity > 0
            ORDER BY item_id
            """,
            (guild_id, user_id),
        )
        return list(await cursor.fetchall())

    async def grant_inventory_quantity(
        self, user_id: int, guild_id: int, item_id: str, quantity: int = 1,
    ) -> int:
        """Silently grant ``quantity`` copies. Returns how many were granted."""
        from items import get_item, is_gear_instance_item

        item = get_item(item_id)
        if item is None:
            return 0
        qty = max(1, min(int(quantity), int(config.DASHBOARD_SPY_MAX_QUANTITY)))
        if is_gear_instance_item(item):
            for _ in range(qty):
                await self.grant_item(user_id, guild_id, item_id)
            return qty
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                INSERT INTO inventory (guild_id, user_id, item_id, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, item_id) DO UPDATE SET
                    quantity = inventory.quantity + excluded.quantity
                """,
                (guild_id, user_id, item_id, qty),
            )
            await self.conn.commit()
        return qty

    async def remove_inventory_quantity(
        self, user_id: int, guild_id: int, item_id: str, quantity: int = 1,
    ) -> int:
        """Silently remove up to ``quantity`` copies. Returns how many were removed."""
        want = max(1, min(int(quantity), int(config.DASHBOARD_SPY_MAX_QUANTITY)))
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self.conn.execute(
                    """
                    SELECT quantity FROM inventory
                    WHERE guild_id = ? AND user_id = ? AND item_id = ?
                    """,
                    (guild_id, user_id, item_id),
                )
                row = await cursor.fetchone()
                if row is None or int(row["quantity"]) <= 0:
                    await self.conn.rollback()
                    return 0
                owned = int(row["quantity"])
                removed = min(want, owned)
                new_qty = owned - removed
                if new_qty <= 0:
                    await self.conn.execute(
                        """
                        DELETE FROM inventory
                        WHERE guild_id = ? AND user_id = ? AND item_id = ?
                        """,
                        (guild_id, user_id, item_id),
                    )
                else:
                    await self.conn.execute(
                        """
                        UPDATE inventory
                        SET quantity = ?
                        WHERE guild_id = ? AND user_id = ? AND item_id = ?
                        """,
                        (new_qty, guild_id, user_id, item_id),
                    )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return removed

    async def gift_inventory_item(
        self,
        sender_id: int,
        receiver_id: int,
        guild_id: int,
        item_id: str,
        quantity: int = 1,
    ) -> str | None:
        """Move stackable items from sender to receiver. Returns error code or None."""
        if sender_id == receiver_id:
            return "self_gift"
        qty = max(1, min(int(quantity), config.SHOP_MAX_BUY_QUANTITY))
        async with self._write_lock:
            await self._ensure_user_no_lock(sender_id, guild_id)
            await self._ensure_user_no_lock(receiver_id, guild_id)
            cursor = await self.conn.execute(
                """
                SELECT quantity FROM inventory
                WHERE guild_id = ? AND user_id = ? AND item_id = ?
                """,
                (guild_id, sender_id, item_id),
            )
            row = await cursor.fetchone()
            if row is None or int(row["quantity"]) < qty:
                await self.conn.commit()
                return "insufficient_items"
            remaining = int(row["quantity"]) - qty
            if remaining <= 0:
                await self.conn.execute(
                    """
                    DELETE FROM inventory
                    WHERE guild_id = ? AND user_id = ? AND item_id = ?
                    """,
                    (guild_id, sender_id, item_id),
                )
            else:
                await self.conn.execute(
                    """
                    UPDATE inventory SET quantity = ?
                    WHERE guild_id = ? AND user_id = ? AND item_id = ?
                    """,
                    (remaining, guild_id, sender_id, item_id),
                )
            await self.conn.execute(
                """
                INSERT INTO inventory (guild_id, user_id, item_id, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, item_id) DO UPDATE SET
                    quantity = inventory.quantity + excluded.quantity
                """,
                (guild_id, receiver_id, item_id, qty),
            )
            from items import get_item, is_gear_instance_item

            item = get_item(item_id)
            if item is not None and is_gear_instance_item(item):
                import time

                now = time.time()
                for _ in range(qty):
                    await self.conn.execute(
                        """
                        INSERT INTO gear_instances (
                            guild_id, user_id, item_id, enhancement_level, is_broken, created_at
                        )
                        VALUES (?, ?, ?, 0, 0, ?)
                        """,
                        (guild_id, receiver_id, item_id, now),
                    )
                records = await self.get_equipment_records(sender_id, guild_id)
                equipped_ids = {
                    int(rec["gear_instance_id"])
                    for rec in records.values()
                    if rec.get("gear_instance_id") is not None
                }
                inst_cursor = await self.conn.execute(
                    """
                    SELECT instance_id
                    FROM gear_instances
                    WHERE guild_id = ? AND user_id = ? AND item_id = ?
                    ORDER BY enhancement_level ASC, instance_id ASC
                    """,
                    (guild_id, sender_id, item_id),
                )
                removable = [
                    int(r["instance_id"])
                    for r in await inst_cursor.fetchall()
                    if int(r["instance_id"]) not in equipped_ids
                ][:qty]
                for instance_id in removable:
                    await self.conn.execute(
                        "DELETE FROM gear_instances WHERE instance_id = ? AND guild_id = ?",
                        (instance_id, guild_id),
                    )
            await self.conn.commit()
        return None

    async def get_inventory_quantity(
        self, user_id: int, guild_id: int, item_id: str
    ) -> int:
        cursor = await self.conn.execute(
            """
            SELECT quantity FROM inventory
            WHERE guild_id = ? AND user_id = ? AND item_id = ?
            """,
            (guild_id, user_id, item_id),
        )
        row = await cursor.fetchone()
        return int(row["quantity"]) if row is not None else 0

