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

    # ---------- AVATAR (links & oben gleich, rechts & unten +1px) ----------
    async with aiohttp.ClientSession() as session:
        async with session.get(member.display_avatar.url) as resp:
            avatar_bytes = await resp.read()

    avatar_size = 304  # +1px rechts & unten
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((avatar_size, avatar_size))

    mask = Image.new("L", (avatar_size, avatar_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
    avatar.putalpha(mask)

    # Position bleibt unverändert
    base.paste(avatar, (29, 31), avatar)

    # ---------- FONTS ----------
    font_title = ImageFont.truetype(FONT_PATH, 30)
    font_desc = ImageFont.truetype(FONT_PATH, 22)
    font_count = ImageFont.truetype(FONT_PATH, 30)

    guild_name = strip_emojis(member.guild.name)
    subtitle = strip_emojis(subtitle) if subtitle else ""

    # ---------- DESCRIPTION BOX (EXAKT MITTIG) ----------
    DESC_X = 400
    DESC_Y = 135
    DESC_WIDTH = 588
    DESC_HEIGHT = 160
    LINE_HEIGHT = 26

    title_text = f"Willkommen auf {guild_name}"
    title_width = draw.textlength(title_text, font=font_title)

    lines = wrap_text(draw, subtitle, font_desc, DESC_WIDTH)
    max_lines = (DESC_HEIGHT // LINE_HEIGHT) - 1
    lines = lines[:max_lines]

    total_height = LINE_HEIGHT + len(lines) * LINE_HEIGHT
    start_y = DESC_Y + (DESC_HEIGHT - total_height) // 2

    # Titel zentriert
    draw.text(
        (DESC_X + (DESC_WIDTH - title_width) // 2, start_y),
        title_text,
        font=font_title,
        fill=(255, 255, 255)
    )

    # Beschreibung zentriert
    for i, line in enumerate(lines):
        line_width = draw.textlength(line, font=font_desc)
        draw.text(
            (
                DESC_X + (DESC_WIDTH - line_width) // 2,
                start_y + LINE_HEIGHT + i * LINE_HEIGHT
            ),
            line,
            font=font_desc,
            fill=(220, 220, 220)
        )

    # ---------- MEMBERCOUNT ----------
    count_text = f"#{member.guild.member_count}"
    count_width = draw.textlength(count_text, font=font_count)

    COUNT_X = 832 + ((158 - count_width) // 2)
    COUNT_Y = 63

    draw.text(
        (COUNT_X, COUNT_Y),
        count_text,
        font=font_count,
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
