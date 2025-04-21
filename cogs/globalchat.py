import discord
from discord.ext import commands
from discord import app_commands
from discord import Message, Guild, TextChannel, Permissions
import pytz
import json
import asyncio
import os
from typing import Literal

slowmode = []
slow_dm = []
bad_words = ['arsch', 'arschloch', 'wixer', 'wixxer', 'nigger', 'niggah', 'nigga', 'moor', 'NIGGA', 'NIGGAH', 'NIGGER',
             'ficken', 'gefickt', 'nudes', 'nude', 'titten', 'vagina', 'penis', 'wagina', 'fotze', 'stripclub', 'nutte',
             'nutten', 'orgasmus'
                       'orgasm', 'sex toy', 'erotic', 'erotisch', 'dildo', 'doggie style', 'doggiestyle', 'doggy style',
             'doggystyle', 'blow job', 'blowjob', 'vagina', 'https://', 'http://', 'discord.gg/', 'www.', 'schwanz',
             'Schwanz']

if os.path.isfile("./servers.json"):
    with open('./servers.json', encoding='utf-8') as f:
        servers = json.load(f)
else:
    servers = {"./servers": []}
    with open('./servers.json', 'w') as f:
        json.dump(servers, f, indent=4)


async def user_init_data(author_id):
    target = str(author_id)

    with open('users.json') as f:
        users_data = json.load(f)

    if target in users_data:
        return False
    else:
        users_data[target] = {}
        users_data[target]["lvl-points"] = 0
        users_data[target]["team"] = False
        users_data[target]["banned"] = False

    with open('./users.json', 'w') as f:
        json.dump(users_data, f)
    return True


async def user_get_data():
    with open('./users.json') as f:
        users_data = json.load(f)
    return users_data


async def user_lvl(author_id):
    users_data = await user_get_data()
    target = str(author_id)
    target_lvl = users_data[target]["lvl-points"]
    lvl = 0
    step = 5
    for level in range(1, 101):
        if level <= 3:
            step += 5
        elif level <= 5:
            step += 10
        elif level <= 10:
            step += 15
        elif level <= 15:
            step += 20
        elif level <= 20:
            step += 25
        elif level <= 30:
            step += 35
        elif level <= 40:
            step += 45
        elif level <= 50:
            step += 70
        elif level <= 75:
            step += 100
        elif level <= 80:
            step += 150
        elif level <= 90:
            step += 300
        else:
            step += 500

        if target_lvl >= step:
            lvl = level
    return str(lvl)


async def user_inc_lvl(author_id):
    users_data = await user_get_data()
    target_lvl = await user_lvl(author_id)
    target = str(author_id)
    users_data[target]["lvl-points"] += 1
    with open('./users.json', 'w') as f:
        json.dump(users_data, f)


async def is_banned(author_id):
    users_data = await user_get_data()
    return users_data[str(author_id)]["banned"]


async def is_mod(author_id):
    users_data = await user_get_data()
    return users_data[str(author_id)]["team"]


async def is_owner(author_id):
    if author_id == 789555434201677824:
        return True
    else:
        return False


def guild_exists(guildid):
    for server in servers['servers']:
        if int(server['guildid'] == int(guildid)):
            return True
    return False


def get_globalChat(guild_id, channelid=None):
    globalChat = None
    for server in servers["servers"]:
        if int(server["guildid"]) == int(guild_id):
            if channelid:
                if int(server["channelid"]) == int(channelid):
                    globalChat = server
            else:
                globalChat = server
    return globalChat


def get_globalChat_id(guild_id):
    globalChat = -1
    i = 0
    for server in servers["servers"]:
        if int(server["guildid"]) == int(guild_id):
            globalChat = i
        i += 1
    return globalChat


##########


class globalchat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_all(self, embed, message):
        conent = message.content
        author = message.author
        for server in servers["servers"]:
            guild: Guild = self.bot.get_guild(int(server["guildid"]))
            if guild:
                channel: TextChannel = guild.get_channel(int(server["channelid"]))
                if channel:
                    perms: Permissions = channel.permissions_for(guild.get_member(self.bot.user.id))
                    if perms.send_messages:
                        if perms.embed_links and perms.attach_files and perms.external_emojis:
                            try:
                                await channel.edit(slowmode_delay=5)
                            except:
                                pass
                            await channel.send(embed=embed)
                        else:
                            await channel.send('{0}: {1}'.format(author.name, conent))
                            await channel.send('Manche Rechte Fehlen.'
                                               '`Nachrichten Senden` `Links Einbetten` `Dateien Anhängen`'
                                               '`Externe Emojis verwenden`')
        try:
            await message.delete()
        except:
            pass

    async def sendAll(self, message: Message):
        users_data = await user_get_data()
        conent = message.content
        author = message.author
        attachments = message.attachments
        de = pytz.timezone('Europe/Berlin')
        icon = author.avatar
        author_lvl = await user_lvl(message.author.id)
        embed = discord.Embed(title=message.author, description=conent,
                              timestamp=discord.utils.utcnow().astimezone(tz=de),
                              color=0x36393F)
        embed.set_author(name=f'👥 User - Level {author_lvl}', icon_url=icon)

        if users_data[str(message.author.id)]["team"] == True:
            embed = discord.Embed(title=message.author, description=conent,
                                  timestamp=discord.utils.utcnow().astimezone(tz=de),
                                  color=0x36393F)
            embed.set_author(name=f'🛠 Staff - Level {author_lvl}', icon_url=icon)
        else:
            if 1 < int(author_lvl) < 5:
                embed = discord.Embed(title=message.author, description=conent,
                                      timestamp=discord.utils.utcnow().astimezone(tz=de),
                                      color=0xe6de37)
                embed.set_author(name=f'🌴 Beginner - Level {author_lvl}', icon_url=icon)
            if 5 < int(author_lvl) < 25:
                embed = discord.Embed(title=message.author, description=conent,
                                      timestamp=discord.utils.utcnow().astimezone(tz=de),
                                      color=0xe63737)
                embed.set_author(name=f'🔥 Advanced - Level {author_lvl}', icon_url=icon)
            if 25 < int(author_lvl) < 40:
                embed = discord.Embed(title=message.author, description=conent,
                                      timestamp=discord.utils.utcnow().astimezone(tz=de),
                                      color=0x339be6)
                embed.set_author(name=f"⭐ Amateur - Level {author_lvl}", icon_url=icon)
            if 40 < int(author_lvl) < 60:
                embed = discord.Embed(title=message.author, description=conent,
                                      timestamp=discord.utils.utcnow().astimezone(tz=de),
                                      color=0x33e680)
                embed.set_author(name=f"🌹 Professional - Level {author_lvl}", icon_url=icon)
            if 60 < int(author_lvl) < 80:
                embed = discord.Embed(title=message.author, description=conent,
                                      timestamp=discord.utils.utcnow().astimezone(tz=de),
                                      color=0x5d33e6)
                embed.set_author(name=f'🥇 Master - Level {author_lvl}', icon_url=icon)
            if int(author_lvl) > 80:
                embed = discord.Embed(title=message.author, description=conent,
                                      timestamp=discord.utils.utcnow().astimezone(tz=de),
                                      color=0x1aecff)
                embed.set_author(name=f'💎 Legend - Level {author_lvl}', icon_url=icon)
        if message.reference is not None:
            embed.add_field(
                name=f'<:Astra_messages:1141303867850641488> Antwortete auf: ``{message.reference.cached_message.embeds[0].title}``',
                value=f'> {message.reference.cached_message.embeds[0].description} - [**Nachricht**]({message.reference.jump_url}).',
                inline=False)
        icon_url = "https://cdn.icon-icons.com/icons2/2108/PNG/512/discord_icon_130958.png"
        icon = message.guild.icon
        if icon:
            icon_url = icon
        embed.set_thumbnail(url=icon_url)
        online = 0
        for i in message.guild.members:
            if str(i.status) == 'online':
                online += 1
        embed.set_footer(
            text=f'{message.guild.name} (🔋{online} - 👥{len([m for m in message.guild.members if not m.bot])} - 🤖{len([m for m in message.guild.members if m.bot])})',
            icon_url=icon_url)

        links = f'<:Astra_user:1141303940365959241> [Invite](https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=1899359446&scope=bot%20applications.commands) ║ '
        globalchat = get_globalChat(message.guild.id, message.channel.id)
        if len(globalchat["invite"]) > 0:
            invite = globalchat["invite"]
            if 'discord.gg' not in invite:
                invite = 'https://discord.gg/{}'.format(invite)
            links += f'<:Astra_url:1141303937056657458>  [Server Invite]({invite})'

        embed.add_field(name='Links', value=links, inline=False)

        if len(attachments) > 0:
            img = attachments[0]
            embed.set_image(url=img.url)

        global slowmode
        if author.id in slowmode:
            await message.delete()
            try:
                if author.id not in slow_dm:
                    slow_dm.append(author.id)
                    await author.send(
                        embed=discord.Embed(description='Du kannst nur eine Nachricht alle 5 Sekunden senden.',
                                            colour=0xFF0000))
                    await asyncio.sleep(2)
                    slow_dm.remove(author.id)
            except:
                pass
        else:
            slowmode.append(author.id)
            await user_inc_lvl(message.author.id)
            await self.send_all(embed, message)
            await asyncio.sleep(5)
            slowmode.remove(author.id)
            return

    @commands.command(name="globalban")
    @commands.has_permissions(administrator=True)
    async def globalban(ctx, member: discord.Member):
        users_data = await user_get_data()
        if await is_mod(ctx.author.id) or await is_owner(ctx.author.id):
            if member.id != 679706007219339376 and member.id != ctx.author.id:
                await user_init_data(member.id)
                users_data = await user_get_data()
                users_data[str(member.id)]["banned"] = True
                with open('users.json', 'w') as f:
                    json.dump(users_data, f)
                await ctx.send(
                    embed=discord.Embed(description=f'{member.mention} wurde erfolgreich gebannt!', colour=0xF44D4D))
            else:
                await ctx.send(embed=discord.Embed(description='Du kannst den Bot Developer oder dich selbst nicht bannen!',
                                                   colour=discord.Colour.blue()))
        else:
            await ctx.message.delete()

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        if not msg.content.startswith("a!"):
            if get_globalChat(msg.guild.id, msg.channel.id):
                if not any(x in msg.content.casefold() for x in bad_words):
                    users_data = await user_get_data()
                    author_id = msg.author.id
                    a = await user_init_data(author_id)
                    if a == True:
                        users_data = await user_get_data()
                    if str(msg.author.id) in users_data and users_data[str(msg.author.id)]["banned"] != True:
                        await self.sendAll(msg)
                        return
                    else:
                        await msg.delete()
                        if msg.author.id not in slow_dm:
                            info_msg = discord.Embed(
                                description=f'{msg.author.mention} du bist gebannt und kannst den globalchat nicht mehr nutzen.\n'
                                            f'--> [Support Server](https://discord.gg/vwh2raq2Xu)', colour=0xF44D4D)
                            await msg.author.send(embed=info_msg)
                            slow_dm.append(msg.author.id)
                            slow_dm.remove(msg.author.id)
                else:
                    try:
                        await msg.delete()
                    except:
                        pass
                    try:
                        await msg.author.send(
                            embed=discord.Embed(description='Bitte drücke dich ordentlich aus!', colour=0xF44D4D))
                    except:
                        pass

    @app_commands.command(name="globalchat")
    async def globalchat(self, interaction: discord.Interaction, argument: Literal['Einschalten', 'Ausschalten']):
        """Richte unseren Globalchat für deinen Server ein."""
        if argument == 'Einschalten':
            if interaction.user.guild_permissions.administrator:
                if not guild_exists(interaction.guild.id):
                    new_channel = await interaction.guild.create_text_channel('global chat')
                    topic = f"__**Willkommen in diesem Globachat**__ <a:chatbox:1141318924475043971>\n<:Astra_moderation:1141303878541918250> Discord Guidelines\nhttps://discord.com/guidelines\n<:Astra_moderation:1141303878541918250> - Der Ton sollte **höflich und freundlich** sein\n<:Astra_moderation:1141303878541918250> - **Streitigkeiten, Beleidigungen** und **Spam** sind in unserem Globalchat verboten!\n<:Astra_moderation:1141303878541918250> - Den **Anweisungen** unseres Teams ist stets Folge zu leisten!\n<:Astra_moderation:1141303878541918250> - Die Sprache unseres Globalchat ist **Deutsch**\n\n__**Wichtige Commands**__ <:Astra_file1:1141303837181886494>\n<:Astra_wichtig:1141303951862534224> - /globalchat\n\n__**Worauf ist zu achten?**__ <:Astra_accept:1141303821176422460>\nAlle in unseren globalen Chats gesendeten Nachrichten werden an alle verbundenen Server unseres Globalchat weitergeleitet!\n**Unser Team** behält sich das Recht vor, diese Regeln **jederzeit** zu ändern!"
                    await new_channel.edit(slowmode_delay=5, topic=topic)
                    server = {
                        "guildid": interaction.guild.id,
                        "channelid": new_channel.id,
                        "invite": f'{(await new_channel.create_invite()).url}'
                    }
                    servers["servers"].append(server)
                    with open('./servers.json', 'w') as f:
                        json.dump(servers, f, indent=4)
                    embed = discord.Embed(title="**Globalchat Setup erfolgreich!**",
                                          description=f"Der Globalchat kann nun in <#{new_channel.id}> genutzt werden!",
                                          color=0x56F44D)
                    await interaction.response.send_message(embed=embed)
                    await new_channel.send(embed=discord.Embed(
                        description='*Das ist der beginn dieses Globalchat...*\nSchreibe deine erste Nachricht!',
                        colour=0x36393F))
                else:
                    embed = discord.Embed(description="Du hast bereits einen Globalchat in deinem Server aktiv.\r\n",
                                          color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)
        if argument == 'Ausschalten':
            if interaction.user.guild_permissions.administrator:
                if guild_exists(interaction.guild.id):
                    globalid = get_globalChat_id(interaction.guild.id)
                    if globalid != -1:
                        servers["servers"].pop(globalid)
                        with open('./servers.json', 'w') as f:
                            json.dump(servers, f, indent=4)
                    embed = discord.Embed(title="**GlobalChat deaktiviert!**",
                                          description="Der Globalchat wurde erfolgreich entfernt. Du kannst ihn jederzeit neu aktivieren:"
                                                      f"`/globalchat add`",
                                          color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = discord.Embed(description="Du hast derzeit keinen Globalchat aktiv.\r\n"
                                                      f"Richte ihn mit `/globalchat add` ein!",
                                          color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(globalchat(bot))