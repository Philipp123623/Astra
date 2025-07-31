import discord
import requests
import json
import random
import threading
import httpx
from discord.ext import commands, tasks
from discord.app_commands import AppCommandError
from discord import app_commands
from discord.app_commands import Group
from flask import Flask, request, jsonify
from topgg import WebhookManager
import math
import sys
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
import datetime
from typing import Literal

import re



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
    except:
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
            "cogs.help",
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
        """Initialisiert Tabellen und startet Tasks"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Tabellen erstellen

                await cur.execute("DROP TABLE IF EXISTS reactionrole_entries")
                await cur.execute("DROP TABLE IF EXISTS reactionrole_messages")

                # Reaction Role Nachricht mit Bezug auf den Server (guild_id)
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS reactionrole_messages (
                    message_id BIGINT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    style VARCHAR(10) NOT NULL,
                    embed_title VARCHAR(256) NOT NULL,
                    embed_description TEXT NOT NULL,
                    embed_color VARCHAR(6) NOT NULL,
                    embed_image TEXT,
                    embed_thumbnail TEXT
                )
                """)

                # Einzelne Reaktionsrollen, pro Nachricht – keine Änderung nötig, aber hier zur Vollständigkeit:
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS reactionrole_entries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    message_id BIGINT NOT NULL,
                    role_id BIGINT NOT NULL,
                    label VARCHAR(100) NOT NULL,
                    emoji VARCHAR(100),
                    FOREIGN KEY (message_id) REFERENCES reactionrole_messages(message_id) ON DELETE CASCADE
                )
                """)

                # Users-Tabelle erstellen
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS gc_users (
                    id BIGINT PRIMARY KEY,
                    lvl_points INT NOT NULL DEFAULT 0,
                    team BOOLEAN NOT NULL DEFAULT FALSE,
                    banned BOOLEAN NOT NULL DEFAULT FALSE
                )
                """)


                # Servers-Tabelle erstellen
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS gc_servers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    guildid BIGINT NOT NULL,
                    channelid BIGINT NOT NULL,
                    invite VARCHAR(255)
                )
                """)


                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS reactionrole_messages (
                        message_id BIGINT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        style VARCHAR(10) NOT NULL, -- "Button" oder "Select"
                        embed_title VARCHAR(256) NOT NULL,
                        embed_description TEXT NOT NULL,
                        embed_color INT NOT NULL
                    )
                """)
                # reactionrole_entries Tabelle
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS reactionrole_entries (
                        message_id BIGINT NOT NULL,
                        role_id BIGINT NOT NULL,
                        label VARCHAR(100) NOT NULL,
                        emoji VARCHAR(100),
                        FOREIGN KEY (message_id) REFERENCES reactionrole_messages(message_id) ON DELETE CASCADE
                    )
                """)

                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS emojiquiz_quizzez(question TEXT, answer VARCHAR(255), hint TEXT)")
                await cur.execute("""
                                    INSERT INTO emojiquiz_quizzez (question, answer, hint) VALUES 
                                    ('🎬🚗👻', 'Ghostbusters', 'Ein Film über Geisterjäger'),
                                    ('🦇👨‍👩‍👧‍👦', 'Batman', 'Ein Superheld, der Gotham City beschützt'),
                                    ('🔗🌳🛤️', 'Linkin Park', 'Eine US-Rockband mit elektronischen Elementen, bekannt durch Songs wie "In the End"'),
                                    ('🤠🎸🌾', 'Country', 'Ein Musikgenre mit ländlichen Themen'),
                                    ('🔴🔵🟡', 'Twister', 'Ein Spiel, bei dem man Körperteile auf Farbpunkte legt'),
                                    ('🚀👾', 'E.T.', 'Ein Außerirdischer wird von Kindern gefunden'),
                                    ('🕵️‍♂️🔍', 'Sherlock Holmes', 'Ein berühmter Detektiv mit messerscharfem Verstand'),
                                    ('🦁👑', 'Der König der Löwen', 'Ein Zeichentrickfilm über Tiere in der Savanne'),
                                    ('🧙‍♂️⚡', 'Harry Potter', 'Ein Zauberer erlebt Abenteuer in einer magischen Welt'),
                                    ('🌌🚀', 'Star Wars', 'Eine epische Weltraumsaga zwischen Gut und Böse'),
                                    ('🍫🏭', 'Charlie und die Schokoladenfabrik', 'Ein Junge gewinnt eine Tour durch eine Fabrik'),
                                    ('🎤🐠', 'Findet Nemo', 'Ein Clownfisch sucht seinen Sohn'),
                                    ('🌈🍭', 'Der Zauberer von Oz', 'Ein Mädchen sucht einen Zauberer in einer Fantasiewelt'),
                                    ('🧛‍♂️🦇', 'Dracula', 'Ein Vampir, der nachts Blut trinkt'),
                                    ('🚶‍♂️👨‍🚀', 'Der Marsianer', 'Ein Astronaut kämpft ums Überleben auf dem Mars'),
                                    ('🏹👧', 'Die Tribute von Panem', 'Ein Mädchen wird zu einem tödlichen Spiel gezwungen'),
                                    ('🚢🌊', 'Titanic', 'Ein Liebesdrama auf einem berühmten Schiff'),
                                    ('🧊⛄', 'Die Eiskönigin', 'Eine Prinzessin mit Eiskräften'),
                                    ('🧟‍♂️🧟‍♀️', 'The Walking Dead', 'Eine Serie über eine Zombieapokalypse'),
                                    ('🐶🐱', 'Haustiere', 'Tiere, die oft als Begleiter gehalten werden'),
                                    ('🍎🍌', 'Früchte', 'Gesundes, essbares Obst'),
                                    ('☀️🌈', 'Regenbogen', 'Ein farbenfrohes Wetterphänomen'),
                                    ('📚📖', 'Bücher', 'Gedruckte oder digitale Literaturwerke'),
                                    ('🍕🍔', 'Fast Food', 'Schnell zubereitetes Essen zum Mitnehmen'),
                                    ('🚗🚦', 'Verkehr', 'Transportmittel und Straßenschilder'),
                                    ('🌳🌺', 'Natur', 'Die belebte und unbelebte Umwelt'),
                                    ('👶🍼', 'Baby', 'Ein neugeborenes oder kleines Kind'),
                                    ('🌞🏖️', 'Strand', 'Ein Ort mit Sand und Wasser'),
                                    ('🎮🕹️', 'Videospiele', 'Elektronische Spiele auf Bildschirmen'),
                                    ('🌙🌠', 'Nachthimmel', 'Der Himmel mit Mond und Sternen'),
                                    ('🎨🖌️', 'Malerei', 'Künstlerische Darstellung mit Farben'),
                                    ('🍲🥗', 'Essen', 'Verschiedene Arten von Gerichten'),
                                    ('📺🎬', 'Fernsehen', 'Sendungen und Filme auf dem Bildschirm'),
                                    ('📱📞', 'Handy', 'Ein Kommunikationsgerät'),
                                    ('📆⏰', 'Zeit', 'Messung von Momenten und Abläufen'),
                                    ('👩‍🍳🍳', 'Kochen', 'Zubereitung von Mahlzeiten'),
                                    ('🚴‍♂️🚶‍♀️', 'Aktivitäten', 'Was du draußen machst, wenn dir langweilig ist'),
                                    ('🎈🥳', 'Party', 'Ein soziales Treffen zum Feiern'),
                                    ('❤️🌹', 'Liebe', 'Ein starkes Gefühl der Zuneigung'),
                                    ('🌞🌻', 'Sonnenblume', 'Eine fröhliche, helle Blume'),
                                    ('📚✏️', 'Schule', 'Ein Ort zum Lernen'),
                                    ('🐶🏠', 'Hundehütte', 'Ein Unterschlupf für Hunde'),
                                    ('📆🎂', 'Jahrestag', 'Jährliche Feier eines Ereignisses'),
                                    ('🚴‍♀️🚴', 'Fahrrad', 'Ein zweirädriges Fortbewegungsmittel'),
                                    ('🏀👟', 'Basketball', 'Ein Mannschaftssport mit zwei Teams'),
                                    ('🛒🛍️', 'Einkaufen', 'Kleidung und andere Dinge kaufen'),
                                    ('🎭🤡', 'Zirkus', 'Reisende Künstler mit Akrobatik und Clowns'),
                                    ('🌧️🌈', 'Wetter', 'Meteorologische Erscheinungen'),
                                    ('🐍⚡🏰', 'Slytherin', 'Ein Haus in Hogwarts – grün, ehrgeizig, listig'),
                                    ('🐵🪄', 'Dschungelbuch', 'Ein Junge wächst im Urwald mit Tieren auf'),
                                    ('🕸️🕷️', 'Spider-Man', 'Ein Superheld mit Spinnenkräften'),
                                    ('🍔👨‍🍳', 'Burger King', 'Ein Fast-Food-Restaurant mit königlichem Namen'),
                                    ('👓⚗️', 'Chemie', 'Eine Naturwissenschaft mit Formeln und Reaktionen'),
                                    ('🎤🎶', 'Musik', 'Etwas, das du hörst und fühlst'),
                                    ('🗺️🧭', 'Abenteuer', 'Eine spannende Reise ins Unbekannte'),
                                    ('💻⌨️', 'Computer', 'Ein digitales Gerät für alles Mögliche'),
                                    ('👽🔭', 'Außerirdischer', 'Ein Wesen nicht von dieser Welt');
                                    """)

                await cur.execute("CREATE TABLE IF NOT EXISTS emojiquiz(guildID BIGINT, channelID BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS emojiquiz_lsg(guildID BIGINT, lösung TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS economy_users (user_id BIGINT PRIMARY KEY, wallet INT DEFAULT 0, bank INT DEFAULT 0, job VARCHAR(100), hours_worked INT DEFAULT 0, last_work DATETIME)")
                await cur.execute("CREATE TABLE IF NOT EXISTS snake(userID BIGINT, highscore BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS topgg(userID BIGINT, count BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS website_stats(servers BIGINT, users BIGINT, channels BIGINT, commands BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS afk(guildID BIGINT, userID BIGINT, reason TEXT, prevName TEXT, time TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS autoreact(guildID BIGINT, channelID BIGINT, emoji TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS blacklist(serverID BIGINT, word TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS botrole(roleID BIGINT, guildID BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS joinrole(roleID BIGINT, guildID BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS capslock(guildID BIGINT, percent BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS counter(guildID BIGINT, channelID BIGINT, number BIGINT, lastuserID BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS leavemsg(guildID BIGINT, channelID BIGINT, msg TEXT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS guessthenumber(guildID BIGINT, channelID BIGINT, number BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS automod(guildID BIGINT, warns BIGINT, action TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS modlog(serverID BIGINT, channelID BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS tags(guildID BIGINT, tagname BIGINT, tagoutput BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS tempchannels(guild_id BIGINT, channel_id BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS welcome(guildID BIGINT, channelID BIGINT, msg TEXT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS ticketsystem_channels(guildID BIGINT, channelID BIGINT, msgID BIGINT, opened BIGINT, claimed TEXT, closed TEXT, time TEXT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS usertempchannels(guildID BIGINT, userID BIGINT, channelID BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS ticketsystem(guildID BIGINT, channelID BIGINT, categoryID BIGINT, roleID BIGINT, thema TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS ticketlog(guildID BIGINT, channelID BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS reminder(userID BIGINT, grund TEXT, time TEXT, remindID BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS levelsystem(user_xp BIGINT, user_level BIGINT, client_id TEXT, guild_id TEXT, enabled BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS levelchannel(guildID BIGINT, type TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS levelmsg(guildID BIGINT, message TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS levelxp(guildID BIGINT, xp BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS levelroles(guildID BIGINT, roleID BIGINT, levelreq BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS giveaway_active(guildID BIGINT, creatorID BIGINT, channelID BIGINT, messageID BIGINT, entrys BIGINT, prize TEXT, winners TEXT, time TEXT, role TEXT, level TEXT, ended BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS giveway_ids(guildID BIGINT, gwID BIGINT, messageID BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS giveaway_entrys(guildID BIGINT, channelID BIGINT, messageID BIGINT, userID BIGINT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS voterole(userID BIGINT, time TEXT)")
                # ... alle weiteren CREATE TABLEs (dein Code bleibt unverändert hier)

                logging.info("✅ Tables Erfolgreich geladen")



                # Reminder-Tasks (gestaffelt laden)
                if not self.task:
                    self.task = True
                    await cur.execute("SELECT time FROM reminder")
                    eintraege = await cur.fetchall()

                    async def starte_reminder_tasks():
                        for eintrag in eintraege:
                            try:
                                t2 = datetime.datetime.fromtimestamp(int(eintrag[0]))
                                asyncio.create_task(funktion(t2))
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                logging.error(f"❌ Reminder-Fehler: {e}")

                    asyncio.create_task(starte_reminder_tasks())

                if not self.task2:
                    self.task2 = True
                    await cur.execute("SELECT time FROM voterole")
                    eintraege2 = await cur.fetchall()

                    async def starte_voterole_tasks():
                        for eintrag in eintraege2:
                            try:
                                t4 = datetime.datetime.fromtimestamp(int(eintrag[0]))
                                asyncio.create_task(funktion2(t4))
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                logging.error(f"❌ Voterole-Fehler: {e}")

                    asyncio.create_task(starte_voterole_tasks())

                if not self.task3:
                    self.task3 = True
                    await cur.execute("SELECT time, guildID, messageID, channelID FROM giveaway_active")
                    eintraege3 = await cur.fetchall()

                    async def starte_giveaway_tasks():
                        for eintrag in eintraege3:
                            try:
                                t2 = datetime.datetime.fromtimestamp(int(eintrag[0]))
                                msg_id = int(eintrag[2])
                                asyncio.create_task(gwtimes(t2, msg_id))
                                await asyncio.sleep(0.5)
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
        botcreated = str(bot.user.created_at.__format__('%A, %d %B, %Y'))
        if msg.content == f"<@{bot.user.id}>" or msg.content == f"<@!{bot.user.id}>":
            embed = discord.Embed(title="Astra", url="https://discord.gg/vwh2raq2Xu", colour=discord.Colour.blue(),
                                  description=f"Hallo Discord!\nIch bin Astra. Ich wurde geboren am {botcreated}\nIch habe viele Verschiedene Systeme und Befehle, welche ein Level- und Ticketsystem beinhalten.\nAlle Befehle sind /-Befehle. Das bedeueter, dass du sie ganz einfach finden kannst.\nWenn du irgendwelche Fragen und Probleme hast, kannst du uns gerne über unseren **[Support Server ➚](https://discord.gg/vwh2raq2Xu)** kontaktieren.\nWenn ich nun dein Interesse geweckt habe, kannst du mich ganz einfach **[Einladen ➚](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)** und mich ausprobieren")
            embed.set_author(name=msg.author, icon_url=msg.author.avatar)
            embed.set_footer(text="Astra Development ©2025 | Für mehr Informationen kontaktiere uns via Discord.",
                             icon_url=msg.guild.icon)
            embed.set_thumbnail(url=msg.guild.icon)
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

@bot.command()
async def chat(ctx, *, prompt: str):
    full_prompt = (
        "Du bist ein hilfreicher, deutscher KI-Assistent. "
        "Antworte klar, sachlich und prägnant. "
        "Vermeide Ausschweifungen, halte die Antwort kompakt.\n\n"
        f"Frage: {prompt}\nAntwort:"
    )

    antwort = ""
    last_update = time.monotonic()
    start_time = time.monotonic()

    # Initiale Nachricht
    message = await ctx.send("🤖 Ich denke nach...")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "http://localhost:11434/api/generate",
                json={"model": "mistral", "prompt": full_prompt, "stream": True, "temperature": 0.3, "num_predict": 2000}
            ) as resp_stream:

                if resp_stream.status != 200:
                    await ctx.send(f"❌ KI-Server Fehler: Status {resp_stream.status}")
                    return

                async for raw_line in resp_stream.content:
                    line = raw_line.decode().strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    if line == "[DONE]":
                        break

                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        antwort += token
                    except Exception as e:
                        logging.error(f"Fehler beim Parsen der Daten: {e}")
                        continue

                    now = time.monotonic()
                    if now - last_update > 0.5:
                        elapsed = now - start_time
                        embed = discord.Embed(
                            title="🤖 KI-Antwort (Streaming...)",
                            description=antwort + "▌",
                            colour=discord.Colour.blue()
                        )
                        embed.set_footer(text=f"Astra Bot | Powered by Ollama | Laufzeit: {elapsed:.1f}s")
                        embed.set_author(
                            name=ctx.author.display_name,
                            icon_url=ctx.author.avatar.url if ctx.author.avatar else None,
                        )
                        await message.edit(embed=embed)
                        last_update = now

            # Finale Embed-Nachricht
            elapsed = time.monotonic() - start_time
            embed = discord.Embed(
                title="🤖 KI-Antwort",
                description=antwort.strip(),
                colour=discord.Colour.blue()
            )
            embed.set_footer(text=f"Astra Bot | Powered by Ollama | Gesamtzeit: {elapsed:.1f}s")
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.avatar.url if ctx.author.avatar else None,
            )
            await message.edit(embed=embed)

        except Exception as e:
            logging.error(f"Fehler im Chat-Command: {e}", exc_info=True)
            await ctx.send(f"❌ Fehler: {e}")


@bot.event
async def on_dbl_vote(data):
    logging.info("on_dbl_vote ausgelöst für User:", data["user"])

    """An event that is called whenever someone votes for the bot on Top.gg."""
    member_votes_first = 0
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            if data["type"] == "test":
                return bot.dispatch('dbl_test', data)

            votedata = await bot.topggpy.get_bot_info()
            heart = bot.get_emoji(1361007251434901664)
            votes = int(votedata["monthly_points"])
            user = bot.get_user(int(data["user"]))
            guild = bot.get_guild(1141116981697859736)
            voterole = guild.get_role(1141116981756575875)
            channel = guild.get_channel(1361006871753789532)

            today = datetime.date.today()
            this_month = today.replace(day=1)
            vote_increase = 2 if today.weekday() in [4, 5, 6] else 1  # Fr, Sa, So: 2, sonst 1

            # Monats-Gesamtvotes aktualisieren oder anlegen
            await cur.execute("SELECT votes FROM monthly_votes WHERE month = %s", (this_month,))
            monthly_result = await cur.fetchone()
            if monthly_result:
                monthly_total = monthly_result[0] + vote_increase
                await cur.execute("UPDATE monthly_votes SET votes = %s WHERE month = %s", (monthly_total, this_month))
            else:
                monthly_total = vote_increase
                await cur.execute("INSERT INTO monthly_votes (month, votes) VALUES (%s, %s)", (this_month, monthly_total))

            # Count und last_reset holen
            await cur.execute("SELECT count, last_reset FROM topgg WHERE userID = %s", (int(data["user"]),))
            result = await cur.fetchone()

            # USER NOCH NICHT IN DB
            if not result:
                member_votes_first2 = member_votes_first + vote_increase
                await cur.execute("INSERT INTO topgg (userID, count, last_reset) VALUES (%s, %s, %s)",
                                  (int(data["user"]), member_votes_first2, this_month))
            else:
                votes_member, last_reset = result
                # Prüfe, ob Monatswechsel -> Reset
                if not last_reset or last_reset < this_month:
                    votes_member = 0
                    await cur.execute("UPDATE topgg SET count = %s, last_reset = %s WHERE userID = %s",
                                      (votes_member, this_month, int(data["user"])))
                member_votes = int(votes_member + vote_increase)
                await cur.execute("UPDATE topgg SET count = %s WHERE userID = %s",
                                  (member_votes, int(data["user"])))
                member_votes_first2 = member_votes

            # Zeitberechnung und Rollen-Handling wie gehabt
            time = "12h"
            time1 = convert(time)
            t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
            t2 = datetime.datetime.fromtimestamp(int(t1))
            asyncio.create_task(funktion2(t2))
            await cur.execute("INSERT INTO voterole(userID, time) VALUES(%s, %s)",
                              (int(data["user"]), t1))

            embed = discord.Embed(
                title="Danke fürs Voten von Astra",
                description=(
                    f"<:Astra_boost:1141303827107164270> ``{user}({user.id})`` hat für **Astra** gevotet.\n"
                    f"Du kannst alle 12 Stunden **[hier](https://top.gg/bot/811733599509544962/vote)** voten."
                ),
                colour=discord.Colour.blue(),
                timestamp=datetime.datetime.now(datetime.UTC)
            )
            embed.set_thumbnail(
                url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg"
            )
            embed.set_footer(
                text="Danke für deinen Support",
                icon_url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg"
            )

            for member in guild.members:
                if member.id == user.id:
                    await member.add_roles(voterole, reason="Voterole")
            msg = await channel.send(embed=embed)
            await msg.add_reaction(heart)
            return None


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
                          colour=discord.Colour.red(), timestamp=datetime.datetime.now(datetime.UTC))
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
            await cur.execute("DROP TABLE website_stats;")
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
            bot.tree.add_command(Giveaway())
            bot.tree.add_command(Reminder())


async def funktion2(when: datetime.datetime):
    await bot.wait_until_ready()
    await discord.utils.sleep_until(when=when)
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT userID FROM voterole")
            result = await cur.fetchall()
            if result == ():
                return
            if result:
                for eintrag in result:
                    userID = eintrag[0]
                    guild = bot.get_guild(1141116981697859736)
                    member = guild.get_member(userID)
                    if not member:
                        try:
                            member = await guild.fetch_member(userID)
                        except:
                            continue

                    voterole = guild.get_role(1141116981756575875)
                    embed = discord.Embed(
                        title="<:Astra_time:1141303932061233202> Du kannst wieder voten!",
                        url="https://top.gg/de/bot/811733599509544962/vote",
                        description="Der Cooldown von 12h ist vorbei. Es wäre schön wenn du wieder votest.\nAls Belohnung erhälst du eine spezielle Rolle auf unserem [Support-Server](https://discord.gg/NH9DdSUJrE).",
                        colour=discord.Colour.blue()
                    )
                    try:
                        await member.send(embed=embed)
                    except:
                        pass

                    try:
                        await member.remove_roles(voterole)
                    except Exception as e:
                        logging.error(f"❌ Fehler beim Entfernen der Rolle von {userID}: {e}")

                    await cur.execute("DELETE FROM voterole WHERE userID = (%s)", (userID,))


async def gwtimes(when: datetime.datetime, messageid: int):
    await bot.wait_until_ready()
    await discord.utils.sleep_until(when=when)
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT guildID, channelID, userID, messageID FROM giveaway_entrys WHERE messageID = (%s)", (messageid))
            result = await cur.fetchall()
            if result == ():
                await cur.execute(
                    "SELECT ended, prize, winners, entrys, time, guildID, channelID FROM giveaway_active WHERE messageID = (%s)",
                    (messageid))
                result3 = await cur.fetchone()

                ended = result3[0]
                if int(ended) == 1:
                    return
                if int(ended) == 0:
                    price = result3[1]
                    winners = result3[2]
                    entrys = result3[3]
                    time = result3[4]
                    guildID = result3[5]
                    channelID = result3[6]

                    guild = bot.get_guild(guildID)
                    channel = guild.get_channel(channelID)
                    message = await channel.fetch_message(messageid)
                    time2 = datetime.datetime.fromtimestamp(int(time))

                    embed = discord.Embed(title=" ",
                                          description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer.",
                                          colour=discord.Colour.red())
                    await message.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                    await message.reply(
                        f"<:Astra_x:1141303954555289600> **Es gab nicht genügend Teilnehmer. Niemand hat das Gewinnspiel gewonnen.**")
                    await cur.execute(
                        "UPDATE giveaway_active SET ended = (%s) WHERE guildID = (%s) AND channelID = (%s) and messageID = (%s)",
                        (1, guild.id, channel.id, messageid))
                    await cur.execute("DELETE FROM giveway_ids WHERE messageID = (%s)", (messageid))
            if result:
                guildID = result[0][0]
                channelID = result[0][1]
                await cur.execute(
                    "SELECT ended, prize, winners, entrys, time FROM giveaway_active WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                    (guildID, channelID, messageid))
                result2 = await cur.fetchone()
                ended = result2[0]
                if int(ended) == 1:
                    return
                if int(ended) == 0:
                    price = result2[1]
                    won = result2[2]
                    entrys = result2[3]
                    time = result2[4]
                    time2 = datetime.datetime.fromtimestamp(int(time))
                    participants = [userid[2] for userid in result]
                    winner = random.sample(participants,
                                           k=len(participants) if len(participants) < int(result2[2]) else int(
                                               result2[2]))
                    guild = bot.get_guild(int(guildID))
                    channel = guild.get_channel(int(channelID))
                    users = []
                    msg = await channel.fetch_message(messageid)
                    for id in winner:
                        idwinners = bot.get_user(id)
                        winembed = discord.Embed(title=" ",
                                                 description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Du hast ein Gewinnspiel auf [{guild.name}](https://discord.com/channels/{guild.id}/{channel.id}/{msg.id}) gewonnen.\n`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}",
                                                 colour=discord.Colour.yellow())
                        winembed.set_thumbnail(url=guild.icon.url)
                        await idwinners.send(
                            "<:heart:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                            embed=winembed)
                        users.append(idwinners)
                    mentions = ", ".join(user.mention for user in users)
                    if entrys < 1:
                        embed = discord.Embed(title=" ",
                                              description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer.",
                                              colour=discord.Colour.red())
                        await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                        await msg.reply(
                            f"<:Astra_x:1141303954555289600> Es gab nicht genügend Teilnehmer. Niemnand hat das Gewinnspiel gewonnen.")
                        await cur.execute(
                            "UPDATE giveaway_active SET ended = (%s) WHERE guildID = (%s) AND channelID = (%s) and messageID = (%s)",
                            (1, guildID, channelID, messageid))
                        await cur.execute("DELETE FROM giveway_ids WHERE messageID = (%s)", (messageid))
                    if entrys >= 1:
                        embed = discord.Embed(title=" ",
                                              description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer.",
                                              colour=discord.Colour.red())
                        await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                        await msg.reply(
                            f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen! Herzlichen Glückwunsch.")
                        await cur.execute(
                            "UPDATE giveaway_active SET ended = (%s) WHERE guildID = (%s) AND channelID = (%s) and messageID = (%s)",
                            (1, guildID, channelID, messageid))
                        await cur.execute("DELETE FROM giveway_ids WHERE messageID = (%s)", (messageid))


class gw_button(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Teilnehmen', style=discord.ButtonStyle.green, custom_id='persistent_view_allg:join_gw',
                       emoji="🎉")
    async def join_gw(self, interaction: discord.Interaction, button: discord.Button):
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await interaction.response.defer()
                await cur.execute(
                    "SELECT userID FROM giveaway_entrys WHERE userID = (%s) AND guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                    (interaction.user.id, interaction.guild.id, interaction.channel.id, interaction.message.id))
                result = await cur.fetchone()
                if not result:
                    await cur.execute(
                        "SELECT role, level, entrys, messageID, prize, winners, time, creatorID FROM giveaway_active WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                        (interaction.guild.id, interaction.channel.id, interaction.message.id))
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
                    time2 = datetime.datetime.fromtimestamp(int(time))
                    if str(roleID) == "Not Set" and str(level) == "Not Set":
                        embed = discord.Embed(title=" ",
                                              description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.",
                                              colour=discord.Colour.blue())
                        embed.set_thumbnail(url=interaction.guild.icon.url)
                        embed.set_footer(text="Viel Erfolg 🍀",
                                         icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embed)
                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = (%s) WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                            ((int(entrys) + 1), interaction.guild.id, interaction.channel.id,
                             interaction.message.id))
                        await cur.execute(
                            "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                            (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id))
                        successemb = discord.Embed(title=f" ",
                                                   description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                                                   colour=discord.Colour.green())
                        successemb.set_thumbnail(url=interaction.guild.icon.url)
                        await interaction.user.send(
                            "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                            embed=successemb)
                    if roleID.isnumeric() and level == "Not Set":
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        if role in interaction.user.roles:
                            embe = discord.Embed(title=" ",
                                                 description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                                                 colour=discord.Colour.blue())
                            embe.set_thumbnail(url=interaction.guild.icon.url)
                            embe.set_footer(text="Viel Erfolg 🍀",
                                            icon_url=interaction.guild.icon.url)
                            msg = await interaction.channel.fetch_message(messageID)
                            await msg.edit(embed=embe)
                            await cur.execute(
                                "UPDATE giveaway_active SET entrys = (%s) WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                                ((int(entrys) + 1), interaction.guild.id, interaction.channel.id,
                                 interaction.message.id))
                            await cur.execute(
                                "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                (interaction.guild.id, interaction.channel.id, interaction.user.id,
                                 interaction.message.id))
                            successemb = discord.Embed(title=" ",
                                                       description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                                                       colour=discord.Colour.green())
                            successemb.set_thumbnail(url=interaction.guild.icon.url)
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                embed=successemb)
                        else:
                            failemb = discord.Embed(title=f" ",
                                                    description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                                                    colour=discord.Colour.red())
                            failemb.set_thumbnail(url=interaction.guild.icon.url)
                            await interaction.user.send(
                                "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                embed=failemb)
                    if roleID == "Not Set" and level.isnumeric():
                        await cur.execute(
                            f"SELECT user_xp, user_level FROM levelsystem WHERE client_id = (%s) AND guild_id = (%s)",
                            (interaction.user.id, interaction.guild.id))
                        result = await cur.fetchall()
                        if not result:
                            await interaction.user.send(
                                "<:Astra_x:1141303954555289600> **Wir haben leider keine Einträge über dich gefunden. Schreibe erst eine Nachricht und versuche es erneut.**")
                        if result:
                            lvl_start = result[0][1]
                            if int(level) == int(lvl_start):
                                emb = discord.Embed(title=" ",
                                                    description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620>__**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> Klicke unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                                    colour=discord.Colour.blue())
                                emb.set_thumbnail(url=interaction.guild.icon.url)
                                emb.set_footer(text="Viel Erfolg 🍀",
                                               icon_url=interaction.guild.icon.url)
                                msg = await interaction.channel.fetch_message(messageID)
                                await msg.edit(embed=emb)
                                await cur.execute(
                                    "UPDATE giveaway_active SET entrys = (%s) WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                                    ((int(entrys) + 1), interaction.guild.id, interaction.channel.id,
                                     interaction.message.id))
                                await cur.execute(
                                    "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                    (interaction.guild.id, interaction.channel.id, interaction.user.id,
                                     interaction.message.id))
                                successemb = discord.Embed(title=f" ",
                                                           description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                                                           colour=discord.Colour.green())
                                successemb.set_thumbnail(url=interaction.guild.icon.url)
                                await interaction.user.send(
                                    "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                    embed=successemb)
                            else:
                                failemb = discord.Embed(title=f" ",
                                                        description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                                        colour=discord.Colour.red())
                                failemb.set_thumbnail(url=interaction.guild.icon.url)
                                await interaction.user.send(
                                    "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                    embed=failemb)
                    if roleID.isnumeric() and level.isnumeric():
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        await cur.execute(
                            f"SELECT user_xp, user_level FROM levelsystem WHERE client_id = (%s) AND guild_id = (%s)",
                            (interaction.user.id, interaction.guild.id))
                        result5 = await cur.fetchall()
                        if not result5:
                            await interaction.user.send(
                                "<:Astra_x:1141303954555289600> **Wir haben leider keine Einträge über dich gefunden. Schreibe erst eine Nachricht und versuche es erneut.**")
                        if result5:
                            lvl_start = result5[0][1]
                            if int(level) == int(lvl_start) or role in interaction.user.roles:
                                if int(level) == int(lvl_start):
                                    if role in interaction.user.roles:
                                        em = discord.Embed(title=" ",
                                                           description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungem:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                                           colour=discord.Colour.blue())
                                        em.set_thumbnail(url=interaction.guild.icon.url)
                                        em.set_footer(text="Viel Erfolg 🍀",
                                                      icon_url=interaction.guild.icon.url)
                                        msg = await interaction.channel.fetch_message(messageID)
                                        await msg.edit(embed=em)
                                        await cur.execute(
                                            "UPDATE giveaway_active SET entrys = (%s) WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                                            ((int(entrys) + 1), interaction.guild.id, interaction.channel.id,
                                             interaction.message.id))
                                        await cur.execute(
                                            "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                            (interaction.guild.id, interaction.channel.id, interaction.user.id,
                                             interaction.message.id))
                                        successemb = discord.Embed(title=f" ",
                                                                   description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.",
                                                                   colour=discord.Colour.green())
                                        successemb.set_thumbnail(url=interaction.guild.icon.url)
                                        await interaction.user.send(
                                            "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                            embed=successemb)
                                    else:
                                        failemb = discord.Embed(title=f" ",
                                                                description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                                                                colour=discord.Colour.red())
                                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                                        await interaction.user.send(
                                            "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                            embed=failemb)
                                else:
                                    failemb = discord.Embed(title=f" ",
                                                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                                            colour=discord.Colour.red())
                                    failemb.set_thumbnail(url=interaction.guild.icon.url)
                                    await interaction.user.send(
                                        "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                        embed=failemb)
                            else:
                                failemb = discord.Embed(title=f" ",
                                                        description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                                        colour=discord.Colour.red())
                                failemb.set_thumbnail(url=interaction.guild.icon.url)
                                await interaction.user.send(
                                    "**<:Astra_x:1141303954555289600> Deime Teilnahme am Gewinnspiel war nicht erfolgreich**",
                                    embed=failemb)
                if result:
                    await cur.execute(
                        "SELECT role, level, entrys, messageID, prize, winners, time, creatorID FROM giveaway_active WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                        (interaction.guild.id, interaction.channel.id, interaction.message.id))
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
                    time2 = datetime.datetime.fromtimestamp(int(time))

                    if roleID.isnumeric() and level.isnumeric():
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        em = discord.Embed(title=" ",
                                           description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                           colour=discord.Colour.blue())
                        em.set_thumbnail(url=interaction.guild.icon.url)
                        em.set_footer(text="Viel Erfolg 🍀",
                                      icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=em)

                        failemb = discord.Embed(title=f" ",
                                                description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                                                colour=discord.Colour.red())
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        await interaction.user.send(
                            "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurrückgezogen.**",
                            embed=failemb)

                        await cur.execute(
                            "DELETE FROM giveaway_entrys WHERE userID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            (interaction.user.id, interaction.guild.id, interaction.message.id))
                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = (%s) WHERE channelID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            ((int(entrys) - 1), interaction.channel.id, interaction.guild.id, interaction.message.id))

                    if str(roleID) == "Not Set" and str(level) == "Not Set":
                        embed = discord.Embed(title=" ",
                                              description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.",
                                              colour=discord.Colour.blue())
                        embed.set_thumbnail(url=interaction.guild.icon.url)
                        embed.set_footer(text="Viel Erfolg 🍀",
                                         icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embed)

                        failemb = discord.Embed(title=f" ",
                                                description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                                                colour=discord.Colour.red())
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        await interaction.user.send(
                            "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                            embed=failemb)

                        await cur.execute(
                            "DELETE FROM giveaway_entrys WHERE userID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            (interaction.user.id, interaction.guild.id, interaction.message.id))
                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = (%s) WHERE channelID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            ((int(entrys) - 1), interaction.channel.id, interaction.guild.id, interaction.message.id))
                    if roleID == "Not Set" and level.isnumeric():
                        emb = discord.Embed(title=" ",
                                            description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                            colour=discord.Colour.blue())
                        emb.set_thumbnail(url=interaction.guild.icon.url)
                        emb.set_footer(text="Viel Erfolg 🍀",
                                       icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=emb)

                        failemb = discord.Embed(title=" ",
                                                description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Reason**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                                                colour=discord.Colour.red())
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        await interaction.user.send(
                            "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                            embed=failemb)

                        await cur.execute(
                            "DELETE FROM giveaway_entrys WHERE userID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            (interaction.user.id, interaction.guild.id, interaction.message.id))
                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = (%s) WHERE channelID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            ((int(entrys) - 1), interaction.channel.id, interaction.guild.id, interaction.message.id))
                    if roleID.isnumeric() and level == "Not Set":
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        embe = discord.Embed(title=" ",
                                             description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                                             colour=discord.Colour.blue())
                        embe.set_thumbnail(url=interaction.guild.icon.url)
                        embe.set_footer(text="Viel Erfolg 🍀",
                                        icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embe)

                        failemb = discord.Embed(title=" ",
                                                description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Deine Teilnahme auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n`⏰` Das Gewinnspiel Endet {discord.utils.format_dt(time2, 'R')}.\n\n`🧨` __**Grund**__\n<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen.",
                                                colour=discord.Colour.red())
                        failemb.set_thumbnail(url=interaction.guild.icon.url)
                        await interaction.user.send(
                            "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                            embed=failemb)
                        asyncio.create_task(gwtimes(time2, msg.id))

                        await cur.execute(
                            "DELETE FROM giveaway_entrys WHERE userID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            (interaction.user.id, interaction.guild.id, interaction.message.id))
                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = (%s) WHERE channelID = (%s) AND guildID = (%s) AND messageID = (%s)",
                            ((int(entrys) - 1), interaction.channel.id, interaction.guild.id, interaction.message.id))


@app_commands.guild_only()
class Giveaway(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="gewinnspiel",
            description="Alles rund um Gewinnspiele."
        )

    @app_commands.command(name="starten")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gw_start(self, interaction: discord.Interaction, *, preis: str, kanal: discord.TextChannel, gewinner: int,
                       zeit: str,
                       rolle: discord.Role = None, level: int = None):
        """Staret ein Gewinnspiel."""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                price = preis
                winner = gewinner
                channel = kanal
                role = rolle
                if role is not None and level is not None:
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> Das Levelsystem ist auf diesem Server deaktiviert.",
                            ephemeral=True)
                    if enabled[0] == 1:
                        time1 = convert(zeit)
                        t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
                        t2 = datetime.datetime.fromtimestamp(int(t1))
                        embed = discord.Embed(title=" ",
                                              description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {interaction.user.mention}\n<:Astra_arrow:1141303823600717885> **{winner}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(t2, 'R')}\n<:Astra_arrow:1141303823600717885> **0** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                              colour=discord.Colour.blue())
                        embed.set_thumbnail(url=interaction.guild.icon.url)
                        embed.set_footer(text="Viel Erfolg 🍀",
                                         icon_url=interaction.guild.icon.url)
                        msg = await channel.send("🎉 **Neues Gewinnspiel** 🎉", embed=embed, view=gw_button())
                        asyncio.create_task(gwtimes(t2, msg.id))
                        await cur.execute(
                            "INSERT INTO giveaway_active(guildID, creatorID, channelID, entrys, messageID, prize, winners, time, role, level, ended) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (interaction.guild.id, interaction.user.id, channel.id, 0, msg.id, price, winner, t1,
                             role.id,
                             level, 0))
                        gwID = 1
                        await cur.execute("SELECT gwID from giveway_ids WHERE guildID = (%s)", (interaction.guild.id))
                        gwid_result = await cur.fetchall()
                        if gwid_result == ():
                            await cur.execute("INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                              (interaction.guild.id, 1, msg.id))
                        if gwid_result:
                            await cur.execute("INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                              (interaction.guild.id, len(result) + 1, msg.id))

                        await interaction.response.send_message(
                            f"**<:Astra_accept:1141303821176422460> Das Gewinnspiel wird in {channel.mention} stattfinden.**")
                if role is None and level is None:
                    time1 = convert(zeit)
                    t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
                    t2 = datetime.datetime.fromtimestamp(int(t1))
                    embed = discord.Embed(title=" ",
                                          description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {interaction.user.mention}\n<:Astra_arrow:1141303823600717885> **{winner}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(t2, 'R')}\n<:Astra_arrow:1141303823600717885> **0** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.",
                                          colour=discord.Colour.blue())
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                    embed.set_footer(text="Viel Erfolg 🍀",
                                     icon_url=interaction.guild.icon.url)
                    msg = await channel.send("🎉 **Neues Gewinnspiel** 🎉", embed=embed, view=gw_button())
                    asyncio.create_task(gwtimes(t2, msg.id))
                    await cur.execute(
                        "INSERT INTO giveaway_active(guildID, creatorID, channelID, entrys, messageID, prize, winners, time, role, level, ended) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (interaction.guild.id, interaction.user.id, channel.id, 0, msg.id, price, winner, t1, "Not Set",
                         "Not Set", 0))
                    gwID = 1
                    await cur.execute("SELECT gwID from giveway_ids WHERE guildID = (%s)", (interaction.guild.id))
                    gwid_result = await cur.fetchall()
                    if gwid_result == ():
                        await cur.execute("INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                          (interaction.guild.id, 1, msg.id))
                        if gwid_result:
                            await cur.execute("INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                              (interaction.guild.id, len(result) + 1, msg.id))
                    await interaction.response.send_message(
                        f"**<:Astra_accept:1141303821176422460> Das Gewinnspiel wird in {channel.mention} stattfinden.**")
                if role is not None and level is None:
                    time1 = convert(zeit)
                    t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
                    t2 = datetime.datetime.fromtimestamp(int(t1))
                    embed = discord.Embed(title=" ",
                                          description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {interaction.user.mention}\n<:Astra_arrow:1141303823600717885> **{winner}** Gewinner\n<:Astra_arrow:1141303823600717885> Ends in {discord.utils.format_dt(t2, 'R')}\n<:Astra_arrow:1141303823600717885> **0** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696>  Du benötigst die **Rolle** `{role.name}` um teilzunehmen.",
                                          colour=discord.Colour.blue())
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                    embed.set_footer(text="Viel Erfolg 🍀",
                                     icon_url=interaction.guild.icon.url)
                    msg = await channel.send("🎉 **Neues Gewinnspiel** 🎉", embed=embed, view=gw_button())
                    asyncio.create_task(gwtimes(t2, msg.id))
                    await cur.execute(
                        "INSERT INTO giveaway_active(guildID, creatorID, channelID, entrys, messageID, prize, winners, time, role, level, ended) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (interaction.guild.id, interaction.user.id, channel.id, 0, msg.id, price, winner, t1, role.id,
                         "Not Set", 0))
                    gwID = 1
                    await cur.execute("SELECT gwID from giveway_ids WHERE guildID = (%s)", (interaction.guild.id))
                    gwid_result = await cur.fetchall()
                    if gwid_result == ():
                        await cur.execute("INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                          (interaction.guild.id, 1, msg.id))
                        if gwid_result:
                            await cur.execute("INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                              (interaction.guild.id, len(result) + 1, msg.id))

                    await interaction.response.send_message(
                        f"**<:Astra_accept:1141303821176422460> Das Gewinnspiel wird in {channel.mention} stattfinden.**")
                if level is not None and role is None:
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server deaktiviert**",
                            ephemeral=True)
                    if enabled[0] == 1:
                        time1 = convert(zeit)
                        t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
                        t2 = datetime.datetime.fromtimestamp(int(t1))
                        embed = discord.Embed(title=" ",
                                              description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {interaction.user.mention}\n<:Astra_arrow:1141303823600717885> **{winner}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel Endet {discord.utils.format_dt(t2, 'R')}\n<:Astra_arrow:1141303823600717885> **0** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.",
                                              colour=discord.Colour.blue())
                        embed.set_thumbnail(url=interaction.guild.icon.url)
                        embed.set_footer(text="Viel Erfolg 🍀",
                                         icon_url=interaction.guild.icon.url)
                        msg = await channel.send("🎉 **Neues Gewinnspiel** 🎉", embed=embed, view=gw_button())
                        asyncio.create_task(gwtimes(t2, msg.id))
                        await cur.execute(
                            "INSERT INTO giveaway_active(guildID, creatorID, channelID, entrys, messageID, prize, winners, time, role, level, ended) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (interaction.guild.id, interaction.user.id, channel.id, 0, msg.id, price, winner, t1,
                             "Not Set",
                             level, 0))
                        gwID = 1
                        await cur.execute("SELECT gwID from giveway_ids WHERE guildID = (%s)", (interaction.guild.id))
                        gwid_result = await cur.fetchall()
                        if gwid_result == ():
                            await cur.execute("INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                              (interaction.guild.id, 1, msg.id))
                            if gwid_result:
                                await cur.execute(
                                    "INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES(%s, %s, %s)",
                                    (interaction.guild.id, len(result) + 1, msg.id))
                        await interaction.response.send_message(
                            f"** The Giveaway will take place in {channel.mention}**")

    @app_commands.command(name="verwalten")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gw_verw(self, interaction: discord.Interaction, *, aktion: Literal[
        'Gewinnspiel beenden(Nachrichten ID angeben)', 'Gewinnspiel neu würfeln(Nachrichten ID angeben)', 'Gewinnspiele Anzeigen'],
                      messageid: str = None):
        """Verwalte deine Gewinnspiele."""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if aktion == "Gewinnspiele Anzeigen":
                    await cur.execute("SELECT gwID, messageID FROM giveway_ids WHERE guildID = (%s)",
                                      interaction.guild.id)
                    result = await cur.fetchall()
                    if result == ():
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Es gibt keine aktiven Gewinnspiele auf diesem Server.**",
                            ephemeral=True)
                    if result:
                        embed = discord.Embed(title=f"Alle Gewinnspiele auf {interaction.guild.id}",
                                              description=f"Um ein Gewinnspiel zu erstellen, nutze `/gewinnspiel starten`.",
                                              color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                        for eintrag in result:
                            giveaway_id = eintrag[0]
                            messageid = eintrag[1]
                            await cur.execute(
                                "SELECT time FROM giveaway_active WHERE guildID = (%s) AND messageID = (%s)",
                                (interaction.guild.id, messageid))
                            time_result = await cur.fetchone()
                            time = time_result[0]
                            embed.add_field(name=f"ID: {giveaway_id}",
                                            value=f"<:Astra_time:1141303932061233202> Das Gewinnspiel endet: <t:{time}:F>",
                                            inline=False)
                        await interaction.response.send_message(embed=embed)

                if aktion == "Gewinnspiel beenden(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT guildID, channelID, userID, messageID FROM giveaway_entrys WHERE messageID = (%s)",
                        (messageid))
                    result = await cur.fetchall()
                    if result == ():
                        await cur.execute(
                            "SELECT prize, winners, entrys, time, guildID, channelID FROM giveaway_active WHERE messageID = (%s) AND ended = (%s)",
                            (messageid, 0))
                        result3 = await cur.fetchone()

                        price = result3[0]
                        winners = result3[1]
                        entrys = result3[2]
                        time = result3[3]
                        guildID = result3[4]
                        channelID = result3[5]

                        guild = bot.get_guild(guildID)
                        channel = guild.get_channel(channelID)
                        message = await channel.fetch_message(int(messageid))
                        time2 = datetime.datetime.fromtimestamp(int(time))

                        embed = discord.Embed(title=" ",
                                              description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer.",
                                              colour=discord.Colour.red())
                        await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                        await message.reply(
                            f"<:Astra_x:1141303954555289600> **Es gab nicht genügend teilnehmer. Niemand hat das Gewinnspiel gewonnen.**")
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> **Das Gewinnspiel wurde erfolgreich beendet.**",
                            ephemeral=True)
                        await cur.execute("DELETE FROM giveway_ids WHERE messageID = (%s)", (messageid))
                        await cur.execute(
                            "UPDATE giveaway_active SET ended = (%s) WHERE guildID = (%s) AND channelID = (%s) and messageID = (%s)",
                            (1, guild.id, channel.id, messageid))
                    if result:
                        guildID = result[0][0]
                        channelID = result[0][1]
                        await cur.execute(
                            "SELECT ended, prize, winners, entrys, time FROM giveaway_active WHERE guildID = (%s) AND channelID = (%s) AND messageID = (%s)",
                            (guildID, channelID, messageid))
                        result2 = await cur.fetchone()
                        ended = result2[0]
                        if int(ended) == 1:
                            return
                        if int(ended) == 0:
                            price = result2[1]
                            won = result2[2]
                            entrys = result2[3]
                            time = result2[4]
                            time2 = datetime.datetime.fromtimestamp(int(time))
                            participants = [userid[2] for userid in result]
                            winner = random.sample(participants,
                                                   k=len(participants) if len(participants) < int(result2[1]) else int(
                                                       result2[1]))
                            guild = bot.get_guild(int(guildID))
                            channel = guild.get_channel(int(channelID))
                            users = []
                            msg = await channel.fetch_message(int(messageid))
                            for id in winner:
                                idwinners = bot.get_user(id)
                                winembed = discord.Embed(title=" ",
                                                         description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Du hast ein Gewinnspiel auf [{guild.name}](https://discord.com/channels/{guild.id}/{channel.id}/{msg.id}) gewonnen.\n`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}",
                                                         colour=discord.Colour.yellow())
                            winembed.set_thumbnail(url=guild.icon.url)
                            await idwinners.send(
                                "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                embed=winembed)
                            users.append(idwinners)
                            mentions = ", ".join(user.mention for user in users)
                            if entrys < 1:
                                embed = discord.Embed(title=" ",
                                                      description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer.",
                                                      colour=discord.Colour.red())
                                await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                                await message.reply(
                                    f"<:Astra_x:1141303954555289600> **Es gab nicht genügend teilnehmer. Niemand hat das Gewinnspiel gewonnen.**")
                                await cur.execute(
                                    "UPDATE giveaway_active SET ended = (%s) WHERE guildID = (%s) AND channelID = (%s) and messageID = (%s)",
                                    (1, guildID, channelID, messageid))
                                await cur.execute("DELETE FROM giveway_ids WHERE messageID = (%s)", (messageid))
                            if entrys >= 1:
                                embed = discord.Embed(title=" ",
                                                      description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1061384624951021578> » __**Who has won this giveaway?**__\n<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer.",
                                                      colour=discord.Colour.red())
                            await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                            await msg.reply(
                                f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen. Herzlichen Glückwunsch.")
                            await cur.execute(
                                "UPDATE giveaway_active SET ended = (%s) WHERE guildID = (%s) AND channelID = (%s) and messageID = (%s)",
                                (1, guildID, channelID, messageid))
                            await cur.execute("DELETE FROM giveway_ids WHERE messageID = (%s)", (messageid))

                if aktion == "Gewinnspiel neu würfeln(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT channelID, prize, winners, entrys, time FROM giveaway_active WHERE guildID = (%s) AND messageID = (%s) AND ended = (%s)",
                        (interaction.guild.id, int(messageid), 1))
                    result = await cur.fetchone()
                    if not result:
                        await interaction.response.send_message(
                            f"<:Astra_x:1141303954555289600> There isnt a giveaway with the messageID {int(messageid)}!",
                            ephemeral=True)
                    if result:
                        channelID = result[0]
                        price = result[1]
                        winners = result[2]
                        entrys = result[3]
                        time = result[4]
                        time2 = datetime.datetime.fromtimestamp(int(time))

                        channel = interaction.guild.get_channel(int(channelID))

                        await cur.execute(
                            "SELECT userID FROM giveaway_entrys WHERE messageID = (%s) AND guildID = (%s) AND channelID = (%s)",
                            (int(messageid), interaction.guild.id, channelID))
                        result2 = await cur.fetchall()

                        participants = [userid[0] for userid in result2]
                        winner = random.sample(participants,
                                               k=len(participants) if len(participants) < int(result[1]) else int(
                                                   result[1]))
                        guild = interaction.guild
                        msg = await channel.fetch_message(int(messageid))
                        users = []
                        for id in winner:
                            idwinners = bot.get_user(id)
                            winembed = discord.Embed(title=" ",
                                                     description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n`🎉` Du hast ein Gewinnspiel auf [{guild.name}](https://discord.com/channels/{guild.id}/{channel.id}/{msg.id}) gewonnen.\n`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}",
                                                     colour=discord.Colour.yellow())
                            winembed.set_thumbnail(url=guild.icon.url)
                            await idwinners.send(
                                "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                embed=winembed)
                            users.append(idwinners)
                        mentions = ", ".join(user.mention for user in users)
                        if entrys < 1:
                            embed = discord.Embed(title=" ",
                                                  description=f"🏆 Preis: {price}\n`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer.",
                                                  colour=discord.Colour.red())
                            await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                            await msg.reply(
                                f"<:Astra_x:1141303954555289600> **Es gab nicht genügend teilnehmer. Niemand hat das Gewinnspiel gewonnen.**")
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Das Gewinnspiel konnte nicht neu ausgelost werden, da es nicht genügend Teilnehmer gab.**",
                                epehemeral=True)
                        if entrys >= 1:
                            embed = discord.Embed(title=" ",
                                                  description=f"🏆 Preis: {price}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_gw_open2:1061384624951021578> » __**Who has won this giveaway?**__\n<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer.",
                                                  colour=discord.Colour.red())
                            await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                            await msg.reply(
                                f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen. Herzlichen Glückwunsch.")
                            if entries == 1:
                                await interaction.response.send_message(
                                    f"<:Astra_accept:1141303821176422460> **Ich habe das Gewinnspiel neu ausgelost, der neue Gewinner ist {mentions}.**",
                                    epehemeral=True)
                            if entrys >= 1:
                                await interaction.response.send_message(
                                    f"<:Astra_accept:1141303821176422460> **Ich habe das Gewinnspiel neu ausgelost, die neuen Gewinner sind {mentions}.**",
                                    epehemeral=True)

async def funktion(when: datetime.datetime):
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

    @app_commands.command(name="erstellen")
    async def reminder_set(self, interaction: discord.Interaction, beschreibung: str, zeit: Literal[
        '1m', '3m', '5m', '10m', '20m', '30m', '45m', '1h', '2h', '5h', '10h', '12h', '18h', '1d', '2d', '5d', '6d', '1w', '2w', '4w']):
        """Set a reminder!"""
        async with bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                description = beschreibung
                time = zeit
                await cur.execute("SELECT grund FROM reminder WHERE userID = (%s)",
                                  (interaction.user.id))
                result = await cur.fetchall()
                if result == ():
                    remindid = 1
                    time1 = convert(time)
                    t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
                    t2 = datetime.datetime.fromtimestamp(int(t1))
                    asyncio.create_task(funktion(t2))
                    await cur.execute("INSERT INTO reminder(userID, grund, time, remindID) VALUES(%s, %s, %s, %s)",
                                      (interaction.user.id, description, t1, remindid))
                    embed = discord.Embed(
                        title=f"<:Astra_time:1141303932061233202> Erinnerung erstellt (ID {remindid})",
                        description=f"Erinnerung gesetzt auf {discord.utils.format_dt(t2, 'F')}\n<:Astra_arrow:1141303823600717885> {description}",
                        colour=discord.Colour.blue())
                    await interaction.response.send_message(embed=embed)
                if result:
                    time1 = convert(time)
                    t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
                    t2 = datetime.datetime.fromtimestamp(int(t1))
                    t3 = datetime.datetime.fromtimestamp(t1)
                    asyncio.create_task(funktion(t2))
                    await cur.execute("INSERT INTO reminder(userID, grund, time, remindID) VALUES(%s, %s, %s, %s)",
                                      (interaction.user.id, description, t1, len(result) + 1))
                    embed = discord.Embed(
                        title=f"<:Astra_time:1141303932061233202> Erinnerung erstellt (ID {len(result) + 1})",
                        description=f"Erinnerung gesetzt auf {discord.utils.format_dt(t2, 'F')}\n<:Astra_arrow:1141303823600717885> {description}",
                        colour=discord.Colour.blue())
                    await interaction.response.send_message(embed=embed)

    @app_commands.command(name="anzeigen")
    async def reminder_list(self, interaction: discord.Interaction):
        """Get a list of reminders!"""
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

    @app_commands.command(name="löschen")
    async def reminder_delete(self, interaction: discord.Interaction, id: int):
        """Delete a reminder!"""
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


# Slash-Command Fehlerbehandlung
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    embed = discord.Embed(colour=discord.Colour.red())
    embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)

    if isinstance(error, app_commands.MissingPermissions):
        embed.title = "Fehlende Berechtigungen"
        embed.description = "❌ Du hast nicht die nötigen Berechtigungen, um diesen Befehl zu verwenden."

    elif isinstance(error, app_commands.BotMissingPermissions):
        embed.title = "Bot hat keine Berechtigung"
        embed.description = "❌ Ich habe nicht die nötigen Berechtigungen, um diesen Befehl auszuführen."

    elif isinstance(error, app_commands.CommandOnCooldown):
        embed.title = "Cooldown aktiv"
        embed.description = f"⏳ Bitte warte noch {round(error.retry_after, 2)} Sekunden, bevor du diesen Befehl erneut verwendest."

    elif isinstance(error, app_commands.CommandNotFound):
        embed.title = "Unbekannter Befehl"
        embed.description = "❌ Dieser Slash-Command wurde nicht gefunden."

    elif isinstance(error, app_commands.CheckFailure):
        embed.title = "Zugriff verweigert"
        embed.description = "❌ Du erfüllst nicht die Voraussetzungen für diesen Befehl."

    elif isinstance(error, app_commands.MissingRole):
        embed.title = "Fehlende Rolle"
        embed.description = "❌ Du brauchst eine bestimmte Rolle, um diesen Befehl zu benutzen."

    elif isinstance(error, app_commands.MissingAnyRole):
        embed.title = "Fehlende Rollen"
        embed.description = "❌ Du brauchst mindestens eine der benötigten Rollen."

    elif isinstance(error, app_commands.errors.TransformerError):
        embed.title = "Ungültige Eingabe"
        embed.description = "❌ Die eingegebenen Argumente sind ungültig oder konnten nicht umgewandelt werden."

    else:
        # Unbekannter Fehler – an Log-Channel senden
        embed.title = "Unbekannter Fehler"
        embed.description = "❌ Ein unerwarteter Fehler ist aufgetreten. Der Fehler wurde geloggt."

        # Fehler an Log-Channel senden
        log_channel = bot.get_channel(1141116983815962819)
        if log_channel:
            error_embed = discord.Embed(title="SlashCommand Error", colour=discord.Colour.red())
            error_embed.add_field(name="User", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            error_embed.add_field(name="Command", value=str(interaction.command), inline=False)
            error_embed.add_field(name="Error", value=f"```{str(error)}```", inline=False)
            await log_channel.send(embed=error_embed)

    # Versuche Antwort zu senden
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.InteractionResponded:
        pass

async def send_vote_dm(user_id, username):
    try:
        user = await bot.fetch_user(user_id)
        embed = discord.Embed(
            title="Danke fürs Voten von Astra",
            description=(
                f"<:Astra_boost:1141303827107164270> ``{user}({user.id})`` hat für **Astra** gevotet.\n"
                f"Du kannst alle 12 Stunden **[hier](https://top.gg/bot/811733599509544962/vote)** voten."
            ),
            colour=discord.Colour.blue(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(
            url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg"
        )
        embed.set_footer(
            text="Danke für deinen Support",
            icon_url="https://media.discordapp.net/attachments/813029623277158420/901963417223573524/Idee_2_blau.jpg"
        )
        await user.send(embed=embed)
        logging.info(f"DM an {username} ({user_id}) gesendet.")
    except Exception as e:
        logging.error(f"Fehler beim Senden der DM an {user_id}: {e}")


app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")  # Holt sich das Secret aus .env

@app.route("/dblwebhook", methods=["POST"])
def dbl_vote():
    auth = request.headers.get("Authorization")
    if auth != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    data = request.json
    user_id = int(data.get("id"))
    username = data.get("username", "Unbekannt")

    # Jetzt DM senden (async aus Flask!)
    asyncio.run_coroutine_threadsafe(
        send_vote_dm(user_id, username),
        bot.loop
    )

    logging.info(f"Vote von: {username} ({user_id})")
    return jsonify({"success": True})

async def main():
    async with bot:
        await bot.start(TOKEN)

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())