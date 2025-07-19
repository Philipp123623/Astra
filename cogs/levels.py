import discord
from discord.ext import commands
from discord import app_commands, File
from discord.app_commands import Group
from datetime import datetime
import random
from typing import Literal
import math
import asyncio
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO


##########


class levelsystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cd_mapping = commands.CooldownMapping.from_cooldown(1, 3, commands.BucketType.guild)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return
        if msg.author.bot:
            return
        else:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    bucket = self.cd_mapping.get_bucket(msg)
                    retry_after = bucket.update_rate_limit()
                    if retry_after:
                        return
                    else:
                        await cur.execute(
                            f"SELECT user_xp, user_level FROM levelsystem WHERE client_id = (%s) AND guild_id = (%s)",
                            (msg.author.id, msg.guild.id))
                        result = await cur.fetchall()

                        await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (msg.guild.id))
                        enabled = await cur.fetchone()
                        if len(result) == 0:
                            await cur.execute(
                                f"INSERT INTO levelsystem (client_id, user_xp, user_level, guild_id, enabled) VALUES (%s, %s, %s, %s, %s)",
                                (msg.author.id, 2, 0, msg.guild.id, 0))
                        else:
                            if enabled[0] == 0:
                                return
                            if enabled[0] == 1:
                                xp_start = int(result[0][0])
                                lvl_start = int(result[0][1])
                                xp_end = 5.5 * (lvl_start ** 2) + 30 * lvl_start
                                await cur.execute("SELECT xp FROM levelxp WHERE guildID = (%s)", (msg.guild.id))
                                xpres = await cur.fetchone()
                                if not xpres:
                                    newxp = random.randint(1, 5)
                                if xpres:
                                    newxp = random.randint(1, 5) * 2

                                await cur.execute(
                                    "UPDATE levelsystem SET user_xp = (%s) WHERE client_id = (%s) AND guild_id = (%s)",
                                    (result[0][0] + newxp, msg.author.id, msg.guild.id))
                                if xp_end >= 58000.0 and lvl_start >= 100 and xp_start >= 58000.0:
                                    return
                                if xp_end <= 58000.0 and lvl_start <= 100 and xp_start <= 58000.0:
                                    if xp_end < (xp_start + newxp):
                                        await cur.execute(
                                            "UPDATE levelsystem SET user_level = (%s) WHERE client_id = (%s) AND guild_id = (%s)",
                                            (int(lvl_start) + 1, msg.author.id, msg.guild.id))
                                        await cur.execute(
                                            "UPDATE levelsystem SET user_xp = (%s) WHERE client_id = (%s) AND guild_id = (%s)",
                                            (0 + 1, msg.author.id, msg.guild.id))
                                        await cur.execute("SELECT type FROM levelchannel WHERE guildID = (%s)",
                                                          (msg.guild.id))
                                        result6 = await cur.fetchone()
                                        if not result6:
                                            await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                              (msg.guild.id))
                                            messageres = await cur.fetchone()
                                            if messageres is None:
                                                await cur.execute(
                                                    "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                    (msg.guild.id, int(lvl_start) + 1))
                                                result8 = await cur.fetchone()
                                                if result8:
                                                    roleid = result8[0]
                                                    role = msg.guild.get_role(roleid)
                                                    member = msg.author
                                                    if role in member.roles:
                                                        pass
                                                    else:
                                                        await member.add_roles(role)
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1}",
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                                if not result8:
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                            if messageres is not None:
                                                await cur.execute(
                                                    "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                    (msg.guild.id, int(lvl_start) + 1))
                                                result5 = await cur.fetchone()
                                                lvl = int(lvl_start + 1)
                                                finalmsg = messageres[0].replace("%member",
                                                                                 str(msg.author.mention)).replace(
                                                    "%level", (str(lvl)))
                                                if result5:
                                                    roleid = result5[0]
                                                    role = msg.guild.get_role(roleid)
                                                    member = msg.author
                                                    if role in member.roles:
                                                        pass
                                                    else:
                                                        await member.add_roles(role)
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=finalmsg,
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                                if not result5:
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=finalmsg,
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                        if result6:
                                            if result6[0] == str("Private Message"):
                                                await cur.execute(
                                                    "SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                    (msg.guild.id))
                                                messageres = await cur.fetchone()
                                                if messageres is None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result11 = await cur.fetchone()
                                                    if result11:
                                                        roleid = result11[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                                    if not result11:
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                                if messageres is not None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result10 = await cur.fetchone()
                                                    lvl = int(lvl_start + 1)
                                                    finalmsg = messageres[0].replace("%member",
                                                                                     str(msg.author.mention)).replace(
                                                        "%level", (str(lvl)))
                                                    if result10:
                                                        roleid = result10[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                                    if not result10:
                                                        lvl = int(lvl_start + 1)
                                                        finalmsg = messageres[0].replace("%member",
                                                                                         str(msg.author.mention)).replace(
                                                            "%level", (str(lvl)))
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                            if result6[0] == str("Deactivated"):
                                                await cur.execute(
                                                    "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                    (msg.guild.id, int(lvl_start) + 1))
                                                result12 = await cur.fetchone()
                                                if result12:
                                                    roleid = result12[0]
                                                    role = msg.guild.get_role(roleid)
                                                    member = msg.author
                                                    if role in member.roles:
                                                        pass
                                                    else:
                                                        await member.add_roles(role)
                                                if not result12:
                                                    pass
                                            if result6[0] == str("Last Channel"):
                                                await cur.execute(
                                                    "SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                    (msg.guild.id))
                                                messageres = await cur.fetchone()
                                                if messageres is None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result15 = await cur.fetchone()
                                                    if result15:
                                                        roleid = result15[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                                    if not result15:
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                                if messageres is not None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result14 = await cur.fetchone()
                                                    lvl = int(lvl_start + 1)
                                                    finalmsg = messageres[0].replace("%member",
                                                                                     str(msg.author.mention)).replace(
                                                        "%level", (str(lvl)))
                                                    if result14 is not None:
                                                        roleid = result14[0]
                                                        role = msg.guild.get_role(roleid)
                                                        lvl = int(lvl_start + 1)
                                                        finalmsg = messageres[0].replace("%member",
                                                                                         str(msg.author.mention)).replace(
                                                            "%level", (str(lvl)))
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                                    if result14 is None:
                                                        embed = discord.Embed(title="Level-UP", description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                            if result6[0].isnumeric():
                                                await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                                  (msg.guild.id))
                                                messageres = await cur.fetchone()
    
                                                if messageres is None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result9 = await cur.fetchone()
                                                    if result9:
                                                        roleid = result9[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await channel.send(msg.author.mention, embed=embed)
                                                    if not result9:
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await channel.send(msg.author.mention, embed=embed)
                                                if messageres is not None:
                                                    lvl = int(lvl_start + 1)
                                                    finalmsg = messageres[0].replace("%member",
                                                                                     str(msg.author.mention)).replace(
                                                        "%level", (str(lvl)))
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result5 = await cur.fetchone()
                                                    if result5:
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        roleid = result5[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
    
                                                        await channel.send(msg.author.mention, embed=embed)
                                                    if not result5:
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await channel.send(msg.author.mention, embed=embed)

    level = app_commands.Group(name='levelsystem', description="Astra")

    @level.command(name="rank", description="Sendet deine Levelcard.")
    @app_commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def rank(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT enabled FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,))
                enabled = await cur.fetchone()
                if not enabled or enabled[0] == 0:
                    return await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server deaktiviert.**",
                        ephemeral=True
                    )

                await cur.execute("SELECT user_xp, user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                                  (user.id, interaction.guild.id))
                result = await cur.fetchone()
                if not result:
                    return await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Keine Einträge für diesen User gefunden.**", ephemeral=True
                    )

                await interaction.response.defer(thinking=True)

                xp_start, lvl_start = result
                xp_end = 5.5 * (lvl_start ** 2) + 30 * lvl_start

                # --- Bild und Zeichner laden
                background = Image.open("cogs/Levelcard_Astra.png").convert("RGBA")
                draw = ImageDraw.Draw(background)

                # --- Fonts laden (achte auf den richtigen Pfad und Dateinamen der Schriftart!)
                font_username = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=34)
                font_rank = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=53)
                font_level = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=38)
                font_xp = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=30)

                # --- Avatar laden und einfügen
                avatar_asset = user.display_avatar.replace(size=256)
                avatar_bytes = await avatar_asset.read()
                avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((138, 138))

                mask = Image.new("L", (138, 138), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, 138, 138), fill=255)

                background.paste(avatar, (64, 100), mask)

                # ✅ Umrandung zeichnen (leicht größer als Avatar)
                draw.ellipse((64, 100, 64 + 138, 100 + 138), outline="white", width=6)

                # --- Username zeichnen (fest positioniert)
                draw.text((246, 95), str(user), font=font_username, fill="white")

                # --- Rank (Platzierung) abrufen
                await cur.execute(
                    "SELECT client_id FROM levelsystem WHERE guild_id = (%s) ORDER BY user_level DESC, user_xp DESC",
                    (interaction.guild.id,))
                result2 = await cur.fetchall()
                rank = 0
                if result2:
                    for x in result2:
                        rank += 1
                        if int(x[0]) == user.id:
                            break

                # --- Rank (#Platz) zeichnen
                draw.text((393, 157), f"#{rank}", font=font_rank, fill="white")

                # LEVEL – vertikal & horizontal zentriert
                level_text = f"{lvl_start}"
                level_bbox = font_level.getbbox(level_text)
                level_width = draw.textlength(level_text, font=font_level)
                level_height = level_bbox[3] - level_bbox[1]
                draw.text((931 - level_width // 2, 95 - level_height // 2), level_text, font=font_level, fill="white")

                # XP – vertikal & horizontal zentriert
                percent = int((xp_start / xp_end) * 100)
                xp_text = f"{xp_start}/{round(xp_end)}"
                xp_bbox = font_xp.getbbox(xp_text)
                xp_width = draw.textlength(xp_text, font=font_xp)
                xp_height = xp_bbox[3] - xp_bbox[1]
                draw.text((931 - xp_width // 2, 223 - xp_height // 2), xp_text, font=font_xp, fill="white")

                # --- Progressbar zeichnen (wenn XP > 5)
                if xp_start > 5:
                    xp_percentage = (xp_start / xp_end)
                    bar_full_width = 675
                    bar_width = int(bar_full_width * xp_percentage)
                    # Füllung
                    draw.rounded_rectangle((209, 276, 209 + bar_width, 276 + 36), radius=6, fill="#54bbbd")

                # --- Bild speichern und senden
                buffer = BytesIO()
                background.save(buffer, format="PNG")
                buffer.seek(0)

                file = File(fp=buffer, filename="card.png")
                await interaction.followup.send(file=file)

    @level.command(name="status")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction, arg: Literal['Einschalten', 'Ausschalten']):
        """Lege einen Kanal fest, in den die Level Up Nachrichten gesendet werden."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if arg == "Ausschalten":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                            ephemeral=True)
                        return
                    if enabled[0] == 1:
                        await cur.execute(f"UPDATE levelsystem SET enabled = 0 WHERE guild_id = (%s)",
                                          (interaction.guild.id))
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> **Das Levelsystem ist jetzt auf diesem Server deaktiviert.**")
                        return
                if arg == "Einschalten":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await cur.execute(f"UPDATE levelsystem SET enabled = 1 WHERE guild_id = (%s)",
                                          (interaction.guild.id))
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> **Das Levelsystem ist jetzt auf diesem Server aktiviert.**")
                        return
                    if enabled[0] == 1:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                            ephemeral=True)
                        return

    @level.command(name="levelupkanal")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def levelsystem_setchannel(self, interaction: discord.Interaction, arg: Literal[
        'Kanal des Levelups', 'Bestimmter Kanal(Kanalangabe benötigt)', 'Private Nachricht', 'Deaktivieren'],
                                     channel: discord.TextChannel = None):
        """Set a channel for your levelmessages."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                await cur.execute("SELECT type FROM levelchannel WHERE guildID = (%s)", (interaction.guild.id))
                result = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                            ephemeral=True)
                    return
                if enabled[0] == 1:
                    if arg == "Kanal des Levelups":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Last Channel"))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Last Channel", interaction.guild.id))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                    if arg == "Bestimmter Kanal(Kanalangabe benötigt)":
                        if not result:
                            try:
                                await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                                  (interaction.guild.id, channel.id))
                                await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                            except:
                                await interaction.response.send_message(
                                    f"<:Astra_x:1141303954555289600> **Du musst einen Kanel angeben.**", ephemeral=True)
                                return
                        if result:
                            try:
                                await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                                  (channel.id, interaction.guild.id))
                                await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                            except:
                                await interaction.response.send_message(
                                    f"<:Astra_x:1141303954555289600> **Du musst einen Kanal angeben.**", ephemeral=True)
                                return
                    if arg == "Private Nachricht":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Private Message"))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Private Message", interaction.guild.id))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                    if arg == "Deaktivieren":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Deactivated"))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der Level-Up-Kanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Deactivated", interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich zurückgesetzt.**")

    @level.command(name="levelupnachricht")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def levelsystem_setmessage(self, interaction: discord.Interaction,
                                     arg: Literal['Custom Nachricht', 'Deaktivieren'], message: str = None):
        """Custom levelmessage: Use %level for the level and %member as member mention."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                            ephemeral=True)
                    return
                if enabled[0] == 1:
                    if arg == "Custom Nachricht":
                        await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await cur.execute("INSERT INTO levelmsg(message, guildID) VALUES(%s, %s)",
                                              (message, interaction.guild.id))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelmsg SET message = (%s) WHERE guildID = (%s)",
                                              (message, interaction.guild.id))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich geändert.**")

                    if arg == "Deaktivieren":
                        await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich zurückgesetzt.**")
                            return
                        if result:
                            await cur.execute("DELETE FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich zurückgesetzt.**")

    @level.command(name="role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def levelsystem_role_add(self, interaction: discord.Interaction, modus: Literal['Hinzufügen', 'Entfernen', 'Anzeigen'], level: int, role: discord.Role):
        """Füge/Entferne Rollen die man ab dem jeweiligem Level bekommt."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if modus == "Hinzufügen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                                ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            "SELECT guildID FROM levelroles WHERE levelreq = (%s) and roleID = (%s) and guildID = (%s)",
                            (level, role.id, interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await cur.execute("INSERT INTO levelroles(guildID, roleID, levelreq) VALUES(%s, %s, %s)",
                                              (interaction.guild.id, role.id, level))
                            await interaction.response.send_message(
                                f"<:Astra_accept:1141303821176422460> **User bekommen nun die Rolle {role.mention} wenn sie Level `{level}` erreichen**")
                        if result:
                            roleid = result[0]
                            roleobj = interaction.guild.get_role(roleid)

                            await interaction.response.send_message(
                                f"<:Astra_x:1141303954555289600> **Die Rolle {roleobj.mention} ist bereits für dieses Level aktiv**.", ephemeral=True)
                
                if modus == "Entfernen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        if enabled[0] == 0:
                        	await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                                ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            "SELECT guildID FROM levelroles WHERE roleID = (%s) and levelreq = (%s) and guildID = (%s)",
                            (role.id, level, interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await interaction.response.send_message(f"<:Astra_x:1141303954555289600> **Es sind keine Rollen für das Level `{level}` aktiv.**",
                                                                    ephemeral=True)
                        if result:
                            await cur.execute(
                                "DELETE FROM levelroles WHERE levelreq = (%s) and roleID = (%s) and guildID = (%s)",
                                (level, role.id, interaction.guild.id))

                            await interaction.response.send_message(
                                f"<:Astra_accept:1141303821176422460> **Rolle `{role.name}` von Level `{level}` entfernt.**")
                            
                if modus == "Anzeigen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                                ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute("SELECT roleID, levelreq FROM levelroles WHERE guildID = (%s)",
                                          (interaction.guild.id))
                        result = await cur.fetchall()
                        if result == ():
                            await interaction.response.send_message("<:Astra_x:1141303954555289600> **Es sind Keine Level-UP-Rollen aktiv.**",
                                                                    ephemeral=True)
                        if result:
                            embed = discord.Embed(title="Aktive Level-UP-Rollen",
                                                  description=f"Um Rollen zu entfernen nutze `/levelsystem role`",
                                                  color=discord.Color.blue())
                            for x in result:
                                roleid = x[0]
                                level = x[1]
                                try:
                                    role = interaction.guild.get_role(int(roleid))
                                except:
                                    await interaction.response.send_message("<:Astra_x:1141303954555289600> **Es sind Keine Level-UP-Rollen aktiv.**",
                                                                    ephemeral=True)

                                embed.add_field(name=f"Level: {level}", value=f"Rolle: {role.mention}", inline=True)
                            await interaction.response.send_message(embed=embed)
                            
    @app_commands.command(name="xpboost")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def levelsystem_xpboost(self, interaction: discord.Interaction, status: Literal['Aktivieren(x2)', 'Deaktivieren(x1)']):
        """Aktiviere den XP-Boost für deinen Server."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                                ephemeral=True)
                if enabled[0] == 1:
                    await cur.execute("SELECT xp FROM levelxp WHERE guildID = (%s)", (interaction.guild.id))
                    result = await cur.fetchone()
                    if status == "Aktivieren(x2)":
                        if not result:
                            await cur.execute("INSERT INTO levelxp(guildID, xp) VALUES(%s, %s)",
                                              (interaction.guild.id, 2))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der XP-Boost ist jetzt für diesen Server aktiviert. User bekommen nun 2x XP.**")
                        if result:
                            await interaction.response.send_message("<:Astra_x:1141303954555289600> **Der XP-Boost ist für diesen Server bereits aktiviert.**", ephemeral=True)
                    if status == "Deaktivieren(x1)":
                        if not result:
                            await interaction.response.send_message("<:Astra_x:1141303954555289600> **Der XP-Boost ist für diesen Server bereits deaktiviert.**.", ephemeral=True)
                        if result:
                            await cur.execute("DELETE FROM levelxp WHERE guildID = (%s) and xp = (%s)",
                                              (interaction.guild.id, 2))
                            await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Der XP-Boost ist jetzt für diesen Server deaktiviert. User bekommen nun nichtmehr 2x XP**")

    @app_commands.command(name="setlevel")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def levelsystem_setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int):
        """Set the level from a user on your server."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if level > 100:
                    await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Level kann icht höher als 100 sein.**", ephemeral=True)
                if level <= 100:
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                                                ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            f"SELECT user_xp, user_level FROM levelsystem WHERE client_id = (%s) AND guild_id = (%s)",
                            (member.id, interaction.guild.id))
                        result = await cur.fetchall()
                        if not result:
                            await interaction.response.send_message("<:Astra_x:1141303954555289600> **Keine Einträge für diesen User gefunden.**", ephemeral=True)
                        if result:
                            await cur.execute(
                                "UPDATE levelsystem SET user_level = (%s) WHERE guild_id = (%s) and client_id = (%s)",
                                (level, interaction.guild.id, member.id))
                            await cur.execute(
                                "UPDATE levelsystem SET user_xp = (%s) WHERE guild_id = (%s) and client_id = (%s) and user_level = (%s)",
                                (0 + 1, interaction.guild.id, member.id, level))
                            await interaction.response.send_message(
                                f"<:Astra_accept:1141303821176422460> **Der User {member.mention} wurde auf Level `{level}` gesetzt.**")


async def setup(bot):
    await bot.add_cog(levelsystem(bot))
