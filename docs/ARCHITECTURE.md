# NuggetBot Architecture Documentation

## Overview

NuggetBot is a Discord economy bot built on **discord.py 2.x** with an
**async SQLite** backend. Each game system is implemented as a separate cog,
and all tunable values live in `config.py`.

## Database Schema

### `users`

Economy is per guild. User rows are keyed by `(user_id, guild_id)` and track
wallet balance, daily/heist cooldowns, arrest/downed timers, and basic stats.

### `bounties`

Stores active bounties, scoped by guild, with the placer, target, amount, and
single trigger word.

### `hacker_pots`

Tracks the active hot-potato virus per guild. At most one virus may be active
in a guild at a time.

### `boss_sessions`, `boss_damage`, `boss_heals`

Boss state is persisted so restarts do not lose the active boss, accumulated
damage, or heal records.

## Permission Boundaries

Only `/summon` is an administrative command in the documented command set. It
uses `@app_commands.checks.has_permissions(administrator=True)` and rejects
non-admin users before any boss state is modified.

## Security Notes

- The Discord token and AI API key are read from environment variables.
- Webhook reposts disable mentions with `discord.AllowedMentions.none()`.
- All user-provided amounts are validated as finite positive values.
- Debit operations are transactional and reject insufficient balances.
- AI endpoints must use `http` or `https` and are called with a short timeout.
