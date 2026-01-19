import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import random
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import io
import re

WELCOME_BANNER_PATH = "cogs/assets/Welcomecards/Willkommens_banner_fullsize.jpg"
FONT_PATH = "cogs/fonts/Poppins-SemiBold.ttf"


# ================== UTILS ==================

def random_color():
    return discord.Color.from_rgb(
        random.randint(1, 255),
        random.randint(1, 255),
        random.randint(1, 255)
    )


def strip_emojis(text: str) -> str:
    return re.sub(r"[^\x00-\x7F]+", "", text)


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = current + (" " if current else "") + word
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


# ================== BANNER GENERATOR ==================

async def generate_banner(member: discord.Member, subtitle: str | None) -> io.BytesIO:
    base = Image.open(WELCOME_BANNER_PATH).convert("RGBA")
    draw = ImageDraw.Draw(base)

    # ---------- AVATAR (EXAKT NACH DEINEN MESSWERTEN) ----------
    async with aiohttp.ClientSession() as session:
        async with session.get(member.display_avatar.url) as resp:
            avatar_bytes = await resp.read()

    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((303, 303))

    mask = Image.new("L", (303, 303), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 303, 303), fill=255)
    avatar.putalpha(mask)

    # Position: (29, 31)
    base.paste(avatar, (29, 31), avatar)

    # ---------- FONTS ----------
    font_title = ImageFont.truetype(FONT_PATH, 38)
    font_name = ImageFont.truetype(FONT_PATH, 30)
    font_desc = ImageFont.truetype(FONT_PATH, 22)

    guild_name = strip_emojis(member.guild.name)
    username = strip_emojis(member.display_name)
    subtitle = strip_emojis(subtitle) if subtitle else None

    # ---------- TITEL ----------
    draw.text((400, 95), "Willkommen", font=font_title, fill=(255, 255, 255))
    draw.text((400, 135), f"Willkommen auf {guild_name}", font=font_name, fill=(230, 230, 230))

    # ---------- DESCRIPTION BOX ----------
    DESC_X = 400
    DESC_Y = 165
    DESC_WIDTH = 588
    DESC_HEIGHT = 160
    LINE_HEIGHT = 26
    MAX_LINES = DESC_HEIGHT // LINE_HEIGHT

    if subtitle:
        lines = wrap_text(draw, subtitle, font_desc, DESC_WIDTH)[:MAX_LINES]
        for i, line in enumerate(lines):
            draw.text(
                (DESC_X, DESC_Y + i * LINE_HEIGHT),
                line,
                font=font_desc,
                fill=(200, 200, 200)
            )

    # ---------- MEMBERCOUNT BOX ----------
    count_text = f"#{member.guild.member_count}"
    text_width = draw.textlength(count_text, font=font_name)

    COUNT_X = 832 + ((158 - text_width) // 2)
    COUNT_Y = 63

    draw.text(
        (COUNT_X, COUNT_Y),
        count_text,
        font=font_name,
        fill=(255, 255, 255)
    )

    out = io.BytesIO()
    base.save(out, format="PNG")
    out.seek(0)
    return out


# ================== MODALS ==================

class EmbedModal(discord.ui.Modal, title="Set Embed Welcome Message"):

    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    text = discord.ui.TextInput(
        label="Embed Text",
        style=discord.TextStyle.long,
        placeholder="%mention Willkommen auf %guild!",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO welcome (guildID, channelID, message, mode)
                    VALUES (%s,%s,%s,'embed')
                    ON DUPLICATE KEY UPDATE
                        channelID=VALUES(channelID),
                        message=VALUES(message),
                        mode='embed'
                    """,
                    (interaction.guild.id, self.channel.id, self.text.value)
                )

        await interaction.response.send_message("✅ Embed Welcome gesetzt.", ephemeral=True)


class BannerModal(discord.ui.Modal, title="Banner Welcome konfigurieren"):

    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    subtitle = discord.ui.TextInput(
        label="Beschreibung (passt garantiert ins Banner)",
        style=discord.TextStyle.short,
        placeholder="Schön, dass du da bist!",
        max_length=120,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        subtitle_text = self.subtitle.value.strip() if self.subtitle.value else None

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO welcome (guildID, channelID, message, mode)
                    VALUES (%s,%s,%s,'banner')
                    ON DUPLICATE KEY UPDATE
                        channelID=VALUES(channelID),
                        message=VALUES(message),
                        mode='banner'
                    """,
                    (interaction.guild.id, self.channel.id, subtitle_text)
                )

        await interaction.response.send_message("✅ Banner Welcome aktiviert.", ephemeral=True)


# ================== COG ==================

class welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID, message, mode FROM welcome WHERE guildID=%s",
                    (member.guild.id,)
                )
                data = await cursor.fetchone()

        if not data:
            return

        channel_id, message, mode = data
        channel = member.guild.get_channel(channel_id)
        if not channel:
            return

        if mode == "banner":
            card = await generate_banner(member, message)
            await channel.send(file=discord.File(card, "welcome.png"))

        elif mode == "embed":
            text = (
                message
                .replace("%member", str(member))
                .replace("%name", member.display_name)
                .replace("%mention", member.mention)
                .replace("%guild", member.guild.name)
                .replace("%usercount", str(member.guild.member_count))
            )
            embed = discord.Embed(description=text, color=random_color())
            await channel.send(embed=embed)

    @app_commands.command(name="testjoin", description="Teste die Welcome Nachricht")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def testjoin(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID, message, mode FROM welcome WHERE guildID=%s",
                    (interaction.guild.id,)
                )
                data = await cursor.fetchone()

        if not data:
            await interaction.response.send_message("❌ Kein Welcome aktiv.", ephemeral=True)
            return

        channel_id, message, mode = data
        channel = interaction.guild.get_channel(channel_id)
        member = interaction.user

        if mode == "banner":
            card = await generate_banner(member, message)
            await channel.send(file=discord.File(card, "welcome.png"))
            await interaction.response.send_message(
                f"✅ Test-Banner gesendet in {channel.mention}",
                ephemeral=True
            )

        elif mode == "embed":
            text = (
                message
                .replace("%member", str(member))
                .replace("%name", member.display_name)
                .replace("%mention", member.mention)
                .replace("%guild", member.guild.name)
                .replace("%usercount", str(member.guild.member_count))
            )
            embed = discord.Embed(description=text, color=random_color())
            embed.set_footer(text=f"Testjoin von {member}")
            await channel.send(embed=embed)
            await interaction.response.send_message(
                f"✅ Test-Embed gesendet in {channel.mention}",
                ephemeral=True
            )

    @app_commands.command(name="joinmsg")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def joinmsg(
        self,
        interaction: discord.Interaction,
        argument: Literal["Einschalten", "Ausschalten", "Anzeigen"],
        channel: discord.TextChannel = None,
        mode: Literal["banner", "embed"] = "embed"
    ):
        if argument == "Einschalten":
            if not channel:
                await interaction.response.send_message("❌ Kanal fehlt.", ephemeral=True)
                return

            if mode == "embed":
                await interaction.response.send_modal(EmbedModal(self.bot, channel))
            else:
                await interaction.response.send_modal(BannerModal(self.bot, channel))

        elif argument == "Ausschalten":
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM welcome WHERE guildID=%s",
                        (interaction.guild.id,)
                    )
            await interaction.response.send_message("✅ Welcome deaktiviert.", ephemeral=True)

        elif argument == "Anzeigen":
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT channelID, message, mode FROM welcome WHERE guildID=%s",
                        (interaction.guild.id,)
                    )
                    data = await cursor.fetchone()

            if not data:
                await interaction.response.send_message("❌ Kein Welcome aktiv.", ephemeral=True)
                return

            ch = interaction.guild.get_channel(data[0])
            await interaction.response.send_message(
                f"📢 Kanal: {ch.mention}\n🎨 Modus: **{data[2]}**",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(welcome(bot))
