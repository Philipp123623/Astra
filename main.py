import discord
import random
from discord.ext import commands, tasks
from discord.app_commands import AppCommandError
from discord import app_commands
from discord.app_commands import Group
import math
import sys
import traceback
import asyncio
import aiomysql
import jishaku
import os
from dotenv import load_dotenv
import aiohttp
from datetime import date
import datetime
from typing import Literal

intents = discord.Intents.default()
intents.message_content = True

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


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
        self.task = False
        self.task2 = False
        self.task3 = False
        self.pool = None  # Pool-Objekt hier zentral gespeichert
        self.initial_extensions = [
            "cogs.help",
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
            await self.connect_db()
            await self.init_tables()
            await self.load_cogs()
            print("Astra ist online!")
            await asyncio.sleep(3)
            print("[PANEL-INFO] Script started!")
            self.keep_alive_task = self.loop.create_task(self.keep_db_alive())
        except Exception as e:
            print(f"❌ Fehler beim Setup:\n{e}")

    async def keep_db_alive(self):
        while True:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")  # Einfacher Testbefehl, um die Verbindung aufrechtzuerhalten
            await asyncio.sleep(120)  # Alle 2 Minuten

    async def connect_db(self):
        """Stellt den DB-Pool her und speichert ihn in self.pool"""
        self.pool = await aiomysql.create_pool(
            host='host',
            port=3306,
            user='username',
            password='password',
            db='db_name',
            autocommit=True,
            pool_recycle=3600,
            connect_timeout=5,
            maxsize=50
        )
        print("✅ DB-Verbindung erfolgreich")

    async def init_tables(self):
        """Initialisiert Tabellen und startet Tasks"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Tabellen erstellen
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
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS website_stats(servers BIGINT, users BIGINT, channels BIGINT, commands BIGINT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS afk(guildID BIGINT, userID BIGINT, reason TEXT, prevName TEXT, time TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS autoreact(guildID BIGINT, channelID BIGINT, emoji TEXT)")
                await cur.execute("CREATE TABLE IF NOT EXISTS blacklist(serverID BIGINT, word TEXT)")
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS reactionrole (guild_id BIGINT, emoji TEXT, msg_id BIGINT, role_id BIGINT)")
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

                print("✅ Tables Erfolgreich geladen")

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
                                print(f"❌ Reminder-Fehler: {e}")

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
                                print(f"❌ Voterole-Fehler: {e}")

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
                                print(f"❌ Giveaway-Fehler: {e}")

                    asyncio.create_task(starte_giveaway_tasks())
                    print("✅ Tasks Registered")

    async def load_cogs(self):
        """Lädt alle Cogs"""
        geladen, fehler = 0, 0
        await bot.load_extension("jishaku")
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                geladen += 1
            except Exception:
                fehler += 1
                print(f'❌ {ext} konnte nicht geladen werden', file=sys.stderr)
                traceback.print_exc()
                print('\n\n---------------------------------------------\n\n')
            print(f"✅ {geladen}/{geladen + fehler} Cogs geladen")

    async def on_message(self, msg):
        if msg.author.bot:
            return
        await bot.process_commands(msg)
        botcreated = str(bot.user.created_at.__format__('%A, %d %B, %Y'))
        if msg.content == f"<@{bot.user.id}>" or msg.content == f"<@!{bot.user.id}>":
            embed = discord.Embed(title="Astra", url="https://discord.gg/vwh2raq2Xu", colour=discord.Colour.blue(),
                                  description=f"Hallo Discord!\nIch bin Astra. Ich wurde geboren am {botcreated}\nIch habe viele Verschiedene Systeme und Befehle, welche ein Level- und Ticketsystem beinhalten.\nAlle Befehle sind /-Befehle. Das bedeueter, dass du sie ganz einfach finden kannst.\nWenn du irgendwelche Fragen und Probleme hast, kannst du uns gerne über unseren **[Support Server ➚](https://discord.gg/vwh2raq2Xu)** kontaktieren.\nWenn ich nun dein Interesse geweckt habe, kannst du mich ganz einfach **[Einladen ➚](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)** und mich ausprobieren")
            embed.set_author(name=msg.author, icon_url=msg.author.avatar)
            embed.set_footer(text="Astra Development ©2022 | Für mehr Informationen kontaktiere uns via Discord.",
                             icon_url=interaction.guild.icon)
            embed.set_thumbnail(url=msg.guild.icon)
            await msg.channel.send(embed=embed)
            await bot.process_commands(msg)


bot = Astra()


@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Game('Astra V2 out now! 💙'),
        status=discord.Status.online)
    bot.add_view(gw_button())


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
                    user = bot.get_user(userID)
                    guild = bot.get_guild(1141116981697859736)
                    role = guild.get_role(1141116981756575875)
                embed = discord.Embed(title="<:Astra_time:1061392304608391229> You can vote again!",
                                      url="https://top.gg/de/bot/811733599509544962/vote",
                                      description=f"Der Cooldown von 12h ist vorbei. Es wäre schön wenn du wieder Votest.\nAls belohnung erhällst du eine Spezielle Rolle auf unserem [Support server](https://discord.gg/NH9DdSUJrE).",
                                      colour=discord.Colour.blue())
                try:
                    await user.send(embed=embed)
                except:
                    pass

                try:
                    await user.remove_roles(voterole)
                except:
                    pass
                await cur.execute("DELETE FROM voterole WHERE userID = (%s)", (userID))


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


gw = Group(name='gewinnspiel', description="Astra")


@gw.command(name="starten")
async def gw_start(interaction: discord.Interaction, *, preis: str, kanal: discord.TextChannel, gewinner: int,
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
                        (interaction.guild.id, interaction.user.id, channel.id, 0, msg.id, price, winner, t1, role.id,
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
                        (interaction.guild.id, interaction.user.id, channel.id, 0, msg.id, price, winner, t1, "Not Set",
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
                        f"** The Giveaway will take place in {channel.mention}**")


@gw.command(name="verwalten")
async def gw_verw(interaction: discord.Interaction, *, aktion: Literal[
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
                        await cur.execute("SELECT time FROM giveaway_active WHERE guildID = (%s) AND messageID = (%s)",
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


bot.tree.add_command(gw)


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
                    print("test")
                    userID = eintrag[0]
                    print(userID)
                    grund = eintrag[1]
                    user = bot.get_user(int(userID))
                    embed = discord.Embed(title="<:Astra_time:1141303932061233202> Erinnerung abgeschlossen.",
                                          description=f"Hier ist deine Erinnerung\n<:Astra_arrow:1141303823600717885> {grund}",
                                          colour=discord.Colour.blue())
                await user.send(embed=embed)
                await cur.execute("DELETE FROM reminder WHERE grund = (%s)", (grund))


reminder = Group(name='erinnerung', description='description')


@reminder.command(name="erstellen")
async def reminder_set(interaction: discord.Interaction, beschreibung: str, zeit: Literal[
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
                embed = discord.Embed(title=f"<:Astra_time:1141303932061233202> Erinnerung erstellt (ID {remindid})",
                                      description=f"Erinnerung gesetzt auf {discord.utils.format_dt(t2, 'F')}\n<:Astra_arrow:1141303823600717885> {description}",
                                      colour=discord.Colour.blue())
                await interaction.response.send_message(embed=embed)
            if result:
                time1 = convert(time)
                print(datetime.datetime.utcnow())
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


@reminder.command(name="anzeigen")
async def reminder_list(interaction: discord.Interaction):
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
                    print(time)
                    embed.add_field(name=f"ID: {warnID}",
                                    value=f"<:Astra_arrow:1141303823600717885>: {reason}\n<:Astra_time:1141303932061233202> Endet: <t:{time}:F>",
                                    inline=True)

                await interaction.response.send_message(embed=embed)


@reminder.command(name="löschen")
async def reminder_delete(interaction: discord.Interaction, id: int):
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


bot.tree.add_command(reminder)


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
                          description="Astra is the only Bot you need, to manage your whole server. There are many servers who use Astra. Maybe you will be the next one?\n\n> __**What do we offer?**__\n・<:Astra_ticket:1141833836204937347> Public Ticketsystem for your server\n・<:Astra_time:1141303932061233202> Automoderation\n・<:Astra_messages:1141303867850641488> Welcome/Leave Messages\n・<:Astra_settings:1141303908778639490> Joinrole&Botrole\n・<:Astra_herz:1141303857855594527> reactionroles\n・<:Astra_global1:1141303843993436200> Globalchat\n\n\n> __**Useful Links:**__\n・[Invite Astra ➚](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n・[Get Support ➚](https://discord.gg/vwh2raq2Xu)",
                          colour=discord.Colour.blue())
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/842039934142513152/879880068262940672/Astra-premium3.gif")
    embed.set_thumbnail(url=ctx.guild.icon.url)
    msg = await ctx.send("https://discord.gg/vwh2raq2Xu", embed=embed)
    await ctx.message.delete()
    await msg.publish()


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


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        embed = discord.Embed(title="Not Owner", description="❌ You must be a Bot Owner to run this command.",
                              colour=discord.Colour.red())
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar)
        await ctx.send(embed=embed)


@bot.tree.command()
async def test(interaction: discord.Interaction, number: int, string: str):
    await interaction.response.send_message(f'{number=} {string=}', ephemeral=True)


bot.run(TOKEN, reconnect=True)
