"""GoonCards catalog — 48 collectible trading cards across six sets."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

Rarity = Literal["common", "uncommon", "rare", "epic", "legendary", "mythic"]
SetId = Literal["velvet", "floor", "personas", "hustle", "lounge", "reliquary"]

RARITY_ORDER: tuple[Rarity, ...] = (
    "common",
    "uncommon",
    "rare",
    "epic",
    "legendary",
    "mythic",
)

RARITY_LABELS: dict[Rarity, str] = {
    "common": "Common",
    "uncommon": "Uncommon",
    "rare": "Rare",
    "epic": "Epic",
    "legendary": "Legendary",
    "mythic": "Mythic",
}

RARITY_EMOJI: dict[Rarity, str] = {
    "common": "⬜",
    "uncommon": "🟩",
    "rare": "🟦",
    "epic": "🟪",
    "legendary": "🟧",
    "mythic": "🟥",
}

RARITY_COLOR: dict[Rarity, int] = {
    "common": 0x9AA0A6,
    "uncommon": 0x2F6B4F,
    "rare": 0x3D6EA8,
    "epic": 0x7A3E8C,
    "legendary": 0xC9A227,
    "mythic": 0x8B1E3F,
}

RARITY_FRAME_RGB: dict[Rarity, tuple[int, int, int]] = {
    "common": (154, 160, 166),
    "uncommon": (47, 107, 79),
    "rare": (61, 110, 168),
    "epic": (122, 62, 140),
    "legendary": (201, 162, 39),
    "mythic": (139, 30, 63),
}

RARITY_BASE_VALUE: dict[Rarity, float] = {
    "common": 50.0,
    "uncommon": 150.0,
    "rare": 400.0,
    "epic": 1200.0,
    "legendary": 4000.0,
    "mythic": 15000.0,
}

PACK_WEIGHTS: dict[Rarity, float] = {
    "common": 0.55,
    "uncommon": 0.25,
    "rare": 0.12,
    "epic": 0.06,
    "legendary": 0.018,
    "mythic": 0.002,
}

SET_ORDER: tuple[SetId, ...] = (
    "velvet",
    "floor",
    "personas",
    "hustle",
    "lounge",
    "reliquary",
)

SET_LABELS: dict[SetId, str] = {
    "velvet": "Velvet Court",
    "floor": "Floor Staff",
    "personas": "Personas",
    "hustle": "Hustle",
    "lounge": "Lounge",
    "reliquary": "Reliquary",
}

SET_EMOJI: dict[SetId, str] = {
    "velvet": "💋",
    "floor": "🥂",
    "personas": "🎭",
    "hustle": "🕶️",
    "lounge": "🔥",
    "reliquary": "🗿",
}

PORTRAIT_STYLE = (
    "Painterly trading-card portrait bust, adult cabaret velvet lounge pin-up, "
    "18+ glamorous nightlife, shoulders up, dramatic rim lighting, charcoal crimson "
    "and warm gold, single character centered, no text, no watermark, no logo"
)


def _prompt(subject: str, extra: str) -> str:
    return f"{PORTRAIT_STYLE}, {subject}, {extra}"


@dataclass(frozen=True)
class CardDefinition:
    card_id: str
    name: str
    set_id: SetId
    rarity: Rarity
    emoji: str
    description: str
    portrait_prompt: str

    @property
    def base_value(self) -> float:
        return RARITY_BASE_VALUE[self.rarity]

    @property
    def set_name(self) -> str:
        return SET_LABELS[self.set_id]

    @property
    def rarity_label(self) -> str:
        return RARITY_LABELS[self.rarity]


def _c(
    card_id: str,
    name: str,
    set_id: SetId,
    rarity: Rarity,
    emoji: str,
    description: str,
    subject: str,
    extra: str,
) -> CardDefinition:
    return CardDefinition(
        card_id,
        name,
        set_id,
        rarity,
        emoji,
        description,
        _prompt(subject, extra),
    )


CARD_DEFINITIONS: dict[str, CardDefinition] = {
    # Velvet Court — 2C 2U 1R 1E 1L 1M
    "card_hostess": _c(
        "card_hostess", "Lounge Hostess", "velvet", "common", "💄",
        "Velvet's front-of-house smile. Everyone gets a drink.",
        "glamorous lounge hostess with crimson lipstick and velvet dress",
        "welcoming smirk, gold jewelry, nightclub bokeh",
    ),
    "card_stagehand": _c(
        "card_stagehand", "Velvet Stagehand", "velvet", "common", "🎬",
        "The one who actually runs the lights while Velvet owns the room.",
        "androgynous stagehand in black with headset and crimson lanyard",
        "backstage spotlight, smoky club, confident half-smile",
    ),
    "card_tomass": _c(
        "card_tomass", "TomAss", "velvet", "uncommon", "💚",
        "Regen menace. Heals on a schedule nobody asked for.",
        "handsome rogue named TomAss with a wicked grin and green glow",
        "leather club outfit, regen aura, velvet curtains",
    ),
    "card_shadow_velvet": _c(
        "card_shadow_velvet", "Shadow Velvet", "velvet", "uncommon", "🌑",
        "The darker twin. Same stage, colder eyes.",
        "shadowy twin of a crimson cabaret queen in black velvet",
        "void lighting, silver highlights, dangerous allure",
    ),
    "card_freaky_nikki": _c(
        "card_freaky_nikki", "Freaky Nikki", "velvet", "rare", "🎀",
        "Special guest. The floor forgets how to behave.",
        "playful adult cabaret star Freaky Nikki with pink accents",
        "mischievous wink, satin and lace, neon lounge",
    ),
    "card_zz_wrath": _c(
        "card_zz_wrath", "ZZ's Wrath", "velvet", "epic", "☠️",
        "Ultra-raid pressure wearing a pretty face.",
        "fierce wrathful cabaret warlord with gold skull jewelry",
        "storm lighting, crimson cape, intimidating beauty",
    ),
    "card_leviathan": _c(
        "card_leviathan", "World Leviathan", "velvet", "legendary", "🐉",
        "World-event scale. The room gets smaller.",
        "mythic leviathan-themed cabaret sovereign with scale jewelry",
        "deep sea gold and crimson, towering presence, regal",
    ),
    "card_velvet_vixen": _c(
        "card_velvet_vixen", "Velvet Vixen", "velvet", "mythic", "💋",
        "The house. The brand. The raid boss you came for.",
        "Velvet Vixen, iconic crimson-haired cabaret queen",
        "red velvet gown, gold crown, spotlight, commanding gaze",
    ),
    # Floor Staff — 3C 2U 1R 1E 1L
    "card_floor_runner": _c(
        "card_floor_runner", "Floor Runner", "floor", "common", "🥂",
        "Velvet's staff slipping extra scrap between sets.",
        "spry floor runner in a tiny waiter vest with champagne tray",
        "busy lounge, gold tray, cheeky grin",
    ),
    "card_velvet_imp": _c(
        "card_velvet_imp", "Velvet Imp", "floor", "common", "😈",
        "Floor jesters taught it dirty duel tricks.",
        "tiny horned imp in a velvet jester collar",
        "mischief spark, crimson and gold motley",
    ),
    "card_bottle_bird": _c(
        "card_bottle_bird", "Bottle Bird", "floor", "common", "🐦",
        "Delivers bigger lounge paychecks.",
        "stylish courier bird with a bottle in its claws and a bowtie",
        "nightlife neon, gold accents, charming",
    ),
    "card_vault_bunny": _c(
        "card_vault_bunny", "Vault Bunny", "floor", "uncommon", "🎀",
        "Sniffs out bonus Velvet Vault loot.",
        "elegant vault bunny in satin with a key charm",
        "gold vault door, soft lighting, alluring",
    ),
    "card_tip_hound": _c(
        "card_tip_hound", "Tip Hound", "floor", "uncommon", "🐕",
        "Barks when duel loot is nearby.",
        "sleek hound in a tiny gold collar sitting beside a tip jar",
        "lounge carpet, warm lamps, loyal smirk",
    ),
    "card_aftercare_softie": _c(
        "card_aftercare_softie", "Aftercare Softie", "floor", "rare", "💋",
        "Keeps you meaner when Velvet is on stage.",
        "soft aftercare attendant with silk robe and caring eyes",
        "dim dressing room, rose lighting, gentle",
    ),
    "card_house_blend": _c(
        "card_house_blend", "House Blend", "floor", "epic", "🌿",
        "Grows on your lab profits.",
        "botanical cabaret alchemist with glowing herbs and gold glasses",
        "lab-lounge hybrid, emerald light, knowing smile",
    ),
    "card_empire_drone": _c(
        "card_empire_drone", "Empire Drone", "floor", "legendary", "📱",
        "Files paperwork for your nightlife empire.",
        "chic corporate drone with holographic clipboard and velvet blazer",
        "penthouse night city, gold circuitry, cool confidence",
    ),
    # Personas — 3C 2U 1R 1E 1L
    "card_talent": _c(
        "card_talent", "Talent", "personas", "common", "🎤",
        "Main-stage energy. Shows up when Velvet walks in.",
        "charismatic stage talent with a microphone and fire-red jacket",
        "spotlight, crowd bokeh, star power",
    ),
    "card_host": _c(
        "card_host", "Host", "personas", "common", "🥂",
        "Floor money specialist — tips, jobs, empire income.",
        "suave nightclub host with gold vest and guest list",
        "velvet rope, warm lighting, wealthy charm",
    ),
    "card_fixer": _c(
        "card_fixer", "Fixer", "personas", "common", "🕶️",
        "Quiet hustles and risky back-room jobs.",
        "shadowy fixer in dark glasses and a long coat",
        "back alley neon, void purple, cool",
    ),
    "card_headliner": _c(
        "card_headliner", "Headliner", "personas", "uncommon", "📈",
        "Evolved talent. The closer on the marquee.",
        "evolved headliner in sequins with a killer stage pose",
        "encore lighting, crimson smoke, fame",
    ),
    "card_promoter": _c(
        "card_promoter", "Promoter", "personas", "uncommon", "📢",
        "Circuit money. The floor hears them coming.",
        "flashy promoter with gold chains and a velvet bomber",
        "city night, posters, hustle energy",
    ),
    "card_ghost": _c(
        "card_ghost", "Ghost", "personas", "rare", "👻",
        "Guest-list phantom. Already inside.",
        "ethereal ghost infiltrator in pale silk and smoke",
        "moonlit club, translucent edges, quiet threat",
    ),
    "card_circuit_boss": _c(
        "card_circuit_boss", "Circuit Boss", "personas", "epic", "🔥",
        "Talent × Fixer hybrid — main-stage heat and back-room hustles.",
        "hybrid circuit boss with fire and shadow styling",
        "dual lighting, crown of sparks, warlord glamour",
    ),
    "card_house_idol": _c(
        "card_house_idol", "House Idol", "personas", "legendary", "👑",
        "Talent × Host hybrid — stage presence and empire money.",
        "house idol in gold crown and velvet stage gown",
        "cathedral of nightlife, adoring lights, regal",
    ),
    # Hustle — 3C 2U 1R 2E
    "card_wallet_lift": _c(
        "card_wallet_lift", "Wallet Lift", "hustle", "common", "🧤",
        "A clean pocket job. Don't get caught.",
        "stylish thief slipping a wallet in a crowded lounge",
        "motion blur crowd, leather gloves, smirk",
    ),
    "card_name_drop": _c(
        "card_name_drop", "Name-Drop Board", "hustle", "common", "📋",
        "Bounties with trigger words. Somebody always slips.",
        "bounty clerk pinning names to a velvet notice board",
        "red string, gold pins, knowing look",
    ),
    "card_table_games": _c(
        "card_table_games", "Table Games", "hustle", "common", "🎲",
        "The house always drinks. Sometimes you do too.",
        "casino dealer at a crimson felt table",
        "dice and cards, gold chips, cool stare",
    ),
    "card_crew_panel": _c(
        "card_crew_panel", "Crew Night", "hustle", "uncommon", "🤝",
        "Your people. Your cut. Your alibi.",
        "tight-knit nightlife crew posing in matching jackets",
        "alley gold light, loyalty, swagger",
    ),
    "card_bank_heist": _c(
        "card_bank_heist", "Bank Heist", "hustle", "uncommon", "🏦",
        "High-risk vault work. Bodyguards hate this card.",
        "heist specialist in a mask and velvet suit",
        "vault laser glow, tension, elegance",
    ),
    "card_bodyguard": _c(
        "card_bodyguard", "Elite Bodyguard", "hustle", "rare", "🛡️",
        "Three tiers of no. The vault stays shut.",
        "elite bodyguard in tailored black with an earpiece",
        "gold lapel pin, stoic beauty, club doors",
    ),
    "card_black_card": _c(
        "card_black_card", "Black Card", "hustle", "epic", "🃏",
        "Guest-list master. The door never existed.",
        "mysterious black-card holder in obsidian fashion",
        "unlimited access vibe, gold trim, midnight",
    ),
    "card_cartel_title": _c(
        "card_cartel_title", "Cartel Title", "hustle", "epic", "🧪",
        "Dealer rank 10. The lab is a throne now.",
        "cartel sovereign with botanical gold crown and lab coat-cape",
        "emerald smoke, empire, dangerous calm",
    ),
    # Lounge — 3C 2U 1R 1E 1L
    "card_edge": _c(
        "card_edge", "On the Edge", "lounge", "common", "🔥",
        "Pump the meter. Don't finish. That's the game.",
        "edging cabaret performer gripping a velvet chair",
        "heat haze, crimson lighting, intense eyes",
    ),
    "card_floor_dare": _c(
        "card_floor_dare", "Floor Dare", "lounge", "common", "🎯",
        "The room picked for you. Perform.",
        "daring lounge guest mid-challenge under a spotlight",
        "crowd watching, gold confetti, thrill",
    ),
    "card_tease": _c(
        "card_tease", "Tease", "lounge", "common", "😉",
        "Pay to push someone else's meter. Mean, effective.",
        "teasing cabaret muse blowing a kiss from the booth",
        "soft focus, rose gold, playful cruelty",
    ),
    "card_group_round": _c(
        "card_group_round", "Group Round", "lounge", "uncommon", "👥",
        "Free join if you're fast. Late join costs a condom.",
        "group of nightlife regulars in a circle of warm light",
        "shared ritual, velvet couches, camaraderie",
    ),
    "card_afterglow": _c(
        "card_afterglow", "Afterglow", "lounge", "uncommon", "✨",
        "The streak cashed. The room still humming.",
        "afterglow portrait, silk sheets and gold dust lighting",
        "satisfied calm, warm skin tones, intimate",
    ),
    "card_ruin": _c(
        "card_ruin", "Ruin", "lounge", "rare", "💦",
        "Dump yours, or pay to ruin someone else's night.",
        "dramatic ruin-themed cabaret villain with spilled champagne",
        "chaotic glitter, wicked delight, high contrast",
    ),
    "card_kisses_velvet": _c(
        "card_kisses_velvet", "Kisses from Velvet", "lounge", "epic", "😘",
        "First yes on the group call. The house notices.",
        "Velvet Vixen leaning in to kiss the camera",
        "extreme close portrait, crimson lipstick, gold light",
    ),
    "card_velvet_ready": _c(
        "card_velvet_ready", "I'm Ready", "lounge", "legendary", "👑",
        "The button. The round. The legend of the floor.",
        "legendary lounge champion answering Velvet's call",
        "heroic cabaret pose, house-pot gold rain, triumph",
    ),
    # Reliquary — 4C 2U 1R 0E 0L 1M
    "card_street_token": _c(
        "card_street_token", "Street Raid Token", "reliquary", "common", "🎫",
        "Starter raid charm. A touch more scrap from bosses.",
        "street charm vendor holding a gold raid token",
        "neon alley, ticket stub aesthetic, hustle",
    ),
    "card_jester_bell": _c(
        "card_jester_bell", "Court Jester's Bell", "reliquary", "common", "🔔",
        "Raid attacks sometimes heal the weakest ally.",
        "court jester relic-keeper ringing a gold bell",
        "motley velvet, playful, shrine lighting",
    ),
    "card_medic_patch": _c(
        "card_medic_patch", "Aftercare Patch", "reliquary", "common", "🩹",
        "Tougher on Velvet nights and in duels.",
        "aftercare medic applying a gold-edged patch",
        "clinic-lounge, soft red light, care",
    ),
    "card_scrap_idol": _c(
        "card_scrap_idol", "Scrap Floor Idol", "reliquary", "common", "⚙️",
        "Velvet nights yield more alchemy scrap.",
        "small brass idol of a floor gnome on a shrine",
        "workshop gold, incense, cult charm",
    ),
    "card_plunder_seal": _c(
        "card_plunder_seal", "Plunderer's Seal", "reliquary", "uncommon", "💰",
        "Steal more goonbux from duel wins.",
        "seal-bearer with a heavy gold signet and coin veil",
        "treasure glow, pirate-lounge mix, greed",
    ),
    "card_duelist_coin": _c(
        "card_duelist_coin", "Duelist's Lucky Coin", "reliquary", "uncommon", "🪙",
        "Sharper crits in PvP.",
        "duelist flipping a glowing lucky coin",
        "sparks, gold arc, sharp eyes",
    ),
    "card_void_heart": _c(
        "card_void_heart", "Void Hardener Heart", "reliquary", "rare", "💜",
        "One free enhance safety charge.",
        "figure holding a crystalline void-purple heart",
        "rift lighting, sacred and dangerous",
    ),
    "card_velvet_vault_key": _c(
        "card_velvet_vault_key", "Velvet Vault Key", "reliquary", "mythic", "🗝️",
        "The key to the afterparty. Everything heavier.",
        "mythic keybearer with an ornate crimson vault key",
        "open gold vault, Velvet's silhouette, destiny",
    ),
}


assert len(CARD_DEFINITIONS) == 48, f"expected 48 cards, got {len(CARD_DEFINITIONS)}"


def card_by_id(card_id: str) -> CardDefinition | None:
    return CARD_DEFINITIONS.get(card_id)


def cards_for_set(set_id: SetId) -> list[CardDefinition]:
    return [c for c in CARD_DEFINITIONS.values() if c.set_id == set_id]


def cards_for_rarity(rarity: Rarity) -> list[CardDefinition]:
    return [c for c in CARD_DEFINITIONS.values() if c.rarity == rarity]


def rarity_counts() -> dict[Rarity, int]:
    counts: dict[Rarity, int] = {r: 0 for r in RARITY_ORDER}
    for card in CARD_DEFINITIONS.values():
        counts[card.rarity] += 1
    return counts


def npc_sell_value(card: CardDefinition, sell_mult: float) -> float:
    return max(1.0, round(card.base_value * max(0.0, sell_mult), 2))


def roll_rarity(rng: random.Random | None = None) -> Rarity:
    roller = rng or random
    roll = roller.random()
    cumulative = 0.0
    last: Rarity = "common"
    for rarity in RARITY_ORDER:
        cumulative += PACK_WEIGHTS[rarity]
        last = rarity
        if roll <= cumulative:
            return rarity
    return last


def roll_card(rng: random.Random | None = None) -> CardDefinition:
    rarity = roll_rarity(rng)
    pool = cards_for_rarity(rarity)
    roller = rng or random
    return roller.choice(pool)


def roll_pack(size: int, rng: random.Random | None = None) -> list[CardDefinition]:
    return [roll_card(rng) for _ in range(max(1, int(size)))]
