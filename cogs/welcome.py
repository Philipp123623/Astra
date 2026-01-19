import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import random

WELCOME_BANNER_PATH = "cogs/assets/Welcomecards/Willkommens_banner_fullsize.jpg"


def random_color():
    return discord.Color.from_rgb(
        random.randint(1, 255),
        random.randint(1, 255),
        random.randint(1, 255)
    )


# ================== MODAL ==================

class Modal2(discord.ui.Modal, title="Set your Join message!"):

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel, mode: str):
        super().__init__()
        self.bot = bot
        self.channel = channel
        self.mode = mode

    name = discord.ui.TextInput(
        label="Text",
        style=discord.TextStyle.long,
        placeholder="%member | %name | %mention | %guild | %usercount",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO welcome (guildID, channelID, message, mode)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    channelID = VALUES(channelID),
                    message = VALUES(message),
                    mode = VALUES(mode)
                    """,
                    (
                        interaction.guild.id,
                        self.channel.id,
                        self.name.value,
                        self.mode
                    )
                )

        embed = discord.Embed(
            title="Willkommens Nachricht wurde gesetzt",
            description=f"Kanal: {self.channel.mention}\nModus: {self.mode.replace('_',' ')}\n\n{self.name.value}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ================== COG ==================

class welcome(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========== MEMBER JOIN ==========

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID, message, mode FROM welcome WHERE guildID = %s",
                    (member.guild.id,)
                )
                data = await cursor.fetchone()

        if not data:
            return

        channel_id, message, mode = data
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return

        finalmsg = (
            message
            .replace("%member", str(member))
            .replace("%name", member.name)
            .replace("%mention", member.mention)
            .replace("%guild", member.guild.name)
            .replace("%usercount", str(member.guild.member_count))
        )

        embed = discord.Embed(description=finalmsg, color=random_color())

        try:
            if mode == "banner":
                file = discord.File(WELCOME_BANNER_PATH, filename="welcome.png")
                await channel.send(file=file)

            elif mode == "banner_embed":
                file = discord.File(WELCOME_BANNER_PATH, filename="welcome.png")
                embed.set_image(url="attachment://welcome.png")
                await channel.send(file=file, embed=embed)

            elif mode == "embed":
                await channel.send(embed=embed)
        except:
            pass

    # ========== TESTJOIN ==========

    @app_commands.command(name="testjoin", description="Teste deine Willkommens Nachricht")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def testjoin(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID, message, mode FROM welcome WHERE guildID = %s",
                    (interaction.guild.id,)
                )
                data = await cursor.fetchone()

        if not data:
            await interaction.response.send_message(
                "❌ Willkommens Nachrichten sind deaktiviert.",
                ephemeral=True
            )
            return

        channel_id, message, mode = data
        channel = interaction.guild.get_channel(int(channel_id))
        member = interaction.user

        finalmsg = (
            message
            .replace("%member", str(member))
            .replace("%name", member.name)
            .replace("%mention", member.mention)
            .replace("%guild", member.guild.name)
            .replace("%usercount", str(member.guild.member_count))
        )

        embed = discord.Embed(description=finalmsg, color=random_color())
        embed.set_footer(text=f"Testjoin von {member}")

        try:
            if mode == "banner":
                file = discord.File(WELCOME_BANNER_PATH, filename="welcome.png")
                await channel.send(file=file)

            elif mode == "banner_embed":
                file = discord.File(WELCOME_BANNER_PATH, filename="welcome.png")
                embed.set_image(url="attachment://welcome.png")
                await channel.send(file=file, embed=embed)

            elif mode == "embed":
                await channel.send(embed=embed)

            await interaction.response.send_message(
                f"✅ Testjoin Nachricht gesendet in {channel.mention}",
                ephemeral=True
            )
        except:
            pass

    # ========== JOINMSG COMMAND ==========

    @app_commands.command(name="joinmsg", description="Verwalte die Willkommens Nachricht")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def joinmsg(
        self,
        interaction: discord.Interaction,
        argument: Literal["Einschalten", "Ausschalten", "Anzeigen"],
        channel: discord.TextChannel = None,
        mode: Literal["banner+embed", "nur banner", "nur embed"] = "nur embed"
    ):
        mode_map = {
            "banner+embed": "banner_embed",
            "nur banner": "banner",
            "nur embed": "embed"
        }

        if argument == "Einschalten":
            if not channel:
                await interaction.response.send_message("❌ Bitte Kanal angeben.", ephemeral=True)
                return

            await interaction.response.send_modal(
                Modal2(self.bot, channel, mode_map[mode])
            )

        elif argument == "Ausschalten":
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM welcome WHERE guildID = %s",
                        (interaction.guild.id,)
                    )

            await interaction.response.send_message(
                "✅ Willkommens Nachrichten deaktiviert.",
                ephemeral=True
            )

        elif argument == "Anzeigen":
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT channelID, message, mode FROM welcome WHERE guildID = %s",
                        (interaction.guild.id,)
                    )
                    data = await cursor.fetchone()

            if not data:
                await interaction.response.send_message(
                    "❌ Willkommens Nachrichten sind deaktiviert.",
                    ephemeral=True
                )
                return

            channel_id, message, mode = data
            channel = interaction.guild.get_channel(int(channel_id))

            embed = discord.Embed(title="Willkommens Nachricht", color=discord.Color.green())
            embed.add_field(name="Kanal", value=channel.mention, inline=False)
            embed.add_field(name="Modus", value=mode.replace("_", " "), inline=False)
            embed.add_field(name="Nachricht", value=message, inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(welcome(bot))
