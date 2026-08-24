"""Wallet and bank operations for Database."""
from __future__ import annotations

from collections.abc import Iterable

import aiosqlite

import config
from database.types import DailyClaimResult, WalletPanelData


class DatabaseWalletMixin:
    async def get_balance(self, user_id: int, guild_id: int) -> float:
        row = await self.get_user(user_id, guild_id)
        return float(row["wallet"])

    async def get_bank(self, user_id: int, guild_id: int) -> float:
        row = await self.get_user(user_id, guild_id)
        return float(row["bank"])

    async def get_wallet_panel_data(self, user_id: int, guild_id: int) -> WalletPanelData:
        row = await self.get_user(user_id, guild_id)
        expansions = await self.get_bank_expansions(user_id, guild_id)
        from utils.bank_capacity import bank_capacity

        return WalletPanelData(
            wallet=float(row["wallet"]),
            bank=float(row["bank"]),
            bank_capacity=bank_capacity(expansions),
            bank_expansions=expansions,
        )

    async def get_bank_expansions(self, user_id: int, guild_id: int) -> dict[int, int]:
        cursor = await self.conn.execute(
            """
            SELECT tier, quantity FROM user_bank_expansions
            WHERE guild_id = ? AND user_id = ? AND quantity > 0
            """,
            (guild_id, user_id),
        )
        rows = await cursor.fetchall()
        return {int(row["tier"]): int(row["quantity"]) for row in rows}

    async def get_bank_expansion_total(self, user_id: int, guild_id: int) -> int:
        expansions = await self.get_bank_expansions(user_id, guild_id)
        return sum(expansions.values())

    async def get_bank_capacity(self, user_id: int, guild_id: int) -> float:
        from utils.bank_capacity import bank_capacity

        expansions = await self.get_bank_expansions(user_id, guild_id)
        return bank_capacity(expansions)

    async def get_bank_deposit_room(self, user_id: int, guild_id: int) -> float:
        from utils.bank_capacity import bank_deposit_room

        bank = await self.get_bank(user_id, guild_id)
        expansions = await self.get_bank_expansions(user_id, guild_id)
        return bank_deposit_room(bank, expansions)

    async def expand_bank_capacity(
        self, user_id: int, guild_id: int, tier: int = 1,
    ) -> tuple[bool, str]:
        """Buy one bank expansion token of the given tier (+capacity) from pocket."""
        import config

        spec = config.BANK_EXPANSION_TIERS.get(tier)
        if spec is None:
            return False, "invalid_tier"
        cost = float(spec["cost"])
        expansions = await self.get_bank_expansions(user_id, guild_id)
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            if row is None or float(row["wallet"]) < cost:
                await self.conn.commit()
                return False, "insufficient_wallet"
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet - ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (cost, user_id, guild_id),
            )
            qty = expansions.get(tier, 0) + 1
            await self.conn.execute(
                """
                INSERT INTO user_bank_expansions (guild_id, user_id, tier, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, tier) DO UPDATE SET
                    quantity = excluded.quantity
                """,
                (guild_id, user_id, tier, qty),
            )
            await self.conn.commit()
        return True, "ok"

    async def _bank_expansions_for_user(self, user_id: int, guild_id: int) -> dict[int, int]:
        cursor = await self.conn.execute(
            """
            SELECT tier, quantity FROM user_bank_expansions
            WHERE guild_id = ? AND user_id = ? AND quantity > 0
            """,
            (guild_id, user_id),
        )
        rows = await cursor.fetchall()
        return {int(row["tier"]): int(row["quantity"]) for row in rows}

    async def get_net_worth(self, user_id: int, guild_id: int) -> float:
        row = await self.get_user(user_id, guild_id)
        return float(row["wallet"]) + float(row["bank"])

    async def deposit_to_bank(self, user_id: int, guild_id: int, amount: float) -> bool:
        if amount <= 0:
            return False
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT wallet, bank FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            if row is None:
                await self.conn.commit()
                return False
            wallet = float(row["wallet"])
            if wallet <= 0:
                await self.conn.commit()
                return False
            from utils.bank_capacity import bank_deposit_room

            expansions = await self._bank_expansions_for_user(user_id, guild_id)
            room = bank_deposit_room(float(row["bank"]), expansions)
            if room <= 0:
                await self.conn.commit()
                return False
            actual = min(amount, wallet, room)
            if actual <= 0:
                await self.conn.commit()
                return False
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet - ?, bank = bank + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (actual, actual, user_id, guild_id),
            )
            await self.conn.commit()
            return True

    async def withdraw_from_bank(self, user_id: int, guild_id: int, amount: float) -> bool:
        if amount <= 0:
            return False
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT bank FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            if row is None or float(row["bank"]) < amount:
                await self.conn.commit()
                return False
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet + ?, bank = bank - ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, amount, user_id, guild_id),
            )
            await self.conn.commit()
            return True

    async def deposit_all_to_bank(self, user_id: int, guild_id: int) -> float:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                """
                SELECT wallet, bank FROM users
                WHERE user_id = ? AND guild_id = ?
                """,
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            wallet = float(row["wallet"]) if row is not None else 0.0
            if wallet <= 0:
                await self.conn.commit()
                return 0.0
            from utils.bank_capacity import bank_deposit_room

            expansions = await self._bank_expansions_for_user(user_id, guild_id)
            bank = float(row["bank"]) if row is not None else 0.0
            room = bank_deposit_room(bank, expansions)
            amount = min(wallet, room)
            if amount <= 0:
                await self.conn.commit()
                return 0.0
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet - ?, bank = bank + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, amount, user_id, guild_id),
            )
            await self.conn.commit()
            return amount

    async def withdraw_all_from_bank(self, user_id: int, guild_id: int) -> float:
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT bank FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            amount = float(row["bank"]) if row is not None else 0.0
            if amount <= 0:
                await self.conn.commit()
                return 0.0
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet + ?, bank = 0
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, user_id, guild_id),
            )
            await self.conn.commit()
            return amount

    async def credit_wallet(
        self,
        user_id: int,
        guild_id: int,
        amount: float,
        *,
        apply_bonuses: bool = True,
    ) -> None:
        if amount <= 0:
            return
        if apply_bonuses:
            amount = await self._apply_income_bonuses(user_id, guild_id, amount)
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
            await self._ensure_progress_no_lock(user_id, guild_id)
            await self.conn.execute(
                """
                UPDATE user_progress
                SET goonbux_spent = goonbux_spent + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (amount, user_id, guild_id),
            )
            await self.conn.commit()
            return True

    async def get_goonbux_spent(self, user_id: int, guild_id: int) -> float:
        progress = await self.get_user_progress(user_id, guild_id)
        try:
            return float(progress["goonbux_spent"])
        except (KeyError, IndexError, TypeError):
            return 0.0

    async def buy_heat_boost(self, user_id: int, guild_id: int) -> tuple[str | None, float]:
        """Spend wallet goonbux to reach the next heat tier. Returns (error, spent)."""
        from utils.heat import cost_to_reach_tier, next_heat_tier

        spent = await self.get_goonbux_spent(user_id, guild_id)
        nxt = next_heat_tier(spent)
        if nxt is None:
            return "max_tier", 0.0
        cost = cost_to_reach_tier(spent, nxt)
        if cost <= 0:
            return "max_tier", 0.0
        if not await self.debit_wallet(user_id, guild_id, cost):
            return "insufficient_funds", 0.0
        return None, cost

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

    async def remove_up_to_bank(self, user_id: int, guild_id: int, amount: float) -> float:
        if amount <= 0:
            return 0.0
        async with self._write_lock:
            await self._ensure_user_no_lock(user_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT bank FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            bank = float(row["bank"]) if row is not None else 0.0
            removed = min(bank, amount)
            if removed:
                await self.conn.execute(
                    """
                    UPDATE users
                    SET bank = bank - ?, wallet = wallet + ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (removed, removed, user_id, guild_id),
                )
            await self.conn.commit()
            return removed

    async def steal_from_bank(
        self,
        target_id: int,
        thief_id: int,
        guild_id: int,
        amount: float,
    ) -> float:
        """Remove up to amount from target bank and credit thief wallet."""
        if amount <= 0 or target_id == thief_id:
            return 0.0
        async with self._write_lock:
            await self._ensure_user_no_lock(target_id, guild_id)
            await self._ensure_user_no_lock(thief_id, guild_id)
            cursor = await self.conn.execute(
                "SELECT bank FROM users WHERE user_id = ? AND guild_id = ?",
                (target_id, guild_id),
            )
            row = await cursor.fetchone()
            bank = float(row["bank"]) if row is not None else 0.0
            stolen = min(bank, amount)
            if stolen <= 0:
                await self.conn.commit()
                return 0.0
            await self.conn.execute(
                """
                UPDATE users
                SET bank = bank - ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (stolen, target_id, guild_id),
            )
            await self.conn.execute(
                """
                UPDATE users
                SET wallet = wallet + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (stolen, thief_id, guild_id),
            )
            await self.conn.commit()
            return stolen

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
        amount = await self._apply_income_bonuses(user_id, guild_id, amount)
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

    async def record_passive_chat_reward(
        self, user_id: int, guild_id: int, base_reward: float,
    ) -> None:
        aspect = await self.get_equipped_aspect_bonuses(user_id, guild_id)
        await self.record_message_reward(user_id, guild_id, base_reward * aspect.passive_income_mult)

    async def claim_daily(
        self,
        user_id: int,
        guild_id: int,
        reward: float,
        cooldown_seconds: float,
        timestamp: float,
    ) -> DailyClaimResult:
        income_mult = await self.get_income_multiplier(user_id, guild_id)
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._ensure_user_no_lock(user_id, guild_id)
                cursor = await self.conn.execute(
                    """
                    SELECT last_daily, daily_streak FROM users
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (user_id, guild_id),
                )
                row = await cursor.fetchone()
                last_daily = float(row["last_daily"]) if row is not None else 0.0
                current_streak = int(row["daily_streak"]) if row is not None else 0
                remaining = (last_daily + cooldown_seconds) - timestamp if last_daily > 0 else -1
                if remaining > 0:
                    await self.conn.rollback()
                    return DailyClaimResult(remaining, 0.0, current_streak, 1.0)

                streak_window = cooldown_seconds + config.DAILY_STREAK_GRACE_SECONDS
                if last_daily > 0 and (timestamp - last_daily) <= streak_window:
                    new_streak = min(current_streak + 1, config.DAILY_STREAK_MAX_DAYS)
                else:
                    new_streak = 1
                streak_bonus_mult = 1.0 + (new_streak - 1) * config.DAILY_STREAK_BONUS_PER_DAY
                max_mult = 1.0 + (config.DAILY_STREAK_MAX_DAYS - 1) * config.DAILY_STREAK_BONUS_PER_DAY
                streak_bonus_mult = min(streak_bonus_mult, max_mult)
                reward_with_streak = reward * streak_bonus_mult
                bonus_reward = reward_with_streak * income_mult
                await self.conn.execute(
                    """
                    UPDATE users
                    SET wallet = wallet + ?,
                        total_earned = total_earned + ?,
                        last_daily = ?,
                        daily_streak = ?
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (bonus_reward, bonus_reward, timestamp, new_streak, user_id, guild_id),
                )
            except Exception:
                await self.conn.rollback()
                raise
            await self.conn.commit()
            return DailyClaimResult(None, bonus_reward, new_streak, streak_bonus_mult)

