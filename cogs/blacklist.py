import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import asyncio

##########


class blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT serverID, word FROM blacklist WHERE serverID = (%s)", (msg.guild.id))
                result = await cursor.fetchall()
                if not result:
                    return
                if result:
                    for eintrag in result:
                        serverID = eintrag[0]

                        word = eintrag[1]
                        lowerword = word.lower()
                        lowercontent = msg.content.lower()
                        if msg.guild.id == serverID:
                            if lowerword in lowercontent:
                                embed = discord.Embed(title="Bitte unterlasse die Schimpfwörter",
                                                      description=f"{msg.author.mention} nutze ein Wort: ``{word}`` welches hier nicht erlaubt ist!",
                                                      colour=discord.Colour.red(), timestamp=discord.utils.utcnow())
                                embed.set_author(name=msg.author, icon_url=msg.author.avatar)
                                delete = await msg.channel.send(embed=embed)
                                channel = msg.channel
                                message = await channel.fetch_message(msg.id)
                                await message.delete()
                                await asyncio.sleep(7)
                                await delete.delete()
                        else:
                            return

    @app_commands.command(name="blacklist")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(argument="Argument", word="Word")
    async def blacklist(self, interaction: discord.Interaction, argument: Literal['Hinzufügen', 'Entfernen', 'Anzeigen'],
                        word: str = None):
        """Nachrichten Blacklisten, von der Blacklist entfernen und eine Liste mit allen geblacklisteten Wörtern erhalten."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if argument == "Hinzufügen":
                    await cursor.execute("INSERT INTO blacklist(word, serverID) VALUES (%s, %s)",
                                         (word, interaction.guild.id))
                    await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> Das Wort **{word}** ist nun verboten.", epehemeral=True)
                if argument == "Entfernen":
                    await cursor.execute("SELECT word FROM blacklist WHERE serverID = (%s)", (interaction.guild.id))
                    result = await cursor.fetchall()
                    if result == ():
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> Es sind keine Einträge vorhanden!", epehemeral=True)
                    if result:
                        await cursor.execute("DELETE FROM blacklist WHERE word = (%s)", (word))
                        await interaction.response.send_message(f"", epehemeral=True)
                if argument == "Anzeigen":
                    await cursor.execute("SELECT word FROM blacklist WHERE serverID = (%s)", (interaction.guild.id))
                    result = await cursor.fetchall()
                    if not result:
                        await interaction.response.send_message("❌ Es sind keine Einträge vorhanden!", ephemeral=True)
                    if result:

                        embed = discord.Embed(title="Aktuelle Einträge",
                                              description=f"Hier siehst du, welche Wörter aktuell verboten sind!",
                                              color=discord.Color.green())

                        for eintrag in result:
                            word = eintrag[0]

                            embed.add_field(name="Wort:", value=word, inline=True)

                        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(blacklist(bot))