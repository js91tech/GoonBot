from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from utils.classes import ClassTier, get_class

SkillEffect = Literal[
    "damage_boost",
    "heavy_strike",
    "crit_surge",
    "fortify",
    "heal_self",
    "heal_ally",
    "purge",
    "heist_smoke",
    "income_spark",
    "chaos_card",
]


TIER_RANK: dict[ClassTier, int] = {
    "starter": 0,
    "evolved": 1,
    "master": 2,
    "hybrid": 2,
    "special": 2,
}


@dataclass(frozen=True)
class SkillDef:
    skill_id: str
    name: str
    description: str
    mana_cost: int
    min_tier_rank: int
    effect: SkillEffect
    magnitude: float
    emoji: str = "✨"


@dataclass(frozen=True)
class SpellBuff:
    skill_id: str
    name: str
    effect: SkillEffect
    magnitude: float


def _kit(
    prefix: str,
    skills: tuple[tuple[str, str, str, int, int, SkillEffect, float, str], ...],
) -> dict[str, SkillDef]:
    out: dict[str, SkillDef] = {}
    for sid, name, desc, cost, tier, effect, mag, emoji in skills:
        skill_id = f"{prefix}_{sid}"
        out[skill_id] = SkillDef(
            skill_id=skill_id,
            name=name,
            description=desc,
            mana_cost=cost,
            min_tier_rank=tier,
            effect=effect,
            magnitude=mag,
            emoji=emoji,
        )
    return out


SKILL_KITS: dict[str, dict[str, SkillDef]] = {
    "vanguard": _kit(
        "vg",
        (
            ("strike", "Power Strike", "Next hit deals +25% damage.", 18, 0, "damage_boost", 1.25, "⚔️"),
            ("charge", "Shield Charge", "Next hit deals +40% damage.", 38, 1, "heavy_strike", 1.40, "🛡️"),
            ("wrath", "Battle Wrath", "Next hit deals +55% damage.", 62, 2, "heavy_strike", 1.55, "🔥"),
        ),
    ),
    "vanguard_bulwark": _kit(
        "vgb",
        (
            ("bash", "Shield Bash", "Next hit +20% damage.", 16, 0, "damage_boost", 1.20, "🛡️"),
            ("fortify", "Fortify", "Next hit taken deals -30% damage to you.", 30, 1, "fortify", 0.70, "🏰"),
            ("stand", "Last Stand", "Heal 20% of your max HP (boss/duel).", 50, 2, "heal_self", 0.20, "❤️"),
        ),
    ),
    "vanguard_slayer": _kit(
        "vgs",
        (
            ("rend", "Rend", "Next hit +30% damage.", 20, 0, "damage_boost", 1.30, "🗡️"),
            ("frenzy", "Frenzy", "+12% crit on next strike.", 34, 1, "crit_surge", 0.12, "💢"),
            ("execute", "Execution", "Next hit +60% damage.", 65, 2, "heavy_strike", 1.60, "☠️"),
        ),
    ),
    "vanguard_warden": _kit(
        "vgw",
        (
            ("mend", "Mend", "Restore 12% of your max HP.", 14, 0, "heal_self", 0.12, "🩹"),
            ("bless", "Blessing", "Restore 15% HP to a downed ally.", 28, 1, "heal_ally", 0.15, "✨"),
            ("sanctify", "Sanctify", "Restore 25% of your max HP.", 48, 2, "heal_self", 0.25, "🌟"),
        ),
    ),
    "mogul": _kit(
        "mg",
        (
            ("tip", "Coin Tip", "Next hit +15% damage.", 16, 0, "damage_boost", 1.15, "🪙"),
            ("invoice", "Invoice", "Next hit +28% damage.", 32, 1, "damage_boost", 1.28, "📜"),
            ("buyout", "Hostile Buyout", "Next hit +45% damage.", 58, 2, "heavy_strike", 1.45, "💰"),
        ),
    ),
    "mogul_prospector": _kit(
        "mgp",
        (
            ("prospect", "Vein Tap", "Next hit +18% damage.", 15, 0, "damage_boost", 1.18, "⛏️"),
            ("spark", "Gold Spark", "Small income spark on cast (+25 goonbux).", 25, 1, "income_spark", 25.0, "✨"),
            ("rush", "Gold Rush", "Next hit +50% damage.", 60, 2, "heavy_strike", 1.50, "🤑"),
        ),
    ),
    "mogul_broker": _kit(
        "mgb",
        (
            ("deal", "Quick Deal", "Next hit +16% damage.", 14, 0, "damage_boost", 1.16, "🤝"),
            ("hedge", "Hedge", "Reduce next damage taken by 25%.", 30, 1, "fortify", 0.75, "📊"),
            ("crash", "Market Crash", "Next hit +48% damage.", 55, 2, "heavy_strike", 1.48, "📉"),
        ),
    ),
    "mogul_tycoon": _kit(
        "mgt",
        (
            ("tip", "Loose Change", "Next hit +14% damage.", 12, 0, "damage_boost", 1.14, "🪙"),
            ("monopoly", "Monopoly", "Next hit +35% damage.", 36, 1, "damage_boost", 1.35, "👑"),
            ("empire", "Empire Strike", "Next hit +52% damage.", 64, 2, "heavy_strike", 1.52, "🏛️"),
        ),
    ),
    "shade": _kit(
        "sh",
        (
            ("stab", "Shadow Stab", "Next hit +22% damage.", 17, 0, "damage_boost", 1.22, "🌑"),
            ("smoke", "Smoke Bomb", "+8% heist success (next heist).", 28, 1, "heist_smoke", 0.08, "💨"),
            ("eclipse", "Eclipse", "Next hit +50% damage.", 60, 2, "heavy_strike", 1.50, "🌘"),
        ),
    ),
    "shade_cutpurse": _kit(
        "shc",
        (
            ("filch", "Filch", "Next hit +20% damage.", 15, 0, "damage_boost", 1.20, "🎭"),
            ("smoke", "Pocket Smoke", "+10% heist success (next heist).", 26, 1, "heist_smoke", 0.10, "💨"),
            ("backstab", "Backstab", "Next hit +55% damage.", 58, 2, "heavy_strike", 1.55, "🗡️"),
        ),
    ),
    "shade_saboteur": _kit(
        "shs",
        (
            ("sap", "Sap", "Next hit +24% damage.", 18, 0, "damage_boost", 1.24, "💣"),
            ("sabotage", "Sabotage", "Next hit +38% damage.", 35, 1, "heavy_strike", 1.38, "⚙️"),
            ("detonate", "Detonate", "Next hit +58% damage.", 62, 2, "heavy_strike", 1.58, "💥"),
        ),
    ),
    "shade_phantom": _kit(
        "shp",
        (
            ("phase", "Phase Step", "Reduce next damage taken by 35%.", 16, 0, "fortify", 0.65, "👻"),
            ("veil", "Ghost Veil", "Next hit +30% damage.", 32, 1, "damage_boost", 1.30, "🌫️"),
            ("assassinate", "Assassinate", "Next hit +62% damage.", 66, 2, "heavy_strike", 1.62, "☠️"),
        ),
    ),
    "warlord": _kit(
        "wl",
        (
            ("warcry", "War Cry", "Next hit +28% damage.", 22, 2, "damage_boost", 1.28, "📯"),
            ("plunder", "Plunder", "Next hit +42% damage.", 40, 2, "heavy_strike", 1.42, "🏴"),
            ("dominion", "Dominion", "Next hit +65% damage.", 70, 2, "heavy_strike", 1.65, "👑"),
        ),
    ),
    "archon": _kit(
        "ar",
        (
            ("decree", "Decree", "Next hit +26% damage.", 20, 2, "damage_boost", 1.26, "📜"),
            ("aegis", "Royal Aegis", "Reduce next damage taken by 28%.", 34, 2, "fortify", 0.72, "🛡️"),
            ("judgment", "Judgment", "Next hit +60% damage.", 68, 2, "heavy_strike", 1.60, "⚖️"),
        ),
    ),
    "jester": _kit(
        "jest",
        (
            ("joke", "Bad Joke", "Next hit +10% damage.", 10, 2, "damage_boost", 1.10, "🃏"),
            ("trick", "Trickster", "Chaos: next hit +35% or you lose 5 mana.", 25, 2, "chaos_card", 1.35, "🎲"),
            ("punchline", "Punchline", "Next hit +45% damage.", 45, 2, "heavy_strike", 1.45, "🎪"),
        ),
    ),
}

def skill_kit_id(class_id: str) -> str:
    if class_id in SKILL_KITS:
        return class_id
    if class_id in ("warlord", "archon", "jester"):
        return class_id
    parts = class_id.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return parts[0] if parts else class_id


def skills_for_class(class_id: str | None) -> tuple[SkillDef, ...]:
    if not class_id:
        return ()
    kit_id = skill_kit_id(class_id)
    kit = SKILL_KITS.get(kit_id)
    if kit is None:
        kit = SKILL_KITS.get(class_id.split("_")[0], {})
    cls = get_class(class_id)
    rank = TIER_RANK.get(cls.tier, 0) if cls else 0
    return tuple(s for s in kit.values() if s.min_tier_rank <= rank)


def get_skill(skill_id: str) -> SkillDef | None:
    sid = skill_id.lower().strip()
    for kit in SKILL_KITS.values():
        if sid in kit:
            return kit[sid]
    return None


def skill_available(skill: SkillDef, class_id: str | None) -> bool:
    cls = get_class(class_id)
    if cls is None:
        return False
    return skill.min_tier_rank <= TIER_RANK.get(cls.tier, 0)


def spell_buff_from_skill(skill: SkillDef) -> SpellBuff:
    return SpellBuff(
        skill_id=skill.skill_id,
        name=skill.name,
        effect=skill.effect,
        magnitude=skill.magnitude,
    )


def apply_spell_to_damage(base_damage: int, spell: SpellBuff | None) -> tuple[int, str]:
    if spell is None:
        return base_damage, ""
    note = f" **{spell.name}**"
    if spell.effect in ("damage_boost", "heavy_strike"):
        return max(1, int(base_damage * spell.magnitude)), note
    if spell.effect == "crit_surge":
        return base_damage, note + " (crit surge)"
    if spell.effect == "chaos_card":
        return max(1, int(base_damage * spell.magnitude)), note
    return base_damage, note


def format_skills_list(class_id: str | None) -> str:
    skills = skills_for_class(class_id)
    if not skills:
        return "No skills (choose a class first)."
    lines = [
        f"{s.emoji} **{s.name}** (`{s.skill_id}`) — **{s.mana_cost}** mana — {s.description}"
        for s in sorted(skills, key=lambda x: x.mana_cost)
    ]
    return "\n".join(lines)
