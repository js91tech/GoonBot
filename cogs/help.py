from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.help_content import HELP_PAGES
from utils.helpers import guild_only_message


class HelpView(discord.ui.View):
    def __init__(self, *, page: int = 0) -> None:
        super().__init__(timeout=120.0)
        self.page = page
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= len(HELP_PAGES) - 1

    def embed(self) -> discord.Embed:
        title, body = HELP_PAGES[self.page]
        return discord.Embed(
            title=f"NuggetBot guide — {title}",
            description=body,
            color=discord.Color.blurple(),
        ).set_footer(text=f"Page {self.page + 1}/{len(HELP_PAGES)}")

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button
        self.page = min(len(HELP_PAGES) - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Browse NuggetBot commands by category.")
    @app_commands.guild_only()
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(guild_only_message(), ephemeral=True)
            return
        view = HelpView(page=0)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
