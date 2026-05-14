from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

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

            CREATE INDEX IF NOT EXISTS idx_users_guild_wallet
                ON users(guild_id, wallet DESC);
            CREATE INDEX IF NOT EXISTS idx_bounties_guild
                ON bounties(guild_id);
            """
        )
        await self.conn.commit()

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
                remaining = (last_daily + cooldown_seconds) - timestamp
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
