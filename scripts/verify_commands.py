#!/usr/bin/env python3
"""Smoke-check: all cogs load and slash commands stay within Discord limits."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DISCORD_TOKEN", "x" * 50)

import discord
from discord.ext import commands

from bot import COGS

MAX_TOP_LEVEL_COMMANDS = 100


class _FakeDB:
    is_postgres = False
    path = ":memory:"

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass


async def _main() -> int:
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
    bot.db = _FakeDB()
    errors: list[str] = []
    for ext in COGS:
        try:
            await bot.load_extension(ext)
        except Exception as exc:
            errors.append(f"{ext}: {exc}")
    top_level = len(list(bot.tree.get_commands()))
    if top_level > MAX_TOP_LEVEL_COMMANDS:
        errors.append(
            f"top-level slash commands={top_level} exceeds Discord limit "
            f"of {MAX_TOP_LEVEL_COMMANDS}",
        )
    if errors:
        print("Command verification failed:", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(f"OK: {len(COGS)} cogs loaded, {top_level} top-level slash commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
