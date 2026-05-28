"""Shop embed must stay within Discord limits."""
from __future__ import annotations

import unittest

from cogs.shop import _shop_embed_chunks
from items import items_for_category


class ShopEmbedTests(unittest.TestCase):
    def test_all_category_fits_discord_limits(self) -> None:
        lines = [f"line-{i}-" + "x" * 80 for i in range(50)]
        description, fields = _shop_embed_chunks(lines)
        if description is not None:
            self.assertLessEqual(len(description), 4096)
        else:
            self.assertTrue(fields)
            for _name, value in fields:
                self.assertLessEqual(len(value), 1024)

    def test_real_all_items_use_fields_or_short_description(self) -> None:
        items = items_for_category("all")
        lines = [f"`{item.id}` {item.name}" for item in items]
        description, fields = _shop_embed_chunks(lines)
        if description is not None:
            self.assertLessEqual(len(description), 4096)
        else:
            self.assertGreater(len(fields), 0)
            for _name, value in fields:
                self.assertLessEqual(len(value), 1024)


if __name__ == "__main__":
    unittest.main()
