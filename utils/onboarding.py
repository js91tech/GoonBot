"""Post-age-gate onboarding — guest list → persona → floor → Velvet."""
from __future__ import annotations

import discord

from utils.goon_theme import FOOTER_BRAND, brand_color, branded_embed, panel_title


ONBOARDING_TITLE = "You're on the guest list"
ONBOARDING_BODY = (
    "Welcome to **GoonBot** — an 18+ nightlife economy. "
    "Tonight isn't a dungeon grind. It's a **night out**.\n\n"
    "**1.** `/daily` — tip yourself in (goonbux)\n"
    "**2.** `/class choose` — pick a **persona** "
    "(Talent / Host / Fixer)\n"
    "**3.** `/jobs` or `/business` — make floor money\n"
    "**4.** `/boss` — when **Velvet Vixen** walks in, be there\n"
    "**5.** `/profile` — casino tables, private rooms, hustles, empire\n\n"
    "Play in **NSFW channels**. Admins can toggle `nsfw_channel_only`."
)


def onboarding_embed(*, member_name: str | None = None) -> discord.Embed:
    embed = branded_embed(
        panel_title(ONBOARDING_TITLE, member_name=member_name),
        description=ONBOARDING_BODY,
        color=brand_color(),
    )
    embed.set_footer(text=FOOTER_BRAND)
    return embed


class NightLoopView(discord.ui.View):
    """Ephemeral pointer panel after 18+ confirm (slash commands do the work)."""

    def __init__(self) -> None:
        super().__init__(timeout=300)

    @discord.ui.button(label="I'm in — open the night", style=discord.ButtonStyle.primary, row=0)
    async def dismiss(
        self, interaction: discord.Interaction, _button: discord.ui.Button,
    ) -> None:
        embed = branded_embed(
            "Doors are open",
            description=(
                "Claim `/daily`, pick `/class choose`, then hit the floor. "
                "When Velvet shows, `/boss` is last call."
            ),
        )
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)
