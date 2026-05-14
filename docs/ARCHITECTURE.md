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
in a guild at a time. Discord presence is intentionally ignored: every target
gets the configured transfer timer, even if their status appears offline.

### `hacker_cooldowns`

Tracks the last `/hack` command use per `(guild_id, user_id)`. The default
cooldown is 300 seconds, and the live `hack_cooldown_seconds` setting can tune
it per server.

### `boss_sessions`, `boss_damage`, `boss_heals`

Boss state is persisted so restarts do not lose the active boss, accumulated
damage, or heal records.

### `inventory`, `equipment`, `combat_state`

Inventory stores purchased shop items per user and guild. Equipment stores the
single equipped weapon and armor item. Combat state tracks current/max HP for
boss counterattacks, allowing armor to increase max HP and reduce incoming
damage before downing a player.

### `guild_config`

Stores per-server overrides for live tuneable settings. Missing rows fall back
to the defaults declared in `config.LIVE_SETTINGS`.

## Permission Boundaries

`/summon` and all admin dashboard commands use
`@app_commands.checks.has_permissions(administrator=True)` and reject non-admin
users before privileged state is modified.

### Admin Dashboard (`cogs/admin.py`)

The admin cog owns currency-management commands, live config updates, and the
`/bot-status` dashboard. Config autocomplete is driven from
`config.LIVE_SETTINGS`, so new settings only need to be registered once.

### Shop (`cogs/shop.py`)

The shop cog exposes `/shop`, `/buy`, `/inventory`, and `/equip`. The item
catalog lives in `items.py` and currently contains 10 weapons plus 10 armor
pieces. Prices scale up to 120,000 nuggets for top-tier gear to keep the best
items as long-term goals for active players.

### Boss Gear Combat (`cogs/boss.py`)

Weapons add flat boss damage and flavor verbs to `/attack`; some top-tier
weapons add critical chance. Boss variants carry threat metadata that controls
counterattack damage ranges and critical-hit chance. Armor blocks counterattack
damage and adds max HP; players are only downed when their combat HP reaches 0.

### Web Dashboard (`dashboard.py`)

The browser dashboard is an `aiohttp` server that runs inside the same process
as the Discord bot. It binds to Railway's `PORT` when present and exposes a
login-protected HTML dashboard plus a token-protected JSON status endpoint.
The public `/health` route intentionally reports only process readiness.

## Security Notes

- The Discord token and AI API key are read from environment variables.
- Webhook reposts disable mentions with `discord.AllowedMentions.none()`.
- All user-provided amounts are validated as finite positive values.
- Debit operations are transactional and reject insufficient balances.
- AI endpoints must use HTTPS unless they point at localhost and are called with
  a short timeout.
- Live config values are validated before storage and are scoped per guild.
- Web dashboard data requires `DASHBOARD_TOKEN`; without it, dashboard data
  routes return setup guidance instead of server/economy information.
