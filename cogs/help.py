import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from datetime import datetime, timezone

# -------------------- WEBSITE BUTTON --------------------
class WebsiteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🌐 Website",
            style=discord.ButtonStyle.link,
            url="https://astra-bot.de"
        )

# -------------------- DROPDOWN --------------------
class Dropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Moderation', value="Mod", emoji='<:Astra_moderation:1141303878541918250>'),
            discord.SelectOption(label="Levelsystem", value="Level", emoji="<:Astra_level:1141825043278598154>"),
            discord.SelectOption(label="Giveaways", value="GW", emoji="<:Astra_gw1:1141303852889550928>"),
            discord.SelectOption(label='Settings & Setup', value="Settings", emoji='<:Astra_settings:1061390649200476170>'),
            discord.SelectOption(label="Backup", value="backups", emoji=':Astra_file1:1141303837181886494>'),
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
        # Seiteninhalt
        pages = {
            "Mod": "> <:Astra_support:1141303923752325210> Nutze diese Befehle, um deinen Server sauber und sicher zu halten. Kicke, banne oder lösche Nachrichten schnell.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </kick:1362756274130915437> - Kickt einen User.\n> </ban:1362756274130915438> - Bannt einen User.\n> </unban:1362756274424647754> - Entbannt einen User.\n> </banlist:1362756274424647755> - Zeigt die Banliste.\n> </clear:1362756274424647751> - Löscht Nachrichten.",
            "Level": "> <:Astra_support:1141303923752325210> Verwalte das Levelsystem, belohne Aktivität und motiviere deine Community. Perfekt für Rankings und Events.\n\n> **👥 × User Befehle:**\n> </levelsystem rank:1362756275133222930> - Zeigt dein Level.\n> </levelsystem leaderboard:1362756275133222930> - Zeigt das Top 10 Leaderboard.\n\n> **👮‍♂ × Team Befehle:**\n> </levelsystem status:1362756275133222930> - System an/aus.\n> </levelsystem levelupkanal:1362756275133222930> - Setzt Level-Kanal.\n> </levelsystem levelupnachricht:1362756275133222930> - Nachricht anpassen.\n> </levelsystem role:1362756275133222930> - Levelrollen einstellen.\n> </xpboost:1362756275544522822> - XP-Boost aktivieren.\n> </setlevel:1362756275544522823> - Level setzen.",
            "GW": "> <:Astra_support:1141303923752325210> Organisiere Gewinnspiele und steigere die Aktivität deiner Community. Einfach starten und verwalten.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </gewinnspiel starten:1197746882164834335> - Starte ein Gewinnspiel.\n> </gewinnspiel verwalten:1197746882164834335> - Verwalte die Gewinnspiele.",
            "Settings": "> <:Astra_support:1141303923752325210> Passe den Server individuell an. Erstelle Rollen, richte AFK, Erinnerungen oder Reactionroles ein.\n\n> **👥 × User Befehle:**\n> </afk:1362756274701340860> - Setze dich auf AFK.\n> </erinnerung erstellen:1197545819507789866> - Erstelle Reminder.\n> </erinnerung anzeigen:1197545819507789866> - Zeige Reminder.\n> </erinnerung löschen:1197545819507789866> - Lösche Reminder.\n\n> **👮‍♂ × Team Befehle:**\n> </joinrole:1362756274701340861> - Setze Joinrollen.\n> </botrole:1362756274701340862> - Setze Botrollen.\n> </voicesetup:1362756274701340859> - Voice Setup.\n> </reactionrole:1362756274701340863> - Reactionroles einrichten.\n> </globalchat:1363910466509869367> - Globalchat einrichten.",
            "Ticket": "> <:Astra_support:1141303923752325210> Biete schnellen Support mit einem Ticketsystem. Einfach Tickets erstellen, verwalten und dokumentieren.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </ticket setup:1362756275133222929> - Ticket-Panel erstellen.\n> </ticket löschen:1362756275133222929> - Ticket-Panel löschen.\n> </ticket anzeigen:1362756275133222929> - Ticket-Panels anzeigen.\n> </ticket log:1362756275133222929> - Ticket-Log einrichten.",
            "Automod": "> <:Astra_support:1141303923752325210> Automatisiere Moderation mit Filtern und Logs. Schütze deinen Server effektiv vor Regelverstößen.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </warn:1362756274877632652> - User verwarnen.\n> </unwarn:1362756275133222922> - Warn entfernen.\n> </warns:1362756275133222923> - Warnliste anzeigen.\n> </automod hinzufügen:1362756274877632651> - Automod einrichten.\n> </automod entfernen:1362756274877632651> - Automod löschen.\n> </automod anzeigen:1362756274877632651> - Automod anzeigen.\n> </modlog:1362756274877632647> - Modlog setzen.\n> </capslock:1362756275133222927> - Capslock-Schutz.\n> </blacklist:1362756274877632650> - Wörter blockieren.",
            "Info": "> <:Astra_support:1141303923752325210> Erhalte nützliche Infos zu Usern, Server oder dem Bot. Alles Wichtige schnell abrufbar.\n\n> **👥 × User Befehle:**\n> </help:1362756274130915429> - Hilfe anzeigen.\n> </about:1362756274424647756> - Infos über Astra.\n> </invite:1362756274424647757> - Bot einladen.\n> </support:1362756274424647758> - Supportserver joinen.\n> </ping:1362756274424647759> - Bot-Ping.\n> </uptime:1362756274424647760> - Bot-Uptime.\n> </info kanal:1362756274130915435> - Kanalinfos.\n> </info server:1362756274130915435> - Serverinfos.\n> </info servericon:1362756274130915435> - Servericon.\n> </info rolle:1362756274130915435> - Rolleninfos.\n> </info user:1362756274130915435> - Userinfos.\n> </info wetter:1362756274130915435> - Wetterinfos.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Fun": "> <:Astra_support:1141303923752325210> Bringe Spaß in den Chat mit Filtern, Memes und mehr. Ideal für lockere Unterhaltung.\n\n> **👥 × User Befehle:**\n> </wanted:1362756274604740659> - Wanted Poster.\n> </pix:1362756274604740660> - Pixel-Effekt.\n> </wasted:1362756274604740661> - Wasted-Effekt.\n> </triggered:1362756274604740662> - Triggered-Effekt.\n> </gay:1362756274604740664> - Pride-Effekt.\n> </color:1362756274604740663> - Farbe anzeigen.\n> </meme:1362756274604740665> - Meme anzeigen.\n> </qrcode:1362756274604740666> - QR-Code erstellen.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Eco": "> <:Astra_support:1141303923752325210> Verdiene und verwalte virtuelles Geld. Spiele, arbeite oder handle mit anderen Usern.\n\n> **👥 × User Befehle:**\n> </economy balance:1362756274130915432> - Kontostand.\n> </economy deposit:1362756274130915432> - Einzahlen.\n> </economy withdraw:1362756274130915432> - Abheben.\n> </economy leaderboard:1362756274130915432> - Rangliste.\n> </economy beg:1362756274130915432> - Betteln.\n> </economy rob:1362756274130915432> - Überfallen.\n> </economy rps:1362756274130915432> - Schere, Stein, Papier.\n> </economy slot:1362756274130915432> - Slots.\n> </economy coinflip:1362756274130915432> - Münzwurf.\n> </economy blackjack:1362756274130915432> - Blackjack.\n> </job list:1362756274130915433> - Jobs anzeigen.\n> </job apply:1362756274130915433> - Job annehmen.\n> </job quit:1362756274130915433> - Job kündigen.\n> </job work:1362756274130915433> - Arbeiten.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Messages": "> <:Astra_support:1141303923752325210> Verwalte Willkommens-, Abschieds- und Youtube/Twitch Benachrichtigungen.\n\n> **👥 × User Befehle:**\n> </joinmsg:1362756274877632644> - Join-Message.\n> </leavemsg:1362756274877632646> - Leave-Message.\n> </autoreact:1362756274877632648> - Auto-Reaction.\n> </embedfy:1362756274424647752> - Embed erstellen.\n\n> **👮‍♂ × Team Befehle:**\n> </benachrichtigung youtube:1404262400890372159> - YouTube-Kanal hinzufügen oder entfernen\n> </benachrichtigung twitch:1404262400890372159> - Twitch-Kanal hinzufügen oder entfernen",
            "Minigames": "> <:Astra_support:1141303923752325210> Spiele direkt im Chat und fordere dich oder andere heraus.\n\n> **👥 × User Befehle:**\n> </emojiquiz:1362756275133222924> - Emojiquiz.\n> </hangman:1362756274130915431> - Hangman.\n> </snake start:1362756275544522825> - Snake.\n> </snake highscore:1362756275544522825> - Highscore anzeigen.\n> </guessthenumber:1362756275133222924> - Zahlen raten.\n> </counting:1362756275133222925> - Zählen.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "backups": "> <:Astra_backup:123456789012345678> Sichere deinen Server mit einem Klick – Backups erstellen, wiederherstellen oder rückgängig machen. Immer sicher, immer unter Kontrolle.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n\n\n> **👮‍♂ × Team Befehle:**\n> </backup create:1404170184305934483> - Erstellt sofort ein Backup und gibt den Code zurück\n</backup load:1404170184305934483> - Stellt ein Backup wieder her und zeigt Fortschritt.\n</backup undo:1404170184305934483> - Entfernt alles, was beim letzten Restore-Job hinzugefügt wurde.\n</backup status:1404170184305934483> - Zeigt den Status des letzten Backup/Restore/Undo-Jobs.\n</backup delete:1404170184305934483> - Löscht ein Backup per Code und bereinigt verknüpfte Jobs.\n</backup latest:1404170184305934483> - Zeigt den letzten Backup-Code dieser Guild."
        }

        description = pages.get(self.values[0], "Seite nicht gefunden!")
        embed = discord.Embed(title=" ", description=description, colour=discord.Colour.blue())
        embed.set_author(name=f"Command Menü | {self.values[0]}", icon_url=interaction.client.user.avatar)
        embed.set_footer(text="Astra Development ©2025", icon_url=interaction.guild.icon)

        view = View(timeout=None)
        view.add_item(Dropdown())
        view.add_item(WebsiteButton())

        await interaction.response.edit_message(embed=embed, view=view)

# -------------------- COG --------------------
class help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.uptime = datetime.utcnow()

    @app_commands.command(name="help", description="Zeigt dir eine Liste aller Befehle an.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def help(self, interaction: discord.Interaction):
        view = View(timeout=None)
        view.add_item(Dropdown())
        view.add_item(WebsiteButton())

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
                "Falls du Hilfe brauchst, komm auf unseren [**Support Server ➚**](https://discord.gg/eatdJPfjWc).\n\n"
                f"**Uptime:** {days}d {hours}h {minutes}m {seconds}s\n"
                f"**Ping**: {self.bot.latency * 1000:.0f} ms\n\n"
            )

        )
        embed.add_field(
            name="Über Astra",
            value=(
                "> <:Astra_support:1141303923752325210> **Astra** ist ein vielseitiger Discord-Bot mit Moderation, Minigames, Economy, Levelsystem und mehr – entwickelt, um deinen Server zu verwalten und zu beleben.\n\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="Letzte Updates",
            value=(
                "> <:Coin:1359178077011181811> Neues Economy: </job:1362756274130915433>, </economy:1362756274130915432>\n"
                "> <:Astra_minigames:1141303876528648232> Neue Minigames: </hangman:1362756274130915431>, </snake:1362756275544522825>\n"
                "> <:Astra_gw1:1141303852889550928> Giveaway: </gewinnspiel:1197746882164834335>\n"
                "> <:Astra_level:1141825043278598154> Levelsystem: </levelsystem status:1362756275133222930>"
            ),
            inline=False,
        )
        embed.add_field(
            name="Links",
            value=(
                "**[Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)"
                " | [Support](https://discord.gg/eatdJPfjWc)"
                " | [Voten](https://top.gg/bot/1113403511045107773/vote)**"
            ),
            inline=False
        )
        embed.set_footer(text="Astra Development ©2025", icon_url=interaction.guild.icon)
        embed.set_image(url="https://cdn.discordapp.com/attachments/1141116983358804118/1403484979266195476/Neuer-Astra-Banner-animiert.gif")

        await interaction.response.send_message(embed=embed, view=view)

# -------------------- SETUP --------------------
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(help(bot))
