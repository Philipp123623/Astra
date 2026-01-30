import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import time


##########


class capslock(commands.Cog):
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
                if msg.author.id == msg.guild.owner.id:
                    return
                await cursor.execute("SELECT percent FROM capslock WHERE guildID = (%s)", (msg.guild.id))
                result = await cursor.fetchone()
                if not result:
                    return
                if result:
                    percent1 = result[0]
                    upper = 0
                    for char in msg.content:
                        if char.isupper():
                            pass
                        else:
                            upper += 1
                    multiplication = 100 / len(msg.content)
                    procent = (len(msg.content) - upper) * multiplication
                    if len(msg.content) < 6:
                        return
                    if int(percent1) < round(procent):
                        channel = self.bot.get_channel(msg.channel.id)
                        message = await channel.fetch_message(msg.id)
                        embed = discord.Embed(title="Bitte unterlasse übermäßige Caps!",
                                              description=f"Die Nachricht hatte `{round(procent)}%` Caps!\nDu wurdest verwarnt {msg.author.mention}!",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                        embed.set_author(name=msg.author, icon_url=msg.author.avatar)
                        embed.add_field(name=f"User: {msg.author}", value=f"Nachricht: {msg.content}")
                        embed.set_footer(text=f"User: {msg.author} | ID: {msg.author.id}")
                        await msg.channel.send(embed=embed)
                        await message.delete()
                        await cursor.execute("SELECT reason FROM warns WHERE userID = (%s) AND guildID = (%s)",
                                             (msg.author.id, msg.guild.id))
                        result2 = await cursor.fetchall()
                        if result2 == ():
                            reason = f"{msg.author.name} überschritt das Caps Limit von `{int(percent1)}%`. Die Nachricht hatte `{round(procent)}%` Caps!"
                            await cursor.execute(
                                "INSERT INTO warns (guildID, userID, reason, warnID) VALUES (%s, %s, %s, %s)",
                                (msg.guild.id, msg.author.id, reason, 1))
                            await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)",
                                                 (msg.guild.id))
                            result3 = await cursor.fetchone()
                            if result3 is None:
                                return
                            if result3 is not None:
                                channel = msg.guild.get_channel(int(result3[0]))
                                embed = discord.Embed(colour=discord.Colour.orange(),
                                                      description=f"Der User {msg.author} (`{msg.author.id}`) wurde verwarnt.")
                                embed.add_field(name=f"👤 User:", value=f"{msg.author.mention}", inline=False)
                                embed.add_field(name=f"👮 Moderator:",
                                                value=f"{self.bot.user} (`{self.bot.user.id}`)",
                                                inline=False)
                                embed.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                                embed.set_author(name=msg.author, icon_url=msg.author.avatar)
                                await channel.send(embed=embed)
                        else:
                            reason = f"{msg.author.name} überschritt das Caps Limit von `{int(percent1)}%`. Die Nachricht hatte `{round(procent)}%` Caps!"
                            await cursor.execute(
                                f"INSERT INTO warns (guildID, userID, reason, warnID) VALUES (%s, %s, %s, %s)",
                                (msg.guild.id, msg.author.id, reason, len(result2) + 1))
                            await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)",
                                                 (msg.guild.id))
                            result4 = await cursor.fetchone()
                            if result4 is None:
                                return
                            if result4 is not None:
                                channel = msg.guild.get_channel(int(result4[0]))
                                embed = discord.Embed(colour=discord.Colour.orange(),
                                                      description=f"Der User {msg.author} (`{msg.author.id}`) wurde verwarnt.")
                                embed.add_field(name=f"👤 User:", value=f"{msg.author.mention}", inline=False)
                                embed.add_field(name=f"👮 Moderator:",
                                                value=f"{self.bot.user} (`{self.bot.user.id}`)",
                                                inline=False)
                                embed.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                                embed.set_author(name=msg.author, icon_url=msg.author.avatar)
                                await channel.send(embed=embed)

    @app_commands.command(name="capslock")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.describe(argument="Soll der capslock check an oder aus sein?", percent="Bei wie viel % Capslock, soll eine Action passieren?")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def capslock(self, interaction: discord.Interaction,
                       argument: Literal['Einschalten', 'Ausschalten'],
                       percent: Literal['10', '20', '30', '40', '50', '60', '70', '80', '90', '100'] = None):
        """Richte den Capslock ein."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if argument == "Einschalten":
                    await cursor.execute("INSERT INTO capslock (guildID, percent) VALUES (%s, %s)",
                                         (interaction.guild.id, percent))
                    embed = discord.Embed(title="Der Caps Filter wurde aktiviert",
                                          description=f"Der Caps Filter ist nun aktiv für diesen Server!\nJede Nachricht mit mnehr als `{percent}%` wird gelöscht und der User gewarnt",
                                          colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    await interaction.response.send_message(embed=embed)
                if argument == "Ausschalten":
                    try:
                        await cursor.execute("DELETE FROM capslock WHERE guildID = (%s)",
                                             (interaction.guild.id))
                        embed = discord.Embed(title="Der Caps Filter wurde deaktiviert",
                                              description="Der Caps Filter ist nun nicht mehr aktiv für diesen Server!",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    except:
                        pass
                    await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(capslock(bot))