"""Onboarding quest progress for gifting."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database import Database
from utils.quests import ONBOARDING_QUESTS, ensure_onboarding_quests, record_quest_event


class GiftQuestTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.db_path)
        await self.db.connect()
        self.guild_id = 1
        self.user_id = 100

    async def asyncTearDown(self) -> None:
        await self.db.close()
        Path(self.db_path).unlink(missing_ok=True)

    async def test_item_gift_completes_onboarding_quest(self) -> None:
        await self.db.ensure_user(self.user_id, self.guild_id)
        await ensure_onboarding_quests(self.db, self.guild_id, self.user_id)
        await self.db.grant_item(self.user_id, self.guild_id, "chia_seeds")
        receiver = 200
        await self.db.ensure_user(receiver, self.guild_id)

        completed_ids = await record_quest_event(
            self.db, self.guild_id, self.user_id, "item_gift",
        )
        self.assertIn("gift_once", completed_ids)
        gift_quest = next(q for q in ONBOARDING_QUESTS if q.quest_id == "gift_once")
        self.assertEqual(gift_quest.event, "item_gift")
        rows = await self.db.list_user_quests(self.guild_id, self.user_id, "onboarding")
        gift_row = next(r for r in rows if str(r["quest_id"]) == "gift_once")
        self.assertEqual(int(gift_row["progress"]), 1)
        self.assertIsNotNone(gift_row["completed_at"])


if __name__ == "__main__":
    unittest.main()
