import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import random
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import io

WELCOME_BANNER_PATH = "cogs/assets/Welcomecards/Willkommens_banner_fullsize.jpg"
FONT_PATH = "cogs/fonts/Poppins-SemiBold.ttf"


def random_color():
    return discord.Color.from_rgb(
        random.randint(1, 255),
        random.randint(1, 255),
        random.randint(1, 255)
    )


# ================== BANNER GENERATOR ==================

async def generate_banner(member: discord.Member) -> io.BytesIO:
    base = Image.open(WELCOME_BANNER_PATH).convert("RGBA")
    draw = ImageDraw.Draw(base)

    async with aiohttp.ClientSession() as session:
        async with session.get(member.display_avatar.url) as resp:
            avatar_bytes = await resp.read()

    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((260, 260))
    mask = Image.new("L", avatar.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 260, 260), fill=255)
    avatar.putalpha(mask)
    base.paste(avatar, (60, 50), avatar)

    font_big = ImageFont.truetype(FONT_PATH, 38)
    font_small = ImageFont.truetype(FONT_PATH, 28)

    draw.text(
        (360, 135),
        f"Willkommen auf {member.guild.name}",
        font=font_big,
        fill=(255, 255, 255)
    )

    draw.text(
        (360, 185),
        f"{member.name}#{member.discriminator}",
        font=font_small,
        fill=(220, 220, 220)
    )

    draw.text(
        (820, 40),
        f"#{member.guild.member_count}",
        font=font_small,
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
        label="Text",
        style=discord.TextStyle.long,
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


class BannerModal(discord.ui.Modal, title="Banner Welcome aktivieren"):

    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO welcome (guildID, channelID, mode)
                    VALUES (%s,%s,'banner')
                    ON DUPLICATE KEY UPDATE
                    channelID=VALUES(channelID),
                    mode='banner'
                    """,
                    (interaction.guild.id, self.channel.id)
                )

        await interaction.response.send_message("✅ Banner Welcome aktiviert.", ephemeral=True)


# ================== COG ==================

class welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ---------- MEMBER JOIN ----------

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
            card = await generate_banner(member)
            await channel.send(file=discord.File(card, "welcome.png"))

        elif mode == "embed":
            text = (
                message
                .replace("%member", str(member))
                .replace("%mention", member.mention)
                .replace("%guild", member.guild.name)
                .replace("%usercount", str(member.guild.member_count))
            )
            embed = discord.Embed(description=text, color=random_color())
            await channel.send(embed=embed)

    # ---------- TESTJOIN ----------

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
            await interaction.response.send_message(
                "❌ Kein Welcome aktiv.",
                ephemeral=True
            )
            return

        channel_id, message, mode = data
        channel = interaction.guild.get_channel(channel_id)
        member = interaction.user

        if mode == "banner":
            card = await generate_banner(member)
            await channel.send(file=discord.File(card, "welcome.png"))
            await interaction.response.send_message(
                f"✅ Test-Banner gesendet in {channel.mention}",
                ephemeral=True
            )

        elif mode == "embed":
            text = (
                message
                .replace("%member", str(member))
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

    # ---------- JOINMSG ----------

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

            await interaction.response.send_message(
                "✅ Welcome deaktiviert.",
                ephemeral=True
            )

        elif argument == "Anzeigen":
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT channelID, mode FROM welcome WHERE guildID=%s",
                        (interaction.guild.id,)
                    )
                    data = await cursor.fetchone()

            if not data:
                await interaction.response.send_message(
                    "❌ Kein Welcome aktiv.",
                    ephemeral=True
                )
                return

            ch = interaction.guild.get_channel(data[0])
            await interaction.response.send_message(
                f"📢 Kanal: {ch.mention}\n🎨 Modus: **{data[1]}**",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(welcome(bot))
