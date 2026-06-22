"""Business Empire: income math and database create/collect/upgrade flows."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import config
from database import Database
from utils.businesses import (
    BUSINESS_TIERS,
    accrue_income,
    capacity_for_level,
    hourly_income,
    next_tier_def,
    tier_def,
    tier_def_by_id,
    upgrade_cost,
)


class BusinessMathTests(unittest.TestCase):
    def test_seven_tiers_increasing(self) -> None:
        self.assertEqual(len(BUSINESS_TIERS), 7)
        costs = [t.purchase_cost for t in BUSINESS_TIERS]
        incomes = [t.base_income_per_hour for t in BUSINESS_TIERS]
        self.assertEqual(costs, sorted(costs))
        self.assertEqual(incomes, sorted(incomes))

    def test_tier_lookup(self) -> None:
        self.assertEqual(tier_def(1).tier_id, "lemon_stand")
        self.assertEqual(tier_def_by_id("corporation").tier, 7)
        self.assertIsNone(tier_def(99))
        self.assertIsNone(next_tier_def(7))
        self.assertEqual(next_tier_def(1).tier, 2)

    def test_hourly_scales_with_upgrades(self) -> None:
        base = hourly_income(tier=1)
        self.assertAlmostEqual(base, 20.0)
        boosted = hourly_income(tier=1, efficiency_level=5, reputation_level=5)
        self.assertGreater(boosted, base)

    def test_growth_branch_boosts_income(self) -> None:
        base = hourly_income(tier=4)
        grown = hourly_income(tier=4, growth_branch_level=3)
        self.assertGreater(grown, base)

    def test_production_branch_boosts_income(self) -> None:
        base = hourly_income(tier=4)
        produced = hourly_income(tier=4, production_branch_level=3)
        self.assertGreater(produced, base)

    def test_satisfaction_swing(self) -> None:
        low = hourly_income(tier=3, satisfaction=0)
        neutral = hourly_income(tier=3, satisfaction=50)
        high = hourly_income(tier=3, satisfaction=100)
        self.assertLess(low, neutral)
        self.assertGreater(high, neutral)

    def test_accrue_caps_at_capacity(self) -> None:
        cap = capacity_for_level(1, 0)
        result = accrue_income(stored=0.0, capacity=cap, hourly=1_000_000.0, elapsed_seconds=99999.0)
        self.assertLessEqual(result, cap)

    def test_accrue_adds_partial(self) -> None:
        result = accrue_income(stored=0.0, capacity=10_000.0, hourly=3600.0, elapsed_seconds=3600.0)
        self.assertAlmostEqual(result, 3600.0, places=2)

    def test_upgrade_cost_grows(self) -> None:
        c0 = upgrade_cost(1, 0)
        c1 = upgrade_cost(1, 1)
        self.assertGreater(c1, c0)


class BusinessDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_create_requires_funds(self) -> None:
        guild_id, uid = 1, 100
        await self.db.ensure_user(uid, guild_id)
        err = await self.db.create_business(uid, guild_id)
        self.assertEqual(err, "insufficient_funds")

    async def test_create_debits_and_persists(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 1_000.0, apply_bonuses=False)
        err = await self.db.create_business(uid, guild_id)
        self.assertIsNone(err)
        self.assertAlmostEqual(await self.db.get_balance(uid, guild_id), 500.0)
        row = await self.db.get_business(uid, guild_id)
        self.assertIsNotNone(row)
        self.assertEqual(int(row["tier"]), 1)

    async def test_create_twice_blocked(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 2_000.0, apply_bonuses=False)
        self.assertIsNone(await self.db.create_business(uid, guild_id))
        self.assertEqual(await self.db.create_business(uid, guild_id), "already_owns")

    async def test_collect_moves_income_to_wallet(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 1_000.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        # Force stored income by backdating last_income_at by an hour.
        async with self.db._write_lock:
            await self.db.conn.execute(
                "UPDATE user_businesses SET last_income_at = last_income_at - 3600 "
                "WHERE user_id = ? AND guild_id = ?",
                (uid, guild_id),
            )
            await self.db.conn.commit()
        before = await self.db.get_balance(uid, guild_id)
        amount, err = await self.db.collect_business_income(uid, guild_id)
        self.assertIsNone(err)
        self.assertGreater(amount, 0)
        after = await self.db.get_balance(uid, guild_id)
        self.assertAlmostEqual(after, before + amount, places=2)

    async def test_collect_without_business(self) -> None:
        guild_id, uid = 1, 100
        amount, err = await self.db.collect_business_income(uid, guild_id)
        self.assertEqual(err, "no_business")
        self.assertEqual(amount, 0.0)

    async def test_collect_immediately_is_negligible(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 1_000.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        amount, err = await self.db.collect_business_income(uid, guild_id)
        # A freshly created business has only milliseconds of accrued income.
        self.assertTrue(err is None or err == "empty")
        self.assertLess(amount, 1.0)

    async def test_tier_up(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 10_000.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        err, new_tier = await self.db.tier_up_business(uid, guild_id)
        self.assertIsNone(err)
        self.assertEqual(new_tier, 2)
        row = await self.db.get_business(uid, guild_id)
        self.assertEqual(str(row["tier_id"]), "food_cart")

    async def test_tier_up_insufficient(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 600.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        err, _ = await self.db.tier_up_business(uid, guild_id)
        self.assertEqual(err, "insufficient_funds")

    async def test_upgrade_attribute(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 5_000.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        cost, err = await self.db.upgrade_business_attribute(uid, guild_id, "efficiency")
        self.assertIsNone(err)
        self.assertGreater(cost, 0)
        row = await self.db.get_business(uid, guild_id)
        self.assertEqual(int(row["efficiency"]), 1)

    async def test_upgrade_branch_growth(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 5_000.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        _, err = await self.db.upgrade_business_attribute(uid, guild_id, "branch_growth")
        self.assertIsNone(err)
        row = await self.db.get_business(uid, guild_id)
        self.assertEqual(int(row["branch_growth"]), 1)

    async def test_branch_cap_enforced(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 5_000_000.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        for _ in range(config.BUSINESS_BRANCH_MAX):
            _, err = await self.db.upgrade_business_attribute(uid, guild_id, "branch_production")
            self.assertIsNone(err)
        _, err = await self.db.upgrade_business_attribute(uid, guild_id, "branch_production")
        self.assertEqual(err, "max_level")

    async def test_upgrade_invalid_attribute(self) -> None:
        guild_id, uid = 1, 100
        await self.db.credit_wallet(uid, guild_id, 5_000.0, apply_bonuses=False)
        await self.db.create_business(uid, guild_id)
        _, err = await self.db.upgrade_business_attribute(uid, guild_id, "nope")
        self.assertEqual(err, "invalid_attribute")


if __name__ == "__main__":
    unittest.main()
