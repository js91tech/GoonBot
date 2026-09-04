"""GoonCards catalog — 148 collectible trading cards across 16 sets.

Launch 48 stay in six 8-card sets (Velvet Court, Floor Staff, Personas, Hustle,
Lounge, Reliquary). The lust expansion adds 100 cards in ten 10-card sets:
The Edge, Private Booth, Floor Heat, Kink Cabinet, Aftercare Suite,
Cabaret Bodies, Voyeur Gallery, Sweet Denial, Altar of Worship, Midnight Encore.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

Rarity = Literal["common", "uncommon", "rare", "epic", "legendary", "mythic"]
SetId = Literal[
    "velvet", "floor", "personas", "hustle", "lounge", "reliquary",
    "edge", "booth", "heat", "kink", "aftercare", "cabaret", "peek", "denial", "worship", "encore",
]

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
    "edge",
    "booth",
    "heat",
    "kink",
    "aftercare",
    "cabaret",
    "peek",
    "denial",
    "worship",
    "encore",
)

SET_LABELS: dict[SetId, str] = {
    "velvet": "Velvet Court",
    "floor": "Floor Staff",
    "personas": "Personas",
    "hustle": "Hustle",
    "lounge": "Lounge",
    "reliquary": "Reliquary",
    "edge": "The Edge",
    "booth": "Private Booth",
    "heat": "Floor Heat",
    "kink": "Kink Cabinet",
    "aftercare": "Aftercare Suite",
    "cabaret": "Cabaret Bodies",
    "peek": "Voyeur Gallery",
    "denial": "Sweet Denial",
    "worship": "Altar of Worship",
    "encore": "Midnight Encore",
}

SET_EMOJI: dict[SetId, str] = {
    "velvet": "💋",
    "floor": "🥂",
    "personas": "🎭",
    "hustle": "🕶️",
    "lounge": "🔥",
    "reliquary": "🗿",
    "edge": "🥵",
    "booth": "🕯️",
    "heat": "💃",
    "kink": "🔗",
    "aftercare": "🛏️",
    "cabaret": "🍒",
    "peek": "👁️",
    "denial": "⏳",
    "worship": "🛐",
    "encore": "🌙",
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


# Launch 48 from Velvet Court / Floor Staff / Personas / Hustle / Lounge / Reliquary.
ORIGINAL_CARD_IDS: frozenset[str] = frozenset((
    'card_hostess',
    'card_stagehand',
    'card_tomass',
    'card_shadow_velvet',
    'card_freaky_nikki',
    'card_zz_wrath',
    'card_leviathan',
    'card_velvet_vixen',
    'card_floor_runner',
    'card_velvet_imp',
    'card_bottle_bird',
    'card_vault_bunny',
    'card_tip_hound',
    'card_aftercare_softie',
    'card_house_blend',
    'card_empire_drone',
    'card_talent',
    'card_host',
    'card_fixer',
    'card_headliner',
    'card_promoter',
    'card_ghost',
    'card_circuit_boss',
    'card_house_idol',
    'card_wallet_lift',
    'card_name_drop',
    'card_table_games',
    'card_crew_panel',
    'card_bank_heist',
    'card_bodyguard',
    'card_black_card',
    'card_cartel_title',
    'card_edge',
    'card_floor_dare',
    'card_tease',
    'card_group_round',
    'card_afterglow',
    'card_ruin',
    'card_kisses_velvet',
    'card_velvet_ready',
    'card_street_token',
    'card_jester_bell',
    'card_medic_patch',
    'card_scrap_idol',
    'card_plunder_seal',
    'card_duelist_coin',
    'card_void_heart',
    'card_velvet_vault_key',
))


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
    # --- Lust expansion: 10 sets × 10 (The Edge through Midnight Encore) ---
    'card_slow_stroke': _c(
        'card_slow_stroke', 'Slow Stroke', 'edge', 'common', '✋',
        "Don't finish. Don't even think about finishing.",
        'adult cabaret muse mid slow stroke, flushed cheeks, velvet chair',
        'heat haze, bitten lip, 18+ nightlife',
    ),
    'card_hold_it': _c(
        'card_hold_it', 'Hold It', 'edge', 'common', '🛑',
        'The meter is full. The rule is wait.',
        'tense adult performer gripping the chair arms, jaw tight',
        'crimson lighting, denial, sweat sheen',
    ),
    'card_not_yet': _c(
        'card_not_yet', 'Not Yet', 'edge', 'common', '⏳',
        'Velvet said not yet. You heard her.',
        'smirking hostess with a finger to painted lips',
        'gold jewelry, hush, booth light',
    ),
    'card_meter_pulse': _c(
        'card_meter_pulse', 'Meter Pulse', 'edge', 'common', '💓',
        'Every chat, every job, every sip fills it.',
        'flushed adult dancer with a glowing pulse at the throat',
        'neon veins of gold, lounge bokeh',
    ),
    'card_edge_queen': _c(
        'card_edge_queen', 'Edge Queen', 'edge', 'uncommon', '👑',
        'She lives on the line and makes you live there too.',
        'regal adult cabaret queen mid-edge, crown tilted',
        'crimson gown slipping, commanding eyes',
    ),
    'card_denial_coach': _c(
        'card_denial_coach', 'Denial Coach', 'edge', 'uncommon', '📋',
        'Counts out loud. You do not get to skip.',
        'sharp-eyed adult coach with a gold clicker and silk gloves',
        'clipboard, cruel kindness, spotlight',
    ),
    'card_leak_scare': _c(
        'card_leak_scare', 'Leak Scare', 'edge', 'uncommon', '💧',
        'Almost. The floor noticed. Hold.',
        'startled adult performer biting a knuckle, shine on skin',
        'wet light, velvet, panic-pleasure',
    ),
    'card_ruined_edge': _c(
        'card_ruined_edge', 'Ruined Edge', 'edge', 'rare', '💦',
        "You waited. She didn't let you have it anyway.",
        'wrecked-beautiful adult cabaret villain after a ruined peak',
        'champagne spill, wicked calm, glitter',
    ),
    'card_overstim': _c(
        'card_overstim', 'Overstim', 'edge', 'epic', '⚡',
        'Past the line. Still not allowed to drop.',
        'overstimulated adult star arching under gold strobes',
        'electric heat, open mouth, high contrast',
    ),
    'card_forever_edge': _c(
        'card_forever_edge', 'Forever Edge', 'edge', 'legendary', '🔥',
        'The streak that never cashes. The house favorite.',
        'legendary edging sovereign locked in beautiful tension',
        'eternal crimson, gold rain, worship lighting',
    ),
    'card_booth_curtain': _c(
        'card_booth_curtain', 'Booth Curtain', 'booth', 'common', '🍷',
        'Heavy velvet. What happens behind it stays billed.',
        'adult host drawing a thick crimson curtain with a knowing look',
        'private booth, gold rod, hush',
    ),
    'card_lap_heat': _c(
        'card_lap_heat', 'Lap Heat', 'booth', 'common', '🔥',
        'Closer than the floor allows. Tips get weird.',
        'adult dancer in the lap-light, breath on the camera',
        'tight booth, skin sheen, rose lamps',
    ),
    'card_whisper_tip': _c(
        'card_whisper_tip', 'Whisper Tip', 'booth', 'common', '👄',
        'A price named against your ear. Pay it.',
        'adult muse whispering with crimson lipstick at the lobe',
        'extreme close, gold earring, intimate',
    ),
    'card_champagne_solo': _c(
        'card_champagne_solo', 'Champagne Solo', 'booth', 'common', '🥂',
        'One bottle. One guest. No audience.',
        'adult cabaret star pouring champagne in a closed booth',
        'flute, wet collarbone, candle gold',
    ),
    'card_private_dance': _c(
        'card_private_dance', 'Private Dance', 'booth', 'uncommon', '💃',
        'The meter climbs without a crowd. Meaner that way.',
        'adult dancer mid private routine, hands on thighs',
        'booth neon, slow roll, heat',
    ),
    'card_one_way_glass': _c(
        'card_one_way_glass', 'One-Way Glass', 'booth', 'uncommon', '🪟',
        "They think it's a mirror. You know it isn't.",
        'adult voyeur portrait behind gold-tinted glass',
        'reflection, dark booth, watching',
    ),
    'card_hands_on_knees': _c(
        'card_hands_on_knees', 'Hands on Knees', 'booth', 'uncommon', '🧎',
        'House posture. You stay there until she says.',
        'adult kneeling in a velvet booth, palms on thighs',
        'collar glint, low angle, worship',
    ),
    'card_closed_booth': _c(
        'card_closed_booth', 'Closed Booth', 'booth', 'rare', '🔒',
        'Occupied. Do not knock. Do not look. (Look.)',
        'adult silhouette against a lit booth curtain',
        'backlit bodies, gold fringe, secrecy',
    ),
    'card_velvet_lap': _c(
        'card_velvet_lap', 'Velvet Lap', 'booth', 'epic', '💋',
        "The house special. You don't sit so much as melt.",
        'Velvet-coded adult star claiming a lap in crimson',
        'close heat, lipstick, commanding smile',
    ),
    'card_after_hours': _c(
        'card_after_hours', 'After Hours Booth', 'booth', 'legendary', '🌙',
        "The club closed. The booth didn't.",
        'legendary after-hours adult hostess in leftover spotlight',
        'empty club, one lamp, invitation',
    ),
    'card_warmup_circle': _c(
        'card_warmup_circle', 'Warm-Up Circle', 'heat', 'common', '⭕',
        'Everybody in. Hands where Velvet can see them.',
        'adult floor regulars in a warm circle of light',
        'shared heat, couches, camaraderie',
    ),
    'card_floor_grind': _c(
        'card_floor_grind', 'Floor Grind', 'heat', 'common', '🕺',
        'The carpet learns your name the long way.',
        'adult dancer grinding under a sweaty spotlight',
        'crowd bokeh, gold dust, motion',
    ),
    'card_crowd_breath': _c(
        'card_crowd_breath', 'Crowd Breath', 'heat', 'common', '😮',
        "The room inhales with you. Don't you dare exhale first.",
        'flushed adult face in a packed lounge, mouths behind',
        'crowd heat, crimson, voyeur',
    ),
    'card_sweaty_spot': _c(
        'card_sweaty_spot', 'Sweaty Spotlight', 'heat', 'common', '💡',
        'The cone finds you. Perform or get ruined.',
        'sweat-sheen adult performer trapped in a hard spotlight',
        'bare shoulder, dare energy, gold',
    ),
    'card_group_pulse': _c(
        'card_group_pulse', 'Group Pulse', 'heat', 'uncommon', '🫀',
        "One meter. Many hands. Free join if you're fast.",
        'cluster of adult nightlife bodies sharing a pulse of light',
        'group ritual, velvet, heat',
    ),
    'card_hands_everywhere': _c(
        'card_hands_everywhere', 'Hands Everywhere', 'heat', 'uncommon', '🙌',
        'Consent was a chorus. The floor got loud.',
        'adult cabaret star surrounded by reaching adult hands',
        'gold rings, skin, crowd worship',
    ),
    'card_voyeur_rail': _c(
        'card_voyeur_rail', 'Voyeur Rail', 'heat', 'uncommon', '👁️',
        'Paid seats along the edge. Looking is the point.',
        'adult watcher at the rail, drink forgotten, eyes hungry',
        'rail light, dark suit, voyeur',
    ),
    'card_full_floor': _c(
        'card_full_floor', 'Full Floor', 'heat', 'rare', '🌊',
        'No empty carpet. The house is a body now.',
        'packed adult cabaret floor from above, gold and crimson',
        'bodies, motion, heatwave',
    ),
    'card_house_heatwave': _c(
        'card_house_heatwave', 'House Heatwave', 'heat', 'epic', '🌡️',
        'AC failed on purpose. Tips went feral.',
        'glowing adult headliner radiating heat in a packed room',
        'haze, sweat, molten gold',
    ),
    'card_the_room_came': _c(
        'card_the_room_came', 'The Room Came', 'heat', 'legendary', '💥',
        'When the floor peaks together, the pot notices.',
        'legendary group-climax portrait, silk and gold rain',
        'aftershock, adult bodies, triumph',
    ),
    'card_silk_rope': _c(
        'card_silk_rope', 'Silk Rope', 'kink', 'common', '🪢',
        'Pretty ties. Pretty marks. Pretty please.',
        'coiled crimson silk rope on velvet, gold ring',
        'macro still, cabaret shrine',
    ),
    'card_soft_cuffs': _c(
        'card_soft_cuffs', 'Soft Cuffs', 'kink', 'common', '🔗',
        'Lined. Labeled. Yours until last call.',
        'padded gold-ring cuffs on a silk cloth',
        'still life, warm lamps',
    ),
    'card_collar_click': _c(
        'card_collar_click', 'Collar Click', 'kink', 'common', '🔔',
        'The sound the floor waits for.',
        'adult muse fastening a velvet collar, ring glinting',
        'throat close, gold hardware, smirk',
    ),
    'card_wax_play': _c(
        'card_wax_play', 'Wax Play', 'kink', 'common', '🕯️',
        'Heat with manners. Drip with intent.',
        'candles and crimson wax pool on dark velvet',
        'still life, gold drip',
    ),
    'card_riding_crop': _c(
        'card_riding_crop', 'Riding Crop', 'kink', 'uncommon', '🏇',
        'A tap is a sentence. A swing is a paragraph.',
        'leather crop across a gold-trimmed cushion',
        'still life, threat and polish',
    ),
    'card_blindfold_kiss': _c(
        'card_blindfold_kiss', 'Blindfold Kiss', 'kink', 'uncommon', '🙈',
        "If you can't see, you feel everything.",
        'adult beauty in a silk blindfold, lips parted',
        'close portrait, velvet, trust',
    ),
    'card_worship_kneel': _c(
        'card_worship_kneel', 'Worship Kneel', 'kink', 'uncommon', '🙏',
        'Knees first. Words second. Mouth whenever told.',
        'adult worshiper kneeling at a velvet dais',
        'low angle, collar, gold',
    ),
    'card_harness_night': _c(
        'card_harness_night', 'Harness Night', 'kink', 'rare', '⛓️',
        'Straps as jewelry. The outfit is the scene.',
        'adult cabaret star in a gold-ring harness',
        'bare torso lighting, confident',
    ),
    'card_full_kit': _c(
        'card_full_kit', 'Full Kit', 'kink', 'epic', '🧰',
        "Drawer open. Night booked. Don't be late.",
        'open toy drawer, gold hardware, crimson silk',
        'pixel cabinet, adult cabaret',
    ),
    'card_dungeon_hostess': _c(
        'card_dungeon_hostess', 'Dungeon Hostess', 'kink', 'legendary', '🖤',
        'Front of house for the rooms downstairs.',
        'legendary adult dungeon hostess in latex and gold',
        'dark velvet, crop, welcoming cruelty',
    ),
    'card_water_bottle': _c(
        'card_water_bottle', 'Water Bottle', 'aftercare', 'common', '💧',
        'First rule after a ruin: drink, then talk.',
        'adult aftercare attendant offering water in gold light',
        'soft robe, care, dim room',
    ),
    'card_soft_towel': _c(
        'card_soft_towel', 'Soft Towel', 'aftercare', 'common', '🧺',
        'Warm. Clean. Around your shoulders like a yes.',
        'adult muse wrapped in a towel, steam and gold',
        'bath light, gentle, intimate',
    ),
    'card_hair_stroke': _c(
        'card_hair_stroke', 'Hair Stroke', 'aftercare', 'common', '🫶',
        'Fingers in the hair. Meter cooling on purpose.',
        'adult aftercare portrait, hand in tousled hair',
        'rose room, soft eyes',
    ),
    'card_check_in': _c(
        'card_check_in', 'Check-In', 'aftercare', 'common', '📝',
        'Color. Water. Want more or want held.',
        'soft-eyed adult attendant with a gold notepad',
        'clinic-lounge, care, warmth',
    ),
    'card_silk_two': _c(
        'card_silk_two', 'Silk for Two', 'aftercare', 'uncommon', '🛏️',
        'Two bodies. One set of sheets. No performance.',
        'silk sheets and gold dust, two indentations',
        'still life afterglow',
    ),
    'card_warm_oil': _c(
        'card_warm_oil', 'Warm Oil', 'aftercare', 'uncommon', '🧴',
        'Hands slow down. Skin stays in the story.',
        'adult aftercare masseur with glowing oil',
        'amber light, bare shoulder, calm',
    ),
    'card_quiet_praise': _c(
        'card_quiet_praise', 'Quiet Praise', 'aftercare', 'uncommon', '💗',
        "Good. That's all. Say it until it sticks.",
        'adult caretaker whispering praise, forehead kiss energy',
        'soft focus, gold, intimate',
    ),
    'card_afterglow_bath': _c(
        'card_afterglow_bath', 'Afterglow Bath', 'aftercare', 'rare', '🛁',
        'Steam, two glasses, nobody counting.',
        'steamy bath scene, adult silhouettes, gold fixtures',
        'pixel bath, afterglow',
    ),
    'card_held_til_dawn': _c(
        'card_held_til_dawn', 'Held Until Dawn', 'aftercare', 'epic', '🌅',
        "The floor closed. The hold didn't.",
        'adult pair in gold morning light, silk and calm',
        'aftercare bed, tender, 18+',
    ),
    'card_house_aftercare': _c(
        'card_house_aftercare', 'House Aftercare', 'aftercare', 'legendary', '💋',
        "Velvet's own cool-down. You earned the quiet.",
        'legendary aftercare sovereign in a silk robe, caring and lethal',
        'rose lighting, gold mug, home',
    ),
    'card_bare_shoulder': _c(
        'card_bare_shoulder', 'Bare Shoulder', 'cabaret', 'common', '✨',
        'The dress did the first half. You do the rest.',
        'adult cabaret beauty, one strap gone, shoulder lit',
        'gold jewelry, smirk, lounge',
    ),
    'card_hip_sway': _c(
        'card_hip_sway', 'Hip Sway', 'cabaret', 'common', '🍑',
        'The walk from the booth to the stage is the act.',
        'adult dancer mid hip-sway, sequin catch-lights',
        'stage, motion, heat',
    ),
    'card_lip_bite': _c(
        'card_lip_bite', 'Lip Bite', 'cabaret', 'common', '🫦',
        'A tell. A dare. A receipt.',
        'extreme close adult mouth, tooth on crimson lip',
        'macro, gold light, lust',
    ),
    'card_glove_peel': _c(
        'card_glove_peel', 'Glove Peel', 'cabaret', 'common', '🧤',
        'Opera gloves coming off one finger at a time.',
        'adult star peeling a black opera glove with teeth',
        'close hands, gold rings, tease',
    ),
    'card_corset_breath': _c(
        'card_corset_breath', 'Corset Breath', 'cabaret', 'uncommon', '🎀',
        'Laced to speak short and mean it.',
        'adult cabaret muse in a tight corset, flushed',
        'laces, gold, shallow breath',
    ),
    'card_thigh_high': _c(
        'card_thigh_high', 'Thigh High', 'cabaret', 'uncommon', '🦵',
        'The line where the night starts paying attention.',
        'adult pin-up, garter clip and velvet, looking back',
        'thigh light, gold clasp, 18+',
    ),
    'card_stage_strip': _c(
        'card_stage_strip', 'Stage Strip', 'cabaret', 'uncommon', '🎤',
        'Not nude yet. Nude is a destination.',
        'adult headliner mid-strip under encore lights',
        'sequins, smoke, fame',
    ),
    'card_body_heat': _c(
        'card_body_heat', 'Body Heat', 'cabaret', 'rare', '🌡️',
        'Skin as the whole costume. Spotlight as the rest.',
        'adult cabaret nude-glam bust, tasteful and explicit heat',
        'skin sheen, gold, commanding',
    ),
    'card_skin_spotlight': _c(
        'card_skin_spotlight', 'Skin and Spotlight', 'cabaret', 'epic', '🌟',
        'The body is the marquee. Read it.',
        'legendary-feeling adult body in a hard cone of light',
        'bare glam, cabaret, no text',
    ),
    'card_the_body_show': _c(
        'card_the_body_show', 'The Body Is the Show', 'cabaret', 'legendary', '🍒',
        'No plot. No metaphor. Just the house in skin.',
        'legendary adult cabaret body-sovereign, velvet and gold',
        'throne of light, 18+ pin-up, command',
    ),
    'card_keyhole': _c(
        'card_keyhole', 'Keyhole', 'peek', 'common', '🔑',
        "You weren't invited. You were installed.",
        'keyhole view of crimson lounge light and a lip',
        'still life voyeur, gold',
    ),
    'card_mirror_wall': _c(
        'card_mirror_wall', 'Mirror Wall', 'peek', 'common', '🪞',
        'Every angle is a seat. Every seat is a mirror.',
        'adult beauty multiplied in gold-framed mirrors',
        'gallery, vanity, watching',
    ),
    'card_dark_seat': _c(
        'card_dark_seat', 'Dark Booth Seat', 'peek', 'common', '💺',
        'Paid shadow. Bring your own breath.',
        'adult silhouette in a dark gallery seat, drink glowing',
        'voyeur rail, red lamp',
    ),
    'card_camera_red': _c(
        'card_camera_red', 'Camera Red', 'peek', 'common', '📷',
        'The rec light is a kink. Smile for the house.',
        'adult performer clocking a red camera light',
        'glint, smirk, recorded',
    ),
    'card_watch_watch': _c(
        'card_watch_watch', 'Watching You Watch', 'peek', 'uncommon', '👀',
        'The gallery watches the watchers. Nested heat.',
        'adult voyeur caught looking, blush and grin',
        'two-way, gold, caught',
    ),
    'card_two_way': _c(
        'card_two_way', 'Two-Way', 'peek', 'uncommon', '🪟',
        'Glass with opinions. You on both sides.',
        'split adult portrait, one side dark, one lit skin',
        'mirror glass, voyeur',
    ),
    'card_peep_show': _c(
        'card_peep_show', 'Peep Show', 'peek', 'rare', '🎬',
        'Coin slot. Tiny window. Entire religion.',
        'pixel peep booth, adult silhouette in crimson',
        'voyeur window, gold coin',
    ),
    'card_hidden_rail': _c(
        'card_hidden_rail', 'Hidden Rail', 'peek', 'rare', '🚧',
        'Staff-only sightline. Staff-only stories.',
        'adult floor watcher behind a dark rail',
        'backstage peek, neon',
    ),
    'card_gallery_pass': _c(
        'card_gallery_pass', 'Gallery Pass', 'peek', 'epic', '🎫',
        "All windows. All nights. Don't get seen getting seen.",
        'black gallery pass on velvet, gold stamp',
        'still life access',
    ),
    'card_night_optics': _c(
        'card_night_optics', 'Night Optics', 'peek', 'epic', '🌃',
        'The whole lounge as a viewing instrument.',
        'adult optic-glam bust with dark lenses and city neon',
        'voyeur tech, gold trim',
    ),
    'card_hands_off': _c(
        'card_hands_off', 'Hands Off', 'denial', 'common', '🚫',
        "Look. Don't. That's the whole game.",
        'adult muse catching a wrist, painted nails, no',
        'close hands, gold rings, denial',
    ),
    'card_wait': _c(
        'card_wait', 'Wait', 'denial', 'common', '⏸️',
        'A full minute can be a life sentence.',
        'adult clock-face still life, crimson hands',
        'edge timer, gold',
    ),
    'card_permission': _c(
        'card_permission', 'Permission Please', 'denial', 'common', '🙋',
        'Ask pretty. Ask again. Maybe.',
        'adult kneeling ask, eyes up, lips parted',
        'collar, booth, please',
    ),
    'card_count_ten': _c(
        'card_count_ten', 'Count to Ten', 'denial', 'common', '🔟',
        'If you finish on eight, you start over.',
        'adult coach mouthing numbers, gold clicker',
        'cruel calm, spotlight',
    ),
    'card_denied_again': _c(
        'card_denied_again', 'Denied Again', 'denial', 'uncommon', '🙅',
        'The third no is the one that ruins people.',
        'adult keyholder shaking her head, delighted',
        'silk, smirk, no',
    ),
    'card_beg_pretty': _c(
        'card_beg_pretty', 'Beg Pretty', 'denial', 'uncommon', '🥺',
        'Pretty is a skill. Begging is a sport.',
        'adult worshiper mid-beg, wet eyes, gold light',
        'kneel, heat, ask',
    ),
    'card_locked_up': _c(
        'card_locked_up', 'Locked Up', 'denial', 'rare', '🔒',
        'Hardware with a schedule. She keeps the diary.',
        'gold lock and velvet, still life of denial',
        'key, shrine, wait',
    ),
    'card_edged_raw': _c(
        'card_edged_raw', 'Edged Raw', 'denial', 'rare', '💢',
        'Hours. No finish. The face tells on you.',
        'wrecked-beautiful adult edging portrait, shine and tension',
        'heat, bite, 18+',
    ),
    'card_orgasm_ban': _c(
        'card_orgasm_ban', 'Orgasm Ban', 'denial', 'epic', '🛑',
        "House rule until Velvet lifts it. She won't.",
        'adult sovereign with a gold stamp, ban in her eyes',
        'decree, crimson, power',
    ),
    'card_keyholder': _c(
        'card_keyholder', 'Keyholder', 'denial', 'epic', '🗝️',
        'Your night lives on a chain around her throat.',
        'adult keyholder, ornate key on a collar ring',
        'smirk, gold, ownership',
    ),
    'card_kneel': _c(
        'card_kneel', 'Kneel', 'worship', 'common', '🧎',
        'The first position. The only honest one.',
        'adult worshiper on both knees at a velvet altar',
        'low light, gold, devotion',
    ),
    'card_kiss_ring': _c(
        'card_kiss_ring', 'Kiss the Ring', 'worship', 'common', '💍',
        "Mouth to metal. That's the greeting.",
        'extreme close of lips on a gold signet',
        'macro worship, crimson',
    ),
    'card_offer': _c(
        'card_offer', 'Offer', 'worship', 'common', '🎁',
        "You brought a body. She'll tell you where to put it.",
        'adult offering portrait, palms up, flushed',
        'altar gold, silk, yes',
    ),
    'card_praise': _c(
        'card_praise', 'Praise', 'worship', 'common', '✨',
        'Say it until your mouth forgets other words.',
        'adult devotee mid-praise, eyes wet with light',
        'altar, gold dust, devotion',
    ),
    'card_tongue_service': _c(
        'card_tongue_service', 'Tongue Service', 'worship', 'uncommon', '👅',
        'The liturgy is wet and specific.',
        'adult worship close-up, tongue and gold jewelry',
        'explicit cabaret, 18+, heat',
    ),
    'card_footstool': _c(
        'card_footstool', 'Footstool', 'worship', 'uncommon', '👠',
        'Furniture with a pulse. Stay.',
        'adult at her feet, gold heel in frame',
        'worship angle, velvet, service',
    ),
    'card_altar_night': _c(
        'card_altar_night', 'Altar Night', 'worship', 'rare', '🛐',
        'The whole room on its knees. She stands.',
        'pixel altar, kneeling adults, gold idol',
        'ritual lounge, candles',
    ),
    'card_holy_ruin': _c(
        'card_holy_ruin', 'Holy Ruin', 'worship', 'rare', '💦',
        'You came for salvation. You left a mess.',
        'dramatic ruin at an altar, spilled gold and crimson',
        'still life blasphemy, glitter',
    ),
    'card_high_priestess': _c(
        'card_high_priestess', 'High Priestess', 'worship', 'epic', '👸',
        'She takes offerings. She does not return change.',
        'adult high priestess of the lounge in gold and bare velvet',
        'crown, altar, command',
    ),
    'card_divine_taste': _c(
        'card_divine_taste', 'Divine Taste', 'worship', 'epic', '🍷',
        'Chalice first. Then you.',
        'gold chalice, wine like lipstick, shrine light',
        'still life sacrament, lust',
    ),
    'card_last_call': _c(
        'card_last_call', 'Last Call Kiss', 'encore', 'common', '😘',
        'Lights up in five. Mouths busy now.',
        'adult kiss close at last call, neon dying',
        "lipstick, gold, night's end",
    ),
    'card_lights_down': _c(
        'card_lights_down', 'Lights Down', 'encore', 'common', '🔅',
        'The house dimmer is a sex act.',
        'adult silhouette as the spots die, one gold leftover',
        'encore dark, skin edge',
    ),
    'card_midnight_toast': _c(
        'card_midnight_toast', 'Midnight Toast', 'encore', 'uncommon', '🥂',
        'One more glass. One more round. One more ruin.',
        'adult toast in an empty lounge, two flutes',
        'after hours, gold, intimacy',
    ),
    'card_encore_strip': _c(
        'card_encore_strip', 'Encore Strip', 'encore', 'rare', '🌟',
        "They already clapped. She isn't done.",
        'adult headliner stripping in leftover spotlight',
        'encore, sequins, heat',
    ),
    'card_final_ruin': _c(
        'card_final_ruin', 'Final Ruin', 'encore', 'rare', '💥',
        'The last dump of the night. Make it count.',
        'chaotic beautiful ruin, glitter and spilled pour',
        'still life finale',
    ),
    'card_house_closer': _c(
        'card_house_closer', 'House Closer', 'encore', 'legendary', '🚪',
        'She locks the door from the inside.',
        'legendary adult closer in a long coat and nothing polite',
        'empty club, one lamp, ownership',
    ),
    'card_velvets_mouth': _c(
        'card_velvets_mouth', "Velvet's Mouth", 'encore', 'mythic', '💋',
        'The myth. The kiss. The reason you came.',
        "mythic macro of Velvet's mouth, crimson and gold",
        'extreme close, 18+, shrine',
    ),
    'card_ruin_crown': _c(
        'card_ruin_crown', 'The Ruin Crown', 'encore', 'mythic', '👑',
        'Whoever wears it decides who gets to finish.',
        'mythic adult sovereign crowned in spilled gold and ruin light',
        'throne, wreckage, power',
    ),
    'card_aftercare_goddess': _c(
        'card_aftercare_goddess', 'Aftercare Goddess', 'encore', 'mythic', '🕊️',
        'She ruins you, then she puts you back.',
        'mythic aftercare goddess, silk robe, lethal tenderness',
        'rose gold, steam, 18+',
    ),
    'card_still_ready': _c(
        'card_still_ready', "I'm Still Ready", 'encore', 'mythic', '🔥',
        'The button after the button. The floor legend continues.',
        "mythic lounge champion still answering Velvet's call",
        'heroic cabaret, gold rain, hunger',
    ),
}


assert len(CARD_DEFINITIONS) == 148, f"expected 148 cards, got {len(CARD_DEFINITIONS)}"
assert ORIGINAL_CARD_IDS <= set(CARD_DEFINITIONS), "original 48 ids must remain"


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


def roll_card_prefer_unowned(
    owned: set[str],
    rng: random.Random | None = None,
) -> CardDefinition:
    """Roll a pack-weighted card, preferring ids the collector does not own yet."""
    rarity = roll_rarity(rng)
    roller = rng or random
    fresh = [c for c in cards_for_rarity(rarity) if c.card_id not in owned]
    if fresh:
        return roller.choice(fresh)
    missing = [c for c in CARD_DEFINITIONS.values() if c.card_id not in owned]
    if missing:
        return roller.choice(missing)
    return roll_card(rng)


def card_copy_tag(granted: dict | None) -> str:
    """NEW / duplicate when the grant row recorded dex status."""
    if not granted or "new_unique" not in granted:
        return ""
    return "NEW" if granted.get("new_unique") else "duplicate"


def format_card_line(granted: dict, *, prefix: str | None = None) -> str:
    defn = card_by_id(str(granted.get("card_id") or ""))
    name = defn.name if defn else str(granted.get("card_id") or "card")
    emoji = defn.emoji if defn else "🃏"
    rarity = defn.rarity_label if defn else ""
    print_number = int(granted.get("print_number") or 0)
    parts = [f"{emoji} **{name}**"]
    if prefix:
        parts = [f"{emoji} {prefix}: **{name}**"]
    elif rarity:
        parts.append(rarity)
    parts.append(f"#{print_number:04d}")
    tag = card_copy_tag(granted)
    if tag == "NEW":
        parts.append("**NEW**")
    elif tag:
        parts.append("duplicate")
    return " · ".join(parts)


def format_card_drop(granted: dict, *, prefix: str = "GoonCard") -> str:
    line = format_card_line(granted, prefix=prefix)
    reward = float(granted.get("set_reward") or 0)
    if granted.get("set_complete") and reward > 0:
        line += f" · set complete **{reward:,.0f}** goonbux"
    return line


def format_pack_odds() -> str:
    chunks: list[str] = []
    for rarity in RARITY_ORDER:
        pct = PACK_WEIGHTS[rarity] * 100.0
        shown = f"{pct:.0f}%" if abs(pct - round(pct)) < 0.05 else f"{pct:.1f}%"
        chunks.append(f"{RARITY_LABELS[rarity]} {shown}")
    return " · ".join(chunks)


def roll_pack(size: int, rng: random.Random | None = None) -> list[CardDefinition]:
    return [roll_card(rng) for _ in range(max(1, int(size)))]
