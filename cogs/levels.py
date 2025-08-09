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

from cogs.ticket import Ticket

import os, json

ASSETS_DIR = "cogs/assets/Levelcards"
DEFAULT_STYLE = "standard"   # entspricht standard.png

def list_styles():
    """Liest alle PNGs aus dem Asset-Ordner und gibt die Namen ohne .png zurück."""
    if not os.path.isdir(ASSETS_DIR):
        return []
    styles = []
    for f in os.listdir(ASSETS_DIR):
        if f.lower().endswith(".png"):
            styles.append(os.path.splitext(f)[0])  # ohne .png
    return sorted(styles)

def style_to_path(style_name: str):
    """Case-insensitive zu einer PNG im Asset-Ordner auflösen; Fallback auf default."""
    files = [f for f in os.listdir(ASSETS_DIR) if f.lower().endswith(".png")]
    for f in files:
        if os.path.splitext(f)[0].lower() == style_name.lower():
            return os.path.join(ASSETS_DIR, f)
    # Fallback
    return os.path.join(ASSETS_DIR, f"{DEFAULT_STYLE}.png")

async def style_autocomplete(interaction: discord.Interaction, current: str):
    names = list_styles()
    return [
        app_commands.Choice(name=n, value=n)
        for n in names if current.lower() in n.lower()
    ][:25]



##########
@app_commands.guild_only()
class Level(app_commands.Group):
    def __init__(self, bot):
        self.bot = bot  # <--- Hinzufügen!
        super().__init__(
            name="levelsystem",
            description="Alles rund ums Levelsystem."
        )

    @app_commands.command(name="rank", description="Sendet deine Levelcard.")
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

                await cur.execute(
                    "SELECT user_xp, user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                    (user.id, interaction.guild.id)
                )
                result = await cur.fetchone()
                if not result:
                    return await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Keine Einträge für diesen User gefunden.**", ephemeral=True
                    )

                # --- Style aus DB laden (User → sonst default)
                await cur.execute(
                    "SELECT style FROM levelstyle WHERE guild_id=%s AND client_id=%s",
                    (interaction.guild.id, user.id)
                )
                row = await cur.fetchone()
                style_name = row[0] if row else DEFAULT_STYLE
                bg_path = style_to_path(style_name)

        await interaction.response.defer(thinking=True)

        xp_start, lvl_start = result
        xp_end = 5.5 * (lvl_start ** 2) + 30 * lvl_start

        # --- Bild und Zeichner laden
        background = Image.open(bg_path).convert("RGBA")
        draw = ImageDraw.Draw(background)

        # --- Fonts
        font_username = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=34)
        font_rank = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=53)
        font_level = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=38)
        font_xp = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=30)

        # --- Avatar
        avatar_asset = user.display_avatar.replace(size=256)
        avatar_bytes = await avatar_asset.read()
        avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((138, 138))
        mask = Image.new("L", (138, 138), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 138, 138), fill=255)
        background.paste(avatar, (64, 100), mask)
        draw.ellipse((64, 100, 64 + 138, 100 + 138), outline="white", width=6)

        # --- Username
        draw.text((246, 95), str(user), font=font_username, fill="white")

        # --- Rank (Platzierung)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT client_id FROM levelsystem WHERE guild_id = %s ORDER BY user_level DESC, user_xp DESC",
                    (interaction.guild.id,)
                )
                result2 = await cur.fetchall()
        rank_pos = 0
        if result2:
            for x in result2:
                rank_pos += 1
                if int(x[0]) == user.id:
                    break
        draw.text((393, 157), f"#{rank_pos}", font=font_rank, fill="white")

        # --- Level zentriert
        level_text = f"{lvl_start}"
        level_width = draw.textlength(level_text, font=font_level)
        level_height = font_level.getbbox(level_text)[3] - font_level.getbbox(level_text)[1]
        draw.text((931 - level_width // 2, 95 - level_height // 2), level_text, font=font_level, fill="white")

        # --- XP zentriert
        xp_text = f"{xp_start}/{round(xp_end)}"
        xp_width = draw.textlength(xp_text, font=font_xp)
        xp_height = font_xp.getbbox(xp_text)[3] - font_xp.getbbox(xp_text)[1]
        draw.text((931 - xp_width // 2, 223 - xp_height // 2), xp_text, font=font_xp, fill="white")

        # --- Progressbar
        if xp_start > 5:
            xp_percentage = (xp_start / xp_end) if xp_end > 0 else 0
            bar_full_width = 675
            bar_width = int(bar_full_width * max(0.0, min(1.0, xp_percentage)))
            draw.rounded_rectangle((209, 276, 209 + bar_width, 276 + 36), radius=6, fill="#54bbbd")

        # --- Bild senden
        buffer = BytesIO()
        background.save(buffer, format="PNG")
        buffer.seek(0)
        file = File(fp=buffer, filename=f"rank_{style_name}.png")
        await interaction.followup.send(file=file)

    # Autocomplete-Helfer (zeigt alle PNG-Namen ohne .png)
    async def _style_autocomplete(self, interaction: discord.Interaction, current: str):
        names = list_styles()
        return [
                   app_commands.Choice(name=n, value=n)
                   for n in names if current.lower() in n.lower()
               ][:25]

    @app_commands.command(name="setstyle", description="Wähle deine Rank-Card (Name = Dateiname ohne .png).")
    @app_commands.describe(style="Style-Name (z. B. standard, Halloween_stripes, türkis_stripes)")
    @app_commands.autocomplete(style=_style_autocomplete)
    async def setstyle(self, interaction: discord.Interaction, style: str):
        names = list_styles()
        if not names:
            return await interaction.response.send_message(
                "❌ Es sind aktuell keine Styles im Ordner vorhanden.",
                ephemeral=True
            )
        if style not in names:
            return await interaction.response.send_message(
                f"❌ Unbekannter Style `{style}`.\nVerfügbar: {', '.join(names)}",
                ephemeral=True
            )

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Speichere den Style pro User & Guild (Upsert)
                await cur.execute(
                    """
                    INSERT INTO levelstyle (guild_id, client_id, style)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE style = VALUES(style)
                    """,
                    (interaction.guild.id, interaction.user.id, style)
                )

        await interaction.response.send_message(
            f"✅ Dein Rank-Card-Style wurde auf **{style}** gesetzt.",
            ephemeral=True
        )

    @app_commands.command(name="previewstyle",
                          description="Zeig dir deine Rankcard mit einem Style an (ohne zu speichern).")
    @app_commands.describe(style="Style-Name (Dateiname ohne .png)")
    @app_commands.autocomplete(style=style_autocomplete)
    async def previewstyle(self, interaction: discord.Interaction, style: str):
        names = list_styles()
        if style not in names:
            return await interaction.response.send_message(
                f"❌ Unbekannter Style `{style}`. Verfügbar: {', '.join(names) or '—'}",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True, ephemeral=True)
        bg_path = style_to_path(style)

        # Hier nutzen wir dieselbe Render-Logik wie bei /rank – nur ohne DB-Style-Lookup
        # (Level/XP des aufrufenden Users nehmen)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT user_xp, user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                    (interaction.user.id, interaction.guild.id)
                )
                res = await cur.fetchone()

        xp_start, lvl_start = res if res else (0, 0)
        xp_end = 5.5 * (lvl_start ** 2) + 30 * lvl_start

        background = Image.open(bg_path).convert("RGBA")
        draw = ImageDraw.Draw(background)
        font_username = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=34)
        font_rank = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=53)
        font_level = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=38)
        font_xp = ImageFont.truetype("cogs/fonts/Poppins-SemiBold.ttf", size=30)

        avatar_asset = interaction.user.display_avatar.replace(size=256)
        avatar_bytes = await avatar_asset.read()
        avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((138, 138))
        mask = Image.new("L", (138, 138), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 138, 138), fill=255)
        background.paste(avatar, (64, 100), mask)
        draw.ellipse((64, 100, 64 + 138, 100 + 138), outline="white", width=6)

        draw.text((246, 95), str(interaction.user), font=font_username, fill="white")
        draw.text((393, 157), f"#—", font=font_rank, fill="white")  # Rang lassen wir in Preview offen

        level_text = f"{lvl_start}"
        lw = draw.textlength(level_text, font=font_level)
        lh = font_level.getbbox(level_text)[3] - font_level.getbbox(level_text)[1]
        draw.text((931 - lw // 2, 95 - lh // 2), level_text, font=font_level, fill="white")

        xp_text = f"{xp_start}/{round(xp_end)}"
        xw = draw.textlength(xp_text, font=font_xp)
        xh = font_xp.getbbox(xp_text)[3] - font_xp.getbbox(xp_text)[1]
        draw.text((931 - xw // 2, 223 - xh // 2), xp_text, font=font_xp, fill="white")

        if xp_start > 5 and xp_end > 0:
            perc = max(0.0, min(1.0, xp_start / xp_end))
            bar_full_width = 675
            bar_width = int(bar_full_width * perc)
            draw.rounded_rectangle((209, 276, 209 + bar_width, 276 + 36), radius=6, fill="#54bbbd")

        buffer = BytesIO()
        background.save(buffer, "PNG")
        buffer.seek(0)
        await interaction.followup.send(
            content=f"**Preview:** `{style}`",
            file=File(buffer, filename=f"preview_{style}.png"),
            ephemeral=True
        )

    @app_commands.command(name="status")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction, arg: Literal['Einschalten', 'Ausschalten']):
        """Lege einen Kanal fest, in den die Level Up Nachrichten gesendet werden."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if arg == "Ausschalten":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
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
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                        return

    @app_commands.command(name="leaderboard", description="Zeigt das Top 10 Level und XP Leaderboard an.")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT client_id, user_level, user_xp FROM levelsystem WHERE guild_id = %s ORDER BY user_level DESC, user_xp DESC LIMIT 10",
                    (interaction.guild.id,)
                )
                top10 = await cur.fetchall()

        if not top10:
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> Es wurden keine Daten für dieses Server-Leaderboard gefunden.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"Top 10 Level Leaderboard für {interaction.guild.name}",
            color=discord.Color.blue()
        )

        description = ""
        place = 1
        for user_id, level, xp in top10:
            user = interaction.guild.get_member(user_id)
            name = user.display_name if user else f"User ID: {user_id}"
            description += f"**#{place}**: {name} — Level {level} ({xp} XP)\n"
            place += 1

        embed.description = description
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="levelupkanal")
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
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                        ephemeral=True)
                    return
                if enabled[0] == 1:
                    if arg == "Kanal des Levelups":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Last Channel"))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Last Channel", interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                    if arg == "Bestimmter Kanal(Kanalangabe benötigt)":
                        if not result:
                            try:
                                await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                                  (interaction.guild.id, channel.id))
                                await interaction.response.send_message(
                                    "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                            except:
                                await interaction.response.send_message(
                                    f"<:Astra_x:1141303954555289600> **Du musst einen Kanel angeben.**", ephemeral=True)
                                return
                        if result:
                            try:
                                await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                                  (channel.id, interaction.guild.id))
                                await interaction.response.send_message(
                                    "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                            except:
                                await interaction.response.send_message(
                                    f"<:Astra_x:1141303954555289600> **Du musst einen Kanal angeben.**", ephemeral=True)
                                return
                    if arg == "Private Nachricht":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Private Message"))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Private Message", interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                    if arg == "Deaktivieren":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Deactivated"))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Level-Up-Kanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Deactivated", interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich zurückgesetzt.**")

    @app_commands.command(name="levelupnachricht")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def levelsystem_setmessage(self, interaction: discord.Interaction,
                                     arg: Literal['Custom Nachricht', 'Deaktivieren'], message: str = None):
        """Custom levelmessage: Use %level for the level and %member as member mention."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                        ephemeral=True)
                    return
                if enabled[0] == 1:
                    if arg == "Custom Nachricht":
                        await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await cur.execute("INSERT INTO levelmsg(message, guildID) VALUES(%s, %s)",
                                              (message, interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelmsg SET message = (%s) WHERE guildID = (%s)",
                                              (message, interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich geändert.**")

                    if arg == "Deaktivieren":
                        await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich zurückgesetzt.**")
                            return
                        if result:
                            await cur.execute("DELETE FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich zurückgesetzt.**")

    @app_commands.command(name="role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def levelsystem_role_add(self, interaction: discord.Interaction,
                                   modus: Literal['Hinzufügen', 'Entfernen', 'Anzeigen'], level: int,
                                   role: discord.Role):
        """Füge/Entferne Rollen die man ab dem jeweiligem Level bekommt."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if modus == "Hinzufügen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
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
                                f"<:Astra_x:1141303954555289600> **Die Rolle {roleobj.mention} ist bereits für dieses Level aktiv**.",
                                ephemeral=True)

                if modus == "Entfernen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        if enabled[0] == 0:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            "SELECT guildID FROM levelroles WHERE roleID = (%s) and levelreq = (%s) and guildID = (%s)",
                            (role.id, level, interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await interaction.response.send_message(
                                f"<:Astra_x:1141303954555289600> **Es sind keine Rollen für das Level `{level}` aktiv.**",
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
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute("SELECT roleID, levelreq FROM levelroles WHERE guildID = (%s)",
                                          (interaction.guild.id))
                        result = await cur.fetchall()
                        if result == ():
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Es sind Keine Level-UP-Rollen aktiv.**",
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
                                    await interaction.response.send_message(
                                        "<:Astra_x:1141303954555289600> **Es sind Keine Level-UP-Rollen aktiv.**",
                                        ephemeral=True)

                                embed.add_field(name=f"Level: {level}", value=f"Rolle: {role.mention}", inline=True)
                            await interaction.response.send_message(embed=embed)


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

                                        # --- CommunityGoal: Levelup-Progress inkrementieren ---
                                        cog = self.bot.get_cog("CommunityGoalsCog")
                                        if cog:
                                            await cog.count_levelup(msg.guild.id)

                                        await cur.execute("SELECT type FROM levelchannel WHERE guildID = (%s)",
                                                          (msg.guild.id,))
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

    @app_commands.command(name="xpboost")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def levelsystem_xpboost(self, interaction: discord.Interaction,
                                  status: Literal['Aktivieren(x2)', 'Deaktivieren(x1)']):
        """Aktiviere den XP-Boost für deinen Server."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                        ephemeral=True)
                if enabled[0] == 1:
                    await cur.execute("SELECT xp FROM levelxp WHERE guildID = (%s)", (interaction.guild.id))
                    result = await cur.fetchone()
                    if status == "Aktivieren(x2)":
                        if not result:
                            await cur.execute("INSERT INTO levelxp(guildID, xp) VALUES(%s, %s)",
                                              (interaction.guild.id, 2))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der XP-Boost ist jetzt für diesen Server aktiviert. User bekommen nun 2x XP.**")
                        if result:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Der XP-Boost ist für diesen Server bereits aktiviert.**",
                                ephemeral=True)
                    if status == "Deaktivieren(x1)":
                        if not result:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Der XP-Boost ist für diesen Server bereits deaktiviert.**.",
                                ephemeral=True)
                        if result:
                            await cur.execute("DELETE FROM levelxp WHERE guildID = (%s) and xp = (%s)",
                                              (interaction.guild.id, 2))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der XP-Boost ist jetzt für diesen Server deaktiviert. User bekommen nun nichtmehr 2x XP**")

    @app_commands.command(name="setlevel")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def levelsystem_setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int):
        """Set the level from a user on your server."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if level > 100:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Level kann icht höher als 100 sein.**",
                        ephemeral=True)
                if level <= 100:
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)",
                                      (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            f"SELECT user_xp, user_level FROM levelsystem WHERE client_id = (%s) AND guild_id = (%s)",
                            (member.id, interaction.guild.id))
                        result = await cur.fetchall()
                        if not result:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Keine Einträge für diesen User gefunden.**",
                                ephemeral=True)
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
    bot.tree.add_command(Level(bot))
