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
import matplotlib.ticker as tkr
import matplotlib.font_manager as fm
import numpy as np
from matplotlib import patheffects
import platform
import io
from PIL import Image
import asyncio
import tempfile


async def get_best_join_channel(guild: discord.Guild) -> discord.TextChannel | None:
    me = guild.me
    if not me:
        return None

    # 1️⃣ System Channel (wenn sendbar)
    ch = guild.system_channel
    if ch and ch.permissions_for(me).send_messages:
        return ch

    # 2️⃣ Bevorzugte Kanalnamen
    preferred = (
        "general", "allgemein", "chat", "welcome",
        "start", "server", "hauptchat"
    )

    for name in preferred:
        for ch in guild.text_channels:
            if name in ch.name.lower() and ch.permissions_for(me).send_messages:
                return ch

    # 3️⃣ Erster Textkanal mit Send-Rechten
    for ch in guild.text_channels:
        perms = ch.permissions_for(me)
        if perms.send_messages and perms.view_channel:
            return ch

    return None

# ------------------------------------------------------------
#  CPU & RAM Helpers
# ------------------------------------------------------------
def get_cpu_usage() -> float:
    # 1‑Sekunden‑Messung => realistische Schwankungen
    return psutil.cpu_percent(interval=1)


def get_ram_usage() -> float:
    return psutil.virtual_memory().percent


# ------------------------------------------------------------
#  Graph Generator (Dark‑Dashboard‑Style, verbessert)
# ------------------------------------------------------------
def generate_graph(cpu, ram, t):
    # 1)  Font registrieren
    FONT_PATH = "cogs/fonts/Poppins-SemiBold.ttf"  # dein absoluter oder relativer Pfad
    fm.fontManager.addfont(FONT_PATH)  # <‑ in den Matplotlib‑Cache eintragen
    # fm._rebuild()  # Font‑Datenbank neu aufbauen

    # Interner Name exakt auslesen
    POPPINS_NAME = fm.FontProperties(fname=FONT_PATH).get_name()
    # -> gibt meist "Poppins SemiBold" zurück

    # ---------- Farben ----------
    BG_FIG = "#181818"     # super‑dunkel
    BG_AX  = "#222222"     # etwas heller
    CPU_C  = "#36A8FF"     # Astra‑Blau
    RAM_C  = "#FFB547"     # Amber‑Orange

    # ---------- Interpolation (smooth) ----------
    x  = np.array(t)
    xs = np.linspace(x.min(), x.max(), 240)
    cpu_s = np.interp(xs, x, cpu)
    ram_s = np.interp(xs, x, ram)

    # ---------- Global Style ----------
    plt.rcParams.update({
        "font.family": POPPINS_NAME,  # Alternativ: 'Segoe UI', 'Ubuntu', 'DejaVu Sans'
        "font.size":   10,
        "axes.edgecolor": "white",
        "axes.labelcolor": "white",
        "xtick.color": "white",
        "ytick.color": "white",
        "text.color":  "white",
        "figure.autolayout": True,
    })

    fig, ax1 = plt.subplots(figsize=(11, 5.5), dpi=130)
    fig.patch.set_facecolor(BG_FIG)
    ax1.set_facecolor(BG_AX)

    # ---------- Optional: Padding für Platz auf Achsen ----------
    fig.subplots_adjust(left=0.08, right=0.92)

    # ---------- CPU‑Linie ----------
    cpu_line, = ax1.plot(
        xs, cpu_s, color=CPU_C, lw=2.4, label="CPU",
        path_effects=[patheffects.Stroke(linewidth=3.4, foreground="#0E4066"),
                      patheffects.Normal()]
    )
    ax1.fill_between(xs, cpu_s, color=CPU_C, alpha=0.12)

    ax1.set_ylabel("CPU (%)", color=CPU_C, weight="bold")
    ax1.tick_params(axis="y", labelcolor=CPU_C)
    ax1.set_ylim(0, max(10, max(cpu) + 5))

    # ---------- RAM‑Linie (rechte Y‑Achse) ----------
    ax2 = ax1.twinx()
    ram_line, = ax2.plot(
        xs, ram_s, color=RAM_C, lw=2.4, label="RAM",
        path_effects=[patheffects.Stroke(linewidth=3.4, foreground="#664315"),
                      patheffects.Normal()]
    )
    ax2.fill_between(xs, ram_s, color=RAM_C, alpha=0.07)  # << dunkleres RAM-Fill

    ax2.set_ylabel("RAM (%)", color=RAM_C, weight="bold")
    ax2.tick_params(axis="y", labelcolor=RAM_C)
    ax2.set_ylim(min(0, min(ram) - 5), min(100, max(ram) + 5))

    # ---------- Achsen & Grid ----------
    ax1.set_xlabel("Zeit (Sekunden)")
    ax1.set_title("Systemauslastung – CPU & RAM", fontsize=16, weight="bold", pad=10)
    ax1.xaxis.set_major_locator(tkr.MaxNLocator(integer=True))
    ax1.grid(ls="--", lw=0.6, alpha=0.15, color="white")  # << smoother Grid

    # ---------- Legende ----------
    ax1.legend(
        handles=[cpu_line, ram_line],
        labels=["CPU", "RAM"],
        loc="upper left",
        frameon=False,
        fontsize=9
    )

    # ---------- Punkt‑Labels ----------
    for x_pt, y_pt in zip(x, cpu):
        ax1.text(x_pt, y_pt + 0.3, f"{y_pt:.1f}", color=CPU_C, fontsize=8, ha="center")
    for x_pt, y_pt in zip(x, ram):
        ax2.text(x_pt, y_pt + 0.3, f"{y_pt:.1f}", color=RAM_C, fontsize=8, ha="center")

    # ---------- Export ----------
    save_path = "system_usage_graph.png"
    plt.savefig(save_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return save_path


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
                    servers = len(self.bot.guilds)

                    embed = discord.Embed(
                        colour=discord.Colour.blurple(),
                        title="✨ ASTRA ✨",
                        description=(
                            "Hallo! Ich bin **Astra** – ein modularer Discord-Bot für "
                            "**Moderation, Organisation und Community-Features**.\n\n"
                            "Ich helfe dabei, Server **sauber**, **strukturiert** und "
                            "**angenehm** zu halten – ohne unnötigen Overhead."
                        )
                    )

                    # =====================
                    # CORE FEATURES
                    # =====================

                    embed.add_field(
                        name="🛡️ Moderation & Sicherheit",
                        value=(
                            "• Warn- & Automod-System\n"
                            "• Blacklists & Caps-Filter\n"
                            "• Mod-Logs & Audit-Übersicht\n"
                            "• Tickets & Support-Workflows"
                        ),
                        inline=False
                    )

                    embed.add_field(
                        name="⚙️ Server-Management",
                        value=(
                            "• Rollen- & Join-Systeme\n"
                            "• Willkommens- & Leave-Nachrichten\n"
                            "• Counting- & Minigames\n"
                            "• Backup- & Wiederherstellung"
                        ),
                        inline=False
                    )

                    embed.add_field(
                        name="📊 Community & Extras",
                        value=(
                            "• Level- & XP-System\n"
                            "• Giveaways & Events\n"
                            "• Economy & Fun-Commands\n"
                            "• YouTube / Twitch Benachrichtigungen"
                        ),
                        inline=False
                    )

                    # =====================
                    # QUICK START
                    # =====================

                    embed.add_field(
                        name="🚀 Schnellstart",
                        value=(
                            "• `/help` – Alle Befehle\n"
                            "• `/about` – Infos zu Astra\n"
                            "• `/ticket setup` – Support-System starten\n"
                            "• `/automod` – Automoderation konfigurieren"
                        ),
                        inline=False
                    )

                    # =====================
                    # STATS & LINKS
                    # =====================

                    embed.add_field(
                        name="📈 Status",
                        value=f"Aktiv auf **{servers}** Servern",
                        inline=False
                    )

                    embed.add_field(
                        name="🔗 Links",
                        value=(
                            "**[Support-Server](https://discord.gg/eatdJPfjWc)**\n"
                            "**[Bot einladen](https://discord.com/oauth2/authorize?"
                            "client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)**"
                        ),
                        inline=False
                    )

                    # =====================
                    # BRANDING
                    # =====================

                    embed.set_footer(
                        text="Astra • Modular • Transparent • Server-fokussiert",
                        icon_url=self.bot.user.display_avatar.url
                    )

                    embed.set_author(
                        name="Danke fürs Einladen!",
                        icon_url="https://cdn.discordapp.com/emojis/823981604752982077.gif"
                    )

                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        pass

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

    @app_commands.command(name="about", description="Zeigt Informationen über den Bot.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def about(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        # -------- Daten sammeln -------------------------------------------
        cpu_data, ram_data = [], []
        for _ in range(10):
            cpu_data.append(get_cpu_usage())
            ram_data.append(get_ram_usage())

        time_points = list(range(10))
        graph_path = generate_graph(cpu_data, ram_data, time_points)
        graph_file = discord.File(graph_path, filename="graph.png")

        # -------- Bot‑Infos ----------------------------------------------
        bot_owner = self.bot.get_user(789555434201677824)  # <‑ deine ID
        servers = len(self.bot.guilds)
        members_total = sum(g.member_count or 0 for g in self.bot.guilds)
        members_avg = members_total / servers if servers else 0

        # -------- Uptime --------------------------------------------------
        delta = datetime.utcnow() - self.uptime
        d, r = divmod(delta.total_seconds(), 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)

        embed = discord.Embed(
            title="🛰️ Astra Systemübersicht",
            description="Hier findest du aktuelle Informationen über den Bot und seine Leistung.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="👤 Bot Owner", value=bot_owner.mention if bot_owner else "Unbekannt", inline=True)
        embed.add_field(name="🌐 Server", value=f"{servers}", inline=True)
        embed.add_field(name="👥 Nutzer", value=f"{members_total}", inline=True)
        embed.add_field(name="📊 Schnitt/Server", value=f"{members_avg:.2f}", inline=True)
        embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
        embed.add_field(name="🤖 discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="🕓 Uptime",
                        value=f"{int(d)}d {int(h)}h {int(m)}m {int(s)}s", inline=True)
        embed.add_field(name="🛠️ Slash Cmds", value=str(len(self.bot.tree.get_commands())), inline=True)
        embed.add_field(name="🏓 Latenz", value=f"{self.bot.latency * 1000:.2f} ms", inline=True)

        embed.set_image(url="attachment://graph.png")
        embed.set_footer(text="Astra • Performance‑Überblick",
                         icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        await interaction.followup.send(embed=embed, file=graph_file)
        os.remove(graph_path)

    @app_commands.command(name="invite")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def invite(self, interaction: discord.Interaction):
        """Link um Astra einzuladen."""
        embed = discord.Embed(colour=discord.Colour.blue(), title=f"Nutze Astra auch auf deinem Server!",
                              description=f"Mit klicken auf [Invite Astra](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands) kannst du Astra auch auf deinen Server einladen.",
                              url="https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="support")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def support(self, interaction: discord.Interaction):
        """Link zu unserem Support Server."""
        embed = discord.Embed(colour=discord.Colour.blue(), title="Wir freuen uns dir helfen zu können!",
                              description="Hast du Fragen oder ein Problem? Wir freuen uns dir auf unserem [support server](https://discord.gg/M2QykAY3Bv) helfen zu können.",
                              url="https://discord.gg/M2QykAY3Bv")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping")
    @app_commands.guild_only()
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
    @app_commands.guild_only()
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