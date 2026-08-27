"""Post-age-gate onboarding — guest list → persona → floor → Velvet."""
from __future__ import annotations

import discord

from utils.goon_theme import FOOTER_BRAND, brand_color, branded_embed, panel_title


ONBOARDING_TITLE = "You're on the guest list"
ONBOARDING_BODY = (
    "Welcome to **GoonBot** — an 18+ nightlife economy. "
    "Tonight isn't a dungeon grind. It's a **session**.\n\n"
    "**1.** `/daily` — another round (goonbux)\n"
    "**2.** `/class choose` — pick a **persona** "
    "(Talent / Host / Fixer) for your floor\n"
    "**3.** `/goon edge` — start a streak. Don't finish.\n"
    "**4.** `/jobs` or `/business` — make floor money "
    "(persona hustles unlock)\n"
    "**5.** `/boss` — when **Velvet Walks In**, be there\n"
    "**6.** `/profile` — heat / VIP, session meter, hustles, empire\n\n"
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
                "Claim `/daily`, pick `/class choose`, then `/goon edge`. "
                "When Velvet shows, `/boss` is last call. Don't finish first."
            ),
        )
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)
