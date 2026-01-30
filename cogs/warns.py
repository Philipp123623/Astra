import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from typing import Literal
from discord.app_commands import Group


##########

@app_commands.guild_only()
class Automod(app_commands.Group):
    def __init__(self, bot):
        self.bot = bot  # <--- Hinzufügen!
        super().__init__(
            name="automod",
            description="Automod Commands"
        )

    @app_commands.command(name="hinzufügen", description="Richte die Automoderation für deinen Server ein.")
    @app_commands.describe(warns="Anzahl der Verwarnungen, bei der eine Aktion ausgelöst wird.", action="Die auszuführende Aktion bei Erreichen der Verwarnungen.")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add(self, interaction: discord.Interaction, warns: Literal['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'], action: Literal['Kick', 'Ban', 'Timeout']):
        """Richte die Automoderation für deinen Server ein."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if action == "Kick":
                    await cursor.execute("INSERT INTO automod (guildID, warns, action) VALUES (%s, %s, %s)",
                                         (interaction.guild.id, warns, action))
                    embed = discord.Embed(title="Automod Aktion gesetzt",
                                          description=f"Wenn ein User {warns} verwarungen bekommt, wird er gekickt.",
                                          colour=discord.Colour.blue())
                    await interaction.response.send_message(embed=embed)
                if action == "Ban":
                    await cursor.execute("INSERT INTO automod (guildID, warns, action) VALUES (%s, %s, %s)",
                                         (interaction.guild.id, warns, action))
                    embed = discord.Embed(title="Automod Aktion gesetzt",
                                          description=f"Wenn ein User {warns} verwarungen bekommt, wird er gebannt.",
                                          colour=discord.Colour.blue())
                    await interaction.response.send_message(embed=embed)
                if action == "Timeout":
                    await cursor.execute("INSERT INTO automod (guildID, warns, action) VALUES (%s, %s, %s)",
                                         (interaction.guild.id, warns, action))
                    embed = discord.Embed(title="Automod Aktion gesetzt",
                                          description=f"Wenn ein User {warns} verwarungen bekommt, wird er getimeouted.",
                                          colour=discord.Colour.blue())
                    await interaction.response.send_message(embed=embed)

    @app_commands.command(name="entfernen", description="Richte die Automoderation für deinen Server ein.")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove(self, interaction: discord.Interaction, warns: Literal['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']):
        """Richte die Automoderation für deinen Server ein."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM automod WHERE guildID = (%s) and warns = (%s)",
                                     (interaction.guild.id, warns))
                embed1 = discord.Embed(title="Automod entfernt",
                                       description=f"Der Automod wird nicht mehr aktiv, wenn ein User `{warns}` verwarnungen bekommt.",
                                       color=discord.Color.blue())
                await interaction.response.send_message(embed=embed1)

    @app_commands.command(name="anzeigen", description="Richte die Automoderation für deinen Server ein.")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_guild=True)
    async def show(self, interaction: discord.Interaction):
        """Richte die Automoderation für deinen Server ein."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT warns, action FROM automod WHERE guildID = (%s)", interaction.guild.id)
                result = await cursor.fetchall()
                if result == ():
                    await interaction.response.send_message(
                        "*<:Astra_x:1141303954555289600> *Es sind keine Automod Aktionen aktiv.**", ephemeral=True)
                if result:

                    embed = discord.Embed(title="Aktuelle Automod Aktionen",
                                          description=f"Hier ist eine Liste aller Automod Aktionen dieses Servers.",
                                          color=discord.Color.green())

                    for eintrag in result:
                        warns = eintrag[0]
                        action = eintrag[1]

                        embed.add_field(name=f"Verwarnungen: {warns}", value=f"Aktion: {action}", inline=True)

                    await interaction.response.send_message(embed=embed)


class Warn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Warne einen User.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        """Warne einen User."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT reason FROM warns WHERE userID = (%s) AND guildID = (%s)",
                                     (member.id, interaction.guild.id))
                result = await cursor.fetchall()
                if result == ():
                    warnid = 1
                    await cursor.execute("INSERT INTO warns (guildID, userID, reason, warnID) VALUES (%s, %s, %s, %s)",
                                         (interaction.guild.id, member.id, reason, 1))
                    embed = discord.Embed(title="Neue Verwarnung",
                                          description=f"Der User {member.mention} mit der ID: ``{warnid}`` wurd für den Grund: `{reason}` verwarnt.\nUm jemanden zu verwarnen nutze `/warn`.",
                                          color=discord.Color.red())
                    await interaction.response.send_message(embed=embed)
                    await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)",
                                         (interaction.guild.id))
                    modlog = await cursor.fetchone()
                    if modlog is None:
                        return
                    if modlog is not None:
                        channel2 = modlog
                        guild = interaction.guild
                        channel = guild.get_channel(int(channel2[0]))
                        embed = discord.Embed(colour=discord.Colour.orange(),
                                              description=f"Der User {member} (`{member.id}`) wurde verwarnt.")
                        embed.add_field(name=f"👤 Member:", value=f"{member.mention}", inline=False)
                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                        inline=False)
                        embed.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                        embed.set_author(name=member, icon_url=member.avatar)
                        await channel.send(embed=embed)
                    await cursor.execute("SELECT action, warns FROM automod WHERE guildID = (%s)",
                                         (interaction.guild.id))
                    result3 = await cursor.fetchall()
                    print(result3)
                    if result3 == ():
                        return
                    if result3:
                        for eintrag in result3:
                            warns = eintrag[1]
                            action = eintrag[0]
                            print(eintrag[0])
                            print(eintrag[1])
                            await cursor.execute("SELECT max(warnID) FROM warns WHERE guildID = (%s) AND userID = (%s)",
                                                 (interaction.guild.id, member.id))
                            warnings = await cursor.fetchone()
                            warns2 = warnings[0]
                            if int(warns2) == int(warns) or int(warns2) > int(warns):
                                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)",
                                                     (interaction.guild.id))
                                modlog = await cursor.fetchone()
                                if action == "Kick":
                                    if modlog is None:
                                        return
                                    if modlog is not None:
                                        channel2 = modlog
                                        guild = interaction.guild
                                        channel = guild.get_channel(int(channel2[0]))
                                        embed = discord.Embed(colour=discord.Colour.orange(),
                                                              description=f"Der User {member} (`{member.id}`) wurde gekickt.")
                                        embed.add_field(name=f"👤 Member:", value=f"{member.mention}", inline=False)
                                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                                        inline=False)
                                        embed.add_field(name=f"📄 Grund:", value=f"Automod", inline=False)
                                        embed.set_author(name=member, icon_url=member.avatar)
                                        await channel.send(embed=embed)
                                    await member.kick(reason="Automod")
                                if action == "Ban":
                                    if modlog is None:
                                        return
                                    if modlog is not None:
                                        channel2 = modlog
                                        guild = interaction.guild
                                        channel = guild.get_channel(int(channel2[0]))
                                        embed = discord.Embed(colour=discord.Colour.orange(),
                                              description=f"Der User {member} (`{member.id}`) wurde gebannt.")
                                        embed.add_field(name=f"👤 Member:", value=f"{member.mention}", inline=False)
                                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                        inline=False)
                                        embed.add_field(name=f"📄 Grund:", value=f"Automod", inline=False)
                                        embed.set_author(name=member, icon_url=member.avatar)
                                        await channel.send(embed=embed)
                                    await member.ban(reason="Automod")
                                if action == "Timeout":
                                    if modlog is None:
                                        return
                                    if modlog is not None:
                                        channel2 = modlog
                                        guild = interaction.guild
                                        channel = guild.get_channel(int(channel2[0]))
                                        embed = discord.Embed(colour=discord.Colour.orange(),
                                              description=f"Der User {member} (`{member.id}`) wurde getimeouted.")
                                        embed.add_field(name=f"👤 Member:", value=f"{member.mention}", inline=False)
                                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                        inline=False)
                                        embed.add_field(name=f"📄 Grund:", value=f"Automod", inline=False)
                                        embed.set_author(name=member, icon_url=member.avatar)
                                        await channel.send(embed=embed)
                                    await member.timeout(timedelta(hours=5), reason="Automod")

                if result:
                    await cursor.execute(f"INSERT INTO warns (guildID, userID, reason, warnID) VALUES (%s, %s, %s, %s)",
                                         (interaction.guild.id, member.id, reason, len(result) + 1))
                    warnid = len(result) + 1
                    embed2 = discord.Embed(title="Added Warn",
                                           description=f"I successfully warned the user {member.mention} with WarnID: ``{warnid}`` for reason: {reason}\nTo warn someone, just type `/warn`!",
                                           color=discord.Color.red())
                    await interaction.response.send_message(embed=embed2)
                    await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)",
                                         (interaction.guild.id))
                    modlog = await cursor.fetchone()
                    if modlog is None:
                        return
                    if modlog is not None:
                        channel2 = modlog
                        guild = interaction.guild
                        channel = guild.get_channel(int(channel2[0]))
                        embed = discord.Embed(colour=discord.Colour.orange(),
                                              description=f"The user {member} (`{member.id}`) got warned.")
                        embed.add_field(name=f"👤 Member:", value=f"{member.mention}", inline=False)
                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                        inline=False)
                        embed.add_field(name=f"📄 Reason:", value=f"{reason}", inline=False)
                        embed.set_author(name=member, icon_url=member.avatar)
                        await channel.send(embed=embed)

                    await cursor.execute("SELECT action, warns FROM automod WHERE guildID = (%s)",
                                         (interaction.guild.id))
                    result3 = await cursor.fetchall()
                    print(result3)
                    if result3 == ():
                        return
                    if result3:
                        for eintrag in result3:
                            warns = eintrag[1]
                            action = eintrag[0]
                            print(eintrag[0])
                            print(eintrag[1])
                            await cursor.execute("SELECT max(warnID) FROM warns WHERE guildID = (%s) AND userID = (%s)",
                                                 (interaction.guild.id, member.id))
                            warnings = await cursor.fetchone()
                            warns2 = warnings[0]
                            if int(warns2) == int(warns) or int(warns2) > int(warns):
                                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)",
                                                     (interaction.guild.id))
                                modlog = await cursor.fetchone()
                                if action == "Kick":
                                    if modlog is None:
                                        return
                                    if modlog is not None:
                                        channel2 = modlog
                                        guild = interaction.guild
                                        channel = guild.get_channel(int(channel2[0]))
                                        embed = discord.Embed(colour=discord.Colour.orange(),
                                              description=f"Der User {member} (`{member.id}`) wurde gekickt.")
                                        embed.add_field(name=f"👤 Member:", value=f"{member.mention}", inline=False)
                                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                        inline=False)
                                        embed.add_field(name=f"📄 Grund:", value=f"Automod", inline=False)
                                        embed.set_author(name=member, icon_url=member.avatar)
                                        await channel.send(embed=embed)
                                    await member.kick(reason="Automod")
                                if action == "Ban":
                                    if modlog is None:
                                        return
                                    if modlog is not None:
                                        channel2 = modlog
                                        guild = interaction.guild
                                        channel = guild.get_channel(int(channel2[0]))
                                        embed = discord.Embed(colour=discord.Colour.orange(),
                                              description=f"Der User {member} (`{member.id}`) wurde gebannt.")
                                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                        inline=False)
                                        embed.add_field(name=f"📄 Grund:", value=f"Automod", inline=False)
                                        embed.set_author(name=member, icon_url=member.avatar)
                                        await channel.send(embed=embed)
                                    await member.ban(reason="Automod")
                                if action == "Timeout":
                                    if modlog is None:
                                        return
                                    if modlog is not None:
                                        channel2 = modlog
                                        guild = interaction.guild
                                        channel = guild.get_channel(int(channel2[0]))
                                        embed = discord.Embed(colour=discord.Colour.orange(),
                                              description=f"Der User {member} (`{member.id}`) wurde getimeouted.")
                                        embed.add_field(name=f"👤 Member:", value=f"{member.mention}", inline=False)
                                        embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                        inline=False)
                                        embed.add_field(name=f"📄 Grund:", value=f"Automod", inline=False)
                                        embed.set_author(name=member, icon_url=member.avatar)
                                        await channel.send(embed=embed)
                                    await member.timeout(timedelta(seconds=30), reason="Automod")

    @app_commands.command(name="unwarn", description="Entferne Warns von einem User.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member, warnid: int):
        """Entferne Warns von einem User.."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT warnID, userID FROM warns WHERE guildID = (%s)", (interaction.guild.id))
                result = await cursor.fetchall()

                if result:
                    await cursor.execute("DELETE FROM warns WHERE guildID = (%s) AND warnID = (%s) AND userID = (%s)",
                                         (interaction.guild.id, warnid, member.id))
                    embed2 = discord.Embed(title="Verwarnung gelöscht",
                                           description=f"Die Verwarnung des Users {member.mention} mit der ID: ``{warnid}``wurde gelöscht.\nUm jemanden zu warnen nutze `/warn`.",
                                           color=discord.Color.green())
                    await interaction.response.send_message(embed=embed2)
                if not result:
                    embed2 = discord.Embed(title="Keine Aktuellen erwarnungen",
                                           description=f"Es gibt aktuell keine Verwarnungen für den User {member.mention} mit der WarnID: ``{warnid}``!\nUm jemanden zu warnen nutze `/warn`.",
                                           color=discord.Color.green())
                    await interaction.response.send_message(embed=embed2)

    @app_commands.command(name="warns", description="Erhalte eine Liste mit allen Warns eines Users.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warns(self, interaction: discord.Interaction, member: discord.Member):
        """Erhalte eine Liste mit allen Warns eines Users."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT reason, warnID FROM warns WHERE guildID = (%s) AND userID = (%s)",
                                     (interaction.guild.id, member.id))
                result = await cursor.fetchall()
                if result == ():
                    embed2 = discord.Embed(title=f"Verwarnungen für {member.name}, {member.id}",
                                           description=f"Der User {member.name} hat keine Verwarnungen.\nUm jemanden zu warnen nutze `/warn`.",
                                           color=discord.Color.blue())
                    await interaction.response.send_message(embed=embed2)

                else:
                    embed = discord.Embed(title=f"Verwarnungen für {member.name}, {member.id}",
                                          description=f"Um jemanden zu warnen nutze `/warn`.\nUm jemanden eine Verwarnung zu entfernen nutze `/unwarn`.",
                                          color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    for eintrag in result:
                        reason = eintrag[0]
                        warnID = eintrag[1]

                        embed.add_field(name=f"WarnID: {warnID}", value=f"Grund: {reason}",
                                        inline=True)

                    await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Warn(bot))
    bot.tree.add_command(Automod(bot))
