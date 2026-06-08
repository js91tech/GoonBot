from __future__ import annotations

HELP_PAGES: tuple[tuple[str, str], ...] = (
    (
        "Economy",
        "**/daily** · **/balance** · **/deposit** · **/withdraw** · **/pay** · **/leaderboard**\n"
        "**/jobs** · **/work** · **/energy** · **/upgrade-energy**\n"
        "Bot Discord accounts can use slash commands and be targeted in PvP (duels, heists, bounties, etc.). Passive chat/VC farming stays human-only to prevent spam.",
    ),
    (
        "Raid & boss",
        "**/boss** — fight panel: Attack, Cast, Items, Heal, Auto-heal, Refresh, Raid LB\n"
        "**/attack** · **/heal** · **/cast** · **/use** · **/boss-status** · **/raid-leaderboard**\n"
        "**/shop** · **/buy** · **/equip** · **/craft** · **/prestige**\n"
        "**/dungeon** — solo standard (**25** energy) · unlock **Gilded Vault** (**50k**, party raid) · **/alchemy** · **/season**",
    ),
    (
        "PvP & casino",
        "**/duel** · **/coinflip** · **/blackjack** · **/slots** · **/jackpot**\n"
        "**/crew** — interactive crew panel (join, deposit, withdraw, loans, repay)\n"
        "**/territory** — map panel with guard hiring, zones, sieges\n"
    ),
    (
        "Character",
        "**/class** · **/cast** · **/mana** · **/aspects** · **/avatar** (upload custom)\n"
        "**/use** — raid potion, energy drink, duel scroll, **Jail Key**, **Pick Key** · **/gift** — chia seeds\n"
        "**/attributes** — interactive stat panel (50 pt pool +5/prestige; 15 + prestige/stat cap)\n"
        "**/profile** · **/stats** · **/quests** · **/achievements** · **/fix** (unstable gear)",
    ),
    (
        "Chaos modules",
        "**/bounty** · **/bounty-board** · **/heist** · **/bank-heist** · **/bodyguards** · **/hack** · **/transfer** · **/scourge-pass** · **/trivia**\n"
        "**Jail Key** (100k, guaranteed escape) · **Pick Key** (20k, 15% escape) while arrested.\n"
        "**/bodyguards** — hire up to 5 guards (3 tiers) to defend your bank from heists.\n"
        "House pot — gambling losses, scourge hits, and unclaimed drops fund random coin drops.\n"
        "Scourge Virus — every **8** hours; warning GIF, then 7 min of infections on the top 5.\n"
        "Boss auto-spawn — every **90** minutes when none is active.\n"
        "**/hall-of-fame** · **/event** (admins)",
    ),
)
