import discord
import psutil
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from psutil import Process, virtual_memory
from dotenv import load_dotenv
import os
import time
import matplotlib.pyplot as plt
import platform
import io
from PIL import Image
import asyncio
import tempfile

# --- CPU & RAM Nutzung ---
def get_cpu_usage():
    return psutil.cpu_percent(interval=None)


def get_ram_usage():
    return psutil.virtual_memory().percent


# --- Grafik-Erstellung ---
def generate_graph(cpu_data, ram_data, time_points):
    plt.style.use("default")  # ← sicherer Stil

    fig, ax1 = plt.subplots(figsize=(10, 5), dpi=100)

    ax1.set_title("Systemauslastung – CPU & RAM", fontsize=14, fontweight="bold")
    ax1.set_xlabel("Zeit (Sekunden)")
    ax1.set_ylabel("CPU-Auslastung (%)", color="tab:blue")
    ax1.plot(time_points, cpu_data, color="tab:blue", marker="o", label="CPU (%)")
    ax1.tick_params(axis='y', labelcolor="tab:blue")
    ax1.set_ylim(0, 100)

    ax2 = ax1.twinx()
    ax2.set_ylabel("RAM-Auslastung (%)", color="tab:orange")
    ax2.plot(time_points, ram_data, color="tab:orange", marker="s", label="RAM (%)")
    ax2.tick_params(axis='y', labelcolor="tab:orange")
    ax2.set_ylim(0, 100)

    fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.85))
    ax1.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()

    file_path = "system_usage_graph.png"
    plt.savefig(file_path)
    plt.close()
    return file_path

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


class testbutton(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label='testbutton', style=discord.ButtonStyle.green)
    async def testbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Confirming', ephemeral=True)


class astra(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.uptime = datetime.utcnow()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    try:
                        await guild.owner.send("**Danke fürs Einladen von Astra!**\n\nAstra verwaltet Ihren Server – Sie können folgende System zum verwalten ihres Servers nutzen:\nAdministration, Levelsystem, Tempchannels, Willkommen Nachrichten,\nund vieles mehr.\n\n **Funktionen**\n\nAstra bringt außerdem folgende Funktionen mit sich: Fun,\nGiveaway, Reactionrole, Utility\nInformationen und Joinrole\n\n**Wichtige Links**\n\nWebsite: https://astra-bot.de/ --> Aktuell nicht in Betrieb\n[Support Server](https://discord.gg/vwh2raq2Xu)\n[Bot Invite](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n")
                    except:
                        pass
                    try:
                        guilds = self.bot.get_guild(1141116981697859736)
                        channels = guilds.get_channel(1141116983815962821)
                        embed = discord.Embed(colour=discord.Colour.green(), title=f"Neuer server! ({len(self.bot.guilds)})",
                                              description="Hier sind einige Informationen:")
                        embed.add_field(name="Name", value=f"{guild.name}", inline=True)
                        embed.add_field(name="ID", value=f"{guild.id}", inline=True)
                        embed.add_field(name="Erstellt am", value=f"{guild.created_at.__format__('at the %d.%m.%Y around %X')}",
                                        inline=False)
                        embed.add_field(name="User count", value=f"{guild.member_count}", inline=False)
                        embed.add_field(name="Owner", value=f"{guild.owner}", inline=False)
                        embed.set_thumbnail(url=guild.icon)
                        await channels.send(embed=embed)
                    except:
                        pass
                    channels = sum(1 for g in self.bot.guilds for _ in g.channels)
                    servers = len(self.bot.guilds)
                    users = len(self.bot.users)
                    commands = len(len(self.bot.tree.get_commands()))
                    embed = discord.Embed(colour=discord.Colour.blurple(), title=f"✨ ASTRA ✨",
                                          description=f"Hallo, mein Name ist Astra und ich bin hier, um diesen Server zu verbessern! ⠀ ⠀ ⠀ ⠀ ⠀ ⠀\nIch bin aktuell auf **{len(self.bot.guilds)}** Servern!")
                    embed.add_field(name="Zum Starten",
                                    value=f"Prefix: `/`",
                                    inline=False)
                    embed.add_field(name="Links",
                                    value="**[Support server](https://discord.gg/vwh2raq2Xu) | [Invite](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)**",
                                    inline=False)
                    embed.set_footer(text=guild.name, icon_url=guild.icon)
                    embed.set_author(name="TDanke fürs Einladen!",
                                     icon_url="https://cdn.discordapp.com/emojis/823981604752982077.gif")
                    for channel in guild.text_channels:
                        await channel.send(embed=embed)
                        break

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        try:
            guilds = self.bot.get_guild(1141116981697859736)
            channels = guilds.get_channel(1141116983815962821)
            embed = discord.Embed(colour=discord.Colour.red(), title=f"Server verlassen! ({len(self.bot.guilds)})",
                                  description="Hier sind einige Informationen:")
            embed.add_field(name="Name", value=f"{guild.name}", inline=True)
            embed.add_field(name="ID", value=f"{guild.id}", inline=True)
            embed.add_field(name="Erstellt am", value=f"{guild.created_at.__format__('at the %d.%m.%Y around %X')}",
                            inline=False)
            embed.add_field(name="User count", value=f"{guild.member_count}", inline=False)
            embed.add_field(name="Owner", value=f"{guild.owner}", inline=False)
            embed.set_thumbnail(url=guild.icon)
            await channels.send(embed=embed)
            return
        except:
            pass

    # --- About Command ---
    @app_commands.command(name="about", description="Zeigt Informationen über den Bot.")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def about(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        cpu_data = []
        ram_data = []

        # Systemdaten sammeln (10 Sekunden)
        for _ in range(10):
            cpu_data.append(get_cpu_usage())
            ram_data.append(get_ram_usage())
            await asyncio.sleep(1)

        time_points = list(range(10))
        graph_path = generate_graph(cpu_data, ram_data, time_points)
        graph_file = discord.File(graph_path, filename="graph.png")

        # Bot-Infos
        bot_owner = self.bot.get_user(789555434201677824)  # Deine ID
        servers_count = len(self.bot.guilds)
        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        average_members = total_members / servers_count if servers_count else 0

        # Uptime
        delta = datetime.utcnow() - self.uptime
        days, rem = divmod(delta.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        embed = discord.Embed(
            title="🛰️ Astra Systemübersicht",
            description="Hier findest du aktuelle Informationen über den Bot und seine Leistung.",
            color=discord.Color.blurple()
        )

        embed.add_field(name="👤 Bot Owner", value=bot_owner.mention if bot_owner else "Unbekannt", inline=True)
        embed.add_field(name="🌐 Server", value=f"{servers_count}", inline=True)
        embed.add_field(name="👥 Nutzer", value=f"{total_members}", inline=True)
        embed.add_field(name="📊 Durchschnitt pro Server", value=f"{average_members:.2f}", inline=True)
        embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
        embed.add_field(name="🤖 discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="🕓 Uptime", value=f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s",
                        inline=True)
        embed.add_field(name="🛠️ Slash Commands", value=str(len(self.bot.tree.get_commands())), inline=True)
        embed.add_field(name="🏓 Latenz", value=f"{self.bot.latency * 1000:.2f} ms", inline=True)

        embed.set_image(url="attachment://graph.png")
        embed.set_footer(
            text="Astra • Performance-Überblick",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        await interaction.followup.send(embed=embed, file=graph_file)

        os.remove(graph_path)

    @app_commands.command(name="invite")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def invite(self, interaction: discord.Interaction):
        """Link um Astra einzuladen."""
        embed = discord.Embed(colour=discord.Colour.blue(), title=f"Nutze Astra auch auf deinem Server!",
                              description=f"Mit klicken auf [Invite Astra](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands) kannst du Astra auch auf deinen Server einladen.",
                              url="https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="support")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def support(self, interaction: discord.Interaction):
        """Link zu unserem Support Server."""
        embed = discord.Embed(colour=discord.Colour.blue(), title="Wir freuen uns dir helfen zu können!",
                              description="Hast du Fragen oder ein Problem? Wir freuen uns dir auf unserem [support server](https://discord.gg/M2QykAY3Bv) helfen zu können.",
                              url="https://discord.gg/M2QykAY3Bv")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def ping(self, interaction: discord.Interaction):
        """Zeigt den Ping von Astra."""
        t_1 = time.perf_counter()
        await interaction.response.send_message(f"```Websocket: {round(self.bot.latency * 1000, 2)} ms```")
        msg = await interaction.original_message()
        t_2 = time.perf_counter()
        time_delta = round((t_2 - t_1) * 1000, 2)
        await msg.edit(content=f"```Websocket: {round(self.bot.latency * 1000, 2)} ms\nAntwort: {time_delta} ms```")

    @app_commands.command(name="uptime")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def uptime(self, interaction: discord.Interaction):
        """Zeigt wie lang Astra online ist."""
        delta_uptime = datetime.utcnow() - self.uptime
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        embed = discord.Embed(colour=discord.Colour.green())
        embed.set_author(name=f"Online seit: {days}d {hours}h {minutes}m {seconds}s",
                         icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(astra(bot))