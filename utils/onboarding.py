"""Post-age-gate onboarding — teach the GoonBot night loop."""
from __future__ import annotations

import discord

from utils.goon_theme import FOOTER_BRAND, brand_color, branded_embed, panel_title


ONBOARDING_TITLE = "Tonight's loop — start here"
ONBOARDING_BODY = (
    "You're in. GoonBot is an **18+ goonbux** economy RPG.\n\n"
    "**1.** `/daily` — claim your goonbux\n"
    "**2.** `/jobs` — grind the lounge for pocket cash\n"
    "**3.** `/shop` — buy a weapon, then `/equip`\n"
    "**4.** `/boss` — raid **Velvet Vixen**\n"
    "**5.** `/profile` — launcher for casino, drugs, crime, empire\n\n"
    "Prefer **NSFW channels**. Admins can toggle `nsfw_channel_only`."
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

    @discord.ui.button(label="Got it — let's goon", style=discord.ButtonStyle.primary, row=0)
    async def dismiss(
        self, interaction: discord.Interaction, _button: discord.ui.Button,
    ) -> None:
        embed = branded_embed(
            "You're cleared",
            description=(
                "Open `/profile` anytime for hubs. "
                "Start with `/daily`, then `/jobs` or `/boss`."
            ),
        )
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)
