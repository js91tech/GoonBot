# GoonBot

**Adult (18+) Discord economy RPG** — a full fork of NuggetBot with explicit NSFW flavor, 18+ age gates, NSFW-channel requirements, and interactive Discord menus for every major player system.

> **Do not merge this branch into NuggetBot `main`.** Deploy GoonBot as its own Discord application, Railway service, and database (ideally its own GitHub repo).

## Product differences from NuggetBot

| Area | GoonBot |
|------|---------|
| Brand | GoonBot · currency **goonbux** 💋 |
| Boss | **Velvet Vixen** (and adult specials) |
| Safety | First-use **18+ confirm**; guild setting `nsfw_channel_only` (default on) |
| UX | Hub panels (Views/Selects/Buttons) for profile, gear, jobs, character, alchemy, companions, relics, museum, GoonCards (148-card lust catalog), crime, casino, dungeon lobby, drugs extras, contracts, expeditions, season, chaos |

## Deploy (new stack)

1. Create a **new Discord application** + bot token (do not reuse NuggetBot’s token).
2. Enable **Message Content** + privileged intents as in the parent project.
3. Prefer a **new GitHub repo** (`GoonBot`). Until then, this branch is the seed — never merge NSFW into NuggetBot production.
4. New **Railway** project + **PostgreSQL**. Set:
   - `DISCORD_TOKEN`
   - `DATABASE_URL` (Postgres)
   - `DASHBOARD_TOKEN` (strong secret)
   - Optional: `GUILD_ID` for guild-scoped slash sync during testing
   - Optional: `DASHBOARD_ENABLED`, `PORT`
5. Invite the bot only to **18+ / NSFW** servers. Mark play channels as Discord **NSFW**.
6. Set the bot room (GoonBot only types here — typically your **nuggetivitesbot** channel):
   - `/admin set-designated-channel #nuggetivitesbot`
   - or set env `BOT_CHANNEL_ID=<snowflake>`
   - `bot_room_only` live setting defaults **on**
7. Lore Roulette is the exception: it posts in the **main** channel (`#yappinmain`):
   - `/admin set-main-channel #yappinmain`
   - or name the channel `yappinmain` / `yappin-main` (auto-detected)
   - or set env `MAIN_CHANNEL_ID=<snowflake>`
8. Admins can set live config `nsfw_channel_only` to `0` to allow non-NSFW channels (not recommended for public servers).

## Age / NSFW gates

- Unverified users get an ephemeral **I am 18+ / I am under 18** panel; under-18 is refused.
- When `nsfw_channel_only` is on (default), slash commands fail outside NSFW channels (server admins can still run commands for setup).
- No sexual content involving minors is permitted in code, lore, items, or bosses.

## First night (after 18+)

1. `/onboard` — age gate + NSFW consent (guest list)
2. `/daily` — another round of goonbux
3. `/goon edge` — start a streak. Don't finish.
4. `/class choose` — pick a **persona** (Talent / Host / Fixer)
5. `/jobs` or `/business` — make floor money (persona-gated hustles unlock)
6. `/boss` — when **Velvet Vixen** walks the floor (auto **Velvet Walks In** windows)
7. `/profile` — heat / VIP, session meter, hustles, empire

### Nightlife verbs

- **Heat / VIP** — lifetime goonbux spent raises table limits; Door role softens; Booth softens Velvet counters. Buy next tier from Profile → **Buy VIP heat**.
- **Persona floors** — Talent / Host / Fixer unlock exclusive jobs (Main-Stage Edge / Private Booth / Back-Room Peek).
- **Session** — `/goon edge` builds a meter and streak. Finish cashes it. Ruin dumps it (yours or theirs). Chat/VC/jobs/`daily` also fill the meter. Every 145 minutes the main chat gets a group-session call with Velvet art (house pot); first answer gets kisses or head from Velvet (follow-up image), then a join round. Condoms block ruins, hold leaks, and keep streak on finish.
- **Velvet Walks In** — UTC nightlife hours (and `/event start velvet_night`) bias Velvet spawns + hotter drops.

## Player hubs (entry points)

- `/profile` — launcher (session meter + **Session** button)
- `/goon` — edge / finish / ruin / tease / dare
- `/jobs`, `/inventory` (self), `/class view`, `/alchemy list`, `/companion status`, `/relics list`, `/museum`
- `/heist` (no target), `/bounty-board`, `/casino`, `/dungeon` (no run), `/drugs stash`
- `/contracts list`, `/expedition` status, `/season` status/shop
- Chaos: trivia answer button on rounds; Chaos Hub via meta panel wiring

## Local run

```bash
pip install -r requirements.txt
cp .env.example .env   # if present; set DISCORD_TOKEN
python3 bot.py
```

SQLite default path is `goonbot.sqlite3` (or volume `/data/goonbot.sqlite3`).

## Tests

```bash
python3 -m pytest tests/ -q
```

Guards include slash-command count &lt; 100, hub panel smoke tests, and age-gate unit tests.

## License / content warning

Adult erotic game content. Operators are responsible for Discord ToS, local law, and keeping the bot out of underage spaces.
