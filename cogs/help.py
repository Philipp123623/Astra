import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime

class Dropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Moderation', value="Mod", emoji='<:Astra_moderation:1141303878541918250>'),
            discord.SelectOption(label="Levelsystem", value="Level", emoji="<:Astra_level:1141825043278598154>"),
            discord.SelectOption(label="Giveaways", value="GW", emoji="<:Astra_gw1:1141303852889550928>"),
            discord.SelectOption(label='Settings & Setup', value="Settings", emoji='<:Astra_settings:1061390649200476170>'),
            discord.SelectOption(label='Tickets', value="Ticket", emoji='<:Astra_ticket:1141833836204937347>'),
            discord.SelectOption(label='Automod', value="Automod", emoji="<:Astra_time:1141303932061233202>"),
            discord.SelectOption(label='Information', value="Info", emoji='<:Astra_support:1141303923752325210>'),
            discord.SelectOption(label='Fun', value="Fun", emoji='<:Astra_fun:1141303841665601667>'),
            discord.SelectOption(label='Economy', value="Eco", emoji='<:Astra_cookie:1141303831293079633>'),
            discord.SelectOption(label='Nachrichten', value="Messages", emoji='<:Astra_messages:1141303867850641488>'),
            discord.SelectOption(label='Minispiele', value="Minigames", emoji='<:Astra_minigames:1141303876528648232>'),
        ]
        super().__init__(placeholder='Wähle eine Seite', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        pages = {
            "Mod": "> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </kick:1362756274130915437> - Kicke einen User.\n> </ban:1362756274130915438> - Banne einen User.\n> </unban:1362756274424647754> - Entbanne einen User.\n> </banlist:1362756274424647755> - Liste gebannter User.\n> </clear:1362756274424647751> - Nachrichten löschen.",
            "Level": "> **👥 × User Befehle:**\n> </levelsystem rank:1362756275133222930> - Zeigt dein Level an.\n\n> **👮‍♂ × Team Befehle:**\n> </levelsystem status:1362756275133222930> - System an/aus.\n> </levelsystem kanal:1362756275133222930> - Lege den Level-Channel fest.\n> </levelsystem levelupnachricht:1362756275133222930> - Custom Nachricht.\n> </levelsystem role:1362756275133222930> - Levelrollen einstellen.\n> </xpboost:1362756275544522822> - XP Boost aktivieren.\n> </setlevel:1362756275544522823> - Level eines Users setzen.",
            "GW": "> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </gewinnspiel start:1197746882164834335> - Starte ein Gewinnspiel.\n> </gewinnspiel end:1197746882164834335> - Beende ein Gewinnspiel.\n> </gewinnspiel reroll:1197746882164834335> - Reroll ein Gewinnspiel.",
            "Settings": "> **👥 × User Befehle:**\n> </afk:1362756274701340860> - Setze dich auf AFK.\n> </erinnerung:1197545819507789866> - Erstelle/Lösche Reminder.\n\n> **👮‍♂ × Team Befehle:**\n> </joinrole:1362756274701340861> - Setze Joinrollen.\n> </botrole:1362756274701340862> - Setze Botrollen.\n> </voicesetup:1362756274701340859> - Voice Setup einrichten.\n> </reactionrole:1362756274701340863> - Reactionroles einrichten.\n> </globalchat:1363910466509869367> - Globalchat einrichten.",
            "Ticket": "> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </ticket setup:1362756275133222929> - Ticket-Panel erstellen.\n> </ticket delete:1362756275133222929> - Ticket-Panel löschen.\n> </ticket list:1362756275133222929> - Ticket-Panels anzeigen.\n> </ticket log:1362756275133222929> - Ticket-Log einrichten.",
            "Automod": "> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </warn:1362756274877632652> - User verwarnen.\n> </unwarn:1362756275133222922> - Warn entfernen.\n> </warns:1362756275133222923> - Warnliste eines Users.\n> </automod:1362756274877632651> - Automod einrichten.\n> </modlog:1362756274877632647> - Modlog setzen.\n> </capslock:1362756275133222927> - Capslock-Schutz.\n> </blacklist:1362756274877632650> - Wörter auf Blacklist setzen.",
            "Info": "> **👥 × User Befehle:**\n> </help:1362756274130915429> - Hilfe anzeigen.\n> </about:1362756274424647756> - Infos über Astra.\n> </invite:1362756274424647757> - Bot einladen.\n> </support:1362756274424647758> - Supportserver joinen.\n> </ping:1362756274424647759> - Bot-Ping.\n> </uptime:1362756274424647760> - Bot-Uptime.\n> </info:1362756274130915435> - Informationen abrufen.",
            "Fun": "> **👥 × User Befehle:**\n> </wanted:1362756274604740659> - Wanted Poster erstellen.\n> </pix:1362756274604740660> - Profilbild pixeln.\n> </wasted:1362756274604740661> - Wasted Effekt.\n> </triggered:1362756274604740662> - Triggered Effekt.\n> </gay:1362756274604740664> - Gay Effekt.\n> </color:1362756274604740663> - Farbe anzeigen.\n> </meme:1362756274604740665> - Meme anzeigen.\n> </qrcode:1362756274604740666> - QR-Code erstellen.",
            "Eco": "> **👥 × User Befehle:**\n> </economy:1362756274130915432> - Economy starten.\n> </job:1362756274130915433> - Jobsystem nutzen.",
            "Messages": "> **👥 × User Befehle:**\n> </joinmsg:1362756274877632644> - Join-Message festlegen.\n> </leavemsg:1362756274877632646> - Leave-Message festlegen.\n> </autoreact:1362756274877632648> - Auto-Reaction setzen.\n> </embedfy:1362756274424647752> - Embed erstellen.",
            "Minigames": "> **👥 × User Befehle:**\n> </hangman:1362756274130915431> - Hangman spielen.\n> </snake:1362756275544522825> - Snake spielen.\n> </guessthenumber:1362756275133222924> - Guess the Number.\n> </counting:1362756275133222925> - Counting Channel."
        }
        description = pages.get(self.values[0], "Seite nicht gefunden!")
        embed = discord.Embed(title=" ", description=description, colour=discord.Colour.blue())
        embed.set_author(name=f"Command Menü | {self.values[0]}", icon_url=interaction.client.user.avatar)
        embed.set_footer(text="Astra Development ©2025", icon_url=interaction.guild.icon)
        await interaction.response.edit_message(embed=embed)

async def button2(interaction: discord.Interaction):
    view = View()
    view.add_item(Dropdown())
    view.timeout = None
    embed = discord.Embed(title="Command Menu", description="Wähle eine Kategorie!", colour=discord.Colour.blue())
    embed.set_author(name="Astra Command Menu", icon_url=interaction.client.user.avatar)
    embed.set_footer(text="Astra Development ©2025", icon_url=interaction.guild.icon)
    embed.set_image(url="https://cdn.discordapp.com/attachments/842039866740178944/987332928767938630/Astra-premium3.gif")
    await interaction.response.edit_message(embed=embed, view=view)

class help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.uptime = datetime.utcnow()

    @app_commands.command(name="help")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def help(self, interaction: discord.Interaction):
        view = View()
        view.add_item(Dropdown())
        view.timeout = None
        delta_uptime = datetime.utcnow() - self.uptime
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        embed = discord.Embed(
            colour=discord.Colour.blue(),
            title="Help Menü",
            description=(
                "<:Astra_info:1141303860556738620> **__Wichtige Informationen:__**\n"
                "Hier findest du alle Commands.\n"
                "Falls du Hilfe brauchst, komm auf unseren [**Support Server ➚**](https://discord.gg/NH9DdSUJrE).\n\n"
                f"**Uptime:** {days}d {hours}h {minutes}m {seconds}s\n"
                f"**Ping**: {self.bot.latency * 1000:.0f} ms"
            )
        )
        embed.add_field(
            name="Letzte Updates",
            value=(
                "> <:Coin:1359178077011181811> Neues Economy: </job:1362756274130915433>, </economy:1362756274130915432>\n"
                "> <:Astra_minigames:1141303876528648232> Neue Minigames: </hangman:1362756274130915431>, </snake:1362756275544522825>\n"
                "> <:Astra_gw1:1141303852889550928> Giveaway: </gewinnspiel:1197746882164834335>\n"
                "> <:Astra_level:1141825043278598154> Levelsystem: </levelsystem status:1362756275133222930>"
            )
        )
        embed.add_field(
            name="Links",
            value=(
                "**[Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)"
                " | [Support](https://discord.gg/NH9DdSUJrE)"
                " | [Voten](https://top.gg/bot/1113403511045107773/vote)**"
            ),
            inline=False
        )
        embed.set_footer(text="Astra Development ©2025", icon_url=interaction.guild.icon)
        embed.set_image(url="https://cdn.discordapp.com/attachments/842039866740178944/987332928767938630/Astra-premium3.gif")
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(help(bot))
