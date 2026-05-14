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


WEAPONS: tuple[ShopItem, ...] = (
    ShopItem("twig_sword", "Twig Sword", "weapon", 250, 5, "A starter blade with splinters.", ("pokes", "swats")),
    ShopItem("rusty_dagger", "Rusty Dagger", "weapon", 750, 9, "Fast, cheap, and suspicious.", ("stabs", "jabs")),
    ShopItem("iron_sword", "Iron Sword", "weapon", 1_800, 15, "Reliable boss-fighting steel.", ("slashes", "cleaves")),
    ShopItem("ember_axe", "Ember Axe", "weapon", 4_000, 23, "Hot enough to leave a mark.", ("chops", "scorches")),
    ShopItem("storm_spear", "Storm Spear", "weapon", 8_500, 34, "Crackles with static.", ("skewers", "thunders into")),
    ShopItem("void_blade", "Void Blade", "weapon", 16_000, 48, "Cuts where armor forgets to exist.", ("rifts", "carves")),
    ShopItem("sunhammer", "Sunhammer", "weapon", 30_000, 66, "Heavy enough to change the weather.", ("smashes", "craters")),
    ShopItem("dragon_lance", "Dragon Lance", "weapon", 52_000, 88, "Built for impossible raids.", ("impales", "pierces")),
    ShopItem("cosmic_greatsword", "Cosmic Greatsword", "weapon", 82_000, 115, "A galaxy with a handle.", ("cleaves", "star-slashes"), crit_chance=0.03),
    ShopItem("nugget_excalibur", "Nugget Excalibur", "weapon", 120_000, 150, "The endgame flex.", ("obliterates", "royally slashes"), crit_chance=0.06),
)

ARMOR: tuple[ShopItem, ...] = (
    ShopItem("paper_hat", "Paper Hat", "armor", 250, 2, "Technically protection.", hp_bonus=3),
    ShopItem("padded_hoodie", "Padded Hoodie", "armor", 750, 5, "Comfortable and mildly sturdy.", hp_bonus=8),
    ShopItem("bronze_vest", "Bronze Vest", "armor", 1_800, 9, "Entry-level raid gear.", hp_bonus=14),
    ShopItem("iron_plate", "Iron Plate", "armor", 4_000, 15, "Classic clanking defense.", hp_bonus=22),
    ShopItem("ember_mail", "Ember Mail", "armor", 8_500, 23, "Warm, dramatic, defensive.", hp_bonus=32),
    ShopItem("stormguard", "Stormguard", "armor", 16_000, 34, "Turns shocks into shrugs.", hp_bonus=45),
    ShopItem("void_ward", "Void Ward", "armor", 30_000, 48, "Makes danger miss its appointment.", hp_bonus=60),
    ShopItem("dragon_scale", "Dragon Scale", "armor", 52_000, 66, "Premium monster-proofing.", hp_bonus=80),
    ShopItem("celestial_aegis", "Celestial Aegis", "armor", 82_000, 88, "A wearable constellation.", hp_bonus=105),
    ShopItem("nugget_immortal_plate", "Nugget Immortal Plate", "armor", 120_000, 115, "Endgame armor for dedicated grinders.", hp_bonus=140),
)

ITEMS: dict[str, ShopItem] = {item.id: item for item in (*WEAPONS, *ARMOR)}
ITEM_ORDER: tuple[str, ...] = tuple(item.id for item in (*WEAPONS, *ARMOR))
CATEGORIES = ("all", "weapon", "armor")


def get_item(item_id: str) -> ShopItem | None:
    return ITEMS.get(item_id)


def items_for_category(category: str) -> list[ShopItem]:
    normalized = category.lower()
    if normalized == "all":
        return [ITEMS[item_id] for item_id in ITEM_ORDER]
    if normalized not in CATEGORIES:
        return []
    return [item for item in ITEMS.values() if item.category == normalized]
