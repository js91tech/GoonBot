"""Dungeon tier difficulty scaling tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import config
from cogs.dungeon import Dungeon
from database import Database
from utils.dungeon_tiers import NORMAL_TIER, VAULT_TIER, next_enemy_hp, next_party_enemy_hp


class DungeonPanelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.connect()
        await self.db.init_schema()
        self.bot = SimpleNamespace(db=self.db)
        self.cog = Dungeon(self.bot)  # type: ignore[arg-type]
        self.guild_id = 9001
        self.user_id = 42

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.tmp.cleanup()

    async def test_build_embed_no_run_shows_tiers(self) -> None:
        embed, has_run, _ = await self.cog.build_dungeon_embed(self.guild_id, self.user_id)
        self.assertFalse(has_run)
        self.assertIn("choose your depth", embed.title.lower())
        standard = next(f for f in embed.fields if f.name == "Standard")
        self.assertIn("Delver's Depths", standard.value)
        premium = next(f for f in embed.fields if f.name == "Premium")
        self.assertIn("Gilded Vault", premium.value)

    async def test_build_embed_active_run_shows_hp(self) -> None:
        await self.db.start_dungeon_run(self.user_id, self.guild_id, 100.0, 100.0, 80.0)
        embed, has_run, _ = await self.cog.build_dungeon_embed(self.guild_id, self.user_id)
        self.assertTrue(has_run)
        self.assertIn("Room 1/", embed.title)
        hp_field = next(f for f in embed.fields if f.name == "Your HP")
        self.assertIn("100", hp_field.value)

    async def test_start_rejects_insufficient_energy(self) -> None:
        char = await self.db.get_user_character(self.user_id, self.guild_id)
        cap = int(char["energy_cap"])
        ok, _ = await self.db.spend_job_energy(self.user_id, self.guild_id, cap)
        self.assertTrue(ok)
        result = await self.cog.execute_dungeon_start(self.guild_id, self.user_id)
        self.assertIsNotNone(result.error)
        assert result.error is not None
        self.assertIn("Not enough energy", result.error)
        run = await self.db.get_dungeon_run(self.user_id, self.guild_id)
        self.assertIsNone(run)

    async def test_start_spends_energy_and_creates_run(self) -> None:
        result = await self.cog.execute_dungeon_start(self.guild_id, self.user_id)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.embed)
        run = await self.db.get_dungeon_run(self.user_id, self.guild_id)
        self.assertIsNotNone(run)
        char = await self.db.get_user_character(self.user_id, self.guild_id)
        expected = int(char["energy_cap"]) - config.DUNGEON_ENERGY_COST
        self.assertEqual(int(char["energy"]), expected)

    async def test_vault_solo_start_rejected(self) -> None:
        await self.db.credit_wallet(self.user_id, self.guild_id, 100_000.0)
        await self.db.unlock_vault_dungeon(
            self.user_id, self.guild_id, config.DUNGEON_VAULT_UNLOCK_COST,
        )
        result = await self.cog.execute_dungeon_start(
            self.guild_id, self.user_id, tier_id=VAULT_TIER.tier_id,
        )
        self.assertIsNotNone(result.error)
        assert result.error is not None
        self.assertIn("party", result.error.lower())

    async def test_vault_party_requires_min_raiders(self) -> None:
        await self.db.credit_wallet(self.user_id, self.guild_id, 100_000.0)
        await self.db.unlock_vault_dungeon(
            self.user_id, self.guild_id, config.DUNGEON_VAULT_UNLOCK_COST,
        )
        create = await self.cog.execute_party_create(
            self.guild_id, self.user_id, tier_id=VAULT_TIER.tier_id,
        )
        self.assertIsNone(create.error)
        fight = await self.cog.execute_party_fight(
            self.guild_id, self.user_id, display_name="Tester",
        )
        self.assertIsNotNone(fight.error)
        assert fight.error is not None
        self.assertIn(str(config.DUNGEON_VAULT_MIN_PARTY_SIZE), fight.error)


class DungeonDifficultyTests(unittest.TestCase):
    def test_standard_enemy_hp_is_10x_base(self) -> None:
        hp = next_enemy_hp(NORMAL_TIER, 1)
        self.assertGreaterEqual(hp, NORMAL_TIER.enemy_hp_room1_min)
        self.assertLessEqual(hp, NORMAL_TIER.enemy_hp_room1_max)
        self.assertEqual(NORMAL_TIER.enemy_hp_room1_min, 1150.0)
        self.assertEqual(NORMAL_TIER.counter_min, 180)

    def test_vault_party_enemy_hp_is_100x_base(self) -> None:
        hp = next_party_enemy_hp(VAULT_TIER, 1)
        self.assertGreaterEqual(hp, VAULT_TIER.party_enemy_hp_room1_min)
        self.assertLessEqual(hp, VAULT_TIER.party_enemy_hp_room1_max)
        self.assertEqual(VAULT_TIER.party_enemy_hp_room1_min, 48_000.0)
        self.assertEqual(VAULT_TIER.party_counter_min, 2400)


if __name__ == "__main__":
    unittest.main()
