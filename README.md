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

## Security and permissions

- The bot token is read only from environment variables and is never logged.
- `/summon` is protected with Discord's administrator permission check.
- Webhook reposts use `AllowedMentions.none()` so altered messages cannot
  trigger accidental mass mentions.
- Economy debit paths validate funds and never create negative balances.
- External AI calls are optional, use a timeout, and only accept HTTP(S) URLs.

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
│   └── trivia.py
├── utils/
│   └── helpers.py
├── models/
│   └── __init__.py
└── docs/
    └── ARCHITECTURE.md
```
