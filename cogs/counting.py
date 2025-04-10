import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import asyncio


##########


class counter(commands.Cog):
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
                await cursor.execute("SELECT channelID FROM counter WHERE guildID = (%s)", (msg.guild.id))
                result = await cursor.fetchone()
                if not result:
                    return
                else:
                    channelid = result[0]
                    await cursor.execute(f"SELECT number FROM counter WHERE channelID = {channelid}")
                    result2 = await cursor.fetchone()
                    number = result2[0]
                    if msg.channel.id == channelid:
                        if str(number) == msg.content:
                            await cursor.execute(f"SELECT lastuserID FROM counter WHERE channelID = {channelid}")
                            result2 = await cursor.fetchone()
                            if not result2:
                                await cursor.execute("INSERT INTO counter (lastuserID) VALUES (%s)", (msg.author.id))
                            if result2[0] == msg.author.id:
                                if msg.author.bot:
                                    return
                                if not msg.author.bot:
                                    alone = await msg.channel.fetch_message(msg.id)
                                    await alone.delete()
                                    msg = await msg.channel.send(
                                        f"<:Astra_x:1141303954555289600> Du kannst nicht alleine Spielen, lass auch mal jemand anderem den Vorrang! {msg.author.mention}")
                                    await asyncio.sleep(5)
                                    await msg.delete()
                                    return
                            if result2[0] != msg.author.id:
                                number2 = int(number + 1)
                                await cursor.execute(f"UPDATE counter SET number = (%s) WHERE guildID = (%s)", (number2, msg.guild.id))
                                await cursor.execute(f"UPDATE counter SET lastuserID = (%s) WHERE guildID = (%s)", (msg.author.id, msg.guild.id))

                                channel2 = msg.channel
                                message = await channel2.fetch_message(msg.id)
                                won = self.bot.get_emoji(1141319026140790885)
                                await message.add_reaction(won)
                        if str(number) != msg.content:
                            wrong = await msg.channel.fetch_message(msg.id)
                            await wrong.delete()
                            msg2 = await msg.channel.send(f"<:Astra_x:1141303954555289600> Falsch! Versuchs nochmal. {msg.author.mention}")
                            await asyncio.sleep(5)
                            await msg2.delete()
                            return

    @app_commands.command(name="counting")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(argument="Argument", channel="Textchannel")
    async def counting(self, interaction: discord.Interaction, argument: Literal['Einschalten', 'Ausschalten'], channel: discord.TextChannel):
        """Richte den Zählkanal ein."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if argument == "Einschalten":
                    await cursor.execute("SELECT channelID FROM counter WHERE guildID = (%s)", interaction.guild.id)
                    result = await cursor.fetchone()
                    if result:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Counting Minispiel ist bereits für diesen Server aktiviert.**")
                    if not result:
                        number = 1
                        await cursor.execute("INSERT INTO counter (guildID, channelID, number) VALUES (%s, %s, %s)",
                                             (interaction.guild.id, channel.id, number))
                        embed = discord.Embed(title="Counting Spiel wurde aktiviert",
                                              description="Das Counting Spiel wurde für diesen Channel aktiviert!",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                        embed.add_field(name="Channel:", value=channel.mention)
                        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                if argument == "Ausschalten":
                    await cursor.execute("SELECT channelID FROM counter WHERE guildID = (%s)", interaction.guild.id)
                    result = await cursor.fetchone()
                    if not result:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Counting Minispiel ist für diesen Server bereits deaktiviert.**")
                    if result:
                        await cursor.execute("DELETE FROM counter WHERE guildID = (%s)", interaction.guild.id)
                        embed = discord.Embed(title="Counting Spiel wurde deaktiviert",
                                              description="Das Counting Spiel wurde für diesen Channel deaktiviert!",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())
                        embed.add_field(name="Channel:", value=channel.mention)
                        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(counter(bot))