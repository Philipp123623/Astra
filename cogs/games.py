import discord
from discord.ext import commands
from discord import app_commands
import discord_games as games

# import base module
from discord_games import button_games

##########


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="hangman")
    async def hangman(self, interaction: discord.Interaction):
        """Play Hangman"""
        game = games.Hangman()
        await game.start(ctx, delete_after_guess=True)
        await interaction.response.send_message("Have fun!", ephemeral=True)
        


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Games(bot))
