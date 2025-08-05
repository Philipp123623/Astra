import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from PIL import Image, ImageOps, ImageDraw
from io import BytesIO
import pyfiglet
from typing import Optional
import io
import aiohttp
import urllib.parse
import qrcode
import os
import requests
import random
import asyncio


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


def check():
    print(1)

    def nsfw(interaction: discord.Interaction):
        print(2)
        return interaction.channel.is_nsfw()

    print(3)

    return app_commands.check(nsfw)


def make_qr(filename, msg):
    img = qrcode.make(msg)
    img.save(filename)


class fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="wanted")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def wanted(self, interaction: discord.Interaction, member: discord.Member = None):
        """Erstellt ein 'Gesucht' Plakat mit dem Profilbild eines Users."""
        if member is None:
            member = interaction.user
        if member != None:
            wanted = Image.open("wanted.jpg")
            asset = member.avatar
            data = BytesIO(await asset.read())
            pfp = Image.open(data)
            pfp = pfp.resize((307, 307))
            wanted.paste(pfp, (165, 273))
            wanted.save("profile.jpg")
            embed = discord.Embed(title=" ", description=f"**Nach {member} wird gefahndet!**", colour=discord.Colour.blue())
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
            file = discord.File("profile.jpg", filename="profile.jpg")
            embed.set_image(url="attachment://profile.jpg")
            await interaction.response.send_message(file=file, embed=embed)
            os.remove("profile.jpg")

    @app_commands.command(name="pix")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def pix(self, interaction: discord.Interaction, member: discord.Member = None):
        """Verpixelt das Profilbild eines Users."""
        if member == None:
            member = interaction.user
        if member != None:
            url = str(member.avatar)
            url = url.replace("gif", "png")
            img = Image.open(requests.get(url, stream=True).raw)
            old = img.size
            img = img.resize((16, 16))
            img = img.resize(old)
            img.save('pix.png')
            embed = discord.Embed(title=" ", description=f"**{member} wurde verpixelt!**", colour=discord.Colour.blue())
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
            file = discord.File("pix.png", filename="pix.png")
            embed.set_image(url="attachment://pix.png")
            await interaction.response.send_message(file=file, embed=embed)
            os.remove("pix.png")

    @app_commands.command(name="wasted")
    @app_commands.describe(user="Der User, dessen Profilbild genutzt werden soll (optional)")
    async def wasted(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Sendet ein Profilbild mit Wasted-Effekt über SomeRandomAPI."""
        await interaction.response.defer()
        user = user or interaction.user
        avatar_url = user.display_avatar.replace(format="png", size=256).url
        encoded_url = urllib.parse.quote(avatar_url, safe='')
        api_url = f"https://some-random-api.com/canvas/wasted?avatar={encoded_url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("❌ Fehler bei der API-Anfrage.", ephemeral=True)
                img_bytes = await resp.read()
                file = discord.File(io.BytesIO(img_bytes), filename="wasted.png")
                embed = discord.Embed(description="**Wasted!**", color=discord.Color.dark_gray())
                embed.set_image(url="attachment://wasted.png")
                await interaction.followup.send(embed=embed, file=file)

    # Gay
    @app_commands.command(name="gay")
    @app_commands.describe(user="Der User, dessen Profilbild genutzt werden soll (optional)")
    async def gay(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Sendet ein Profilbild mit Rainbow/Gay-Effekt über SomeRandomAPI."""
        await interaction.response.defer()
        user = user or interaction.user
        avatar_url = user.display_avatar.replace(format="png", size=256).url
        encoded_url = urllib.parse.quote(avatar_url, safe='')
        api_url = f"https://some-random-api.com/canvas/gay?avatar={encoded_url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("❌ Fehler bei der API-Anfrage.", ephemeral=True)
                img_bytes = await resp.read()
                file = discord.File(io.BytesIO(img_bytes), filename="gay.png")
                embed = discord.Embed(description="🏳️‍🌈 **Gay!**", color=discord.Color.magenta())
                embed.set_image(url="attachment://gay.png")
                await interaction.followup.send(embed=embed, file=file)

    # Triggered
    @app_commands.command(name="triggered")
    @app_commands.describe(user="Der User, dessen Profilbild genutzt werden soll (optional)")
    async def triggered(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Sendet ein Profilbild mit Triggered-Effekt (animiertes GIF) über SomeRandomAPI."""
        await interaction.response.defer()
        user = user or interaction.user
        avatar_url = user.display_avatar.replace(format="png", size=256).url
        encoded_url = urllib.parse.quote(avatar_url, safe='')
        api_url = f"https://some-random-api.com/canvas/triggered?avatar={encoded_url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("❌ Fehler bei der API-Anfrage.", ephemeral=True)
                img_bytes = await resp.read()
                file = discord.File(io.BytesIO(img_bytes), filename="triggered.gif")
                embed = discord.Embed(description="**Triggered!**", color=discord.Color.red())
                embed.set_image(url="attachment://triggered.gif")
                await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(name="color")
    @app_commands.describe(hex="Hex-Code der Farbe, z. B. ff0055 oder #ff0055")
    async def color(self, interaction: discord.Interaction, hex: str):
        """Zeigt eine Farbe als Bild über Some Random API."""
        hex_color = hex.lstrip("#")
        # Optional: Validierung
        if len(hex_color) not in (3, 6):
            return await interaction.response.send_message(
                "Bitte gültigen Hex-Code (z. B. ff0055) angeben.", ephemeral=True
            )

        api_url = f"https://api.some-random-api.com/canvas/colorviewer?hex={hex_color}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    return await interaction.response.send_message(
                        f"❌ Fehler bei der API-Anfrage ({resp.status}):\n{err}", ephemeral=True
                    )
                img_bytes = await resp.read()
                buf = io.BytesIO(img_bytes)
                file = discord.File(buf, filename="color.png")
                embed = discord.Embed(
                    title=f"Hier ist die Farbe #{hex_color}",
                    color=int(hex_color, 16) if len(hex_color) == 6 else None
                )
                embed.set_image(url="attachment://color.png")
                await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="meme", nsfw=True)
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def meme(self, interaction: discord.Interaction):
        """Zeigt lustige Memes."""
        if interaction.channel.is_nsf():
            return await interaction.response.send_message("<:Astra_x:1141303954555289600> Dieser Command kann nur in NSFW-Channel ausgeführt werden!", ephemeral=True)
        else:
            async with aiohttp.ClientSession() as cs:
                async with cs.get('https://www.reddit.com/r/memes/random/.json') as r:
                    res = await r.json()

                    data = res[0]['data']['children'][0]['data']

                    image = data['url']
                    permalink = data['permalink']
                    url = f'https://reddit.com{permalink}'
                    title = data['title']
                    ups = data['ups']
                    downs = data['downs']
                    comments = data['num_comments']

                    embed = discord.Embed(colour=discord.Colour.blue(), title=title, url=url)
                    embed.set_image(url=image)
                    embed.set_footer(text=f"🔺 {ups} | 🔻 {downs} | 💬 {comments} ")
                    await interaction.response.send_message(embed=embed)

    @app_commands.command(name="qrcode")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def qrcode(self, interaction: discord.Interaction, link: str):
        """Erstelle einen QR-Code für einen Link."""
        time = datetime.utcnow()
        user = interaction.user.name
        name = interaction.channel.name
        if link is not None:
            make_qr("qrcode.png", link)

            embed = discord.Embed(title=" ", description=f"**Qr Code für {link}**",
                                  colour=discord.Colour.blue())
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
            file = discord.File("qrcode.png", filename="qrcode.png")
            embed.set_image(url="attachment://qrcode.png")
            await interaction.response.send_message(file=file, embed=embed)
            os.remove('qrcode.png')

    @app_commands.command(name="lostrate")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def lostrate(self, interaction: discord.Interaction, user: discord.Member = None):
        """Kalkuliert, wie Lost ein user ist."""
        if user is None:
            user = interaction.user
        x = random.randint(1, 100)
        embed = discord.Embed(colour=discord.Color.gold(), description=f"{user.mention} is LOST to {x}%.")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="iq")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def iq(self, interaction: discord.Interaction, user: discord.Member = None):
        """Find heraus wie hoch der IQ eines Users ist.."""
        if user is None:
            user = interaction.user
        x = random.randint(14, 230)
        if x < 40:
            iq = "ein ziemlicher Idiot."
        elif x < 80:
            iq = "nicht der Beste in Mathe."
        elif x < 150:
            iq = "sehr durchschnittlich."
        elif x < 200:
            iq = "jedenfalls ziemlich schlau ..."
        else:
            iq = "ein **SUPERGEHIRN**!"
        embed = discord.Embed(colour=discord.Color.gold(), description=f"Mit einem IQ von {x} ist {user.mention} {iq}")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ask")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def ask(self, interaction: discord.Interaction, question: str):
        """Frage berühmte Persöhnlichkeiten."""
        all_gifs = ['https://tenor.com/view/shrek-of-course-sarcasm-sarcastic-really-gif-14499396',
                    'https://tenor.com/view/timon-lion-king-nope-no-shake-gif-3834543',
                    'https://tenor.com/view/yes-nod-old-spice-oh-yes-commercial-gif-15384634',
                    'https://tenor.com/view/agt-americas-got-talent-stop-buzzer-no-gif-4434972',
                    'https://tenor.com/view/yes-melb-agt-americas-got-talent-agtgifs-gif-4519427',
                    'https://tenor.com/view/egal-singing-ocean-sea-boat-ride-gif-16080257',
                    'https://tenor.com/view/thats-a-no-elmo-shaking-shaking-head-nope-gif-7663315',
                    'https://tenor.com/view/definitiv-nein-n%C3%B6-tv-total-raab-gif-11127197',
                    'https://tenor.com/view/shannon-sharpe-shay-nope-nah-nuhuh-gif-12298561',
                    'https://tenor.com/view/ja-jack-nicholson-fryslan-friesland-omrop-gif-12148366',
                    'https://tenor.com/view/ok-okay-awkward-smile-gif-5307535',
                    'https://tenor.com/view/elmo-shrug-gif-5094560',
                    'https://tenor.com/view/horrible-crying-noooo-no-gif-11951898',
                    'https://tenor.com/view/maaaayyybe-fallon-maybe-gif-5280420',
                    'https://tenor.com/view/idk-i-dont-know-sebastian-stan-lol-wtf-gif-5364867',
                    'https://tenor.com/view/yes-no-maybe-owl-funny-gif-13722109',
                    'https://tenor.com/view/yes-minions-movie-minions-gi-fs-minions-gif-5026357',
                    'https://tenor.com/view/steve-carell-no-please-no-gif-5026106',
                    'https://tenor.com/view/obama-wtf-why-president-wut-gif-12221156',
                    'https://tenor.com/view/trump-donald-trump-dance-thinking-idk-gif-5753267',
                    'https://tenor.com/view/inauguration-cnn2017-donald-trump-finger-wag-no-absolutely-not-gif-12953442',
                    'https://tenor.com/view/angela-merkel-keine-ahnung-no-clue-kanzlerin-deutschland-gif-11189427',
                    'https://tenor.com/view/merkel-n%C3%B6-n%C3%B6merkel-merkel-meme-gif-gif-16050778',
                    'https://tenor.com/view/angela-merkel-schmunzel-nicken-zufrieden-politik-gif-11862007']
        await interaction.response.send_message(f"**{question}**\n\n{random.choice(all_gifs)}")

    @app_commands.command(name="love")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def love(self, interaction: discord.Interaction, u1: discord.Member, u2: discord.Member):
        """Finde heraus, wie sehr sich 2 User lieben."""
        if u2 is None and u1 is not None:
            u2 = interaction.message.author

        love_per = random.randint(1, 100)

        # erstes Embed
        embed = discord.Embed(color=discord.Color.orange(),
                              description=f"Sieh an, wie sehr {u1.mention} und {u2.mention} sich gegenseitig lieben ... <3")
        embed.add_field(name="❤️ Loverator", value="💌 Ich kalkuliere deren Liebe ...")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(3)

        # 2. embed
        embed2 = discord.Embed(color=discord.Color.orange(),
                              description=f"Sieh an, wie sehr {u1.mention} und {u2.mention} sich gegenseitig lieben ... <3")
        embed2.add_field(name="❤️ Loverator",
                         value=f"{u1.mention} und {u2.mention} lieben sich zu **{love_per}%**.")
        embed2.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        message = await interaction.original_message()
        await message.edit(embed=embed2)

    @app_commands.command(name="los")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def los(self, interaction: discord.Interaction, user: discord.Member):
        """Ziehe ein Rubbellos."""
        choices1 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices2 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices3 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices4 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices5 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices6 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices7 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices8 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        choices9 = ["||⚪||", "||🔵||", "||⚪||", "||⚪||"]
        ergebnis1 = random.choice(choices1)
        ergebnis2 = random.choice(choices2)
        ergebnis3 = random.choice(choices3)
        ergebnis4 = random.choice(choices4)
        ergebnis5 = random.choice(choices5)
        ergebnis6 = random.choice(choices6)
        ergebnis7 = random.choice(choices7)
        ergebnis8 = random.choice(choices8)
        ergebnis9 = random.choice(choices9)
        embed = discord.Embed(colour=discord.Colour.dark_blue(), title="Rubbellos",
                              description=f"{ergebnis1} {ergebnis2} {ergebnis3}\n"
                                          f"{ergebnis4} {ergebnis5} {ergebnis6}\n"
                                          f"{ergebnis7} {ergebnis8} {ergebnis9}\n")
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        embed.set_footer(text="3 von 🔵 in Vertical, Horizontal und Diagonal")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="games")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def games(self, interaction: discord.Interaction):
        """Zeigt alle Spiele an, die grade gespielt werden."""
        msg = ':chart: Aktuelle Spiele:\n'
        msg += '```js\n'
        for member in interaction.guild.members:
            for activity in member.activities:
                if isinstance(activity, discord.Game):
                    msg += f'{activity}\n'
                elif isinstance(activity, discord.Activity):
                    msg += f'{activity.name}\n'

        msg += '```'
        await interaction.response.send_message(msg)


    @app_commands.command(name="password")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def password(self, interaction: discord.Interaction):
        """Generiert ein zufälliges Passwort für dich."""
        user = interaction.user
        letters = ["a", "A", "b", "B", "c", "C", "d", "D", "e", "E", "f", "F", "g", "G", "h", "H", "i", "I", "j", "J",
                   "k", "K", "l", "L", "m", "M", "n", "N", "o", "O", "p", "P", "q", "Q", "r", "R", "s", "S", "t", "T",
                   "u", "U", "v", "V", "w", "W", "x", "X", "y", "Y", "z", "Z"]
        choices = [f"{random.choice(letters)}", f"{random.randint(1, 9)}", f"{random.choice(letters)}",
                   f"{random.randint(1, 9)}", f"{random.choice(letters)}", f"{random.randint(1, 9)}",
                   f"{random.choice(letters)}", f"{random.randint(1, 9)}", f"{random.choice(letters)}"]
        x1 = random.choice(choices)
        x2 = random.choice(choices)
        x3 = random.choice(choices)
        x4 = random.choice(choices)
        x5 = random.choice(choices)
        x6 = random.choice(choices)
        x7 = random.choice(choices)
        x8 = random.choice(choices)
        x9 = random.choice(choices)
        x10 = random.choice(choices)
        x11 = random.choice(choices)
        x12 = random.choice(choices)
        x13 = random.choice(choices)
        x14 = random.choice(choices)
        x15 = random.choice(choices)
        x16 = random.choice(choices)
        x17 = random.choice(choices)
        x18 = random.choice(choices)
        x19 = random.choice(choices)
        x20 = random.choice(choices)
        x21 = random.choice(choices)
        x22 = random.choice(choices)
        result = f"||{x1}{x2}{x3}{x4}{x5}{x6}{x7}{x8}{x9}{x10}{x11}{x12}{x13}{x14}{x15}{x16}{x17}{x18}{x19}{x20}{x21}{x22}||"

        embed = discord.Embed(colour=discord.Colour.green(), title="🔐 Passwort",
                              description=f"**Gebe dein Passwort nicht einfach weiter.**")
        embed.set_author(name=user, icon_url=user.avatar)
        embed.add_field(name="Generiertes Passwort:", value=result)
        await user.send(embed=embed)
        await interaction.response.send_message(f"{user.mention}, ich habe dir das Passwort in deine DM's gesendet.")
        return


async def setup(bot: commands.Bot):
    await bot.add_cog(fun(bot))
