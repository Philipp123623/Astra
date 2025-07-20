import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Group
from typing import Literal
import asyncio


##########


class tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        if not msg.guild:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT tagname, tagoutput FROM tags WHERE guildID = (%s)", (msg.guild.id))
                result = await cursor.fetchall()
                if not result:
                    return
                if result:
                    for eintrag in result:
                        name = eintrag[0]
                        upper = name.upper()
                        output = eintrag[1]
                        if f"a!{name}" == msg.content:
                            embed = discord.Embed(title=f"__{upper}__", description=output,
                                                  colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                            embed.set_author(name=msg.author, icon_url=msg.author.avatar)
                            embed.set_thumbnail(url=msg.guild.icon)
                            await msg.channel.send(embed=embed)

    @app_commands.command(name="tags")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tags(self, interaction: discord.Interaction, modus: Literal['Hinzufügen', 'Entfernen', 'Anzeigen'], name: str, ausgabe: str=None):
        """Erstelle eigene Befehle nur für deinen Server."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if modus == "Hinzufügen":
                    await cursor.execute("INSERT INTO tags (guildID, tagname, tagoutput) VALUES (%s, %s, %s)",
                                         (interaction.guild.id, name, ausgabe))
                    embed = discord.Embed(title="Tag wird erstellt",
                                          description="Der Tag wurde erstellt.",
                                          colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                    embed.add_field(name="Name:", value=f"a!{name}")
                    embed.add_field(name="Ausgabe:", value=f"{ausgabe}")
                    embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
               
                if modus == "Entfernen":
                    await cursor.execute("SELECT tagname FROM tags WHERE tagname = (%s)", (name))
                    result = await cursor.fetchone()
                    if result is None:
                        await interaction.response.send_message(f"<:Astra_x:1141303954555289600> **Es existiert kein Tag mit dem Namen `{name}`. Füge einen mit `/tag hinzufügen <name> <ausgabe>`**", ephemeral=True)
                    if result:
                        await cursor.execute("DELETE FROM tags WHERE tagname = (%s)", (name))
                        embed = discord.Embed(title="Tag Entfernt",
                                              description=f"Der Tag `{name}`` wurde entfernt.",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                        embed.add_field(name="Name:", value=f"a!{name}")
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        
                if modus == "Anzeigen":
                    await cursor.execute("SELECT tagname, tagoutput FROM tags WHERE guildID = (%s)", (interaction.guild.id))
                    result = await cursor.fetchall()
                    embed = discord.Embed(title="Tags",
                                          description=f"Hier ist eine Liste mit allen Tags dieses Servers.",
                                          colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                    if not result:
                        await interaction.response.send_message(f"<:Astra_x:1141303954555289600> **Es existiert kein Tag mit dem Namen `{name}`. Füge einen mit `/tag hinzufügen <name> <output>`**", ephemeral=True)
                    if result:
                        for eintrag in result:
                            tagname = eintrag[0]
                            tagoutput = eintrag[1]
                            embed.add_field(name=f"Name: `{tagname}`", value=f"**Ausgabe: `{tagoutput}`**", inline=True)
                        await interaction.response.send_message(embed=embed)
                        
                        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(tags(bot))
