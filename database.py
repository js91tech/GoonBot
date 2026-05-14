from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import aiosqlite

import config


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()
        self._config_cache: dict[int, dict[str, float]] = {}

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            msg = "Database connection has not been opened"
            raise RuntimeError(msg)
        return self._conn

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.execute("PRAGMA busy_timeout = 5000")
        await self.conn.commit()
        await self.init_schema()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def init_schema(self) -> None:
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                wallet REAL NOT NULL DEFAULT 0 CHECK (wallet >= 0),
                last_daily REAL NOT NULL DEFAULT 0,
                last_heist REAL NOT NULL DEFAULT 0,
                last_active_ts REAL NOT NULL DEFAULT 0,
                arrested_until REAL NOT NULL DEFAULT 0,
                downed_until REAL NOT NULL DEFAULT 0,
                total_earned REAL NOT NULL DEFAULT 0 CHECK (total_earned >= 0),
                messages_sent INTEGER NOT NULL DEFAULT 0 CHECK (messages_sent >= 0),
                PRIMARY KEY (user_id, guild_id)
            );

            CREATE TABLE IF NOT EXISTS bounties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                placer_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                trigger_word TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hacker_pots (
                guild_id INTEGER PRIMARY KEY,
                holder_id INTEGER NOT NULL,
                pass_count INTEGER NOT NULL DEFAULT 0 CHECK (pass_count >= 0),
                started_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hacker_cooldowns (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                last_hack REAL NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS boss_sessions (
                guild_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                variant TEXT NOT NULL,
                hp REAL NOT NULL CHECK (hp >= 0),
                max_hp REAL NOT NULL CHECK (max_hp > 0),
                spawned_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS boss_damage (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                damage REAL NOT NULL DEFAULT 0 CHECK (damage >= 0),
                PRIMARY KEY (guild_id, user_id),
                FOREIGN KEY (guild_id) REFERENCES boss_sessions(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS boss_heals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                healer_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS inventory (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                PRIMARY KEY (guild_id, user_id, item_id)
            );

            CREATE TABLE IF NOT EXISTS equipment (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                slot TEXT NOT NULL CHECK (slot IN ('weapon', 'armor')),
                item_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id, slot)
            );

            CREATE TABLE IF NOT EXISTS combat_state (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                hp REAL NOT NULL CHECK (hp >= 0),
                max_hp REAL NOT NULL CHECK (max_hp > 0),
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER NOT NULL,
                setting TEXT NOT NULL,
                value REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (guild_id, setting)
            );

            CREATE INDEX IF NOT EXISTS idx_users_guild_wallet
                ON users(guild_id, wallet DESC);
            CREATE INDEX IF NOT EXISTS idx_bounties_guild
                ON bounties(guild_id);
            """
        )
        await self.conn.commit()

    async def _load_config_no_lock(self, guild_id: int) -> dict[str, float]:
        cursor = await self.conn.execute(
            "SELECT setting, value FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        )
        rows = await cursor.fetchall()
        values = {
            name: spec.default
            for name, spec in config.LIVE_SETTINGS.items()
        }
        for row in rows:
            setting = str(row["setting"])
            if setting in values:
                values[setting] = float(row["value"])
        self._config_cache[guild_id] = values
        return values

    async def get_config_values(self, guild_id: int) -> dict[str, float]:
        cached = self._config_cache.get(guild_id)
        if cached is not None:
            return dict(cached)
        return dict(await self._load_config_no_lock(guild_id))

    async def get_config_value(self, guild_id: int, setting: str) -> float:
        if setting not in config.LIVE_SETTINGS:
            msg = f"Unknown setting: {setting}"
            raise KeyError(msg)
        values = await self.get_config_values(guild_id)
        return values[setting]

    async def set_config_value(self, guild_id: int, setting: str, value: float) -> float:
        spec = config.LIVE_SETTINGS.get(setting)
        if spec is None:
            msg = f"Unknown setting: {setting}"
            raise KeyError(msg)
        normalized = spec.validate(float(value))
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO guild_config (guild_id, setting, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, setting) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (guild_id, setting, normalized, time.time()),
            )
            await self.conn.commit()
            self._config_cache.pop(guild_id, None)
        return float(normalized)

    async def reset_config_value(self, guild_id: int, setting: str) -> None:
        if setting not in config.LIVE_SETTINGS:
            msg = f"Unknown setting: {setting}"
            raise KeyError(msg)
        async with self._write_lock:
            await self.conn.execute(
                "DELETE FROM guild_config WHERE guild_id = ? AND setting = ?",
                (guild_id, setting),
            )
            await self.conn.commit()
            self._config_cache.pop(guild_id, None)

    async def custom_config_names(self, guild_id: int) -> set[str]:
        cursor = await self.conn.execute(
            "SELECT setting FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        )
        return {
            setting
            for row in await cursor.fetchall()
            if (setting := str(row["setting"])) in config.LIVE_SETTINGS
        }

    async def _ensure_user_no_lock(self, user_id: int, guild_id: int) -> None:
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO users (user_id, guild_id)
            VALUES (?, ?)
            """,
            (user_id, guild_id),
        )

    async def ensure_user(self, user_id: int, guild_id: int) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.commit()

    async def ensure_users(self, user_ids: Iterable[int], guild_id: int) -> None:
        async with self._write_lock:
            for user_id in set(user_ids):
                await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.commit()

    async def get_user(self, user_id: int, guild_id: int) -> aiosqlite.Row:
        await self.ensure_user(user_id, guild_id)
        cursor = await self.conn.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = await cursor.fetchone()
        if row is None:
            msg = "Expected user row to exist"
            raise RuntimeError(msg)
        return row

    async def get_balance(self, user_id: int, guild_id: int) -> float:
        row = await self.get_user(user_id, guild_id)
        return float(row["wallet"])

    async def credit_wallet(self, user_id: int, guild_id: int, amount: float) -> None:
        if amount <= 0:
            return
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet + ?,
                    total_earned = total_earned + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, amount, user_id, guild_id),
            )
            await self.conn.commit()

    async def credit_wallets(self, user_ids: Iterable[int], guild_id: int, amount: float) -> int:
        unique_ids = set(user_ids)
        if amount <= 0 or not unique_ids:
            return 0
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                for user_id in unique_ids:
                    await self._ensure_user_no_lock(user_id, guild_id)
                    await self.conn.execute(
                        """
                        UPDATE users
                        SET wallet = wallet + ?,
                            total_earned = total_earned + ?
                        WHERE user_id = ? AND guild_id = ?
                        """,
                        (amount, amount, user_id, guild_id),
                    )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return len(unique_ids)

    async def set_wallet(self, user_id: int, guild_id: int, amount: float) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, user_id, guild_id),
            )
            await self.conn.commit()

    async def reset_user(self, user_id: int, guild_id: int) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = 0,
                    last_daily = 0,
                    last_heist = 0,
                    last_active_ts = 0,
                    arrested_until = 0,
                    downed_until = 0,
                    total_earned = 0,
                    messages_sent = 0
                WHERE user_id = ? AND guild_id = ?
                """,
                (user_id, guild_id),
            )
            await self.conn.execute(
                "DELETE FROM inventory WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await self.conn.execute(
                "DELETE FROM equipment WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await self.conn.execute(
                "DELETE FROM combat_state WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await self.conn.commit()

    async def buy_item(self, user_id: int, guild_id: int, item_id: str, price: float) -> bool:
        if price <= 0:
            return False
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._ensure_user_no_lock(user_id, guild_id)
                cursor = await self.conn.execute(
                    "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                    (user_id, guild_id),
                )
                row = await cursor.fetchone()
                if row is None or float(row["wallet"]) < price:
                    await self.conn.rollback()
                    return False
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet - ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (price, user_id, guild_id),
                )
                await self.conn.execute(
                    """
                    INSERT INTO inventory (guild_id, user_id, item_id, quantity)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(guild_id, user_id, item_id) DO UPDATE SET
                        quantity = quantity + 1
                    """,
                    (guild_id, user_id, item_id),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return True

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

    async def equip_item(self, user_id: int, guild_id: int, slot: str, item_id: str) -> bool:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
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
                    return False
                await self.conn.execute(
                    """
                    INSERT INTO equipment (guild_id, user_id, slot, item_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id, slot) DO UPDATE SET
                        item_id = excluded.item_id
                    """,
                    (guild_id, user_id, slot, item_id),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return True

    async def get_equipment(self, user_id: int, guild_id: int) -> dict[str, str]:
        cursor = await self.conn.execute(
            """
            SELECT slot, item_id
            FROM equipment
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        return {str(row["slot"]): str(row["item_id"]) for row in await cursor.fetchall()}

    async def sync_combat_hp(self, user_id: int, guild_id: int, max_hp: float) -> aiosqlite.Row:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self.conn.execute(
                    """
                    SELECT hp, max_hp
                    FROM combat_state
                    WHERE guild_id = ? AND user_id = ?
                    """,
                    (guild_id, user_id),
                )
                row = await cursor.fetchone()
                if row is None:
                    await self.conn.execute(
                        """
                        INSERT INTO combat_state (guild_id, user_id, hp, max_hp)
                        VALUES (?, ?, ?, ?)
                        """,
                        (guild_id, user_id, max_hp, max_hp),
                    )
                else:
                    old_max = float(row["max_hp"])
                    old_hp = float(row["hp"])
                    hp = max_hp if old_max <= 0 else min(max_hp, old_hp + max(0.0, max_hp - old_max))
                    await self.conn.execute(
                        """
                        UPDATE combat_state
                        SET hp = ?, max_hp = ?
                        WHERE guild_id = ? AND user_id = ?
                        """,
                        (hp, max_hp, guild_id, user_id),
                    )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
        cursor = await self.conn.execute(
            "SELECT hp, max_hp FROM combat_state WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        row = await cursor.fetchone()
        if row is None:
            msg = "Expected combat state row"
            raise RuntimeError(msg)
        return row

    async def damage_player(
        self,
        user_id: int,
        guild_id: int,
        amount: float,
        max_hp: float,
    ) -> tuple[float, float]:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self.conn.execute(
                    """
                    SELECT hp, max_hp
                    FROM combat_state
                    WHERE guild_id = ? AND user_id = ?
                    """,
                    (guild_id, user_id),
                )
                row = await cursor.fetchone()
                hp = max_hp if row is None else min(max_hp, float(row["hp"]))
                new_hp = max(0.0, hp - max(0.0, amount))
                await self.conn.execute(
                    """
                    INSERT INTO combat_state (guild_id, user_id, hp, max_hp)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        hp = excluded.hp,
                        max_hp = excluded.max_hp
                    """,
                    (guild_id, user_id, new_hp, max_hp),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return new_hp, max_hp

    async def restore_player_hp(self, user_id: int, guild_id: int, max_hp: float) -> None:
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO combat_state (guild_id, user_id, hp, max_hp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    hp = excluded.hp,
                    max_hp = excluded.max_hp
                """,
                (guild_id, user_id, max_hp, max_hp),
            )
            await self.conn.commit()

    async def debit_wallet(self, user_id: int, guild_id: int, amount: float) -> bool:
        if amount <= 0:
            return True
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            if row is None or float(row["wallet"]) < amount:
                await self.conn.commit()
                return False
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet - ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, user_id, guild_id),
            )
            await self.conn.commit()
            return True

    async def remove_up_to_balance(self, user_id: int, guild_id: int, amount: float) -> float:
        if amount <= 0:
            return 0.0
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            balance = float(row["wallet"]) if row is not None else 0.0
            removed = min(balance, amount)
            if removed:
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet - ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (removed, user_id, guild_id),
                )
            await self.conn.commit()
            return removed

    async def transfer_wallet(
        self,
        payer_id: int,
        receiver_id: int,
        guild_id: int,
        amount: float,
    ) -> bool:
        if amount <= 0 or payer_id == receiver_id:
            return False
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._ensure_user_no_lock(payer_id, guild_id)
                await self._ensure_user_no_lock(receiver_id, guild_id)
                cursor = await self.conn.execute(
                    "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                    (payer_id, guild_id),
                )
                row = await cursor.fetchone()
                if row is None or float(row["wallet"]) < amount:
                    await self.conn.rollback()
                    return False
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet - ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (amount, payer_id, guild_id),
                )
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet + ?,
                        total_earned = total_earned + ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (amount, amount, receiver_id, guild_id),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return True

    async def record_message_reward(self, user_id: int, guild_id: int, amount: float) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet + ?,
                    total_earned = total_earned + ?,
                    messages_sent = messages_sent + 1
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, amount, user_id, guild_id),
            )
            await self.conn.commit()

    async def claim_daily(
        self,
        user_id: int,
        guild_id: int,
        reward: float,
        cooldown_seconds: float,
        timestamp: float,
    ) -> float | None:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._ensure_user_no_lock(user_id, guild_id)
                cursor = await self.conn.execute(
                    "SELECT last_daily FROM users WHERE user_id = ? AND guild_id = ?",
                    (user_id, guild_id),
                )
                row = await cursor.fetchone()
                last_daily = float(row["last_daily"]) if row is not None else 0.0
                remaining = (last_daily + cooldown_seconds) - timestamp if last_daily > 0 else -1
                if remaining > 0:
                    await self.conn.rollback()
                    return remaining
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet + ?,
                        total_earned = total_earned + ?,
                        last_daily = ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (reward, reward, timestamp, user_id, guild_id),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return None

    async def set_last_daily(self, user_id: int, guild_id: int, timestamp: float) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET last_daily = ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (timestamp, user_id, guild_id),
            )
            await self.conn.commit()

    async def set_last_heist(self, user_id: int, guild_id: int, timestamp: float) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET last_heist = ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (timestamp, user_id, guild_id),
            )
            await self.conn.commit()

    async def set_last_active(self, user_id: int, guild_id: int, timestamp: float) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET last_active_ts = ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (timestamp, user_id, guild_id),
            )
            await self.conn.commit()

    async def set_arrested_until(self, user_id: int, guild_id: int, timestamp: float) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET arrested_until = ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (timestamp, user_id, guild_id),
            )
            await self.conn.commit()

    async def set_downed_until(self, user_id: int, guild_id: int, timestamp: float) -> None:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE users
                SET downed_until = ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (timestamp, user_id, guild_id),
            )
            await self.conn.commit()

    async def is_arrested(self, user_id: int, guild_id: int, at: float | None = None) -> bool:
        row = await self.get_user(user_id, guild_id)
        return float(row["arrested_until"]) > (time.time() if at is None else at)

    async def is_downed(self, user_id: int, guild_id: int, at: float | None = None) -> bool:
        row = await self.get_user(user_id, guild_id)
        return float(row["downed_until"]) > (time.time() if at is None else at)

    async def is_restricted(self, user_id: int, guild_id: int, at: float | None = None) -> bool:
        now = time.time() if at is None else at
        row = await self.get_user(user_id, guild_id)
        return float(row["arrested_until"]) > now or float(row["downed_until"]) > now

    async def leaderboard(self, guild_id: int, limit: int = 10) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT user_id, wallet
            FROM users
            WHERE guild_id = ?
            ORDER BY wallet DESC, user_id ASC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        return list(await cursor.fetchall())

    async def total_circulation(self, guild_id: int) -> float:
        cursor = await self.conn.execute(
            "SELECT COALESCE(SUM(wallet), 0) AS total FROM users WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        return float(row["total"])

    async def economy_stats(self, guild_id: int) -> aiosqlite.Row:
        cursor = await self.conn.execute(
            """
            SELECT
                COUNT(*) AS users,
                COALESCE(SUM(wallet), 0) AS total_wallet,
                COALESCE(SUM(total_earned), 0) AS total_earned,
                COALESCE(SUM(messages_sent), 0) AS messages_sent
            FROM users
            WHERE guild_id = ?
            """,
            (guild_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            msg = "Expected aggregate row"
            raise RuntimeError(msg)
        return row

    async def count_bounties(self, guild_id: int) -> int:
        value = await self.fetch_value("SELECT COUNT(*) FROM bounties WHERE guild_id = ?", (guild_id,))
        return int(value or 0)

    async def create_bounty_with_payment(
        self,
        guild_id: int,
        placer_id: int,
        target_id: int,
        amount: float,
        tax: float,
        trigger_word: str,
    ) -> int | None:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._ensure_user_no_lock(placer_id, guild_id)
                cursor = await self.conn.execute(
                    "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                    (placer_id, guild_id),
                )
                row = await cursor.fetchone()
                if row is None or float(row["wallet"]) < amount + tax:
                    await self.conn.rollback()
                    return None
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet - ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (amount + tax, placer_id, guild_id),
                )
                cursor = await self.conn.execute(
                    """
                    INSERT INTO bounties (
                        guild_id, placer_id, target_id, amount, trigger_word, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (guild_id, placer_id, target_id, amount, trigger_word, time.time()),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return int(cursor.lastrowid)

    async def list_bounties(self, guild_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT *
            FROM bounties
            WHERE guild_id = ?
            ORDER BY created_at ASC
            """,
            (guild_id,),
        )
        return list(await cursor.fetchall())

    async def delete_bounty(self, bounty_id: int, guild_id: int) -> None:
        async with self._write_lock:
            await self.conn.execute(
                "DELETE FROM bounties WHERE id = ? AND guild_id = ?",
                (bounty_id, guild_id),
            )
            await self.conn.commit()

    async def get_hacker_pot(self, guild_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM hacker_pots WHERE guild_id = ?",
            (guild_id,),
        )
        return await cursor.fetchone()

    async def claim_hack_start(
        self,
        guild_id: int,
        user_id: int,
        cooldown_seconds: float,
        timestamp: float,
    ) -> float | None:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self.conn.execute(
                    """
                    SELECT last_hack
                    FROM hacker_cooldowns
                    WHERE guild_id = ? AND user_id = ?
                    """,
                    (guild_id, user_id),
                )
                row = await cursor.fetchone()
                last_hack = float(row["last_hack"]) if row is not None else 0.0
                remaining = (last_hack + cooldown_seconds) - timestamp if last_hack > 0 else -1
                if remaining > 0:
                    await self.conn.rollback()
                    return remaining
                await self.conn.execute(
                    """
                    INSERT INTO hacker_cooldowns (guild_id, user_id, last_hack)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        last_hack = excluded.last_hack
                    """,
                    (guild_id, user_id, timestamp),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return None

    async def set_hacker_pot(
        self,
        guild_id: int,
        holder_id: int,
        pass_count: int,
        started_at: float,
        expires_at: float,
    ) -> None:
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO hacker_pots (guild_id, holder_id, pass_count, started_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    holder_id = excluded.holder_id,
                    pass_count = excluded.pass_count,
                    started_at = excluded.started_at,
                    expires_at = excluded.expires_at
                """,
                (guild_id, holder_id, pass_count, started_at, expires_at),
            )
            await self.conn.commit()

    async def clear_hacker_pot(self, guild_id: int) -> None:
        async with self._write_lock:
            await self.conn.execute("DELETE FROM hacker_pots WHERE guild_id = ?", (guild_id,))
            await self.conn.commit()

    async def get_active_boss(self, guild_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM boss_sessions WHERE guild_id = ?",
            (guild_id,),
        )
        return await cursor.fetchone()

    async def replace_boss(
        self,
        guild_id: int,
        name: str,
        variant: str,
        hp: float,
        spawned_at: float | None = None,
    ) -> None:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self.conn.execute("DELETE FROM boss_sessions WHERE guild_id = ?", (guild_id,))
                await self.conn.execute(
                    """
                    INSERT INTO boss_sessions (guild_id, name, variant, hp, max_hp, spawned_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (guild_id, name, variant, hp, hp, time.time() if spawned_at is None else spawned_at),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()

    async def damage_boss(
        self,
        guild_id: int,
        user_id: int,
        damage: float,
    ) -> aiosqlite.Row | None:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self.conn.execute(
                    "SELECT * FROM boss_sessions WHERE guild_id = ?",
                    (guild_id,),
                )
                boss = await cursor.fetchone()
                if boss is None:
                    await self.conn.rollback()
                    return None
                applied = min(float(boss["hp"]), damage)
                await self.conn.execute(
                    """
                    UPDATE boss_sessions
                    SET hp = MAX(hp - ?, 0)
                    WHERE guild_id = ?
                    """,
                    (applied, guild_id),
                )
                await self.conn.execute(
                    """
                    INSERT INTO boss_damage (guild_id, user_id, damage)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        damage = damage + excluded.damage
                    """,
                    (guild_id, user_id, applied),
                )
                cursor = await self.conn.execute(
                    "SELECT * FROM boss_sessions WHERE guild_id = ?",
                    (guild_id,),
                )
                updated = await cursor.fetchone()
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return updated

    async def list_boss_damage(self, guild_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT *
            FROM boss_damage
            WHERE guild_id = ?
            ORDER BY damage DESC
            """,
            (guild_id,),
        )
        return list(await cursor.fetchall())

    async def record_heal(self, guild_id: int, healer_id: int, target_id: int) -> None:
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO boss_heals (guild_id, healer_id, target_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, healer_id, target_id, time.time()),
            )
            await self.conn.commit()

    async def clear_boss(self, guild_id: int) -> None:
        async with self._write_lock:
            await self.conn.execute("DELETE FROM boss_sessions WHERE guild_id = ?", (guild_id,))
            await self.conn.commit()

    async def fetch_value(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        cursor = await self.conn.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return row[0]
