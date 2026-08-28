#!/usr/bin/env python3
"""One-time helper: split database.py into database/ package with wallet + inventory mixins."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "database.py"
PKG = ROOT / "database"

WALLET_METHODS = {
    "get_balance",
    "get_bank",
    "get_wallet_panel_data",
    "get_bank_expansions",
    "get_bank_expansion_total",
    "get_bank_capacity",
    "get_bank_deposit_room",
    "expand_bank_capacity",
    "_bank_expansions_for_user",
    "get_net_worth",
    "deposit_to_bank",
    "withdraw_from_bank",
    "deposit_all_to_bank",
    "withdraw_all_from_bank",
    "credit_wallet",
    "credit_wallets",
    "set_wallet",
    "debit_wallet",
    "remove_up_to_balance",
    "remove_up_to_bank",
    "steal_from_bank",
    "transfer_wallet",
    "record_message_reward",
    "record_passive_chat_reward",
    "claim_daily",
}

INVENTORY_METHODS = {
    "buy_item",
    "sell_one_item",
    "get_inventory",
    "grant_inventory_quantity",
    "remove_inventory_quantity",
    "gift_inventory_item",
    "get_inventory_quantity",
}


def extract_methods(source: str, class_name: str, method_names: set[str]) -> tuple[str, str]:
    """Return (extracted_methods_text, source_with_methods_removed)."""
    pattern = re.compile(
        rf"(?m)^    async def ({'|'.join(re.escape(n) for n in sorted(method_names))})\(",
    )
    lines = source.splitlines(keepends=True)
    in_class = False
    class_indent = 0
    extracted_blocks: list[str] = []
    skip_ranges: list[tuple[int, int]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(f"class {class_name}"):
            in_class = True
            class_indent = len(line) - len(line.lstrip())
            i += 1
            continue
        if in_class and line.startswith("class ") and not line.startswith(" " * (class_indent + 1)):
            in_class = False

        if in_class:
            match = pattern.match(line)
            if match and match.group(1) in method_names:
                start = i
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip() == "":
                        i += 1
                        continue
                    if (
                        next_line.startswith("    async def ")
                        or next_line.startswith("    def ")
                        or (next_line.startswith("class ") and not next_line.startswith(" "))
                    ):
                        break
                    i += 1
                extracted_blocks.append("".join(lines[start:i]))
                skip_ranges.append((start, i))
                continue
        i += 1

    remaining: list[str] = []
    skip_idx = 0
    for idx, line in enumerate(lines):
        if skip_idx < len(skip_ranges) and idx == skip_ranges[skip_idx][0]:
            skip_idx += 1
            continue
        if skip_idx > 0 and idx < skip_ranges[skip_idx - 1][1]:
            continue
        remaining.append(line)

    return "".join(extracted_blocks), "".join(remaining)


def main() -> None:
    source = SRC.read_text()
    types_end = source.index("\n\nclass PostgresCursor:")
    types_block = source[:types_end].rstrip() + "\n"

    wallet_block, after_wallet = extract_methods(source, "Database", WALLET_METHODS)
    inventory_block, after_both = extract_methods(after_wallet, "Database", INVENTORY_METHODS)

    if PKG.exists():
        shutil.rmtree(PKG)
    PKG.mkdir()

    # types.py — shared helpers and NamedTuples (no Postgres classes; those stay in core)
    types_only_end = source.index("\n\nclass PostgresCursor:")
    # Keep Postgres in core; types file gets NamedTuples + _spendable_cents only
    spendable_end = source.index("\n\nclass PostgresCursor:")
    types_header = source[:spendable_end]
    # Trim to end of _spendable_cents function
    types_trim = types_header[: types_header.rindex("\n\n") + 2]
    (PKG / "types.py").write_text(
        types_trim.replace("from database_expansion import DatabaseExpansionMixin\n", "")
        + "\n",
    )

    shutil.copy(ROOT / "database_expansion.py", PKG / "expansion.py")
    exp_text = (PKG / "expansion.py").read_text()
    exp_text = exp_text.replace(
        "class DatabaseExpansionMixin:",
        "class DatabaseExpansionMixin:\n    \"\"\"Gameplay expansion tables and helpers.\"\"\"",
    )
    (PKG / "expansion.py").write_text(exp_text)

    wallet_header = '''"""Wallet and bank operations for Database."""
from __future__ import annotations

from collections.abc import Iterable

import aiosqlite

import config
from database.types import DailyClaimResult, WalletPanelData


class DatabaseWalletMixin:
'''
    (PKG / "wallet.py").write_text(wallet_header + wallet_block)

    inventory_header = '''"""Stackable inventory shop operations for Database."""
from __future__ import annotations

import aiosqlite

import config
from database.types import _spendable_cents


class DatabaseInventoryMixin:
'''
    (PKG / "inventory.py").write_text(inventory_header + inventory_block)

    core = after_both
    core = core.replace(
        "from database_expansion import DatabaseExpansionMixin",
        "from database.expansion import DatabaseExpansionMixin\n"
        "from database.inventory import DatabaseInventoryMixin\n"
        "from database.types import DailyClaimResult, WalletPanelData, _spendable_cents\n"
        "from database.wallet import DatabaseWalletMixin",
    )
    core = core.replace(
        "class Database(DatabaseExpansionMixin):",
        "class Database(DatabaseWalletMixin, DatabaseInventoryMixin, DatabaseExpansionMixin):",
    )

    # Remove duplicate type definitions from core (moved to types.py)
    core_start = core.index("from __future__")
    postgres_start = core.index("\n\nclass PostgresCursor:")
    imports_and_postgres = core[core_start:postgres_start]
    # Rebuild: keep imports (minus duplicate types), then Postgres+Database from postgres_start
    imports_lines = []
    for line in imports_and_postgres.splitlines():
        if line.startswith("class DailyClaimResult") or line.startswith("class WalletPanelData"):
            continue
        if line.startswith("def _spendable_cents"):
            break
        imports_lines.append(line)
    # Find where _spendable_cents ends in original core section
    rest_from_postgres = core[postgres_start:]
    core_body = "\n".join(imports_lines).rstrip() + "\n" + rest_from_postgres

    (PKG / "core.py").write_text(core_body)

    init_py = '''"""GoonBot database layer."""
from database.core import Database
from database.types import DailyClaimResult, WalletPanelData

__all__ = ["Database", "DailyClaimResult", "WalletPanelData"]
'''
    (PKG / "__init__.py").write_text(init_py)

    SRC.unlink()
    (ROOT / "database_expansion.py").unlink()

    print("Created database/ package")
    print(f"  wallet methods: {len(WALLET_METHODS)}")
    print(f"  inventory methods: {len(INVENTORY_METHODS)}")


if __name__ == "__main__":
    main()
