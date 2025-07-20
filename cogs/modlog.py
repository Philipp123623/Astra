import discord
from discord.ext import commands
import pymysql.err
from discord import app_commands
from typing import Literal


##########
def convert(time):
    pos = ["s", "m", "h", "d"]
    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24}
    unit = time[-1]
    if unit not in pos:
        return -1
    try:
        val = int(time[:-1])
    except:
        return -2
    return val * time_dict[unit]


async def timeline(seconds):
    result = []
    intervals = (
        ('Weeks', 604800),
        ('Days', 86400),
        ('Hours', 3600),
        ('Minutes', 60),
        ('Seconds', 1),
    )

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(int(value), name))
    return ', '.join(result)


class modlog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute("SELECT channelID FROM modlog WHERE serverID = (%s)", (after.guild.id,))
                except pymysql.err.OperationalError as e:
                    print(f"MySQL Fehler: {e}")
                    return  # oder fallback Verhalten
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    channel2 = result
                    guild = before.guild
                    channel = guild.get_channel(int(channel2[0]))
                    if before.display_name != after.display_name:
                        embed = discord.Embed(title="Member Update", description="Nickname Change",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                        fields = [("Before", before.display_name, True),
                                  ("After", after.display_name, True)]

                        for name, value, inline in fields:
                            embed.add_field(name=name, value=value, inline=inline)
                        await channel.send(embed=embed)
                    elif before.avatar != after.avatar:
                        embed = discord.Embed(title="Member Update", description="Avatar Change (below image is new!)",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                        embed.set_thumbnail(url=before.avatar)
                        embed.set_image(url=after.avatar)

                        await channel.send(embed=embed)
                    elif len(before.roles) > len(after.roles):
                        role = next(role for role in before.roles if role not in after.roles)

                        async for entry in guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):

                            embed = discord.Embed(title="Member Update", description=f"Role Removed by {entry.user.mention}",
                                                  colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                            fields = [("Member", before.mention, True),
                                      ("Removed Role", role.mention, True)]

                            for name, value, inline in fields:
                                embed.add_field(name=name, value=value, inline=inline)
                            await channel.send(embed=embed)

                    elif len(after.roles) > len(before.roles):
                        role = next(role for role in after.roles if role not in before.roles)
                        async for entry in guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):

                            embed = discord.Embed(title="Member Update", description=f"Role Added by {entry.user.mention}",
                                                  colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                            fields = [("Member", before.mention, True),
                                      ("Added Role", role.mention, True)]

                            for name, value, inline in fields:
                                embed.add_field(name=name, value=value, inline=inline)
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channelname):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (channelname.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    if "ticket-" in channelname.name:
                        return
                    else:
                        channel2 = result
                        guild = channelname.guild
                        channel = guild.get_channel(int(channel2[0]))
                        async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):

                            embed = discord.Embed(title="Channel Created",
                                                  description=f"Channel Created by {entry.user.mention}",
                                                  colour=discord.Colour.green(), timestamp=discord.utils.utcnow())

                            fields = [("Channel Name", channelname.name, True),
                                      ("Channel Category", channelname.category, True)]

                            for name, value, inline in fields:
                                embed.add_field(name=name, value=value, inline=inline)
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channelname):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (channelname.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    if "ticket-" in channelname.name:
                        return
                    else:
                        channel2 = result
                        guild = channelname.guild
                        channel = guild.get_channel(int(channel2[0]))
                        async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):

                            embed = discord.Embed(title="Channel Deleted",
                                                  description=f"Channel Deleted by {entry.user.mention}",
                                                  colour=discord.Colour.red(), timestamp=discord.utils.utcnow())

                            fields = [("Channel Name", channelname.name, True),
                                      ("Channel Category", channelname.category, True)]

                            for name, value, inline in fields:
                                embed.add_field(name=name, value=value, inline=inline)
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (before.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    channel2 = result
                    guild = before.guild
                    channel = guild.get_channel(int(channel2[0]))
                    if before.name != after.name:
                        async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_update, limit=1):
                            embed = discord.Embed(title="Channel Update",
                                                  description=f"Channel Updated by {entry.user.mention}",
                                                  colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                            fields = [("Before:", before.name, True),
                                      ("After:", after.name, True)]

                            for name, value, inline in fields:
                                embed.add_field(name=name, value=value, inline=inline)
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (member.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    channel2 = result
                    guild = member.guild
                    channel = guild.get_channel(int(channel2[0]))
                    if before.channel is None:
                        embed = discord.Embed(title="Channel Joined",
                                              description=f"Channel Joined by {member.mention}",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                        fields = [("Channel", after.channel, True)]

                        for name, value, inline in fields:
                            embed.add_field(name=name, value=value, inline=inline)
                        await channel.send(embed=embed)
                    if after.channel is None:
                        embed = discord.Embed(title="Channel Left",
                                              description=f"Channel Left by {member.mention}",
                                              colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                        fields = [("Channel", before.channel, True)]

                        for name, value, inline in fields:
                            embed.add_field(name=name, value=value, inline=inline)
                        await channel.send(embed=embed)
                    if before.channel and after.channel:
                        if before.channel != after.channel:
                            embed = discord.Embed(title="Channel Switched",
                                                  description=f"Channel switched by {member.mention}",
                                                  colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                            fields = [("Before", before.channel, True),
                                      ("After", after.channel, True)]

                            for name, value, inline in fields:
                                embed.add_field(name=name, value=value, inline=inline)
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (role.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    channel2 = result
                    guild = role.guild
                    channel = guild.get_channel(int(channel2[0]))
                    async for entry in guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
                        embed = discord.Embed(title="Role Created",
                                              description=f"Role created by {entry.user.mention}",
                                              colour=discord.Colour.green(), timestamp=discord.utils.utcnow())

                        fields = [("Role Name", role.name, True),
                                  ("Role Color", role.colour, True)]

                        for name, value, inline in fields:
                            embed.add_field(name=name, value=value, inline=inline)
                        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (role.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    channel2 = result
                    guild = role.guild
                    channel = guild.get_channel(int(channel2[0]))
                    async for entry in guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
                        embed = discord.Embed(title="Role Delted",
                                              description=f"Role deleted by {entry.user.mention}",
                                              colour=discord.Colour.red(), timestamp=discord.utils.utcnow())

                        fields = [("Role Name", role.name, True),
                                  ("Role Color", role.color, True)]

                        for name, value, inline in fields:
                            embed.add_field(name=name, value=value, inline=inline)
                        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.author.bot:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (after.guild.id))
                    result = await cursor.fetchone()
                    if result is None:
                        return
                    if result is not None:
                        channel2 = result
                        guild = before.guild
                        channel = guild.get_channel(int(channel2[0]))

                        if before.content != after.content:
                            embed = discord.Embed(title="Message Update",
                                                  description=f"Message edited by {after.author.mention}",
                                                  colour=discord.Colour.blue(), timestamp=discord.utils.utcnow())

                            fields = [("Before", before.content, True),
                                      ("After", after.content, True)]

                            for name, value, inline in fields:
                                embed.add_field(name=name, value=value, inline=inline)
                            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.author.bot:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT word FROM blacklist WHERE serverID = (%s)", (message.guild.id))
                    result2 = await cursor.fetchall()
                    if not result2:
                        return
                    if result2:
                        for eintrag2 in result2:
                            word = eintrag2[0]
                            lowerword = word.lower()
                            lowercontent = message.content.lower()
                            if lowerword in lowercontent:
                                return
                    await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (message.guild.id))
                    result = await cursor.fetchone()
                    if result is None:
                        return
                    if result is not None:
                        if message.author.bot:
                            return
                        channel2 = result
                        guild = message.guild
                        channel = guild.get_channel(int(channel2[0]))

                        embed = discord.Embed(title="Message Deleted",
                                              description=f"Message deleted by {message.author.mention}",
                                              colour=discord.Colour.red(), timestamp=discord.utils.utcnow())

                        fields = [("Content", message.content, True),
                                  ("Channel", message.channel.mention, True)]

                        for name, value, inline in fields:
                            embed.add_field(name=name, value=value, inline=inline)
                        await channel.send(embed=embed)

    @app_commands.command(name="modlog")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def modlog(self, interaction: discord.Interaction,
                     argument: Literal['Add', 'Delete', 'Show'],
                     channel: discord.TextChannel = None):
        """Setup a Modlog for your Server!"""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if argument == "Add":
                    await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (interaction.guild.id))
                    server2 = await cursor.fetchone()
                    await cursor.execute(f"SELECT serverID FROM modlog WHERE channelID = (%s)", (channel.id))
                    channel2 = await cursor.fetchone()
                    if server2 is None and channel2 is None:
                        await cursor.execute("INSERT INTO modlog (serverID, channelID) VALUES (%s, %s)",
                                             (interaction.guild.id, channel.id))

                        embed1 = discord.Embed(title="Setted up a modlog!",
                                               description=f"The modlog will take place in {channel.mention}.",
                                               color=discord.Color.blue())
                        await interaction.response.send_message(embed=embed1)

                    else:
                        try:
                            ch = interaction.guild.get_channel(int(server2[0]))
                        except:
                            return
                        embed = discord.Embed(title="Modlog already enabled",
                                              description=f"To update the Modlog just type `/modlog`",
                                              color=discord.Color.green())
                        embed.add_field(name="Channel", value=ch, inline=False)
                        await interaction.response.send_message(embed=embed)
                elif argument == "Delete":
                    await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (interaction.guild.id))
                    result = await cursor.fetchone()
                    if result is None:
                        await interaction.response.send_message("`✅` Modlog System got deleted", ephemeral=True)
                    if result is not None:
                        channelID = result
                        if (channel.id,) == channelID:
                            await cursor.execute(
                                f"DELETE FROM modlog WHERE channelID = (%s) AND serverID = (%s)",
                                (channel.id, interaction.guild.id))
                            await interaction.response.send_message("`✅` Modlog System got deleted", ephemeral=True)
                        else:
                            await interaction.response.send_message("`❌` You need to Setup Modlog first!", ephemeral=True)
                            return
                elif argument == "Show":
                    await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (interaction.guild.id))
                    result = await cursor.fetchone()
                    if not result:
                        await interaction.response.send_message("`❌` The modlog is currently disabled", ephemeral=True)
                    if result:
                        channelID = result[0]
                        guild = interaction.guild
                        channelid = guild.get_channel(channelID)
                        
                        await interaction.response.send_message(f"`✅` The modlog takes place in {channelid.mention}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(modlog(bot))
