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
            "Mod": "> ❓ In dieser Kategorie findest du alle Werkzeuge, um deinen Server professionell zu verwalten und für Ordnung zu sorgen. Hier kannst du Mitglieder kicken, bannen oder entbannen, die Bannliste einsehen und Nachrichten in Channels aufräumen. Perfekt für Moderatoren und Admins, die ihre Community unter Kontrolle halten wollen.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </kick:1362756274130915437> - Kicke einen User.\n> </ban:1362756274130915438> - Banne einen User.\n> </unban:1362756274424647754> - Entbanne einen User.\n> </banlist:1362756274424647755> - Liste gebannter User.\n> </clear:1362756274424647751> - Nachrichten löschen.",
            "Level": "> ❓ Alles rund ums Levelsystem, um Aktivität zu belohnen und Fortschritt sichtbar zu machen. Du kannst dir dein Level und Rangkarte anzeigen lassen, Leaderboards ansehen, das System aktivieren oder deaktivieren und Level-Up Nachrichten personalisieren. Zusätzlich lassen sich Levelrollen festlegen oder XP-Booster aktivieren, um besondere Events zu gestalten.\n\n> **👥 × User Befehle:**\n> </levelsystem rank:1362756275133222930> - Zeigt dein Level an.\n> </levelsystem leaderboard:1362756275133222930> - Zeigt das Top 10 Level und XP Leaderboard an.\n\n> **👮‍♂ × Team Befehle:**\n> </levelsystem status:1362756275133222930> - System an/aus.\n> </levelsystem levelupkanal:1362756275133222930> - Lege den Level-Channel fest.\n> </levelsystem levelupnachricht:1362756275133222930> - Custom Nachricht.\n> </levelsystem role:1362756275133222930> - Levelrollen einstellen.\n> </xpboost:1362756275544522822> - XP Boost aktivieren.\n> </setlevel:1362756275544522823> - Level eines Users setzen.",
            "GW": "> ❓ Hier kannst du spannende Gewinnspiele auf deinem Server starten und verwalten. Ob kleine Events oder große Community-Aktionen – mit diesen Befehlen organisierst du alles von der Erstellung bis zur Auswertung. Ideal, um Aktivität und Engagement zu fördern.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </gewinnspiel starten:1197746882164834335> - Starte ein Gewinnspiel.\n> </gewinnspiel verwalten:1197746882164834335> - Verwalte die Gewinnspiele.",
            "Settings": "> ❓ In den Einstellungen kannst du grundlegende Funktionen deines Servers anpassen und automatisieren. Setze AFK-Status, erstelle Erinnerungen, lege Join- und Botrollen fest oder richte Reactionroles und Globalchat ein. Hier findest du alles, um deinen Server optimal zu konfigurieren.\n\n> **👥 × User Befehle:**\n> </afk:1362756274701340860> - Setze dich auf AFK.\n> </erinnerung erstellen:1197545819507789866> - Erstelle Reminder.\n> </erinnerung anzeigen:1197545819507789866> - Zeige dir alle Reminder an.\n> </erinnerung löschen:1197545819507789866> - Lösche Reminder.\n\n> **👮‍♂ × Team Befehle:**\n> </joinrole:1362756274701340861> - Setze Joinrollen.\n> </botrole:1362756274701340862> - Setze Botrollen.\n> </voicesetup:1362756274701340859> - Voice Setup einrichten.\n> </reactionrole:1362756274701340863> - Reactionroles einrichten.\n> </globalchat:1363910466509869367> - Globalchat einrichten.",
            "Ticket": "> ❓ Mit dem Ticket-System bietest du schnellen Support direkt auf deinem Server. Erstelle Ticket-Panels, in denen Nutzer ihre Anfragen einreichen können, und verwalte diese übersichtlich. Perfekt für Support-Teams oder Bewerbungsverfahren.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </ticket setup:1362756275133222929> - Ticket-Panel erstellen.\n> </ticket löschen:1362756275133222929> - Ticket-Panel löschen.\n> </ticket anzeigen:1362756275133222929> - Ticket-Panels anzeigen.\n> </ticket log:1362756275133222929> - Ticket-Log einrichten.",
            "Automod": "> ❓ Automatisiere Moderation und Sicherheit mit den Automod-Befehlen. Hier kannst du Nutzer verwarnen, Verwarnungen entfernen, Automod-Regeln hinzufügen oder löschen und ein Modlog einrichten. Zusätzlich gibt es Schutzfunktionen wie Capslock-Filter und Wort-Blacklist.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </warn:1362756274877632652> - User verwarnen.\n> </unwarn:1362756275133222922> - Warn entfernen.\n> </warns:1362756275133222923> - Warnliste eines Users.\n> </automod hinzufügen:1362756274877632651> - Automod einrichten.\n> </automod entfernen:1362756274877632651> - Automod Löschen.\n> </automod anzeigen:1362756274877632651> - Automod anzeigen.\n> </modlog:1362756274877632647> - Modlog setzen.\n> </capslock:1362756275133222927> - Capslock-Schutz.\n> </blacklist:1362756274877632650> - Wörter auf Blacklist setzen.",
            "Info": "> ❓ Zeige dir nützliche Informationen über deinen Server, Nutzer oder den Bot selbst an. Ob Uptime, Ping, Servericon oder Wetterbericht – hier findest du alle Befehle, die dir Daten und Statistiken liefern.\n\n> **👥 × User Befehle:**\n> </help:1362756274130915429> - Hilfe anzeigen.\n> </about:1362756274424647756> - Infos über Astra.\n> </invite:1362756274424647757> - Bot einladen.\n> </support:1362756274424647758> - Supportserver joinen.\n> </ping:1362756274424647759> - Bot-Ping.\n> </uptime:1362756274424647760> - Bot-Uptime.\n> </info kanal:1362756274130915435> - Kanalinformationen abrufen.\n> </info server:1362756274130915435> - Serverinformationen abrufen.\n> </info servericon:1362756274130915435> - Servericon abrufen.\n> </info rolle:1362756274130915435> - Rolleninformationen abrufen.\n> </info user:1362756274130915435> - Userinformationen abrufen.\n> </info wetter:1362756274130915435> - Wetterinformationen abrufen.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Fun": "> ❓ Sorge für Spaß und Unterhaltung mit Effekten, Memes und Minigames. Verpasse Profilbildern lustige Filter oder generiere Memes direkt im Chat. Ideal, um die Stimmung aufzulockern und gemeinsam zu lachen.\n\n> **👥 × User Befehle:**\n> </wanted:1362756274604740659> - Wanted Poster erstellen.\n> </pix:1362756274604740660> - Profilbild pixeln.\n> </wasted:1362756274604740661> - Wasted Effekt.\n> </triggered:1362756274604740662> - Triggered Effekt.\n> </gay:1362756274604740664> - Gay Effekt.\n> </color:1362756274604740663> - Farbe anzeigen.\n> </meme:1362756274604740665> - Meme anzeigen.\n> </qrcode:1362756274604740666> - QR-Code erstellen.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Eco": "> ❓ Baue deine eigene Wirtschaft mit virtueller Währung auf. Spiele Minigames, arbeite in Jobs oder handle mit anderen Spielern, um dein Guthaben zu erhöhen. Perfekt für Langzeitmotivation und freundliche Konkurrenz auf dem Server.\n\n> **👥 × User Befehle:**\n> </economy balance:1362756274130915432> - Balance einsehen.\n> </economy deposit:1362756274130915432> - Geld aufs Konto einzahlen.\n> </economy withdraw:1362756274130915432> - Geld abheben.\n> </economy leaderboard:1362756274130915432> - Liste der reichsten Spieler eines Servers.\n> </economy beg:1362756274130915432> - Bettel um Geld.\n> </economy rob:1362756274130915432> - Beraube einen Spieler.\n> </economy rps:1362756274130915432> - Spiele Schere, Stein, Papier.\n> </economy slot:1362756274130915432> - Spiele Slot-Maschinen.\n> </economy coinflip:1362756274130915432> - Wirf eine Münze.\n> </economy blackjack:1362756274130915432> - Spiele Blackjack.\n> </job list:1362756274130915433> - Liste aller verfügbaren Jobs.\n> </job apply:1362756274130915433> - Nehme einen Job an.\n> </job quit:1362756274130915433> - Kündige deinen Job.\n> </job work:1362756274130915433> - Arbeite in deinem Job.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Messages": "> ❓ Steuere Willkommens- und Abschiedsnachrichten oder automatische Reaktionen. Perfekt, um neuen Mitgliedern einen netten Empfang zu bereiten oder deinen Chat mit automatischen Emojis aufzupeppen.\n\n> **👥 × User Befehle:**\n> </joinmsg:1362756274877632644> - Join-Message festlegen.\n> </leavemsg:1362756274877632646> - Leave-Message festlegen.\n> </autoreact:1362756274877632648> - Auto-Reaction setzen.\n> </embedfy:1362756274424647752> - Embed erstellen.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Minigames": "> ❓ Teste dein Wissen und deine Reflexe mit kleinen Spielen direkt im Chat. Egal ob Emojiquiz, Hangman oder Snake – hier findest du alles, um dir oder deiner Community zwischendurch ein wenig Spaß zu gönnen.\n\n> **👥 × User Befehle:**\n> </emojiquiz:1362756275133222924> - Aktiviere oder deaktiviere das Emojiquiz in einem bestimmten Kanal.\n> </hangman:1362756274130915431> - Hangman spielen.\n> </snake start:1362756275544522825> - Snake spielen.\n> </snake highscore:1362756275544522825> - Zeigt den Highscore anderer Spieler an.\n> </guessthenumber:1362756275133222924> - Guess the Number.\n> </counting:1362756275133222925> - Counting Channel.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle."
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
        embed.set_image(url="https://cdn.discordapp.com/attachments/1141116983358804118/1403484979266195476/Neuer-Astra-Banner-animiert.gif")

        await interaction.response.send_message(embed=embed, view=view)

# -------------------- SETUP --------------------
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(help(bot))
