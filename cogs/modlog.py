import discord
from discord.ext import commands
import pymysql.err
from discord import app_commands
from typing import Literal
from cogs.tempchannel import PENDING_TEMPCHANNEL_CREATORS

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
        ('Wochen', 604800),
        ('Tage', 86400),
        ('Stunden', 3600),
        ('Minuten', 60),
        ('Sekunden', 1),
    )

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            result.append(f"{int(value)} {name}")
    return ', '.join(result)


async def is_tempchannel_db(bot: commands.Bot, channel: discord.abc.GuildChannel) -> bool:
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT 1 FROM usertempchannels WHERE guildID = %s AND channelID = %s LIMIT 1",
                (channel.guild.id, channel.id)
            )
            return await cursor.fetchone() is not None


class modlog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        "SELECT channelID FROM modlog WHERE serverID = (%s)",
                        (after.guild.id,)
                    )
                except pymysql.err.OperationalError as e:
                    print(f"MySQL Fehler: {e}")
                    return

                result = await cursor.fetchone()
                if result is None:
                    return

                channel2 = result
                guild = before.guild
                channel = guild.get_channel(int(channel2[0]))

                if before.display_name != after.display_name:
                    embed = discord.Embed(
                        title="📝 Mitgliedsupdate",
                        description="Nickname geändert",
                        colour=discord.Colour.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(name="Vorher", value=before.display_name, inline=True)
                    embed.add_field(name="Nachher", value=after.display_name, inline=True)
                    await channel.send(embed=embed)

                elif before.avatar != after.avatar:
                    embed = discord.Embed(
                        title="🖼️ Mitgliedsupdate",
                        description="Avatar geändert (unten neuer Avatar)",
                        colour=discord.Colour.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_thumbnail(url=before.avatar)
                    embed.set_image(url=after.avatar)
                    await channel.send(embed=embed)

                elif len(before.roles) > len(after.roles):
                    role = next(role for role in before.roles if role not in after.roles)

                    async for entry in guild.audit_logs(
                        action=discord.AuditLogAction.member_role_update,
                        limit=1
                    ):
                        embed = discord.Embed(
                            title="➖ Mitgliedsupdate",
                            description=f"Rolle entfernt von {entry.user.mention}",
                            colour=discord.Colour.orange(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.add_field(name="Mitglied", value=before.mention, inline=True)
                        embed.add_field(name="Entfernte Rolle", value=role.mention, inline=True)
                        await channel.send(embed=embed)

                elif len(after.roles) > len(before.roles):
                    role = next(role for role in after.roles if role not in before.roles)

                    async for entry in guild.audit_logs(
                        action=discord.AuditLogAction.member_role_update,
                        limit=1
                    ):
                        embed = discord.Embed(
                            title="➕ Mitgliedsupdate",
                            description=f"Rolle hinzugefügt von {entry.user.mention}",
                            colour=discord.Colour.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.add_field(name="Mitglied", value=before.mention, inline=True)
                        embed.add_field(name="Hinzugefügte Rolle", value=role.mention, inline=True)
                        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):

        # 1️⃣ RACE-SCHUTZ (Tempchannel gerade im Erstellen)
        async for entry in channel.guild.audit_logs(
                action=discord.AuditLogAction.channel_create,
                limit=1
        ):
            if entry.user and entry.user.id in PENDING_TEMPCHANNEL_CREATORS:
                return

        # 2️⃣ PERSISTENTER CHECK (nach Restart)
        if await is_tempchannel_db(self.bot, channel):
            return

        # 3️⃣ Modlog-Channel holen
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = %s",
                    (channel.guild.id,)
                )
                result = await cursor.fetchone()
                if not result:
                    return

        # 4️⃣ Tickets ignorieren
        if channel.name.startswith("ticket-"):
            return

        log_channel = channel.guild.get_channel(int(result[0]))
        if not log_channel:
            return

        # 5️⃣ Embed senden
        embed = discord.Embed(
            title="📁 Kanal erstellt",
            description=f"Kanal erstellt von {entry.user.mention}",
            colour=discord.Colour.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Kanalname", value=channel.name, inline=True)
        embed.add_field(name="Kategorie", value=channel.category, inline=True)

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):

        # Tempchannels NIE loggen
        if await is_tempchannel_db(self.bot, channel):
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = %s",
                    (channel.guild.id,)
                )
                result = await cursor.fetchone()
                if not result:
                    return

        if channel.name.startswith("ticket-"):
            return

        log_channel = channel.guild.get_channel(int(result[0]))
        if not log_channel:
            return

        async for entry in channel.guild.audit_logs(
                action=discord.AuditLogAction.channel_delete,
                limit=1
        ):
            embed = discord.Embed(
                title="🗑️ Kanal gelöscht",
                description=f"Kanal gelöscht von {entry.user.mention}",
                colour=discord.Colour.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Kanalname", value=channel.name, inline=True)
            embed.add_field(name="Kategorie", value=channel.category, inline=True)

            await log_channel.send(embed=embed)
            break

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):

        # Tempchannels NIE loggen
        if await is_tempchannel_db(self.bot, channel):
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = %s",
                    (channel.guild.id,)
                )
                result = await cursor.fetchone()
                if not result:
                    return

        if channel.name.startswith("ticket-"):
            return

        log_channel = channel.guild.get_channel(int(result[0]))
        if not log_channel:
            return

        async for entry in channel.guild.audit_logs(
                action=discord.AuditLogAction.channel_delete,
                limit=1
        ):
            embed = discord.Embed(
                title="🗑️ Kanal gelöscht",
                description=f"Kanal gelöscht von {entry.user.mention}",
                colour=discord.Colour.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Kanalname", value=channel.name, inline=True)
            embed.add_field(name="Kategorie", value=channel.category, inline=True)

            await log_channel.send(embed=embed)
            break

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = (%s)",
                    (role.guild.id,)
                )
                result = await cursor.fetchone()
                if result is None:
                    return

                channel2 = result
                guild = role.guild
                channel = guild.get_channel(int(channel2[0]))

                async for entry in guild.audit_logs(
                    action=discord.AuditLogAction.role_create,
                    limit=1
                ):
                    embed = discord.Embed(
                        title="➕ Rolle erstellt",
                        description=f"Rolle erstellt von {entry.user.mention}",
                        colour=discord.Colour.green(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(name="Rollenname", value=role.name, inline=True)
                    embed.add_field(name="Rollenfarbe", value=role.colour, inline=True)
                    await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = (%s)",
                    (role.guild.id,)
                )
                result = await cursor.fetchone()
                if result is None:
                    return

                channel2 = result
                guild = role.guild
                channel = guild.get_channel(int(channel2[0]))

                async for entry in guild.audit_logs(
                    action=discord.AuditLogAction.role_create,
                    limit=1
                ):
                    embed = discord.Embed(
                        title="❌ Rolle gelöscht",
                        description=f"Rolle gelöscht von {entry.user.mention}",
                        colour=discord.Colour.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(name="Rollenname", value=role.name, inline=True)
                    embed.add_field(name="Rollenfarbe", value=role.color, inline=True)
                    await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.guild is None or after.author.bot:
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = (%s)",
                    (after.guild.id,)
                )
                result = await cursor.fetchone()
                if result is None:
                    return

                channel = after.guild.get_channel(int(result[0]))

                if before.content != after.content:
                    embed = discord.Embed(
                        title="✏️ Nachricht bearbeitet",
                        description=f"Nachricht bearbeitet von {after.author.mention}",
                        colour=discord.Colour.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(name="Vorher", value=before.content or "Leer", inline=True)
                    embed.add_field(name="Nachher", value=after.content or "Leer", inline=True)
                    await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None or message.author.bot:
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT word FROM blacklist WHERE serverID = (%s)",
                    (message.guild.id,)
                )
                result2 = await cursor.fetchall()
                if not result2:
                    return

                for eintrag2 in result2:
                    if eintrag2[0].lower() in message.content.lower():
                        return

                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = (%s)",
                    (message.guild.id,)
                )
                result = await cursor.fetchone()
                if result is None:
                    return

                channel2 = result
                guild = message.guild
                channel = guild.get_channel(int(channel2[0]))

                embed = discord.Embed(
                    title="🗑️ Nachricht gelöscht",
                    description=f"Nachricht gelöscht von {message.author.mention}",
                    colour=discord.Colour.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Inhalt", value=message.content, inline=True)
                embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
                await channel.send(embed=embed)

    @app_commands.command(
        name="modlog",
        description="Modlog für deinen Server einrichten, anzeigen oder entfernen."
    )
    @app_commands.describe(
        argument="Aktion: Hinzufügen, Löschen oder Anzeigen",
        channel="Kanal für Modlog-Einträge (nur bei Hinzufügen erforderlich)"
    )
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_guild=True)
    async def modlog(
        self,
        interaction: discord.Interaction,
        argument: Literal["Hinzufügen", "Löschen", "Anzeigen"],
        channel: discord.TextChannel = None
    ):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if argument == "Hinzufügen":
                    await cursor.execute(
                        "SELECT channelID FROM modlog WHERE serverID = (%s)",
                        (interaction.guild.id,)
                    )
                    server2 = await cursor.fetchone()

                    await cursor.execute(
                        "SELECT serverID FROM modlog WHERE channelID = (%s)",
                        (channel.id,)
                    )
                    channel2 = await cursor.fetchone()

                    if server2 is None and channel2 is None:
                        await cursor.execute(
                            "INSERT INTO modlog (serverID, channelID) VALUES (%s, %s)",
                            (interaction.guild.id, channel.id)
                        )

                        embed1 = discord.Embed(
                            title="✅ Modlog aktiviert",
                            description=f"Das Modlog wird ab sofort in {channel.mention} geführt.",
                            color=discord.Color.blue()
                        )
                        await interaction.response.send_message(embed=embed1)

                    else:
                        try:
                            ch = interaction.guild.get_channel(int(server2[0]))
                        except:
                            return

                        embed = discord.Embed(
                            title="ℹ️ Modlog bereits aktiv",
                            description="Um den Modlog zu ändern, nutze erneut `/modlog`.",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Aktueller Kanal", value=ch, inline=False)
                        await interaction.response.send_message(embed=embed)

                elif argument == "Löschen":
                    await cursor.execute(
                        "SELECT channelID FROM modlog WHERE serverID = (%s)",
                        (interaction.guild.id,)
                    )
                    result = await cursor.fetchone()

                    if result is None:
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> Das Modlog-System wurde gelöscht.",
                            ephemeral=True
                        )

                    if result is not None:
                        channelID = result
                        if (channel.id,) == channelID:
                            await cursor.execute(
                                "DELETE FROM modlog WHERE channelID = (%s) AND serverID = (%s)",
                                (channel.id, interaction.guild.id)
                            )
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> Das Modlog-System wurde gelöscht.",
                                ephemeral=True
                            )
                        else:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> Der Modlog ist bereits deaktiviert.",
                                ephemeral=True
                            )
                            return

                elif argument == "Anzeigen":
                    await cursor.execute(
                        "SELECT channelID FROM modlog WHERE serverID = (%s)",
                        (interaction.guild.id,)
                    )
                    result = await cursor.fetchone()

                    if not result:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> Der Modlog ist derzeit deaktiviert.",
                            ephemeral=True
                        )

                    if result:
                        channelID = result[0]
                        guild = interaction.guild
                        channelid = guild.get_channel(channelID)

                        await interaction.response.send_message(
                            f"📋 Der Modlog-Kanal ist aktuell {channelid.mention}",
                            ephemeral=True
                        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(modlog(bot))
