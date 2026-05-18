# NuggetBot Patch Notes — 18 May 2026

## Overview

Today’s update adds social progression, server legends, regulated gambling, and full PvP duels — plus admin dashboard controls for duel rules.

---

## Quests

**Onboarding** guides new raiders through their first steps (daily claim, shop purchase, boss attack, heal, pay). Completing each step pays a nugget reward.

**Daily goals** give veterans three random objectives each UTC day (raid hits, heals, crafting, casino play, and more).

| Command | What it does |
|---------|----------------|
| `/quests` | View your current onboarding or daily goals |
| `/quest-hint` | Get a nudge on your next objective |

---

## Hall of Fame

**`/hall-of-fame`** shows server leaderboards in one embed:

- Richest wallets  
- Most boss kills  
- Most heals given  
- Most achievements unlocked  

The web dashboard also displays a **Hall of Fame** snapshot per server.

---

## Casino mini-games

Gamble nuggets with a house tax on winnings (tunable per server).

| Command | What it does |
|---------|----------------|
| `/coinflip <amount>` | 50/50 vs the house |
| `/coinflip-duel @user <amount>` | Challenge a player; they Accept to fight for the pot |
| `/blackjack <amount>` | Hit or stand vs the dealer; natural blackjack pays extra |

You cannot gamble while arrested or downed.

---

## PvP Duels

**`/duel @player`** starts a real gear-based fight:

- Turn-by-turn combat using your equipped **weapon** and **armor** (damage, crit, mitigation, set bonuses, prestige).  
- The **challenger strikes first**.  
- A public embed shows the **battle log** and final HP.

**If you lose**, **10% of your wallet** is transferred to the **winner** (not destroyed).

**Rate limits (defaults):**

- Same opponent: once every **40 minutes**  
- Attacks: **3 duels started per hour**  

---

## Economy dashboard (admins)

The bot’s web dashboard now includes:

- **Economy tuning** sliders (drops, craft cost, prestige floor, gambling tax, passive income, and more)  
- **Duel tuning** sliders (loss %, same-target cooldown, hourly duel cap)  

No Railway env var edits required for these — save from the dashboard after login.

---

## Quick command cheat sheet

```
/quests          /hall-of-fame     /coinflip
/quest-hint      /duel @player     /coinflip-duel
                                   /blackjack
```

---

## Balance defaults

| Setting | Default |
|---------|---------|
| Duel loss (to winner) | 10% of loser’s wallet |
| Re-duel same player | 40 minutes |
| Duels per hour | 3 |
| Gambling tax on winnings | 5% |

Admins can change these per server on the dashboard or with `/config`.
