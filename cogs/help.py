import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from datetime import datetime


class WebsiteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🌐 Website", style=discord.ButtonStyle.link, url="https://astra-bot.de")


class Dropdown(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(label='Moderation', value="Mod", emoji='<:Astra_moderation:1141303878541918250>'),
            discord.SelectOption(label="Levelsystem", value="Level", emoji="<:Astra_level:1141825043278598154>"),
            discord.SelectOption(label="Giveaways", value="GW", emoji="<:Astra_gw1:1141303852889550928>"),
            discord.SelectOption(label='Settings & Setup', value="Settings", emoji='<:Astra_settings:1061390649200476170>'),
            discord.SelectOption(label="Backup", value="backups", emoji='<:Astra_file1:1141303837181886494>'),
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
        embed = discord.Embed(
            title=" ",
            description=self.cog.pages.get(self.values[0], "Seite nicht gefunden!"),
            colour=discord.Colour.blue()
        )
        # safer: .display_avatar.url
        embed.set_author(
            name=f"Command Menü | {self.values[0]}",
            icon_url=getattr(interaction.client.user.display_avatar, "url", None)
        )
        # safer: guild icon may be None
        guild_icon_url = getattr(getattr(interaction.guild, "icon", None), "url", None)
        embed.set_footer(text="Astra Development ©2025", icon_url=guild_icon_url)

        view = View(timeout=None)
        view.add_item(Dropdown(self.cog))
        view.add_item(WebsiteButton())
        await interaction.response.edit_message(embed=embed, view=view)


class HelpCog(commands.Cog):
    # Aliasse für abweichende Gruppen-Namen
    ALIASES = {
        # englisch -> tatsächlich genutzter Name
        "economy": "eco",
        "eco": "eco",
        "job": "job",
        # hier ggf. weitere Synonyme hinterlegen
        "levels": "levelsystem",
        "level": "levelsystem",
        "levelsystem": "levelsystem",
        "backup": "backup",
        "gewinnspiele": "gewinnspiel",
        "gewinnspiel": "gewinnspiel",
        "benachrichtigungen": "benachrichtigung",
        "notifications": "benachrichtigung",
        "info": "info",
        "infos": "info",
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.uptime = datetime.utcnow()
        self.command_ids = {}  # keys werden lowercase gehalten
        self.pages = {}

    async def on_ready_cache_ids(self):
        cmds = await self.bot.tree.fetch_commands()
        for cmd in cmds:
            if isinstance(cmd, app_commands.Group):
                # root group
                self.command_ids[cmd.name.lower()] = cmd.id
                # subcommands -> wir mappen "group sub" auf die group-id (für Mentions ausreichend)
                for sub in cmd.commands:
                    key = f"{cmd.name} {sub.name}".lower()
                    self.command_ids[key] = cmd.id
            else:
                self.command_ids[cmd.name.lower()] = cmd.id

    def _normalize_key(self, path: str) -> str:
        return path.strip().lower()

    def _cid(self, path: str) -> int:
        """
        Holt robust die Command-ID:
        - exakter key (lowercase)
        - Alias (z. B. economy -> eco)
        - bei "group sub": Alias auf group anwenden
        """
        key = self._normalize_key(path)

        # exakter Treffer
        if key in self.command_ids:
            return self.command_ids[key]

        # Alias auf gesamten key
        if key in self.ALIASES and self.ALIASES[key] in self.command_ids:
            return self.command_ids[self.ALIASES[key]]

        # group + sub?
        if " " in key:
            group, sub = key.split(" ", 1)
            group_alias = self.ALIASES.get(group, group)
            combo = f"{group_alias} {sub}".lower()
            if combo in self.command_ids:
                return self.command_ids[combo]
            # Falls Subcommand als anderer Name existiert (fallback: startswith-match)
            for k in self.command_ids.keys():
                if k.startswith(f"{group_alias} "):
                    # irgendein sub unter dieser group gefunden -> nutze group-id
                    return self.command_ids[k]

        # letzter Versuch: fuzzy startswith auf root-namen
        for k in self.command_ids.keys():
            if k == key or k.startswith(key + " ") or key.startswith(k + " "):
                return self.command_ids[k]

        # nichts gefunden -> klare Fehlermeldung
        available = ", ".join(sorted(self.command_ids.keys()))
        raise KeyError(f"Command '{path}' nicht gefunden. Verfügbar: {available}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.on_ready_cache_ids()
        self._build_pages()
        print(f"✅ Help command IDs cached: {len(self.command_ids)}")

    def _build_pages(self):
        self.pages = {
            "Mod": f"> <:Astra_support:1141303923752325210> Nutze diese Befehle, um deinen Server sauber und sicher zu halten. Kicke, banne oder lösche Nachrichten schnell.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </kick:{self._cid('kick')}> - Kickt einen User.\n> </ban:{self._cid('ban')}> - Bannt einen User.\n> </unban:{self._cid('unban')}> - Entbannt einen User.\n> </banlist:{self._cid('banlist')}> - Zeigt die Banliste.\n> </clear:{self._cid('clear')}> - Löscht Nachrichten.",
            "Level": f"> <:Astra_support:1141303923752325210> Verwalte das Levelsystem, belohne Aktivität und motiviere deine Community. Perfekt für Rankings und Events.\n\n> **👥 × User Befehle:**\n> </levelsystem rank:{self._cid('levelsystem')}> - Zeigt dein Level.\n> </levelsystem leaderboard:{self._cid('levelsystem')}> - Zeigt das Top 10 Leaderboard.\n\n> **👮‍♂ × Team Befehle:**\n> </levelsystem status:{self._cid('levelsystem')}> - System an/aus.\n> </levelsystem levelupkanal:{self._cid('levelsystem')}> - Setzt Level-Kanal.\n> </levelsystem levelupnachricht:{self._cid('levelsystem')}> - Nachricht anpassen.\n> </levelsystem role:{self._cid('levelsystem')}> - Levelrollen einstellen.\n> </xpboost:{self._cid('xpboost')}> - XP-Boost aktivieren.\n> </setlevel:{self._cid('setlevel')}> - Level setzen.",
            "GW": f"> <:Astra_support:1141303923752325210> Organisiere Gewinnspiele und steigere die Aktivität deiner Community. Einfach starten und verwalten.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </gewinnspiel starten:{self._cid('gewinnspiel')}> - Starte ein Gewinnspiel.\n> </gewinnspiel verwalten:{self._cid('gewinnspiel')}> - Verwalte die Gewinnspiele.",
            "Settings": f"> <:Astra_support:1141303923752325210> Passe den Server individuell an. Erstelle Rollen, richte AFK, Erinnerungen oder Reactionroles ein.\n\n> **👥 × User Befehle:**\n> </afk:{self._cid('afk')}> - Setze dich auf AFK.\n> </erinnerung erstellen:{self._cid('erinnerung')}> - Erstelle Reminder.\n> </erinnerung anzeigen:{self._cid('erinnerung')}> - Zeige Reminder.\n> </erinnerung löschen:{self._cid('erinnerung')}> - Lösche Reminder.\n\n> **👮‍♂ × Team Befehle:**\n> </joinrole:{self._cid('joinrole')}> - Setze Joinrollen.\n> </botrole:{self._cid('botrole')}> - Setze Botrollen.\n> </voicesetup:{self._cid('voicesetup')}> - Voice Setup.\n> </reactionrole:{self._cid('reactionrole')}> - Reactionroles einrichten.\n> </globalchat:{self._cid('globalchat')}> - Globalchat einrichten.",
            "Ticket": f"> <:Astra_support:1141303923752325210> Biete schnellen Support mit einem Ticketsystem. Einfach Tickets erstellen, verwalten und dokumentieren.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </ticket setup:{self._cid('ticket')}> - Ticket-Panel erstellen.\n> </ticket löschen:{self._cid('ticket')}> - Ticket-Panel löschen.\n> </ticket anzeigen:{self._cid('ticket')}> - Ticket-Panels anzeigen.\n> </ticket log:{self._cid('ticket')}> - Ticket-Log einrichten.",
            "Automod": f"> <:Astra_support:1141303923752325210> Automatisiere Moderation mit Filtern und Logs. Schütze deinen Server effektiv vor Regelverstößen.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </warn:{self._cid('warn')}> - User verwarnen.\n> </unwarn:{self._cid('unwarn')}> - Warn entfernen.\n> </warns:{self._cid('warns')}> - Warnliste anzeigen.\n> </automod hinzufügen:{self._cid('automod')}> - Automod einrichten.\n> </automod entfernen:{self._cid('automod')}> - Automod löschen.\n> </automod anzeigen:{self._cid('automod')}> - Automod anzeigen.\n> </modlog:{self._cid('modlog')}> - Modlog setzen.\n> </capslock:{self._cid('capslock')}> - Capslock-Schutz.\n> </blacklist:{self._cid('blacklist')}> - Wörter blockieren.",
            "Info": f"> <:Astra_support:1141303923752325210> Erhalte nützliche Infos zu Usern, Server oder dem Bot. Alles Wichtige schnell abrufbar.\n\n> **👥 × User Befehle:**\n> </help:{self._cid('help')}> - Hilfe anzeigen.\n> </about:{self._cid('about')}> - Infos über Astra.\n> </invite:{self._cid('invite')}> - Bot einladen.\n> </support:{self._cid('support')}> - Supportserver joinen.\n> </ping:{self._cid('ping')}> - Bot-Ping.\n> </uptime:{self._cid('uptime')}> - Bot-Uptime.\n> </info kanal:{self._cid('info')}> - Kanalinfos.\n> </info server:{self._cid('info')}> - Serverinfos.\n> </info rolle:{self._cid('info')}> - Rolleninfos.\n> </info user:{self._cid('info')}> - Userinfos.\n> </info wetter:{self._cid('info')}> - Wetterinfos.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Fun": f"> <:Astra_support:1141303923752325210> Bringe Spaß in den Chat mit Filtern, Memes und mehr. Ideal für lockere Unterhaltung.\n\n> **👥 × User Befehle:**\n> </wanted:{self._cid('wanted')}> - Wanted Poster.\n> </pix:{self._cid('pix')}> - Pixel-Effekt.\n> </wasted:{self._cid('wasted')}> - Wasted-Effekt.\n> </triggered:{self._cid('triggered')}> - Triggered-Effekt.\n> </gay:{self._cid('gay')}> - Pride-Effekt.\n> </color:{self._cid('color')}> - Farbe anzeigen.\n> </meme:{self._cid('meme')}> - Meme anzeigen.\n> </qrcode:{self._cid('qrcode')}> - QR-Code erstellen.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Eco": f"> <:Astra_support:1141303923752325210> Verdiene und verwalte virtuelles Geld. Spiele, arbeite oder handle mit anderen Usern.\n\n> **👥 × User Befehle:**\n> </economy balance:{self._cid('economy')}> - Kontostand.\n> </economy deposit:{self._cid('economy')}> - Einzahlen.\n> </economy withdraw:{self._cid('economy')}> - Abheben.\n> </economy leaderboard:{self._cid('economy')}> - Rangliste.\n> </economy beg:{self._cid('economy')}> - Betteln.\n> </economy rob:{self._cid('economy')}> - Überfallen.\n> </economy rps:{self._cid('economy')}> - Schere, Stein, Papier.\n> </economy slot:{self._cid('economy')}> - Slots.\n> </economy coinflip:{self._cid('economy')}> - Münzwurf.\n> </economy blackjack:{self._cid('economy')}> - Blackjack.\n> </job list:{self._cid('job')}> - Jobs anzeigen.\n> </job apply:{self._cid('job')}> - Job annehmen.\n> </job quit:{self._cid('job')}> - Job kündigen.\n> </job work:{self._cid('job')}> - Arbeiten.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "Messages": f"> <:Astra_support:1141303923752325210> Verwalte Willkommens-, Abschieds- und Youtube/Twitch Benachrichtigungen.\n\n> **👥 × User Befehle:**\n> </joinmsg:{self._cid('joinmsg')}> - Join-Message.\n> </leavemsg:{self._cid('leavemsg')}> - Leave-Message.\n> </autoreact:{self._cid('autoreact')}> - Auto-Reaction.\n> </embedfy:{self._cid('embedfy')}> - Embed erstellen.\n\n> **👮‍♂ × Team Befehle:**\n> </benachrichtigung youtube:{self._cid('benachrichtigung')}> - YouTube-Kanal hinzufügen oder entfernen\n> </benachrichtigung twitch:{self._cid('benachrichtigung')}> - Twitch-Kanal hinzufügen oder entfernen",
            "Minigames": f"> <:Astra_support:1141303923752325210> Spiele direkt im Chat und fordere dich oder andere heraus.\n\n> **👥 × User Befehle:**\n> </emojiquiz:{self._cid('emojiquiz')}> - Emojiquiz.\n> </hangman:{self._cid('hangman')}> - Hangman.\n> </snake start:{self._cid('snake')}> - Snake.\n> </snake highscore:{self._cid('snake')}> - Highscore anzeigen.\n> </guessthenumber:{self._cid('guessthenumber')}> - Zahlen raten.\n> </counting:{self._cid('counting')}> - Zählen.\n\n> **👮‍♂ × Team Befehle:**\n> Keine Team Befehle.",
            "backups": f"> <:Astra_support:1141303923752325210> Sichere deinen Server mit einem Klick – Backups erstellen, wiederherstellen oder rückgängig machen. Immer sicher, immer unter Kontrolle.\n\n> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </backup create:{self._cid('backup create')}> - Erstellt sofort ein Backup und gibt den Code zurück\n> </backup load:{self._cid('backup load')}> - Stellt ein Backup wieder her und zeigt Fortschritt.\n> </backup undo:{self._cid('backup undo')}> - Entfernt alles, was beim letzten Restore-Job hinzugefügt wurde.\n> </backup status:{self._cid('backup status')}> - Zeigt den Status des letzten Backup/Restore/Undo-Jobs.\n> </backup delete:{self._cid('backup delete')}> - Löscht ein Backup per Code und bereinigt verknüpfte Jobs.\n> </backup latest:{self._cid('backup latest')}> - Zeigt den letzten Backup-Code dieser Guild."
        }

    @app_commands.command(name="help", description="Zeigt dir eine Liste aller Befehle an.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def help(self, interaction: discord.Interaction):
        view = View(timeout=None)
        view.add_item(Dropdown(self))  # <-- hier war der Fehler
        view.add_item(WebsiteButton())

        delta_uptime = datetime.utcnow() - self.uptime
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        embed = discord.Embed(
            colour=discord.Colour.blue(),
            title="Help Menü",
            description=(
                "<:Astra_info:1141303860556738620> **Wichtige Informationen**\n"
                "Hier findest du alle Commands.\n"
                "Falls du Hilfe brauchst, komm auf unseren [Support Server ➚](https://discord.gg/eatdJPfjWc).\n\n"
                f"**Uptime:** {days}d {hours}h {minutes}m {seconds}s\n"
                f"**Ping:** {self.bot.latency * 1000:.0f} ms\n\n"
            )
        )

        embed.add_field(
            name="Über Astra",
            value=(
                "> <:Astra_support:1141303923752325210> Astra ist ein vielseitiger Discord-Bot mit Moderation, Minigames, "
                "Economy, Levelsystem und mehr – entwickelt, um deinen Server zu verwalten und zu beleben.\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="Letzte Updates",
            value=(
                "> <:Astra_file1:1141303837181886494> Backup-System: `/backup create`, `/backup load`, `/backup undo`\n"
                "> <:Astra_news:1141303885533827072> Benachrichtigungssystem: `/benachrichtigung youtube/twitch`\n"
                "> <:Astra_cookie:1141303831293079633> Economy: `/job`, `/economy`, `/economy blackjack`\n"
                "> <:Astra_minigames:1141303876528648232> Minigames: `/hangman`, `/snake`, `/emojiquiz`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Links",
            value=(
                "[Einladen](https://astra-bot.de/invite)"
                " | [Support](https://discord.gg/eatdJPfjWc)"
                " | [Voten](https://top.gg/bot/XXXXXXXXXXXX/vote)"
            ),
            inline=False
        )

        # safer: avatar/icon können None sein
        author_icon = getattr(interaction.client.user.display_avatar, "url", None)
        embed.set_author(name="Astra – Hilfe", icon_url=author_icon)

        guild_icon_url = getattr(getattr(interaction.guild, "icon", None), "url", None)
        embed.set_footer(text="Astra Development ©2025", icon_url=guild_icon_url)

        # Banner: Entweder absolute URL ODER als Attachment senden (siehe unten)
        embed.set_image(url="https://astra-bot.de/assets/Neuer-Astra-Banner-animiert.gif")

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))