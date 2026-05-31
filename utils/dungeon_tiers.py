from __future__ import annotations

import random
from dataclasses import dataclass

import config


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
    enemy_hp_room1_min=115.0,
    enemy_hp_room1_max=185.0,
    enemy_hp_room_bonus=22.0,
    enemy_hp_room_spread=28.0,
    counter_min=18,
    counter_max=36,
    party_enemy_hp_room1_min=160.0,
    party_enemy_hp_room1_max=260.0,
    party_enemy_hp_room_bonus=30.0,
    party_enemy_hp_room_spread=35.0,
    party_counter_min=14,
    party_counter_max=28,
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
    enemy_hp_room1_min=115.0,
    enemy_hp_room1_max=185.0,
    enemy_hp_room_bonus=22.0,
    enemy_hp_room_spread=28.0,
    counter_min=18,
    counter_max=36,
    party_enemy_hp_room1_min=480.0,
    party_enemy_hp_room1_max=680.0,
    party_enemy_hp_room_bonus=55.0,
    party_enemy_hp_room_spread=65.0,
    party_counter_min=24,
    party_counter_max=42,
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
    base = 100 + room * tier.enemy_hp_room_bonus
    spread = 150 + room * tier.enemy_hp_room_spread
    return random.uniform(base, spread)


def next_party_enemy_hp(tier: DungeonTier, room: int) -> float:
    if room <= 1:
        return random.uniform(
            tier.party_enemy_hp_room1_min,
            tier.party_enemy_hp_room1_max,
        )
    base = 140 + room * tier.party_enemy_hp_room_bonus
    spread = 200 + room * tier.party_enemy_hp_room_spread
    return random.uniform(base, spread)
