from __future__ import annotations

import random
from dataclasses import dataclass

import config

_STD = config.DUNGEON_NORMAL_DIFFICULTY_MULT
_VAULT = config.DUNGEON_VAULT_DIFFICULTY_MULT


@dataclass(frozen=True)
class DungeonTier:
    tier_id: str
    name: str
    emoji: str
    unlock_cost: float
    room_reward: float
    clear_bonus: float
    scrap_per_clear: int
    energy_cost: int
    party_only: bool
    min_party_size: int
    enemy_hp_room1_min: float
    enemy_hp_room1_max: float
    enemy_hp_room_bonus: float
    enemy_hp_room_spread: float
    counter_min: int
    counter_max: int
    party_enemy_hp_room1_min: float
    party_enemy_hp_room1_max: float
    party_enemy_hp_room_bonus: float
    party_enemy_hp_room_spread: float
    party_counter_min: int
    party_counter_max: int


NORMAL_TIER = DungeonTier(
    tier_id="normal",
    name="Delver's Depths",
    emoji="🕳️",
    unlock_cost=0.0,
    room_reward=config.DUNGEON_ROOM_REWARD,
    clear_bonus=config.DUNGEON_CLEAR_BONUS,
    scrap_per_clear=config.DUNGEON_SCRAP_PER_CLEAR,
    energy_cost=config.DUNGEON_ENERGY_COST,
    party_only=False,
    min_party_size=1,
    enemy_hp_room1_min=115.0 * _STD,
    enemy_hp_room1_max=185.0 * _STD,
    enemy_hp_room_bonus=22.0 * _STD,
    enemy_hp_room_spread=28.0 * _STD,
    counter_min=18 * _STD,
    counter_max=36 * _STD,
    party_enemy_hp_room1_min=160.0 * _STD,
    party_enemy_hp_room1_max=260.0 * _STD,
    party_enemy_hp_room_bonus=30.0 * _STD,
    party_enemy_hp_room_spread=35.0 * _STD,
    party_counter_min=14 * _STD,
    party_counter_max=28 * _STD,
)

VAULT_TIER = DungeonTier(
    tier_id="vault",
    name="Gilded Vault",
    emoji="🏛️",
    unlock_cost=config.DUNGEON_VAULT_UNLOCK_COST,
    room_reward=config.DUNGEON_VAULT_ROOM_REWARD,
    clear_bonus=config.DUNGEON_VAULT_CLEAR_BONUS,
    scrap_per_clear=config.DUNGEON_VAULT_SCRAP_PER_CLEAR,
    energy_cost=config.DUNGEON_ENERGY_COST,
    party_only=True,
    min_party_size=config.DUNGEON_VAULT_MIN_PARTY_SIZE,
    enemy_hp_room1_min=115.0 * _VAULT,
    enemy_hp_room1_max=185.0 * _VAULT,
    enemy_hp_room_bonus=22.0 * _VAULT,
    enemy_hp_room_spread=28.0 * _VAULT,
    counter_min=18 * _VAULT,
    counter_max=36 * _VAULT,
    party_enemy_hp_room1_min=480.0 * _VAULT,
    party_enemy_hp_room1_max=680.0 * _VAULT,
    party_enemy_hp_room_bonus=55.0 * _VAULT,
    party_enemy_hp_room_spread=65.0 * _VAULT,
    party_counter_min=24 * _VAULT,
    party_counter_max=42 * _VAULT,
)

DUNGEON_TIERS: dict[str, DungeonTier] = {
    NORMAL_TIER.tier_id: NORMAL_TIER,
    VAULT_TIER.tier_id: VAULT_TIER,
}


def get_dungeon_tier(tier_id: str | None) -> DungeonTier:
    if tier_id and tier_id in DUNGEON_TIERS:
        return DUNGEON_TIERS[tier_id]
    return NORMAL_TIER


def next_enemy_hp(tier: DungeonTier, room: int) -> float:
    if room <= 1:
        return random.uniform(tier.enemy_hp_room1_min, tier.enemy_hp_room1_max)
    rooms_in = room - 1
    lo = tier.enemy_hp_room1_min + rooms_in * tier.enemy_hp_room_bonus
    hi = tier.enemy_hp_room1_max + rooms_in * tier.enemy_hp_room_spread
    return random.uniform(lo, hi)


def next_party_enemy_hp(tier: DungeonTier, room: int) -> float:
    if room <= 1:
        return random.uniform(
            tier.party_enemy_hp_room1_min,
            tier.party_enemy_hp_room1_max,
        )
    rooms_in = room - 1
    lo = tier.party_enemy_hp_room1_min + rooms_in * tier.party_enemy_hp_room_bonus
    hi = tier.party_enemy_hp_room1_max + rooms_in * tier.party_enemy_hp_room_spread
    return random.uniform(lo, hi)
