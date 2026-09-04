"""Public GoonCards drop posts so the whole channel can see pulls and awards."""
from __future__ import annotations

import io
from typing import Any, Sequence

import discord

from utils.bot_room import send_channel_message
from utils.card_canvas import render_card_png, render_pack_reveal
from utils.cards import CardDefinition, card_by_id, format_card_drop, format_card_line
from utils.goon_theme import branded_embed, panel_title

_USER_MENTIONS = discord.AllowedMentions(users=True, roles=False)


def cards_from_granted(rows: Sequence[dict[str, Any]]) -> tuple[list[CardDefinition], list[int]]:
    cards: list[CardDefinition] = []
    prints: list[int] = []
    for row in rows:
        defn = card_by_id(str(row.get("card_id") or ""))
        if defn is None:
            continue
        cards.append(defn)
        prints.append(int(row.get("print_number") or 0))
    return cards, prints


def build_card_event_payload(
    *,
    title: str,
    cards: Sequence[CardDefinition],
    prints: Sequence[int],
    extra: str = "",
    granted: dict[str, Any] | None = None,
    granted_rows: Sequence[dict[str, Any]] | None = None,
) -> tuple[discord.Embed, discord.File, str]:
    """Return embed + attachment for a public card drop. Testable without Discord I/O."""
    if not cards:
        raise ValueError("cards is empty")
    rows = list(granted_rows or ())
    lines: list[str] = []
    for i, card in enumerate(cards):
        print_n = int(prints[i] if i < len(prints) else 0)
        row = rows[i] if i < len(rows) else granted
        if row:
            payload = {
                **row,
                "card_id": row.get("card_id") or card.card_id,
                "print_number": int(row.get("print_number") or print_n),
            }
            lines.append(format_card_line(payload))
        else:
            lines.append(
                f"{card.emoji} **{card.name}** · {card.rarity_label} · #{print_n:04d}"
            )
    set_row = granted or next((row for row in rows if row.get("set_complete")), None)
    if set_row and set_row.get("set_complete"):
        drop = format_card_drop(set_row)
        if "set complete" in drop:
            lines.append(drop[drop.index("set complete"):])
    description = "\n".join(lines)
    if extra:
        description = f"{extra}\n{description}" if description else extra
    if len(cards) == 1:
        png = render_card_png(cards[0], print_number=int(prints[0]) if prints else None)
        filename = "card.png"
    else:
        png = render_pack_reveal(list(cards), [int(n) for n in prints])
        filename = "pack.png"
    embed = branded_embed(panel_title(title), description=description)
    embed.set_image(url=f"attachment://{filename}")
    file = discord.File(io.BytesIO(png), filename=filename)
    return embed, file, filename


async def announce_card_event(
    bot: discord.Client,
    channel: discord.abc.Messageable | None,
    *,
    user: discord.abc.User | discord.Member,
    title: str,
    cards: Sequence[CardDefinition],
    prints: Sequence[int],
    content: str | None = None,
    extra: str = "",
    granted: dict[str, Any] | None = None,
) -> discord.Message | None:
    if not cards:
        return None
    embed, file, _filename = build_card_event_payload(
        title=title,
        cards=cards,
        prints=prints,
        extra=extra,
        granted=granted,
        granted_rows=(granted,) if granted else None,
    )
    body = content if content is not None else f"{user.mention} pulled **{title}**."
    return await send_channel_message(
        bot,
        channel,
        body,
        embed=embed,
        file=file,
        allowed_mentions=_USER_MENTIONS,
    )


async def announce_granted_cards(
    bot: discord.Client,
    channel: discord.abc.Messageable | None,
    *,
    user: discord.abc.User | discord.Member,
    granted_rows: Sequence[dict[str, Any]],
    title: str,
    content: str | None = None,
    extra: str = "",
) -> discord.Message | None:
    cards, prints = cards_from_granted(granted_rows)
    if not cards:
        return None
    set_row = next((row for row in granted_rows if row.get("set_complete")), None)
    embed, file, _filename = build_card_event_payload(
        title=title,
        cards=cards,
        prints=prints,
        extra=extra,
        granted=set_row,
        granted_rows=granted_rows,
    )
    body = content if content is not None else f"{user.mention} pulled **{title}**."
    return await send_channel_message(
        bot,
        channel,
        body,
        embed=embed,
        file=file,
        allowed_mentions=_USER_MENTIONS,
    )


def interaction_channel(
    interaction: discord.Interaction,
) -> discord.abc.Messageable | None:
    channel = interaction.channel
    if channel is None:
        return None
    return channel
