"""Crew banking helpers, loans, withdraw caps, and level perks."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import config
from database import Database
from utils.crew_banking import (
    crew_level_from_xp,
    heist_same_crew_bonus,
    max_loan_amount,
)


class CrewBankingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def _setup_member(
        self,
        guild_id: int,
        uid: int,
        crew: str,
        wallet: float,
        treasury: float = 0.0,
    ) -> None:
        await self.db.ensure_user(uid, guild_id)
        await self.db.credit_wallet(uid, guild_id, wallet + treasury)
        await self.db.join_crew(uid, guild_id, crew)
        if treasury > 0:
            err = await self.db.deposit_crew_treasury(uid, guild_id, treasury)
            self.assertIsNone(err)

    def test_heist_same_crew_bonus_stacks_and_caps(self) -> None:
        ids = [1, 2, 3]
        crews = {1: "Raiders", 2: "Raiders", 3: "Other"}
        bonus = heist_same_crew_bonus(ids, crews)
        self.assertAlmostEqual(bonus, 0.05)

        crews_both = {1: "Raiders", 2: "Raiders", 3: "Raiders"}
        capped = heist_same_crew_bonus(ids, crews_both)
        self.assertAlmostEqual(capped, 0.10)

    def test_max_loan_amount_scales_with_level(self) -> None:
        low = max_loan_amount(1000.0, 1)
        high = max_loan_amount(1000.0, 5)
        self.assertGreater(high, low)

    def test_crew_level_from_xp(self) -> None:
        self.assertEqual(crew_level_from_xp(0), 1)
        self.assertEqual(crew_level_from_xp(config.CREW_XP_PER_LEVEL), 2)

    async def test_deposit_increases_contributed(self) -> None:
        guild_id, uid = 1, 100
        await self._setup_member(guild_id, uid, "Raiders", wallet=500.0)
        err = await self.db.deposit_crew_treasury(uid, guild_id, 200.0)
        self.assertIsNone(err)
        contributed = await self.db.get_crew_contributed(guild_id, "Raiders", uid)
        self.assertAlmostEqual(contributed, 200.0)

    async def test_loan_moves_treasury_to_wallet(self) -> None:
        guild_id, uid = 2, 200
        await self._setup_member(guild_id, uid, "Lenders", wallet=100.0, treasury=1000.0)
        wallet_before = await self.db.get_balance(uid, guild_id)
        stats_before = await self.db.get_crew_stats(guild_id, "Lenders")
        assert stats_before is not None
        treasury_before = float(stats_before["treasury"])

        err = await self.db.issue_crew_loan(uid, guild_id, config.CREW_LOAN_MIN_AMOUNT)
        self.assertIsNone(err)

        wallet_after = await self.db.get_balance(uid, guild_id)
        stats_after = await self.db.get_crew_stats(guild_id, "Lenders")
        assert stats_after is not None
        self.assertAlmostEqual(
            wallet_after - wallet_before,
            config.CREW_LOAN_MIN_AMOUNT,
        )
        self.assertAlmostEqual(
            treasury_before - float(stats_after["treasury"]),
            config.CREW_LOAN_MIN_AMOUNT,
        )

    async def test_repay_reduces_remaining_and_increases_treasury(self) -> None:
        guild_id, uid = 3, 300
        await self._setup_member(guild_id, uid, "Repayers", wallet=500.0, treasury=2000.0)
        loan_amount = 100.0
        self.assertIsNone(await self.db.issue_crew_loan(uid, guild_id, loan_amount))
        await self.db.credit_wallet(uid, guild_id, 500.0)
        stats_mid = await self.db.get_crew_stats(guild_id, "Repayers")
        assert stats_mid is not None
        treasury_mid = float(stats_mid["treasury"])

        loan_row = await self.db.get_active_crew_loan(uid, guild_id)
        assert loan_row is not None
        remaining_before = float(loan_row["remaining"])
        err = await self.db.repay_crew_loan(uid, guild_id, 50.0)
        self.assertIsNone(err)

        loan_after = await self.db.get_active_crew_loan(uid, guild_id)
        if loan_after is not None:
            self.assertLess(float(loan_after["remaining"]), remaining_before)
        stats_after = await self.db.get_crew_stats(guild_id, "Repayers")
        assert stats_after is not None
        self.assertGreater(float(stats_after["treasury"]), treasury_mid)

    async def test_cannot_withdraw_more_than_contributed(self) -> None:
        guild_id, uid = 4, 400
        await self._setup_member(guild_id, uid, "Hoarders", wallet=500.0, treasury=300.0)
        err = await self.db.withdraw_crew_contribution(uid, guild_id, 400.0)
        self.assertEqual(err, "insufficient_contribution")

    async def test_cannot_leave_with_active_loan(self) -> None:
        guild_id, uid = 5, 500
        await self._setup_member(guild_id, uid, "Debtors", wallet=200.0, treasury=1000.0)
        self.assertIsNone(
            await self.db.issue_crew_loan(uid, guild_id, config.CREW_LOAN_MIN_AMOUNT),
        )
        result = await self.db.leave_crew(uid, guild_id)
        self.assertEqual(result, "active_loan")

    async def test_level_increases_after_xp_deposits(self) -> None:
        guild_id, uid = 6, 600
        await self._setup_member(guild_id, uid, "Grinders", wallet=500_000.0)
        xp_needed = config.CREW_XP_PER_LEVEL
        deposit_amount = float(xp_needed * 100)
        err = await self.db.deposit_crew_treasury(uid, guild_id, deposit_amount)
        self.assertIsNone(err)
        stats = await self.db.get_crew_stats(guild_id, "Grinders")
        assert stats is not None
        self.assertGreaterEqual(int(stats["level"]), 2)
        self.assertGreaterEqual(int(stats["xp"]), xp_needed)

    async def test_list_joinable_crews_returns_member_counts(self) -> None:
        guild_id = 9
        await self.db.join_crew(501, guild_id, "Alpha")
        await self.db.join_crew(502, guild_id, "Alpha")
        crews = await self.db.list_joinable_crews(guild_id)
        alpha = next((c for c in crews if c[0] == "Alpha"), None)
        self.assertIsNotNone(alpha)
        assert alpha is not None
        self.assertEqual(alpha[1], 2)


if __name__ == "__main__":
    unittest.main()
