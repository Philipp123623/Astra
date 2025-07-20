import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import random


##########

def random_color():
    return discord.Color.from_rgb(random.randint(1, 255), random.randint(1, 255), random.randint(1, 255))


class Modal2(discord.ui.Modal, title="Set your Join message!"):
    def __init__(self, bot: commands.Bot, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel
        self.bot = bot

    name = discord.ui.TextInput(
        label='Text',
        style=discord.TextStyle.long,
        placeholder='%member-Member#0000  | %name-Member  | %mention-@Member | %guild-Severname | %usercount-Memberanzahl',
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute("INSERT INTO welcome (guildID, channelID, msg) VALUES (%s, %s, %s)",
                                         (interaction.guild.id, self.channel.id, self.name.value))

                    embed1 = discord.Embed(title="Willkommens Nachricht wurde gesetzt",
                                           description=f"Die Willkommens Nachricht findet nun in {self.channel.mention} statt.\nNachricht: {self.name.value}.",
                                           color=discord.Color.blue())
                    await interaction.response.send_message(embed=embed1)
                except:
                    await cursor.execute(f"SELECT channelID FROM welcome WHERE guildID = {interaction.guild.id}")
                    wel = await cursor.fetchone()
                    await cursor.execute(f"SELECT msg FROM welcome WHERE guildID = {interaction.guild.id}")
                    come = await cursor.fetchone()

                    try:
                        ch = interaction.guild.get_channel(int(wel[0]))
                    except:
                        return

                    embed = discord.Embed(title="WIllkommens Nachricht",
                                          description=f"Die welcome Message ist bereits aktiv. Um sie zu ändern nutze `/welcome`.",
                                          color=discord.Color.green())
                    embed.add_field(name="Kanal", value=ch, inline=False)
                    embed.add_field(name="Nachricht", value=come[0], inline=False)
                    await interaction.response.send_message(embed=embed)


class welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM welcome WHERE guildID = {member.guild.id}")
                channel = await cursor.fetchone()
                await cursor.execute(f"SELECT msg FROM welcome WHERE guildID = {member.guild.id}")
                message = await cursor.fetchone()
                if channel is None and message is None:
                    return
                else:
                    try:
                        ch = member.guild.get_channel(int(channel[0]))
                    except:
                        return
                    finalmsg = message[0].replace("%member", str(member)).replace("%name", str(member.name)).replace(
                        "%mention", str(member.mention)).replace("%guild", str(member.guild)).replace("%usercount",
                                                                                                      str(member.guild.member_count))
                    embed = discord.Embed(description=finalmsg, color=random_color())
                    try:
                        await ch.send(embed=embed)
                    except:
                        pass
                    return

    @app_commands.command(name="testjoin")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def testjoin(self, interaction: discord.Interaction):
        """Schaue ob deine Joinmsg gut funktioniert."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                member = interaction.user
                await cursor.execute(f"SELECT channelID FROM welcome WHERE guildID = {member.guild.id}")
                channel = await cursor.fetchone()
                await cursor.execute(f"SELECT msg FROM welcome WHERE guildID = {member.guild.id}")
                message = await cursor.fetchone()
                if channel is None and message is None:
                    embed = discord.Embed(
                        description=f"Die Willkommens Nachricht ist auf diesem Server deaktiviert. Füge eine hinzu mit `/joinmsg`.",
                        color=discord.Color.green())
                    await interaction.response.send_message(embed=embed)
                    return
                else:
                    try:
                        ch = interaction.guild.get_channel(int(channel[0]))
                    except:
                        return
                    finalmsg = message[0].replace("%member", str(member)).replace("%name", str(member.name)).replace(
                        "%mention",
                        str(member.mention)).replace(
                        "%guild", str(member.guild)).replace("%usercount", str(member.guild.member_count))
                    embed = discord.Embed(description=finalmsg, color=random_color())
                    embed.set_footer(text=f"Testjoin von {member}")
                    try:
                        await ch.send(embed=embed)
                        await interaction.response.send_message(f"<:Astra_x:1141303954555289600> **Testjoin Nachricht gesendet in {ch.mention}**")
                    except:
                        pass
                    return

    @app_commands.command(name="joinmsg")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def joinmsg(self, interaction: discord.Interaction, argument: Literal[
        'Einschalten', 'Ausschalten', 'Anzeigen'],
                      channel: discord.TextChannel = None):
        """Lege eine Nachricht fest für User, die deinem Server joinen."""
        if argument == "Einschalten":
            await interaction.response.send_modal(Modal2(channel=channel, bot=self.bot))
        if argument == "Ausschalten":
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"SELECT channelID FROM welcome WHERE guildID = {interaction.guild.id}")
                    result = await cursor.fetchone()
                    if result is None:
                        return
                    if result is not None:
                        channelID = result
                        if (channel.id,) == channelID:
                            await cursor.execute(
                                f"DELETE FROM welcome WHERE channelID = {channel.id} AND guildID = {interaction.guild.id}")
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Die Willkommens Nachricht ist nun für diesen Server deaktiviert.**", ephemeral=True)
                        else:
                            await interaction.response.send_message("<:Astra_x:1141303954555289600> **Die Willkommens Nachricht ist bereits für diesen Server deaktiviert.**",
                                                                    ephemeral=True)
                            return
        if argument == "Anzeigen":
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"SELECT channelID FROM welcome WHERE guildID = {interaction.guild.id}")
                    wel = await cursor.fetchone()
                    if not wel:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Die Willkommensnachrichten sind auf diesem Server zurzeit deaktiviert.**", ephemeral=True)
                    if result:
                        await cursor.execute(f"SELECT msg FROM welcome WHERE guildID = {interaction.guild.id}")
                        come = await cursor.fetchone()

                        try:
                            ch = interaction.guild.get_channel(int(wel[0]))
                        except:
                            return

                        embed = discord.Embed(title="Willkommens Nachricht",
                                              description=f"Du kannst sie jederzeit über `/joinsmg` ändern",
                                              color=discord.Color.green())
                        embed.add_field(name="Kanal", value=ch, inline=False)
                        embed.add_field(name="Nachricht", value=come[0], inline=False)
                        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(welcome(bot))
