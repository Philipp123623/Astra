import discord
from discord import app_commands
from discord.ext import commands
from discord.ui.button import Button
from discord.ui.view import View
from datetime import datetime


async def button2(interaction: discord.Interaction):
    view = View()
    view.add_item(Dropdown())
    view.timeout = None
    embed = discord.Embed(title="Command Menu", description="Wähle eine Kategorie!", colour=discord.Colour.blue())
    embed.set_author(name="Astra Command Menu", icon_url=interaction.client.user.avatar)
    embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/842039866740178944/987332928767938630/Astra-premium3.gif")
    await interaction.response.edit_message(embed=embed, view=view)


class Dropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Moderation', value="Mod",
                                 emoji='<:Astra_moderation:1141303878541918250>'),
            discord.SelectOption(label="Levelsystem", value="Level",
                                 emoji="<:Astra_level:1141825043278598154>"),
            discord.SelectOption(label="Giveaways", value="GW", 
                                 emoji="<:Astra_gw1:1141303852889550928>"),
            discord.SelectOption(label='Settings & Setup', value="Settings",
                                 emoji='<:Astra_settings:1061390649200476170>'),
            discord.SelectOption(label='Tickets', value="Ticket",
                                 emoji='<:Astra_ticket:1141833836204937347>'),
            discord.SelectOption(label='Automod', value="Automod",
                                 emoji="<:Astra_time:1141303932061233202>"),
            discord.SelectOption(label='Information', value="Info",
                                 emoji='<:Astra_support:1141303923752325210>'),
            discord.SelectOption(label='Fun', value="Fun",
                                 emoji='<:Astra_fun:1141303841665601667>'),
            discord.SelectOption(label='Economy', value="Eco",
                                 emoji='<:Astra_cookie:1141303831293079633>'),
            discord.SelectOption(label='Nachrichten', value="Messages",
                                 emoji='<:Astra_messages:1141303867850641488>'),
            discord.SelectOption(label='Minispiele', value="Minigames",
                                 emoji='<:Astra_minigames:1141303876528648232>'),
        ]
        super().__init__(placeholder='Wähle eine Seite', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "Mod":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Dies sind Befehle, die eigentlich jeder Bot hat. Einfache Moderation per Slash Befehle.\n\n> **`👥` × User Befehle:**\n> Keine User Befehle.\n\n> **`👮‍♂` × Team Befehle:**\n> `/kick` - Kicke einen User.\n> `/ban` - Banne einen User.\n> `/unban` - Entbanne einen User.\n> `/banlist` - Zeigt eine Liste mit gebannten Usern.\n> `/clear` - Löscht eine Bestimmte Anzahl an Nachrichten.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Moderation", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)

        elif self.values[0] == "Level":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Hier kannst du unser Umfangreiches Levelsystem Einstellen und Verwalten. Es gibt einige sehr Coole Funktionen sowie ein schlichtes Design.\n\n> **`👥` × User Befehle:**\n> `/rank` - Sendet deine Levelcard.\n\n> **`👮‍♂` × Team Befehle:**\n> `/levelsystem status` - An-/Ausschalten des Levelsystems.\n> `/levelsystem kanal` - Lege einen Kanal fest, in den die Level Up Nachrichten gesendet werden.\n> `/levelsystem levelupnachricht` - Lege eine Custom Level-Up Nachricht fest.\n> `/levelsystem role` - Füge/Entferne Rollen die man ab dem jeweiligem Level bekommt.\n> `/xpboost` - Aktiviere den XP-Boost für deinen Server.\n> `/setlevel` - Lege das Level eines Users auf deinem Server Fest.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Levelsystem", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Settings":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Diese Kategorie ist für Einstellungen deines Servers gedacht. Hier kannst du jegliche Systeme wie Joinrole oder den Globalchat verwalten. Es gibt auch nützliche Befehle für dich selber.\n\n> **`👥` × User Befehle:**\n> `/afk` - Setze dich selbst auf AFK!\n> `/reminder` - Erstelle/Lösche einen Reminder oder kriege eine Liste mit allen Remindern.\n\n> **`👮‍♂` × Team Befehle:**\n> `/joinrole` - Lege eine Joinrolle für deinen Server fest.\n> `/botrole` - Lege eine Botrolle für deinen Server fest.\n> `/voicesetup` - Richtet einen Kanal ein, der beim Betreten einen Kanal nur für dich erstellt.\n> `/reactionrole` - Richte Reactionroles für deinen Server ein.\n> `/globalchat` - Richte unseren Globalchat für deinen Server ein.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Levelsystem", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "GW":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Hier kannst du unser Umfangreiches Ticketsystem verwalten.\n> **`👥` × User Befehle:**\n> Keine User Befehle.\n\n> **`👮‍♂` × Team Befehle:**\n> `giveaway start` - Staret ein Gewinnspiel.\n> `giveaway end` - Beende ein Gewinnspiel.\n> `giveaway reroll` - Lose ein Gewinnspiel neu aus.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Gewinnspiel", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Ticket":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Hiermit kannst du unser Ticket-Panel Erstellen und Verwalten. Wir haben versucht, dies so einfach wie möglich zu gestalten\n\n> **`👥` × User Befehle:**\n> Keine User befehle.\n\n> **`👮‍♂` × Team Befehle:**\n> `/ticket setup` - Erstelle ein Ticket-Panel.\n> `/ticket delete` - Lösche ein Ticket-Panel.\n> `/ticket list` - Listet alle Ticket-Panels deines Servers auf.\n> `/ticket log` - Lege einen Kanal fürs Loggen von Tickets fest.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Ticketsystem", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Automod":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Dieses System ermöglicht dir automatische Handlungen gegen Nutzer, die eine bestimmte Warnanzahl erreicht haben. Warns können manuell und automatisch, über z.B.: Blacklist, verteilt werden.\n\n> **`👥` × User Befehle:**\n> Keine User Befehle.\n\n> **`👮‍♂` × Team Befehle:**\n> `/warn` - Warne einen User.\n> `/unwarn` - Entferne Warns von einem User.\n> `warns` - Erhalte eine Liste mit allen Warns eines Users.\n\n> `/automod add/remove` Richte die Auto Moderation für deinen Server ein.\n\n> `/modlog` - Lege einen Kanal für den Modlog fest.\n\n> `/capslock` - Richte den Capslock ein.\n\n> `/blacklist add/remove/show` - Nachrichten Blacklisten, von der Blacklist entfernen und eine Liste mit allen geblacklisteten Wörtern erhalten.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Automod", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Info":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Hier stehen Befehle, die hauptsächlich Informationen ausgeben oder nützlich sind.\n\n> **`👥` × User Befehle:**\n> `/help` - Alle wichtigen Befehle und Links.\n> `/feedback` - Gib uns gerne ein kleines Feedback :D.\n> `/about` - Infos über Astra.\n> `/invite` - Link um Astra einzuladen.\n> `/support` - Link zu unserem Support Server.\n> `/ping` - Zeigt den Ping von Astra.\n> `/uptime` - Zeigt wie lang Astra online ist.\n> `/info kanal` - Zeigt einige Infos über einen Channel.\n> `/info user` - Zeigt einige Infos über einen User.\n> `/info server` - Zeigt einige Infos über einen Server.\n> `/info rolle` - Zeigt einige Infos über eine Rolle.\n> `/info servericon` - Zeigt das Server Profilbild.\n> `/info wetter` - Zeigt dir einige Infos über das Wetter einer Stadt.\n> `/poll` - Erstelle eine Umfrage.\n> `/invites` - Zeigt die Einladungen eines Users.\n\n> **`👮‍♂` × Team Befehle:**\n> Keine Team Befehle.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Information", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Fun":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Lustige Befehle für dich und deine Freunde gesucht? Dann Schau doch mal hier nach ob du was findest.\n\n> **`👥` × User Befehle:**\n> `/wanted` - Erstellt ein 'Gesucht' Plakat mit dem Profilbild eines Users.\n> `/pix` - Verpixelt das Profilbild eines Users.\n> `/wasted` - Sendet ein Profilbild mit Effekten.\n> `/triggered` - Sendet ein Profilbild mit Effekten.\n> `/gay` - Sendet ein Profilbild mit Effekten.\n> `/color` - Gebe einen Hex-Code an und schaue dir die Farbe an.\n> `/meme` - Zeigt lustige Memes.\n> `/qrcode` - Erstelle einen QR-Code für einen Link.\n> `/lostrate` - Kalkuliert, wie Lost ein user ist.\n> `/iq` - Find heraus wie hoch der IQ eines Users ist.\n> `/ask` - Frage berühmte Persöhnlichkeiten.\n> `/love` - Finde heraus, wie sehr sich 2 User lieben.\n> `/susrate` - Kalkuliert, wie SUS ein User ist.\n> `/los` - Ziehe ein Rubbellos.\n> `/games` - Zeigt alle Spiele an, die grade gespielt werden.\n> `/password` - Generiert ein zufälliges Passwort für dich.\n\n> **`👮‍♂` × Team Befehle:**\n> Keine Team Befehle.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Fun", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Eco":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Schau dir doch gerne unser Economy System an. Aktuell wird es jedoch überarbeitet!\n\n> **`👥` × User Commands:**\n > `/job list` - Erhalte eine Liste mit allen Jobs.\n > `/job apply` - Bewirb dich auf einen verfügbaren Job\n> `/job quit` - Kündige deinen aktuellen Job.\n> `/job work` - Arbeite in deinem aktuellen Job.\n> `/economy balance` - Zeigt deinen aktuellen Kontostand an.\n> `/ecomnomy deposit` - Zahle Geld auf dein Bankkonto ein.\n> `/economy withdraw` - Hebe Geld von deinem Bankkonto ab.\n> `/economy beg` - Bitte um ein kleines Trinkgeld.\n> `/economy slot` - Spiele ein Slot-Spiel um Coins zu gewinnen oder zu verlieren.\n> `/economy` - Spiele Schere, Stein, Papier gegen den Bot.\n> `/economy coinflip` - Lass die Münze entscheiden! Wähle 'Kopf' oder 'Zahl' und setze einen Einsatz.\n> `/economy rob` - Versuche, einen anderen Nutzer auszurauben!\n> `/economy leaderboard` - Zeige die reichsten Spieler.\n> `/economy blackjack` - Spiele eine Runde Blackjack.\n\n> **`👮‍♂️` × Team Commands:**\n> Kein Team Befehle.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Economy", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Messages":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Die Kategorie Nachrichten beschreibt Befehle, mit denen du auf bestimmte Nachrichten reagieren kannst. Automatisch und manuell. z.B.: automatische Reaktionen\n\n> **`👥` × User Befehle:**\n> Keine User Befehle.\n\n> **`👮‍♂` × Team Befehle:**\n> `/joinmsg` - Lege eine Nachricht fest für User, die deinem Server joinen.\n> `testjoin` - Schaue ob deine Joinmsg gut funktioniert.\n> `/leavemsg` - Lege eine Nachricht fest für User, die deinen Server verlassen.\n> `/testleave` - Schaue ob deine Leavemsg gut funktioniert.\n> `/autoreact` - Richte Auto Reaktionen in Channels ein.\n> `/embedfy` - Erstelle ein schönes Embed.\n> `/customcommand add/delete/list` - Erstelle eigene Befehle nur für deinen Server.",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Nachrichten", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)
        elif self.values[0] == "Minigames":
            embed = discord.Embed(title=" ",
                                  description="> <:Astra_info:1141303860556738620> Du suchst kleine Lustige Spiele und hast Langeweile? Dann Schau doch mal hier nach :D.\n\n> **`👥` × User Befehle\n> `/hangman` - Spiele Hangman.\n> `/snake` - Spiele Snake.\n\n> **`👮‍♂` × Team Befehle:**\n> `/guessthenumber` - Verwalte das Minispiel 'Guess the number' auf deinem Server.\n> `/counting` - Richte den Zählkanal ein.\n> **Bald Mehr!**",
                                  colour=discord.Colour.blue())
            embed.set_author(name="Command Menü | Minispiele", icon_url=interaction.client.user.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
            await interaction.response.edit_message(embed=embed)


class help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.uptime = datetime.utcnow()

    @app_commands.command(name="help")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def help(self, interaction: discord.Interaction):
        """Alle wichtigen Befehle und Links."""
        view = View()
        view.add_item(Dropdown())
        view.timeout = None
        delta_uptime = datetime.utcnow() - self.uptime
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        embed = discord.Embed(colour=discord.Colour.blue(),
                              title="Help Menü",
                              description=f"<:Astra_info:1141303860556738620> **__Wichtige informationen:__** Hier findest du alle Commands,\nfalls du Hilfe benötigst, komm auf unseren [**Support Server ➚**](https://discord.gg/NH9DdSUJrE).\n\n**Uptime:** {days}d {hours}h {minutes}m {seconds}s\n**Ping**: {self.bot.latency * 1000:.0f} ms")
        embed.add_field(name="Letze Updates",
                        value="> <:Astra_gw1:1141303852889550928> Giveaway: `/giveaway start/end/reroll`\n> <:Astra_level:1141825043278598154> Levelsystem: `/levelsystem status`\n> <:Astra_time:1141303932061233202> Erinnerungen: `/reminder`\n> <:Astra_ticket:1141833836204937347> Ticketsystem: `/ticket setup`")
        embed.set_author(name="Astra", icon_url=interaction.client.user.avatar)
        embed.add_field(name="Links",
                        value="**[Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands) | [Support](https://discord.gg/NH9DdSUJrE) | [Voten](https://top.gg/bot/1113403511045107773/vote)**",
                        inline=False)
        embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.", icon_url=interaction.guild.icon)
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/842039866740178944/987332928767938630/Astra-premium3.gif")
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(help(bot))
