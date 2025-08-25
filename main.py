import discord
import requests
import json
import random
from waitress import serve
import threading
import httpx
from discord.ext import commands, tasks
from discord.app_commands import AppCommandError
from discord import app_commands
from discord.app_commands import Group
from flask import Flask, request, jsonify
import io
import hashlib
import json
import platform
import datetime
import tempfile
from pathlib import Path
from topgg import WebhookManager
import math
import traceback
import asyncio
import topgg
import aiomysql
import jishaku
import os
import logging
import time
from dotenv import load_dotenv
import aiohttp
from datetime import datetime, timezone
from typing import Literal

import re

SCHEMA_PATH = "/root/Astra/opt/schema.sql"  # <- Pfad zu deiner Datei

async def run_sql_file(pool, path: str):
    p = Path(path)
    if not p.exists():
        logging.error(f"[DB] SQL-Datei nicht gefunden: {path}")
        return

    raw = p.read_text(encoding="utf-8")

    # -- Kommentare entfernen (-- … und /* … */), dann an ';' splitten
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)          # block comments
    lines = []
    for line in raw.splitlines():
        # entferne Zeilenkommentare, aber nicht in Strings (einfacher Ansatz reicht hier)
        line = re.sub(r"--.*$", "", line)
        lines.append(line)
    cleaned = "\n".join(lines)

    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in statements:
                try:
                    await cur.execute(stmt)
                except Exception as e:
                    logging.error(f"[DB] Fehler in Statement:\n{stmt}\n{e}")

logging.basicConfig(
    level=logging.INFO,  # oder DEBUG für mehr Details
    format="%(asctime)s - %(levelname)s - %(message)s"
)

intents = discord.Intents.default()
intents.message_content = True

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
host = os.getenv('host')
benutzer = os.getenv('benutzer')
password_db = os.getenv('password_db')
db_name = os.getenv('db_name')

def convert(time):
    pos = ["s", "m", "h", "d", "w"]
    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24, "w": 3600 * 24 * 7}
    unit = time[-1]
    if unit not in pos:
        return -1
    try:
        val = int(time[:-1])
    except Exception:
        return -2
    return val * time_dict[unit]


class Astra(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="astra!", help_command=None, case_insensitive=True,
                         intents=discord.Intents.all())
        self.topggpy = None
        self.task = False
        self.task2 = False
        self.task3 = False
        self.pool = None  # Pool-Objekt hier zentral gespeichert
        self.initial_extensions = [
            "cogs.errors",
            "cogs.notifier",
            "cogs.backups",
            "cogs.help",
            "cogs.goals",
            "cogs.dev",
            "cogs.emojiquiz",
            "cogs.hangman",
            "cogs.economy",
            "cogs.meta",
            "cogs.mod",
            "cogs.astra",
            "cogs.fun",
            "cogs.tempchannel",
            "cogs.afk",
            "cogs.joinrole",
            "cogs.botrole",
            "cogs.reactionrole",
            "cogs.welcome",
            "cogs.leave",
            "cogs.modlog",
            "cogs.autoreact",
            "cogs.blacklist",
            "cogs.warns",
            "cogs.guessthenumber",
            "cogs.counting",
            "cogs.tags",
            "cogs.capslock",
            "cogs.globalchat",
            "cogs.ticket",
            "cogs.levels",
            "cogs.snake"
        ]

    async def setup_hook(self):
        try:
            dbl_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjExMTM0MDM1MTEwNDUxMDc3NzMiLCJib3QiOnRydWUsImlhdCI6MTcwNTU4ODgxNn0.aX0_b94xKLSPLaEweiWojdU2LCOOmbhXQfMH_-3gc_8'  # set this to your bot's Top.gg token
            self.topggpy = topgg.DBLClient(self, dbl_token)
            bot.topgg_webhook = topgg.WebhookManager(bot).dbl_webhook("/dblwebhook", "test")
            await bot.topgg_webhook.run(8082)
            await self.connect_db()
            await self.init_tables()
            await self.load_cogs()
            self.tree.add_command(Giveaway())
            self.tree.add_command(Reminder())
            logging.info("Astra ist online!")
            await asyncio.sleep(3)
            logging.info("[PANEL-INFO] Script started!")
            self.keep_alive_task = self.loop.create_task(self.keep_db_alive())
        except Exception as e:
            logging.error(f"❌ Fehler beim Setup:\n{e}")

    async def keep_db_alive(self):
        while True:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")  # Einfacher Testbefehl, um die Verbindung aufrechtzuerhalten
            await asyncio.sleep(120)  # Alle 2 Minuten

    async def connect_db(self):
        """Stellt den DB-Pool her und speichert ihn in self.pool"""
        self.pool = await aiomysql.create_pool(
            host=host,
            port=3306,
            user=benutzer,
            password=password_db,
            db=db_name,
            autocommit=True,
            pool_recycle=3600,
            connect_timeout=5,
            maxsize=50
        )
        logging.info("✅ DB-Verbindung erfolgreich")

    async def init_tables(self):
        """Erstellt/Registriert Tasks und führt einen DB-Healthcheck aus."""
        await run_sql_file(self.pool, SCHEMA_PATH)

        # DB-Healthcheck
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        logging.info("✅ DB erreichbar")

        # Aiomysql anstoßen
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:

                # --- Reminder-Tasks (deine bestehende reminder-Tabelle) ---
                if not self.task:
                    self.task = True
                    # Nur zukünftige Reminder laden; wenn 'time' TEXT ist, trotzdem als int vergleichbar, wenn Unix-Zeit
                    await cur.execute(
                        "SELECT time FROM reminder WHERE time REGEXP '^[0-9]+$' AND CAST(time AS UNSIGNED) > UNIX_TIMESTAMP()")
                    eintraege = await cur.fetchall()

                    async def starte_reminder_tasks():
                        for (t_str,) in eintraege:
                            try:
                                t2 = datetime.fromtimestamp(int(t_str), timezone.utc)
                                asyncio.create_task(funktion(t2))
                                await asyncio.sleep(0.2)
                            except Exception as e:
                                logging.error(f"❌ Reminder-Fehler: {e}")

                    asyncio.create_task(starte_reminder_tasks())

                # --- Vote-Reminder (topgg.next_vote_epoch) ---
                if not self.task2:
                    self.task2 = True
                    await cur.execute("SELECT next_vote_epoch FROM topgg WHERE next_vote_epoch > UNIX_TIMESTAMP()")
                    eintraege2 = await cur.fetchall()

                    async def starte_voterole_tasks():
                        for (ts,) in eintraege2:
                            try:
                                if ts is None:
                                    continue
                                when = datetime.fromtimestamp(int(ts), timezone.utc)
                                asyncio.create_task(funktion2(when))
                                await asyncio.sleep(0.05)
                            except Exception as e:
                                logging.error(f"❌ Reminder-Replay-Fehler (ts={ts}): {e}")

                    asyncio.create_task(starte_voterole_tasks())

                # --- Giveaway-Tasks ---
                if not self.task3:
                    self.task3 = True
                    await cur.execute(
                        "SELECT time, guildID, messageID, channelID FROM giveaway_active WHERE time REGEXP '^[0-9]+$' AND CAST(time AS UNSIGNED) > UNIX_TIMESTAMP()")
                    eintraege3 = await cur.fetchall()

                    async def starte_giveaway_tasks():
                        for time_str, guild_id, message_id, channel_id in eintraege3:
                            try:
                                t2 = datetime.fromtimestamp(int(time_str), timezone.utc)
                                msg_id = int(message_id)
                                asyncio.create_task(gwtimes(t2, msg_id))
                                await asyncio.sleep(0.2)
                            except Exception as e:
                                logging.error(f"❌ Giveaway-Fehler: {e}")

                    asyncio.create_task(starte_giveaway_tasks())

        logging.info("✅ Tasks Registered!")

    async def load_cogs(self):
        """Lädt alle Cogs"""
        geladen, fehler = 0, 0

        # Optional: jishaku laden, aber Fehler ignorieren
        try:
            await self.load_extension("jishaku")
            logging.info("🧪 jishaku erfolgreich geladen")
        except Exception as e:
            logging.error("⚠️  jishaku konnte nicht geladen werden:", e)

        for ext in self.initial_extensions:
            logging.info(f"🔄 Lade: {ext}")
            try:
                await self.load_extension(ext)
                geladen += 1
                logging.info(f"✅ Erfolgreich geladen: {ext}")
            except Exception:
                fehler += 1
                logging.error(f'❌ Fehler beim Laden von: {ext}')
                traceback.print_exc()
                logging.info('---------------------------------------------')

        gesamt = geladen + fehler
        logging.info(f"\n📦 Cogs geladen: {geladen}/{gesamt} erfolgreich ✅")
        if fehler > 0:
            logging.error(f"❗ {fehler} Cog(s) konnten nicht geladen werden.")

    async def on_message(self, msg):
        if msg.author.bot:
            return
        await bot.process_commands(msg)

        botcreated_ts = int(bot.user.created_at.timestamp())

        if msg.content in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
            embed = discord.Embed(
                title="Astra",
                url="https://astra-bot.de/support",
                colour=discord.Colour.blue(),
                description=(
                    f"Hallo Discord! 👋\n"
                    f"Ich bin **Astra**, geboren am <t:{botcreated_ts}:D>. "
                    f"Ich bringe praktische Systeme wie ein Level- und Ticketsystem, Moderationstools, "
                    f"Automod-Schutz, Statistiken, temporäre Sprachkanäle und weitere hilfreiche Funktionen mit. "
                    f"Alle Befehle findest du bequem als **Slash-Befehle** (z. B. `/help`).\n\n"
                    f"Falls du Fragen oder Probleme hast, besuche gerne unseren "
                    f"**[Support-Server ↗](https://astra-bot.de/support)**. "
                    f"Wenn ich dein Interesse geweckt habe, kannst du mich "
                    f"**[hier einladen ↗](https://astra-bot.de/invite)** "
                    f"und direkt ausprobieren 🚀"
                )
            )

            embed.set_author(
                name=str(msg.author),
                icon_url=msg.author.avatar.url if msg.author.avatar else None
            )
            if msg.guild and msg.guild.icon:
                embed.set_thumbnail(url=msg.guild.icon.url)
            embed.set_footer(
                text="Astra Development ©2025 • Mehr Infos auf unserem Support-Server",
                icon_url=msg.guild.icon.url if msg.guild and msg.guild.icon else None
            )

            await msg.channel.send(embed=embed)
            await bot.process_commands(msg)

    @staticmethod
    def find_translatable_strings(path):
        string_regex = re.compile(r'["\'](.*?)["\']')
        translatable = []

        # Ordner cogs durchsuchen
        cogs_path = os.path.join(path, "cogs")
        if os.path.exists(cogs_path):
            for root, dirs, files in os.walk(cogs_path):
                for file in files:
                    if file.endswith(".py"):
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            content = f.read()
                            matches = string_regex.findall(content)
                            for match in matches:
                                if any(word in match.lower() for word in
                                       ["du", "bitte", "nicht", "kannst", "coin", "rolle", "hilfe", "server"]):
                                    translatable.append(match)

        # main.py separat prüfen
        main_py_path = os.path.join(path, "main.py")
        if os.path.isfile(main_py_path):
            with open(main_py_path, "r", encoding="utf-8") as f:
                content = f.read()
                matches = string_regex.findall(content)
                for match in matches:
                    if any(word in match.lower() for word in
                           ["du", "bitte", "nicht", "kannst", "coin", "rolle", "hilfe", "server"]):
                        translatable.append(match)

        return translatable


bot = Astra()


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class VoteView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Auch Voten",
                url="https://top.gg/bot/1113403511045107773/vote",
                emoji=discord.PartialEmoji(name="Herz", id=1361007251434901664)
            )
        )



@bot.event
async def on_dbl_vote(data):
    logging.info(f"on_dbl_vote ausgelöst für User: {data.get('user')}")
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Test-Hook früh raus
            if data.get("type") == "test":
                return bot.dispatch('dbl_test', data)

            # --- User/Guild/Objekte ---
            user_id = int(data["user"])
            user = bot.get_user(user_id)
            if user is None:
                try:
                    user = await bot.fetch_user(user_id)
                except Exception:
                    logging.error(f"User {user_id} nicht gefunden")
                    return

            guild = bot.get_guild(1141116981697859736)
            if not guild:
                logging.error("Guild nicht gefunden!")
                return

            voterole = guild.get_role(1141116981756575875)
            channel = guild.get_channel(1361006871753789532)

            # --- Zeit/Vote-Logik ---
            now_utc = datetime.now(timezone.utc)
            now_ts = int(now_utc.timestamp())
            next_vote_ts = now_ts + 12 * 3600
            this_month = now_utc.date().replace(day=1)
            vote_increase = 2 if now_utc.weekday() in [4, 5, 6] else 1  # Fr/Sa/So doppelt

            # --- DB: topgg lesen/aktualisieren (nur diese Tabelle) ---
            await cur.execute("SELECT count, last_reset FROM topgg WHERE userID=%s", (user_id,))
            row = await cur.fetchone()

            if not row:
                member_votes = vote_increase
                await cur.execute(
                    "INSERT INTO topgg (userID, count, last_reset, last_vote, last_vote_epoch, next_vote_epoch) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, member_votes, this_month, now_utc, now_ts, next_vote_ts)
                )
            else:
                count, last_reset = row
                if not last_reset or last_reset < this_month:
                    count = 0
                member_votes = count + vote_increase
                await cur.execute(
                    "UPDATE topgg SET count=%s, last_reset=%s, last_vote=%s, last_vote_epoch=%s, next_vote_epoch=%s "
                    "WHERE userID=%s",
                    (member_votes, this_month, now_utc, now_ts, next_vote_ts, user_id)
                )

    # --- (Optional) aktuelle Monatsvotes von top.gg ---
    total_votes = 0
    try:
        votedata = await bot.topggpy.get_bot_info()
        total_votes = int(votedata.get("monthly_points", 0))
    except Exception:
        pass

    # --- Channel-Embed für den Vote ---
    embed = discord.Embed(
        title="Danke fürs Voten von Astra",
        description=(
            f"<:Astra_boost:1141303827107164270> `{user}({user.id})` hat für **Astra** gevotet.\n"
            f"Wir haben nun `{total_votes}` in diesem Monat.\n"
            f"Du hast diesen Monat bereits **{member_votes}** Mal gevotet.\n\n"
            "Du kannst alle 12 Stunden **[hier](https://top.gg/bot/1113403511045107773/vote)** voten."
        ),
        colour=discord.Colour.blue(),
        timestamp=now_utc
    )
    embed.set_thumbnail(
        url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg"
    )
    embed.set_footer(
        text="Danke für deinen Support",
        icon_url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg"
    )

    # --- Rolle vergeben (beim Vote) ---
    member = guild.get_member(user_id)
    if not member:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            logging.error(f"Member {user_id} nicht gefunden")
            member = None

    if member and voterole:
        try:
            await member.add_roles(voterole, reason="Voterole vergeben (Vote erkannt)")
        except Exception as e:
            logging.error(f"Fehler beim Hinzufügen der Rolle an {user_id}: {e}")

    # --- Channel-Post mit Button ---
    try:
        if channel:
            await channel.send(embed=embed, view=VoteView())
    except Exception as e:
        logging.error(f"Fehler beim Senden im Channel: {e}")

    # --- Reminder (DM) für 12h terminieren ---
    when = datetime.fromtimestamp(next_vote_ts, timezone.utc)
    logging.info(f"[VoteReminder] scheduled DM for {user_id} at {when.isoformat()} (ts={next_vote_ts})")
    asyncio.create_task(funktion2(when))




@bot.event
async def on_dbl_test(data):
    """An event that is called whenever someone tests the webhook system for your bot on Top.gg."""
    user = bot.get_user(int(data["user"]))
    guild = bot.get_guild(1141116981697859736)
    data2 = await bot.topggpy.get_bot_info()
    votes = int(data2["monthly_points"])
    channel = guild.get_channel(1361006871753789532)
    astra = bot.get_user(int(data['bot']))
    embed = discord.Embed(title="Test Vote Erfolgreich",
                          description=f"<:Astra_boost:1141303827107164270> ``{user}({user.id})`` hat für {astra} gevoted.\nWir haben nun ``{votes}`` Votes diesen Monat.\n\nDu kannst alle 12 Stunden **[hier](https://top.gg/bot/811733599509544962/vote)** voten.",
                          colour=discord.Colour.red(), timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(
        url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg")
    embed.set_footer(text="Danke für deinen Support",
                     icon_url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg")
    msg = await channel.send(embed=embed)
    heart = bot.get_emoji(1361007251434901664)
    await msg.add_reaction(heart)

def all_app_commands(bot):
    global_commands = bot.tree.get_commands()
    from itertools import chain
    guild_commands = chain.from_iterable(bot.tree._guild_commands.values())
    all_commands = list(global_commands) + list(guild_commands)
    # Optional unique machen:
    seen = set()
    unique = []
    for cmd in all_commands:
        sig = (cmd.name, getattr(cmd, "type", None))
        if sig not in seen:
            seen.add(sig)
            unique.append(cmd)
    return unique

@bot.event
async def on_ready():
    servercount = len(bot.guilds)
    usercount = sum(guild.member_count for guild in bot.guilds)
    commandCount = len(all_app_commands(bot))
    channelCount = sum(len(guild.channels) for guild in bot.guilds)

    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Tabelle erstellen, falls sie noch nicht existiert

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS website_stats (
                    id INT PRIMARY KEY,
                    servercount INT,
                    usercount INT,
                    commandCount INT,
                    channelCount INT
                )
            """)

            # Prüfen, ob Zeile mit id=1 existiert
            await cur.execute("SELECT id FROM website_stats WHERE id=1")
            result = await cur.fetchone()

            if result is None:
                # Wenn nicht, initialen Datensatz anlegen
                await cur.execute(
                    "INSERT INTO website_stats (id, servercount, usercount, commandCount, channelCount) VALUES (1, %s, %s, %s, %s)",
                    (servercount, usercount, commandCount, channelCount)
                )
            else:
                # Ansonsten updaten
                await cur.execute(
                    "UPDATE website_stats SET servercount=%s, usercount=%s, commandCount=%s, channelCount=%s WHERE id=1",
                    (servercount, usercount, commandCount, channelCount)
                )

            # Dein bisheriger Präsenz- und Command-Teil
            await bot.change_presence(
                activity=discord.Game('Astra V2 out now! 💙'),
                status=discord.Status.online
            )
            bot.add_view(gw_button())


# Funktion, die nach 12h die Rolle entfernt und Erinnerungen per DM schickt
async def funktion2(when: datetime):
    await bot.wait_until_ready()

    # TZ-sicher: immer UTC-aware
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    await discord.utils.sleep_until(when)

    cutoff = int(when.timestamp())
    logging.info(f"[VoteReminder] firing at {datetime.now(timezone.utc).isoformat()} (cutoff={cutoff})")

    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Alle fälligen User direkt aus 'topgg'
            await cur.execute(
                "SELECT userID FROM topgg WHERE next_vote_epoch IS NOT NULL AND next_vote_epoch <= %s",
                (cutoff,)
            )
            results = await cur.fetchall()
            if not results:
                logging.info("[VoteReminder] no due users")
                return

            # Für Rollen-Entfernung (DM ist unabhängig von Guild)
            guild = bot.get_guild(1141116981697859736)
            voterole = guild.get_role(1141116981756575875) if guild else None

            for (user_id,) in results:
                # --- DM senden (unabhängig von Guild) ---
                try:
                    user = bot.get_user(user_id) or await bot.fetch_user(user_id)
                    embed = discord.Embed(
                        title="<:Astra_time:1141303932061233202> Du kannst wieder voten!",
                        url="https://top.gg/de/bot/1113403511045107773/vote",
                        description=(
                            "Der Cooldown von 12h ist vorbei. Es wäre schön, wenn du wieder votest.\n"
                            "Als Belohnung erhältst du eine spezielle Rolle auf unserem Support-Server."
                        ),
                        colour=discord.Colour.blue()
                    )
                    await user.send(embed=embed)
                    logging.info(f"[VoteReminder] DM erfolgreich an {user_id} gesendet")
                except Exception as e:
                    logging.warning(f"[VoteReminder] ❌ DM an {user_id} fehlgeschlagen: {e}")

                # --- Rolle entfernen (falls vorhanden) ---
                if guild and voterole:
                    try:
                        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                    except Exception:
                        member = None
                    if member and voterole in getattr(member, "roles", []):
                        try:
                            await member.remove_roles(voterole, reason="Voterole Cooldown abgelaufen")
                            logging.info(f"[VoteReminder] Rolle entfernt bei {user_id}")
                        except Exception as e:
                            logging.warning(f"[VoteReminder] Rolle entfernen fehlgeschlagen ({user_id}): {e}")

                # --- Reminder „verbrauchen“ ---
                try:
                    await cur.execute("UPDATE topgg SET next_vote_epoch=NULL WHERE userID=%s", (user_id,))
                except Exception as e:
                    logging.error(f"[VoteReminder] DB-Update next_vote_epoch=NULL fehlgeschlagen ({user_id}): {e}")

        # falls dein Pool nicht autocommit nutzt – schadet nicht:
        try:
            await conn.commit()
        except Exception:
            pass

    logging.info("[VoteReminder] finished")


async def gwtimes(when: datetime, messageid: int):
    await bot.wait_until_ready()
    await discord.utils.sleep_until(when=when)
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT guildID, channelID, userID, messageID FROM giveaway_entrys WHERE messageID = %s", (messageid,)
            )
            result = await cur.fetchall()
            await cur.execute(
                "SELECT ended, prize, winners, entrys, time, guildID, channelID FROM giveaway_active WHERE messageID = %s",
                (messageid,)
            )
            result3 = await cur.fetchone()
            if not result3:
                return

            ended = result3[0]
            price = result3[1]
            winners = result3[2]
            entrys = result3[3]
            time = result3[4]
            guildID = result3[5]
            channelID = result3[6]

            # == SICHERHEITSCHECKS für Guild & Channel ==
            guild = bot.get_guild(int(guildID))
            if guild is None:
                logging.error(f"Guild {guildID} not found for giveaway {messageid}!")
                return

            channel = guild.get_channel(int(channelID))
            if channel is None:
                logging.error(f"Channel {channelID} not found in guild {guildID} for giveaway {messageid}!")
                return

            try:
                msg = await channel.fetch_message(messageid)
            except Exception as e:
                logging.error(f"Giveaway message {messageid} not found in channel {channelID} in guild {guildID}: {e}")
                return

            time2 = datetime.fromtimestamp(int(time), tz=timezone.utc)

            # Niemand hat teilgenommen
            if not result:
                if int(ended) == 1:
                    return
                if int(ended) == 0:
                    embed = discord.Embed(
                        title=" ",
                        description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer.",
                        colour=discord.Colour.red()
                    )
                    await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                    await msg.reply("<:Astra_x:1141303954555289600> **Es gab nicht genügend Teilnehmer. Niemand hat das Gewinnspiel gewonnen.**")
                    await cur.execute(
                        "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s and messageID = %s",
                        (1, guild.id, channel.id, messageid)
                    )
                    await cur.execute("DELETE FROM giveway_ids WHERE messageID = %s", (messageid,))

            # Es gibt Teilnehmer
            if result:
                guildID = result[0][0]
                channelID = result[0][1]
                await cur.execute(
                    "SELECT ended, prize, winners, entrys, time FROM giveaway_active WHERE guildID = %s AND channelID = %s AND messageID = %s",
                    (guildID, channelID, messageid)
                )
                result2 = await cur.fetchone()
                ended = result2[0]
                if int(ended) == 1:
                    return
                if int(ended) == 0:
                    price = result2[1]
                    winners_amount = int(result2[2])
                    entrys = result2[3]
                    time = result2[4]
                    time2 = datetime.fromtimestamp(int(time), tz=timezone.utc)
                    participants = [userid[2] for userid in result]

                    # Gewinner bestimmen (Anzahl nie höher als Teilnehmer)
                    chosen_winners = []
                    if len(participants) > 0:
                        to_pick = min(len(participants), winners_amount)
                        chosen_winners = random.sample(participants, k=to_pick)
                    users = []
                    for id in chosen_winners:
                        idwinners = bot.get_user(id)
                        winembed = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Du hast ein Gewinnspiel auf [{guild.name}](https://discord.com/channels/{guild.id}/{channel.id}/{msg.id}) gewonnen.\n`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}",
                            colour=discord.Colour.yellow()
                        )
                        winembed.set_thumbnail(url=guild.icon.url)
                        try:
                            await idwinners.send(
                                "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                embed=winembed
                            )
                        except Exception:
                            pass
                        users.append(idwinners)
                    mentions = ", ".join(user.mention for user in users if user)
                    if entrys < 1 or not users:
                        embed = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer.",
                            colour=discord.Colour.red()
                        )
                        await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                        await msg.reply("<:Astra_x:1141303954555289600> Es gab nicht genügend Teilnehmer. Niemand hat das Gewinnspiel gewonnen.")
                        await cur.execute(
                            "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s and messageID = %s",
                            (1, guildID, channelID, messageid)
                        )
                        await cur.execute("DELETE FROM giveway_ids WHERE messageID = %s", (messageid,))
                    else:
                        embed = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer.",
                            colour=discord.Colour.red()
                        )
                        await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                        await msg.reply(f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen! Herzlichen Glückwunsch.")
                        await cur.execute(
                            "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s and messageID = %s",
                            (1, guildID, channelID, messageid)
                        )
                        await cur.execute("DELETE FROM giveway_ids WHERE messageID = %s", (messageid,))


class gw_button(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Teilnehmen', style=discord.ButtonStyle.green, custom_id='persistent_view_allg:join_gw', emoji="🎉")
    async def join_gw(self, interaction: discord.Interaction, button: discord.Button):
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await interaction.response.defer(ephemeral=True)
                await cur.execute(
                    "SELECT userID FROM giveaway_entrys WHERE userID = %s AND guildID = %s AND channelID = %s AND messageID = %s",
                    (interaction.user.id, interaction.guild.id, interaction.channel.id, interaction.message.id)
                )
                result = await cur.fetchone()
                await cur.execute(
                    "SELECT role, level, entrys, messageID, prize, winners, time, creatorID FROM giveaway_active WHERE guildID = %s AND channelID = %s AND messageID = %s",
                    (interaction.guild.id, interaction.channel.id, interaction.message.id)
                )
                result2 = await cur.fetchone()
                roleID = result2[0]
                level = result2[1]
                entrys = result2[2]
                messageID = result2[3]
                price = result2[4]
                winners = result2[5]
                time = result2[6]
                creatorID = result2[7]
                creator = bot.get_user(creatorID)
                time2 = datetime.fromtimestamp(int(time), tz=timezone.utc)

                # TEILNAHME (User ist NICHT drin)
                if not result:
                    # KEINE Anforderungen
                    if str(roleID) == "Not Set" and str(level) == "Not Set":
                        embed = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.",
                            colour=discord.Colour.blue()
                        )
                        embed.set_thumbnail(url=interaction.guild.icon.url)
                        embed.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embed)
                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                            (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                        )
                        await cur.execute(
                            "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                            (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                        )
                        successemb = discord.Embed(
                            title=f" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                            colour=discord.Colour.green()
                        )
                        successemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                embed=successemb
                            )
                        except Exception:
                            pass

                    # NUR ROLLE
                    if str(roleID).isnumeric() and level == "Not Set":
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        if role in interaction.user.roles:
                            embe = discord.Embed(
                                title=" ",
                                description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                                colour=discord.Colour.blue()
                            )
                            embe.set_thumbnail(url=interaction.guild.icon.url)
                            embe.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                            msg = await interaction.channel.fetch_message(messageID)
                            await msg.edit(embed=embe)
                            await cur.execute(
                                "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                                (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                            )
                            await cur.execute(
                                "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                            )
                            successemb = discord.Embed(
                                title=" ",
                                description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                                colour=discord.Colour.green()
                            )
                            successemb.set_thumbnail(url=interaction.guild.icon.url)
                            try:
                                await interaction.user.send(
                                    "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                    embed=successemb
                                )
                            except Exception:
                                pass
                        else:
                            failemb = discord.Embed(
                                title=f" ",
                                description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                                colour=discord.Colour.red()
                            )
                            failemb.set_thumbnail(url=interaction.guild.icon.url)
                            try:
                                await interaction.user.send(
                                    "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                    embed=failemb
                                )
                            except Exception:
                                pass

                    # NUR LEVEL
                    if roleID == "Not Set" and str(level).isnumeric():
                        await cur.execute(
                            "SELECT user_xp, user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                            (interaction.user.id, interaction.guild.id)
                        )
                        result = await cur.fetchone()
                        if not result:
                            try:
                                await interaction.user.send(
                                    "<:Astra_x:1141303954555289600> **Wir haben leider keine Einträge über dich gefunden. Schreibe erst eine Nachricht und versuche es erneut.**"
                                )
                            except Exception:
                                pass
                        else:
                            lvl_start = result[1]
                            if int(level) <= int(lvl_start):
                                emb = discord.Embed(
                                    title=" ",
                                    description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620>__**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> Klicke unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                    colour=discord.Colour.blue()
                                )
                                emb.set_thumbnail(url=interaction.guild.icon.url)
                                emb.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                                msg = await interaction.channel.fetch_message(messageID)
                                await msg.edit(embed=emb)
                                await cur.execute(
                                    "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                                    (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                                )
                                await cur.execute(
                                    "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                    (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                                )
                                successemb = discord.Embed(
                                    title=f" ",
                                    description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                                    colour=discord.Colour.green()
                                )
                                successemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                        embed=successemb
                                    )
                                except Exception:
                                    pass
                            else:
                                failemb = discord.Embed(
                                    title=f" ",
                                    description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                    colour=discord.Colour.red()
                                )
                                failemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                        embed=failemb
                                    )
                                except Exception:
                                    pass

                    # BEIDES
                    if str(roleID).isnumeric() and str(level).isnumeric():
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        await cur.execute(
                            "SELECT user_xp, user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                            (interaction.user.id, interaction.guild.id)
                        )
                        result5 = await cur.fetchone()
                        if not result5:
                            try:
                                await interaction.user.send(
                                    "<:Astra_x:1141303954555289600> **Wir haben leider keine Einträge über dich gefunden. Schreibe erst eine Nachricht und versuche es erneut.**"
                                )
                            except Exception:
                                pass
                        else:
                            lvl_start = result5[1]
                            if int(level) <= int(lvl_start) and role in interaction.user.roles:
                                em = discord.Embed(
                                    title=" ",
                                    description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                    colour=discord.Colour.blue()
                                )
                                em.set_thumbnail(url=interaction.guild.icon.url)
                                em.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                                msg = await interaction.channel.fetch_message(messageID)
                                await msg.edit(embed=em)
                                await cur.execute(
                                    "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                                    (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                                )
                                await cur.execute(
                                    "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                    (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                                )
                                successemb = discord.Embed(
                                    title=" ",
                                    description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                                    colour=discord.Colour.green()
                                )
                                successemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                        embed=successemb
                                    )
                                except Exception:
                                    pass
                            else:
                                failemb = discord.Embed(
                                    title=f" ",
                                    description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` und **Level {level}** um teilzunehmen.",
                                    colour=discord.Colour.red()
                                )
                                failemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                        embed=failemb
                                    )
                                except Exception:
                                    pass

                # ABMELDEN (User ist bereits drin)
                if result:
                    await cur.execute(
                        "DELETE FROM giveaway_entrys WHERE userID = %s AND guildID = %s AND messageID = %s",
                        (interaction.user.id, interaction.guild.id, interaction.message.id)
                    )
                    await cur.execute(
                        "UPDATE giveaway_active SET entrys = %s WHERE channelID = %s AND guildID = %s AND messageID = %s",
                        (max(int(entrys) - 1, 0), interaction.channel.id, interaction.guild.id, interaction.message.id)
                    )

                    # Embed aktualisieren (Teilnehmer-1)
                    if str(roleID).isnumeric() and str(level).isnumeric():
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        em = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                            colour=discord.Colour.blue()
                        )
                        em.set_thumbnail(url=interaction.guild.icon.url)
                        em.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=em)
                        failemb = discord.Embed(
                            title=f" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                            colour=discord.Colour.red()
                        )
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass

                    if str(roleID) == "Not Set" and str(level) == "Not Set":
                        embed = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.",
                            colour=discord.Colour.blue()
                        )
                        embed.set_thumbnail(url=interaction.guild.icon.url)
                        embed.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embed)
                        failemb = discord.Embed(
                            title=f" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                            colour=discord.Colour.red()
                        )
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass

                    if roleID == "Not Set" and str(level).isnumeric():
                        emb = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                            colour=discord.Colour.blue()
                        )
                        emb.set_thumbnail(url=interaction.guild.icon.url)
                        emb.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=emb)
                        failemb = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                            colour=discord.Colour.red()
                        )
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass

                    if str(roleID).isnumeric() and level == "Not Set":
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        embe = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                            colour=discord.Colour.blue()
                        )
                        embe.set_thumbnail(url=interaction.guild.icon.url)
                        embe.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embe)
                        failemb = discord.Embed(
                            title=" ",
                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                            colour=discord.Colour.red()
                        )
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass



@app_commands.guild_only()
class Giveaway(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="gewinnspiel",
            description="Alles rund um Gewinnspiele."
        )

    @app_commands.command(name="starten", description="Startet ein Gewinnspiel.")
    @app_commands.describe(preis="Der Preis des Gewinnspiels.")
    @app_commands.describe(kanal="Der Kanal, in dem das Gewinnspiel stattfinden soll.")
    @app_commands.describe(gewinner="Anzahl der Gewinner.")
    @app_commands.describe(zeit="Dauer des Gewinnspiels (z.B. 10m, 2h, 3d).")
    @app_commands.describe(rolle="Optional: Rolle, die teilnehmen darf.")
    @app_commands.describe(level="Optional: Mindestlevel für Teilnahme.")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gw_start(self, interaction: discord.Interaction, *, preis: str, kanal: discord.TextChannel, gewinner: int, zeit: str, rolle: discord.Role = None, level: int = None):
        """Startet ein Gewinnspiel."""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Validierung Levelsystem (wenn benötigt)
                if (rolle or level):
                    if level:
                        await cur.execute("SELECT enabled FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,))
                        enabled = await cur.fetchone()
                        if not enabled or enabled[0] == 0:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> Das Levelsystem ist auf diesem Server deaktiviert.",
                                ephemeral=True)
                            return
                # Zeit umrechnen
                time1 = convert(zeit)  # → float oder int (Sekunden, z. B. 43200 für 12h)
                t1 = math.floor(discord.utils.utcnow().timestamp() + time1)  # ergibt korrekten Unix-Timestamp
                t2 = datetime.fromtimestamp(t1, tz=timezone.utc)  # ✅ Zeitzone-aware!

                # Embed-Description bauen (abhängig von Anforderungen)
                req_lines = []
                if rolle:
                    req_lines.append(f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{rolle.name}` um teilzunehmen.")
                if level:
                    req_lines.append(f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.")

                req_text = "\n".join(req_lines) if req_lines else ""
                if req_text:
                    req_text = f"\n{req_text}"

                embed = discord.Embed(
                    title=" ",
                    description=(
                        f"🏆 Preis: {preis}\n"
                        "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                        "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                        f"<:Astra_arrow:1141303823600717885> Erstellt von {interaction.user.mention}\n"
                        f"<:Astra_arrow:1141303823600717885> **{gewinner}** Gewinner\n"
                        f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(t2, 'R')}\n"
                        f"<:Astra_arrow:1141303823600717885> **0** Teilnehmer\n\n"
                        "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                        "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen."
                        f"{req_text}"
                    ),
                    colour=discord.Colour.blue()
                )
                embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)

                msg = await kanal.send("🎉 **Neues Gewinnspiel** 🎉", embed=embed, view=gw_button())
                asyncio.create_task(gwtimes(t2, msg.id))  # Deine Task für das Beenden

                # Einträge für Rolle und Level
                role_id = rolle.id if rolle else "Not Set"
                level_val = level if level else "Not Set"

                await cur.execute(
                    "INSERT INTO giveaway_active(guildID, creatorID, channelID, entrys, messageID, prize, winners, time, role, level, ended) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (interaction.guild.id, interaction.user.id, kanal.id, 0, msg.id, preis, gewinner, t1, role_id, level_val, 0)
                )

                # gwID Management (verbessert)
                await cur.execute("SELECT gwID FROM giveway_ids WHERE guildID = %s", (interaction.guild.id,))
                gwid_result = await cur.fetchall()
                new_gw_id = (len(gwid_result) + 1) if gwid_result else 1
                await cur.execute(
                    "INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES (%s, %s, %s)",
                    (interaction.guild.id, new_gw_id, msg.id)
                )

                await interaction.response.send_message(
                    f"**<:Astra_accept:1141303821176422460> Das Gewinnspiel wird in {kanal.mention} stattfinden.**"
                )

    @app_commands.command(name="verwalten", description="Verwalte ein Gewinnspiel.")
    @app_commands.describe(aktion="Aktion, die durchgeführt werden soll.")
    @app_commands.describe(messageid="Nachrichten-ID des Gewinnspiels (falls benötigt).")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gw_verwalten(self, interaction: discord.Interaction, *, aktion: Literal['Gewinnspiel beenden(Nachrichten ID angeben)', 'Gewinnspiel neu würfeln(Nachrichten ID angeben)', 'Gewinnspiele Anzeigen'],  messageid: str = None):
        """Verwalte ein Gewinnspiel."""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:

                if aktion == "Gewinnspiele Anzeigen":
                    await cur.execute(
                        "SELECT gwID, messageID FROM giveway_ids WHERE guildID = %s",
                        (interaction.guild.id,)
                    )
                    result = await cur.fetchall()
                    if not result:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Es gibt keine aktiven Gewinnspiele auf diesem Server.**",
                            ephemeral=True
                        )
                        return

                    embed = discord.Embed(
                        title=f"Alle Gewinnspiele auf {interaction.guild.name}",
                        description="Um ein Gewinnspiel zu erstellen, nutze `/gewinnspiel starten`.",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    for gwid, messageid in result:
                        await cur.execute(
                            "SELECT time FROM giveaway_active WHERE guildID = %s AND messageID = %s",
                            (interaction.guild.id, messageid)
                        )
                        time_result = await cur.fetchone()
                        if time_result:
                            unix_time = int(time_result[0])
                            embed.add_field(
                                name=f"ID: {gwid}",
                                value=f"<:Astra_time:1141303932061233202> Das Gewinnspiel endet: <t:{unix_time}:F>",
                                inline=False
                            )
                    await interaction.response.send_message(embed=embed)
                    return

                if not messageid:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Bitte gib eine Nachrichten-ID an!**",
                        ephemeral=True
                    )
                    return

                if aktion == "Gewinnspiel beenden(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT guildID, channelID, userID FROM giveaway_entrys WHERE messageID = %s",
                        (messageid,)
                    )
                    entrys_result = await cur.fetchall()
                    await cur.execute(
                        "SELECT prize, winners, entrys, time, guildID, channelID, ended FROM giveaway_active WHERE messageID = %s",
                        (messageid,)
                    )
                    gw = await cur.fetchone()
                    if not gw:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Kein aktives Gewinnspiel mit dieser Nachricht gefunden.**",
                            ephemeral=True
                        )
                        return
                    preis, winners, entrys, end_time, guildID, channelID, ended = gw

                    guild = bot.get_guild(guildID)
                    channel = guild.get_channel(channelID)
                    msg = await channel.fetch_message(int(messageid))
                    time2 = datetime.fromtimestamp(int(end_time), tz=timezone.utc)

                    if ended:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Gewinnspiel ist bereits beendet!**",
                            ephemeral=True
                        )
                        return

                    if not entrys_result:
                        # Niemand hat teilgenommen
                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {preis}\n"
                                "`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                                "<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n"
                                f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                                "<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer."
                            ),
                            colour=discord.Colour.red()
                        )
                        await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                        await msg.reply(
                            "<:Astra_x:1141303954555289600> **Es gab nicht genügend Teilnehmer. Niemand hat das Gewinnspiel gewonnen.**"
                        )
                    else:
                        # Gewinner ziehen
                        teilnehmer = [row[2] for row in entrys_result]
                        winners_count = min(len(teilnehmer), int(winners))
                        gewinner_ids = random.sample(teilnehmer, k=winners_count)
                        users = [bot.get_user(uid) for uid in gewinner_ids]
                        mentions = ", ".join(user.mention for user in users if user)

                        # Gewinnenachricht an die User schicken
                        for user in users:
                            if user:
                                winembed = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {preis}\n"
                                        "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        f"`🎉` Du hast ein Gewinnspiel auf [{guild.name}](https://discord.com/channels/{guild.id}/{channel.id}/{msg.id}) gewonnen.\n"
                                        f"`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}"
                                    ),
                                    colour=discord.Colour.yellow()
                                )
                                winembed.set_thumbnail(url=guild.icon.url)
                                try:
                                    await user.send(
                                        "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                        embed=winembed
                                    )
                                except Exception:
                                    pass  # User hat DMs geschlossen

                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {preis}\n"
                                "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                                f"<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n"
                                f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer."
                            ),
                            colour=discord.Colour.red()
                        )
                        await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                        await msg.reply(
                            f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen. Herzlichen Glückwunsch."
                        )

                    # Giveaway als beendet markieren und ID entfernen
                    await cur.execute(
                        "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                        (1, guildID, channelID, messageid)
                    )
                    await cur.execute(
                        "DELETE FROM giveway_ids WHERE messageID = %s", (messageid,)
                    )
                    await interaction.response.send_message(
                        "<:Astra_accept:1141303821176422460> **Das Gewinnspiel wurde erfolgreich beendet.**",
                        ephemeral=True
                    )
                    return

                if aktion == "Gewinnspiel neu würfeln(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT channelID, prize, winners, entrys, time, ended FROM giveaway_active WHERE guildID = %s AND messageID = %s",
                        (interaction.guild.id, int(messageid))
                    )
                    gw = await cur.fetchone()
                    if not gw:
                        await interaction.response.send_message(
                            f"<:Astra_x:1141303954555289600> Es gibt kein Gewinnspiel mit der ID {messageid}!",
                            ephemeral=True
                        )
                        return

                    channelID, preis, winners, entrys, end_time, ended = gw
                    if not ended:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Gewinnspiel läuft noch!**",
                            ephemeral=True
                        )
                        return

                    channel = interaction.guild.get_channel(channelID)
                    msg = await channel.fetch_message(int(messageid))

                    await cur.execute(
                        "SELECT userID FROM giveaway_entrys WHERE messageID = %s AND guildID = %s AND channelID = %s",
                        (int(messageid), interaction.guild.id, channelID)
                    )
                    result2 = await cur.fetchall()

                    teilnehmer = [row[0] for row in result2]
                    winners_count = min(len(teilnehmer), int(winners))
                    if winners_count < 1:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Gewinnspiel konnte nicht neu ausgelost werden, da es nicht genügend Teilnehmer gab.**",
                            ephemeral=True
                        )
                        return

                    gewinner_ids = random.sample(teilnehmer, k=winners_count)
                    users = [bot.get_user(uid) for uid in gewinner_ids]
                    mentions = ", ".join(user.mention for user in users if user)

                    time2 = datetime.fromtimestamp(int(end_time), tz=timezone.utc)
                    # Gewinne-Embed verschicken
                    for user in users:
                        if user:
                            winembed = discord.Embed(
                                title=" ",
                                description=(
                                    f"🏆 Preis: {preis}\n"
                                    "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                    f"`🎉` Du hast ein Gewinnspiel auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{channel.id}/{msg.id}) gewonnen.\n"
                                    f"`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}"
                                ),
                                colour=discord.Colour.yellow()
                            )
                            winembed.set_thumbnail(url=interaction.guild.icon.url)
                            try:
                                await user.send(
                                    "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                    embed=winembed
                                )
                            except Exception:
                                pass

                    embed = discord.Embed(
                        title=" ",
                        description=(
                            f"🏆 Preis: {preis}\n"
                            "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                            "<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                            f"<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n"
                            f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                            f"<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer."
                        ),
                        colour=discord.Colour.red()
                    )
                    await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                    await msg.reply(
                        f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen. Herzlichen Glückwunsch."
                    )

                    await interaction.response.send_message(
                        f"<:Astra_accept:1141303821176422460> **Ich habe das Gewinnspiel neu ausgelost, die neuen Gewinner sind {mentions}.**",
                        ephemeral=True
                    )


async def funktion(when: datetime):
    await bot.wait_until_ready()
    await discord.utils.sleep_until(when=when)
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT userID, grund FROM reminder")
            result = await cur.fetchall()
            if result == ():
                return
            if result:
                for eintrag in result:
                    userID = eintrag[0]
                    grund = eintrag[1]
                    user = bot.get_user(int(userID))
                    embed = discord.Embed(title="<:Astra_time:1141303932061233202> Erinnerung abgeschlossen.",
                                          description=f"Hier ist deine Erinnerung\n<:Astra_arrow:1141303823600717885> {grund}",
                                          colour=discord.Colour.blue())
                await user.send(embed=embed)
                await cur.execute("DELETE FROM reminder WHERE grund = (%s)", (grund))

@app_commands.guild_only()
class Reminder(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="erinnerung",
            description="Verwalte Erinnerungen."
        )

    @app_commands.command(name="erstellen", description="Setze eine Erinnerung.")
    @app_commands.describe(beschreibung="Beschreibung der Erinnerung.")
    @app_commands.describe(zeit="Wie lange bis zur Erinnerung.")
    async def reminder_set(self, interaction: discord.Interaction, beschreibung: str, zeit: Literal['1m', '3m', '5m', '10m', '20m', '30m', '45m', '1h', '2h', '5h', '10h', '12h', '18h', '1d', '2d', '5d', '6d', '1w', '2w', '4w']):
        """Setze eine Erinnerung."""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                description = beschreibung
                time = zeit
                await cur.execute("SELECT grund FROM reminder WHERE userID = (%s)",
                                  (interaction.user.id))
                result = await cur.fetchall()
                if result == ():
                    remindid = 1
                    time1 = convert(zeit)  # → float oder int (Sekunden, z. B. 43200 für 12h)
                    t1 = math.floor(discord.utils.utcnow().timestamp() + time1)  # ergibt korrekten Unix-Timestamp
                    t2 = datetime.fromtimestamp(t1, tz=timezone.utc)  # ✅ Zeitzone-aware!
                    asyncio.create_task(funktion(t2))
                    await cur.execute("INSERT INTO reminder(userID, grund, time, remindID) VALUES(%s, %s, %s, %s)",
                                      (interaction.user.id, description, t1, remindid))
                    embed = discord.Embed(
                        title=f"<:Astra_time:1141303932061233202> Erinnerung erstellt (ID {remindid})",
                        description=f"Erinnerung gesetzt auf {discord.utils.format_dt(t2, 'F')}\n<:Astra_arrow:1141303823600717885> {description}",
                        colour=discord.Colour.blue())
                    await interaction.response.send_message(embed=embed)
                if result:
                    time1 = convert(zeit)  # → float oder int (Sekunden, z. B. 43200 für 12h)
                    t1 = math.floor(discord.utils.utcnow().timestamp() + time1)  # ergibt korrekten Unix-Timestamp
                    t2 = datetime.fromtimestamp(t1, tz=timezone.utc)  # ✅ Zeitzone-aware!
                    asyncio.create_task(funktion(t2))
                    await cur.execute("INSERT INTO reminder(userID, grund, time, remindID) VALUES(%s, %s, %s, %s)",
                                      (interaction.user.id, description, t1, len(result) + 1))
                    embed = discord.Embed(
                        title=f"<:Astra_time:1141303932061233202> Erinnerung erstellt (ID {len(result) + 1})",
                        description=f"Erinnerung gesetzt auf {discord.utils.format_dt(t2, 'F')}\n<:Astra_arrow:1141303823600717885> {description}",
                        colour=discord.Colour.blue())
                    await interaction.response.send_message(embed=embed)

    @app_commands.command(name="anzeigen", description="Zeigt alle Erinnerungen an.")
    async def reminder_list(self, interaction: discord.Interaction):
        """Zeigt eine Liste aller gesetzten Erinnerungen."""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                memberid = interaction.user.id
                member = interaction.user
                await cur.execute("SELECT grund, remindID, time FROM reminder WHERE userID = (%s)",
                                  (interaction.user.id))
                result = await cur.fetchall()
                if result == ():
                    embed2 = discord.Embed(title=f"Alle Erinnerungen von {member}, {memberid}",
                                           description=f"{member.name} hat zur Zeit keine aktiven Erinnerungen.",
                                           color=discord.Color.blue())
                    await interaction.response.send_message(embed=embed2)

                else:
                    embed = discord.Embed(title=f"Alle Erinnerungen von {member.name}, {memberid}",
                                          description=f"Um eine Erinnerung zu setzen, nutze den Befehl `/erinnerung erstellen`.",
                                          color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    for eintrag in result:
                        reason = eintrag[0]
                        warnID = eintrag[1]
                        time = eintrag[2]
                        embed.add_field(name=f"ID: {warnID}",
                                        value=f"<:Astra_arrow:1141303823600717885>: {reason}\n<:Astra_time:1141303932061233202> Endet: <t:{time}:F>",
                                        inline=True)

                    await interaction.response.send_message(embed=embed)

    @app_commands.command(name="löschen", description="Löscht eine Erinnerung.")
    @app_commands.describe(id="Die ID der Erinnerung, die gelöscht werden soll.")
    async def reminder_delete(self, interaction: discord.Interaction, id: int):
        """Löscht eine gespeicherte Erinnerung anhand der ID."""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                member = interaction.user
                await cur.execute("SELECT remindID FROM reminder WHERE userID = (%s)", (interaction.user.id))
                result = await cur.fetchall()

                if result:
                    await cur.execute("DELETE FROM reminder WHERE userID = (%s) AND remindID = (%s)",
                                      (member.id, id))
                    embed2 = discord.Embed(title="Erinnerung Gelöscht",
                                           description=f"Die Erinnerung mit der ID ``{id}`` wurde gelöscht.",
                                           color=discord.Color.green())
                    await interaction.response.send_message(embed=embed2)
                if not result:
                    embed2 = discord.Embed(title="Keine Erinnerung gefunden",
                                           description=f"Es gibt keine Aktive Erinnerung mit der ID: ``{id}``.",
                                           color=discord.Color.green())
                    await interaction.response.send_message(embed=embed2)



@bot.command(aliases=["servers", ])
@commands.is_owner()
async def serverlist(ctx):
    global chunk
    activeservers = bot.guilds
    i = 1
    test = "\n".join(
        f"`{i + 1}` {guild.name}({guild.member_count}) — {guild.id}" for i, guild in enumerate(activeservers))
    try:
        for chunk in [test[i: i + 2000] for i in range(0, len(test), 2000)]:
            embed = discord.Embed(title="Liste in denen der Bot ist", description=chunk, color=0x3498db)
            embed.set_author(name=ctx.author, icon_url=ctx.me.avatar)
            await ctx.send("`Number` **Guildname(Guildmembercount) — Guildid**", embed=embed)
    except discord.HTTPException:
        embed = discord.Embed(title="List of servers the bot is in", description=chunk, color=0x3498db)
        embed.set_author(name=ctx.author, icon_url=ctx.me.avatar)
        await ctx.send(embed=embed)


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def advert(ctx):
    embed = discord.Embed(title="`🎃` Astra x Astra Support",
                          url="https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands",
                          description="Astra ist der einzige Bot, den Sie zur Verwaltung Ihres gesamten Servers benötigen. Es gibt viele Server, die Astra verwenden. Vielleicht sind Sie der Nächste?\n\n> __**Was bieten wir an?**__\n・<:Astra_ticket:1141833836204937347> Öffentliches Ticketsystem für Ihren Server\n・<:Astra_time:1141303932061233202> Automatische Moderation\n・<:Astra_messages:1141303867850641488> Willkommen/Nachrichten hinterlassen\n・<:Astra_settings:1141303908778639490> Joinrole&Botrole\n・<:Astra_herz:1141303857855594527> Reaktionsrollen\n・<:Astra_global1:1141303843993436200> Globalchat\n\n\n> __**Nützliche Links:**__\n・[Astra einladen ➚](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n・[Support erhalten ➚](https://discord.gg/eatdJPfjWc)",colour=discord.Colour.blue())
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/842039934142513152/879880068262940672/Astra-premium3.gif")
    embed.set_thumbnail(url=ctx.guild.icon.url)
    msg = await ctx.send("https://discord.gg/eatdJPfjWc", embed=embed)
    await ctx.message.delete()


@bot.command()
@commands.is_owner()
async def sync(ctx, serverid: int = None):
    """Synchronisiere bestimmte Commands."""
    if serverid is None:
        try:
            s = await bot.tree.sync()
            a = 0
            for command in s:
                a += 1
            globalembed = discord.Embed(color=discord.Color.orange(), title="Synchronisierung",
                                        description=f"Die Synchronisierung von `{a} Commands` wurde eingeleitet.\nEs wird ungefähr eine Stunde dauern, damit sie global angezeigt werden.")
            await ctx.send(embed=globalembed)
        except Exception as e:
            await ctx.send(f"**❌ Synchronisierung fehlgeschlagen**\n```\n{e}```")

    if serverid is not None:
        guild = bot.get_guild(int(serverid))
        if guild:
            try:
                s = await bot.tree.sync(guild=discord.Object(id=guild.id))
                a = 0
                for command in s:
                    a += 1
                localembed = discord.Embed(color=discord.Color.orange(), title="Synchronisierung",
                                           description=f"Die Synchronisierung von `{a} Commands` ist fertig.\nEs wird nur maximal eine Minute dauern, weil sie nur auf dem Server {guild.name} synchronisiert wurden.")
                await ctx.send(embed=localembed)
            except Exception as e:
                await ctx.send(f"**❌ Synchronisierung fehlgeschlagen**\n```\n{e}```")
        if guild is None:
            await ctx.send(f"❌ Der Server mit der ID `{serverid}` wurde nicht gefunden.")


app = Flask(__name__)

@app.route('/status')
def status():
    return jsonify(online=True)

def run_flask():
    serve(app, host="0.0.0.0", port=5000)  # produktionsreif, keine Warning

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(TOKEN)
