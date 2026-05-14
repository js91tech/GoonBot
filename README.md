# NuggetBot

A chaos-driven Discord economy bot built with **discord.py** and **SQLite**.

## Features

| Phase | Module | Description |
|-------|--------|-------------|
| 1 | **The Vault** | Economy: passive chat earning, active bonus, VC earning, daily claims, payments, leaderboards |
| 2 | **The Hit** | Bounty system: place bounties with trigger words, claim when targets slip up |
| 3 | **The Steal** | Heist & crew system: rob users, form crews, arrest failed thieves |
| 4 | **The Virus** | Hot potato: infect users, pass the virus, scaling penalties |
| 5 | **The Boss** | Boss raids: fight Hannah variants, scale HP with economy, down/heal mechanics |
| 6 | **The AI** | Imposter webhook word sabotage + Lore Roulette trivia |

## Quick Start

### 1. Prerequisites

- Python 3.11+
- A Discord bot token
- Message Content intent enabled in the Discord Developer Portal
- Optional: an OpenAI-compatible API key for the Imposter module

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in `DISCORD_TOKEN`. If you want the Imposter AI module
to call an external service, also set `AI_API_KEY`, `AI_API_URL`, and `AI_MODEL`.

### 4. Run

```bash
python bot.py
```

## Commands

### Economy

| Command | Description |
|---------|-------------|
| `/daily` | Claim 75 nuggets daily |
| `/balance` | Check your wallet |
| `/leaderboard` | Top 10 richest users |
| `/pay @user amount` | Send nuggets to another user |

### Bounty

| Command | Description |
|---------|-------------|
| `/bounty @user amount trigger_word` | Place a bounty (min 50 + tax) |
| `/bounties` | List active bounties |

### Heist

| Command | Description |
|---------|-------------|
| `/heist @user [@crew1] [@crew2]` | Attempt a robbery |
| `/arrest @thief` | Arrest a failed thief during the arrest window |
| `/crew` | Crew info |

### Hacker

| Command | Description |
|---------|-------------|
| `/hack @user` | Start a hot potato virus |
| `/transfer @user` | Pass the virus to someone else |

### Boss

| Command | Description |
|---------|-------------|
| `/attack` | Attack the active boss |
| `/heal @user` | Revive a downed teammate |
| `/boss` | Check boss status |
| `/summon variant` | **Admin only:** force-spawn a boss |

### Trivia

| Command | Description |
|---------|-------------|
| `/trivia` | Lore Roulette: guess the blanked word from server history |

### Admin Dashboard

All dashboard commands require Discord administrator permission.

| Command | Description |
|---------|-------------|
| `/gift @user amount` | Give nuggets to one user from thin air |
| `/gift-all amount` | Give nuggets to every human in the server |
| `/set-currency @user amount` | Set a user's wallet to an exact amount |
| `/reset-user @user` | Wipe a user's wallet and stats |
| `/config` | View all live tuneable settings |
| `/config setting value` | Change a setting live for this server |
| `/config-reset setting` | Revert a setting to its default |
| `/bot-status` | View economy totals, active games, and custom settings |

## Live Config

`/config` includes autocomplete for setting names. Settings are stored per
server in SQLite and take effect without restarting the bot.

| Setting | Default | Description |
|---------|---------|-------------|
| `passive_chat_reward` | 0.5 | Per-message earning |
| `passive_active_bonus` | 15.0 | Per active hour earning |
| `voice_chat_reward` | 3.0 | Per minute in VC |
| `daily_reward` | 75.0 | `/daily` claim amount |
| `bounty_min_amount` | 50.0 | Minimum bounty |
| `bounty_bot_tax` | 5.0 | Bot tax on bounties |
| `heist_base_success` | 0.20 | Heist success rate |
| `heist_cooldown_seconds` | 1800 | Heist cooldown |
| `arrest_lockout_seconds` | 3600 | Arrest lockout duration |
| `hack_timer_seconds` | 60 | Hot potato timer |
| `hack_base_penalty` | 35.0 | Starting virus penalty |
| `hack_penalty_increment` | 2.0 | Penalty increase per pass |
| `boss_health_scale_factor` | 0.05 | Boss HP scaling |
| `boss_downed_seconds` | 120 | Boss downed duration |
| `imposter_chance` | 0.01 | Per-message sabotage chance |
| `trivia_reward` | 25.0 | Trivia answer reward |

## Security and permissions

- The bot token is read only from environment variables and is never logged.
- `/summon` and all dashboard commands are protected with Discord's
  administrator permission check.
- Webhook reposts use `AllowedMentions.none()` so altered messages cannot
  trigger accidental mass mentions.
- Economy debit paths validate funds and never create negative balances.
- External AI calls are optional, use a timeout, and require HTTPS unless the
  URL points at localhost.

## Project Structure

```text
NuggetBot/
├── bot.py
├── config.py
├── database.py
├── requirements.txt
├── .env.example
├── cogs/
│   ├── economy.py
│   ├── bounty.py
│   ├── heist.py
│   ├── hacker.py
│   ├── boss.py
│   ├── imposter.py
│   ├── trivia.py
│   └── admin.py
├── utils/
│   └── helpers.py
├── models/
│   └── __init__.py
└── docs/
    └── ARCHITECTURE.md
```
