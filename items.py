from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShopItem:
    id: str
    name: str
    category: str
    price: float
    power: int
    description: str
    verbs: tuple[str, ...] = ()
    crit_chance: float = 0.0
    hp_bonus: int = 0
    shop_listed: bool = True


STARTER_WEAPON = ShopItem(
    "training_stick",
    "Training Stick",
    "weapon",
    0,
    6,
    "A free launch gift. Weaker than the cheapest shop weapon.",
    ("whacks", "taps"),
)
STARTER_ARMOR = ShopItem(
    "cardboard_shield",
    "Cardboard Shield",
    "armor",
    0,
    4,
    "A free launch gift. Weaker than the cheapest shop armor.",
    hp_bonus=12,
)

WEAPONS: tuple[ShopItem, ...] = (
    ShopItem("twig_sword", "Twig Sword", "weapon", 250, 12, "A starter blade with splinters.", ("pokes", "swats")),
    ShopItem("rusty_dagger", "Rusty Dagger", "weapon", 750, 43, "Fast, cheap, and suspicious.", ("stabs", "jabs"), crit_chance=0.02),
    ShopItem("iron_sword", "Iron Sword", "weapon", 1_800, 75, "Reliable boss-fighting steel.", ("slashes", "cleaves"), crit_chance=0.04),
    ShopItem("ember_axe", "Ember Axe", "weapon", 4_000, 106, "Hot enough to leave a mark.", ("chops", "scorches"), crit_chance=0.05),
    ShopItem("storm_spear", "Storm Spear", "weapon", 8_500, 137, "Crackles with static.", ("skewers", "thunders into"), crit_chance=0.07),
    ShopItem("void_blade", "Void Blade", "weapon", 16_000, 169, "Cuts where armor forgets to exist.", ("rifts", "carves"), crit_chance=0.09),
    ShopItem("sunhammer", "Sunhammer", "weapon", 30_000, 200, "Heavy enough to change the weather.", ("smashes", "craters"), crit_chance=0.11),
    ShopItem("dragon_lance", "Dragon Lance", "weapon", 52_000, 232, "Built for impossible raids.", ("impales", "pierces"), crit_chance=0.13),
    ShopItem(
        "cosmic_greatsword",
        "Cosmic Greatsword",
        "weapon",
        82_000,
        263,
        "A galaxy with a handle.",
        ("cleaves", "star-slashes"),
        crit_chance=0.14,
    ),
    ShopItem(
        "nugget_excalibur",
        "Nugget Excalibur",
        "weapon",
        120_000,
        295,
        "The endgame flex.",
        ("obliterates", "royally slashes"),
        crit_chance=0.16,
    ),
    ShopItem(
        "mythic_voidreaver",
        "Mythic Voidreaver",
        "weapon",
        175_000,
        328,
        "Forged past the shop ceiling for raid veterans.",
        ("void-renders", "annihilates"),
        crit_chance=0.18,
    ),
)

GUNS: tuple[ShopItem, ...] = (
    ShopItem(
        "cap_gun",
        "Cap Gun",
        "gun",
        280,
        12,
        "Fires disappointment at point-blank range.",
        ("pops", "pegs"),
        crit_chance=0.03,
    ),
    ShopItem(
        "rust_revolver",
        "Rust Revolver",
        "gun",
        800,
        43,
        "Six chambers of tetanus.",
        ("blasts", "tags"),
        crit_chance=0.04,
    ),
    ShopItem(
        "iron_pistol",
        "Iron Pistol",
        "gun",
        1_900,
        75,
        "Reliable sidearm for raid night.",
        ("shoots", "drills"),
        crit_chance=0.05,
    ),
    ShopItem(
        "flare_pistol",
        "Flare Pistol",
        "gun",
        4_200,
        106,
        "Incendiary rounds with dramatic flair.",
        ("ignites", "flares into"),
        crit_chance=0.06,
    ),
    ShopItem(
        "storm_rifle",
        "Storm Rifle",
        "gun",
        9_000,
        137,
        "Full-auto thunder in a metal tube.",
        ("strafes", "volleys"),
        crit_chance=0.08,
    ),
    ShopItem(
        "void_carbine",
        "Void Carbine",
        "gun",
        17_000,
        169,
        "Bullets that forget where armor ends.",
        ("void-shots", "hollows"),
        crit_chance=0.10,
    ),
    ShopItem(
        "sunshot_rifle",
        "Sunshot Rifle",
        "gun",
        32_000,
        200,
        "Long-range solar punishment.",
        ("snipes", "solar-bores through"),
        crit_chance=0.12,
    ),
    ShopItem(
        "dragon_shotgun",
        "Dragon Shotgun",
        "gun",
        54_000,
        232,
        "Spread pattern: entire dragon.",
        ("buckshots", "shreds"),
        crit_chance=0.14,
    ),
    ShopItem(
        "cosmic_railgun",
        "Cosmic Railgun",
        "gun",
        85_000,
        263,
        "One shot, one constellation.",
        ("rails", "star-pierces"),
        crit_chance=0.15,
    ),
    ShopItem(
        "nugget_minigun",
        "Nugget Minigun",
        "gun",
        125_000,
        295,
        "BRRRRT currency.",
        ("shreds", "minces"),
        crit_chance=0.17,
    ),
    ShopItem(
        "mythic_annihilator",
        "Mythic Annihilator",
        "gun",
        180_000,
        328,
        "Deletes the concept of cover.",
        ("annihilates", "unmakes"),
        crit_chance=0.19,
    ),
)

ARMOR: tuple[ShopItem, ...] = (
    ShopItem("paper_hat", "Paper Hat", "armor", 250, 8, "Technically protection.", hp_bonus=18),
    ShopItem("padded_hoodie", "Padded Hoodie", "armor", 750, 29, "Comfortable and mildly sturdy.", hp_bonus=54),
    ShopItem("bronze_vest", "Bronze Vest", "armor", 1_800, 51, "Entry-level raid gear.", hp_bonus=90),
    ShopItem("iron_plate", "Iron Plate", "armor", 4_000, 72, "Classic clanking defense.", hp_bonus=127),
    ShopItem("ember_mail", "Ember Mail", "armor", 8_500, 93, "Warm, dramatic, defensive.", hp_bonus=163),
    ShopItem("stormguard", "Stormguard", "armor", 16_000, 115, "Turns shocks into shrugs.", hp_bonus=199),
    ShopItem("void_ward", "Void Ward", "armor", 30_000, 136, "Makes danger miss its appointment.", hp_bonus=236),
    ShopItem("dragon_scale", "Dragon Scale", "armor", 52_000, 157, "Premium monster-proofing.", hp_bonus=272),
    ShopItem("celestial_aegis", "Celestial Aegis", "armor", 82_000, 179, "A wearable constellation.", hp_bonus=309),
    ShopItem(
        "nugget_immortal_plate",
        "Nugget Immortal Plate",
        "armor",
        120_000,
        200,
        "Endgame armor for dedicated grinders.",
        hp_bonus=345,
    ),
    ShopItem(
        "mythic_aetherplate",
        "Mythic Aetherplate",
        "armor",
        175_000,
        220,
        "Reality-bent plating for players who outgrew the shop.",
        hp_bonus=385,
    ),
)

BOSS_SLAYER_BLADE = ShopItem(
    "boss_slayer_blade",
    "Heartsplitter Fang",
    "weapon",
    6_500,
    118,
    "Boss-forged steel pulsing with leftover raid energy.",
    ("rends", "finishes"),
    crit_chance=0.095,
    shop_listed=False,
)
BOSS_SLAYER_MAIL = ShopItem(
    "boss_slayer_mail",
    "Trophy Bastion Mail",
    "armor",
    6_500,
    84,
    "Plates tempered in Hannah's defeat — prized raid salvage.",
    hp_bonus=148,
    shop_listed=False,
)
MYTHIC_RAID_BLADE = ShopItem(
    "mythic_raid_blade",
    "Hannah's Shattered Fang",
    "weapon",
    0,
    142,
    "Ultra-rare mythic boss drop — stronger than Heartsplitter Fang.",
    ("shatters", "eclipses"),
    crit_chance=0.11,
    shop_listed=False,
)
MYTHIC_RAID_MAIL = ShopItem(
    "mythic_raid_mail",
    "Hannah's Aegis Fragment",
    "armor",
    0,
    98,
    "Ultra-rare mythic boss drop — endgame raid trophy armor.",
    hp_bonus=178,
    shop_listed=False,
)


def _inferior_boss_drop(base: ShopItem) -> ShopItem:
    """Weaker, sellable variant of shop gear for boss loot."""
    pow_scaled = max(1, int(round(base.power * 0.58)))
    price_scaled = float(max(35, int(round(base.price * 0.28 / 25)) * 25))
    crit = round(base.crit_chance * 0.72, 4)
    hp_b = max(8, int(round(base.hp_bonus * 0.58))) if base.category == "armor" else 0
    desc = f"A battered knockoff of shop-tier gear. {base.description}"
    return ShopItem(
        f"boss_weak_{base.id}",
        f"Battle-Worn {base.name}",
        base.category,
        price_scaled,
        pow_scaled,
        desc,
        base.verbs,
        crit_chance=crit,
        hp_bonus=hp_b,
        shop_listed=False,
    )


BOSS_WEAK_ITEMS: tuple[ShopItem, ...] = tuple(
    _inferior_boss_drop(it) for it in (*WEAPONS, *GUNS, *ARMOR) if it.price > 0
)

GRANT_ITEMS: tuple[ShopItem, ...] = (STARTER_WEAPON, STARTER_ARMOR)
ITEMS: dict[str, ShopItem] = {
    item.id: item
    for item in (
        *GRANT_ITEMS,
        *WEAPONS,
        *GUNS,
        *ARMOR,
        BOSS_SLAYER_BLADE,
        BOSS_SLAYER_MAIL,
        MYTHIC_RAID_BLADE,
        MYTHIC_RAID_MAIL,
        *BOSS_WEAK_ITEMS,
    )
}
ITEM_ORDER: tuple[str, ...] = tuple(item.id for item in (*WEAPONS, *GUNS, *ARMOR))
CATEGORIES = ("all", "weapon", "gun", "armor")
SHOP_CATEGORIES = ("all", "weapon", "gun", "armor")


def equip_slot_for(item: ShopItem) -> str:
    """Database equipment slot for an item (guns share the weapon slot)."""
    if item.category in ("weapon", "gun"):
        return "weapon"
    return item.category


def is_damage_dealer(item: ShopItem) -> bool:
    return item.category in ("weapon", "gun")


def get_item(item_id: str) -> ShopItem | None:
    return ITEMS.get(item_id)


def armor_mitigation_percent(power: int) -> int:
    return int(round(100 * power / (power + 100)))


def items_for_category(category: str) -> list[ShopItem]:
    normalized = category.lower()
    if normalized == "all":
        return [ITEMS[item_id] for item_id in ITEM_ORDER if ITEMS[item_id].shop_listed]
    if normalized not in SHOP_CATEGORIES:
        return []
    return [
        item
        for item in ITEMS.values()
        if item.category == normalized and item.shop_listed
    ]
