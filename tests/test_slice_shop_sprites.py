"""Tests for shop sprite sheet slicing."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from scripts.slice_shop_sprites import (
    NORMAL_CELL_IDS,
    _extract_cell_boxes,
    _foreground_mask,
    battle_worn_name,
    slice_sheet,
)


class SliceShopSpritesTests(unittest.TestCase):
    def test_battle_worn_name_skips_non_gear(self) -> None:
        self.assertEqual(battle_worn_name("twig_sword"), "boss_weak_twig_sword")
        self.assertIsNone(battle_worn_name("trap_bomb"))
        self.assertIsNone(battle_worn_name("training_stick"))

    def test_extract_cell_boxes_on_synthetic_grid(self) -> None:
        cols, rows = 8, 7
        cell = 64
        pad = 12
        width = cols * cell + (cols + 1) * pad
        height = rows * cell + (rows + 1) * pad
        img = Image.new("RGB", (width, height), (32, 34, 37))
        draw = ImageDraw.Draw(img)
        for row in range(rows):
            for col in range(cols):
                x = pad + col * (cell + pad)
                y = pad + row * (cell + pad)
                draw.rectangle((x + 8, y + 8, x + cell - 8, y + cell - 8), fill=(200, 80, 80))
        mask = _foreground_mask(img, (32, 34, 37))
        boxes = _extract_cell_boxes(mask, rows=rows, cols=cols)
        self.assertEqual(len(boxes), cols * rows)

    def test_slice_sheet_writes_icons(self) -> None:
        cols, rows = 8, 7
        cell = 48
        pad = 10
        width = cols * cell + (cols + 1) * pad
        height = rows * cell + (rows + 1) * pad
        img = Image.new("RGB", (width, height), (32, 34, 37))
        draw = ImageDraw.Draw(img)
        for row in range(rows):
            for col in range(cols):
                x = pad + col * (cell + pad)
                y = pad + row * (cell + pad)
                draw.ellipse((x + 4, y + 4, x + cell - 4, y + cell - 4), fill=(120, 180, 255))
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.png"
            out_dir = Path(tmp) / "items"
            img.save(sheet)
            written = slice_sheet(
                sheet,
                cell_ids=NORMAL_CELL_IDS,
                name_for=lambda item_id: item_id,
                out_dir=out_dir,
            )
            self.assertGreaterEqual(len(written), 40)
            for path in written:
                self.assertTrue(path.is_file())
                with Image.open(path) as icon:
                    self.assertEqual(icon.size, (64, 64))


if __name__ == "__main__":
    unittest.main()
