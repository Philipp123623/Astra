import discord
from discord.ext import commands
from discord import app_commands
from discord import Message, Guild, TextChannel, Permissions
import pytz
import asyncio
import aiomysql
from typing import Literal

# Für slowmode und andere Interaktionen, die auf Nachrichtenteilen basieren
slowmode = []
slow_dm = []
bad_words = ['arsch', 'arschloch', 'wixer', 'wixxer', 'nigger', 'niggah', 'nigga', 'moor', 'NIGGA', 'NIGGAH', 'NIGGER',
             'ficken', 'gefickt', 'nudes', 'nude', 'titten', 'vagina', 'penis', 'wagina', 'fotze', 'stripclub', 'nutte',
             'nutten', 'orgasmus', 'orgasm', 'sex toy', 'erotic', 'erotisch', 'dildo', 'doggie style', 'doggiestyle',
             'doggy style', 'doggystyle', 'blow job', 'blowjob', 'vagina', 'https://', 'http://', 'discord.gg/', 'www.',
             'schwanz', 'Schwanz']

class GlobalChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_all(self, embed, message):
        content = message.content
        author = message.author
        for server in await self.get_servers():
            guild: Guild = self.bot.get_guild(server['guildid'])
            if guild:
                channel: TextChannel = guild.get_channel(server['channelid'])
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
                            await channel.send(f'{author.name}: {content}')
                            await channel.send('Fehlende Rechte: `Nachrichten Senden`, `Links Einbetten`, `Dateien Anhängen`, `Externe Emojis verwenden`')
        try:
            await message.delete()
        except:
            pass

    async def sendAll(self, message: Message):
        users_data = await self.get_user_data()
        content = message.content
        author = message.author
        attachments = message.attachments
        de = pytz.timezone('Europe/Berlin')
        icon = author.avatar
        author_lvl = await self.get_user_level(message.author.id)
        embed = discord.Embed(title=message.author, description=content, timestamp=discord.utils.utcnow().astimezone(tz=de), color=0x36393F)
        embed.set_author(name=f'👥 User - Level {author_lvl}', icon_url=icon)

        if users_data[str(message.author.id)]["team"]:
            embed.set_author(name=f'🛠 Staff - Level {author_lvl}', icon_url=icon)
        else:
            embed.color = self.get_level_color(author_lvl)
            embed.set_author(name=f'🌴 {self.get_level_name(author_lvl)} - Level {author_lvl}', icon_url=icon)

        if message.reference:
            embed.add_field(
                name=f'<:Astra_messages:1141303867850641488> Antwortete auf: ``{message.reference.cached_message.embeds[0].title}``',
                value=f'> {message.reference.cached_message.embeds[0].description} - [**Nachricht**]({message.reference.jump_url}).',
                inline=False)

        icon_url = message.guild.icon_url if message.guild.icon else "https://cdn.icon-icons.com/icons2/2108/PNG/512/discord_icon_130958.png"
        embed.set_thumbnail(url=icon_url)

        online = sum(1 for m in message.guild.members if m.status == discord.Status.online)
        embed.set_footer(
            text=f'{message.guild.name} (🔋{online} - 👥{len([m for m in message.guild.members if not m.bot])} - 🤖{len([m for m in message.guild.members if m.bot])})',
            icon_url=icon_url)

        if attachments:
            embed.set_image(url=attachments[0].url)

        if message.author.id in slowmode:
            await message.delete()
            try:
                if message.author.id not in slow_dm:
                    slow_dm.append(message.author.id)
                    await message.author.send(embed=discord.Embed(description='Du kannst nur eine Nachricht alle 5 Sekunden senden.', colour=0xFF0000))
                    await asyncio.sleep(2)
                    slow_dm.remove(message.author.id)
            except:
                pass
        else:
            slowmode.append(message.author.id)
            await self.increment_user_level(message.author.id)
            await self.send_all(embed, message)
            await asyncio.sleep(5)
            slowmode.remove(message.author.id)

    async def get_servers(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM gc_servers")
                return await cur.fetchall()

    async def get_user_data(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM users")
                return await cur.fetchall()

    async def get_user_level(self, user_id):
        users_data = await self.get_user_data()
        return users_data[str(user_id)]["lvl-points"]

    async def increment_user_level(self, user_id):
        users_data = await self.get_user_data()
        users_data[str(user_id)]["lvl-points"] += 1
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE users SET lvl-points = %s WHERE user_id = %s", (users_data[str(user_id)]["lvl-points"], user_id))

    def get_level_color(self, lvl):
        if lvl < 5:
            return 0xe6de37
        elif lvl < 25:
            return 0xe63737
        elif lvl < 40:
            return 0x339be6
        elif lvl < 60:
            return 0x33e680
        elif lvl < 80:
            return 0x5d33e6
        else:
            return 0x1aecff

    def get_level_name(self, lvl):
        if lvl < 5:
            return "Beginner 🌱"
        elif lvl < 25:
            return "Advanced 🏃‍♂️"
        elif lvl < 40:
            return "Amateur 🥉"
        elif lvl < 60:
            return "Professional 🏆"
        elif lvl < 80:
            return "Master 🥇"
        else:
            return "Legend ⚡"

    @app_commands.command(name="globalchat")
    async def globalchat(self, interaction: discord.Interaction, argument: Literal['Einschalten', 'Ausschalten']):
        """Richte unseren Globalchat für deinen Server ein."""
        if argument == 'Einschalten':
            if interaction.user.guild_permissions.administrator:
                if not await self.guild_exists(interaction.guild.id):
                    new_channel = await interaction.guild.create_text_channel('global chat')
                    topic = f"__**Willkommen in diesem Globachat**__ <a:chatbox:1141318924475043971>\n<:Astra_moderation:1141303878541918250> Discord Guidelines\nhttps://discord.com/guidelines\n<:Astra_moderation:1141303878541918250> - Der Ton sollte **höflich und freundlich** sein\n<:Astra_moderation:1141303878541918250> - **Streitigkeiten, Beleidigungen** und **Spam** sind in unserem Globalchat verboten!\n<:Astra_moderation:1141303878541918250> - Den **Anweisungen** unseres Teams ist stets Folge zu leisten!\n<:Astra_moderation:1141303878541918250> - Die Sprache unseres Globalchat ist **Deutsch**\n\n__**Wichtige Commands**__ <:Astra_file1:1141303837181886494>\n<:Astra_wichtig:1141303951862534224> - /globalchat\n\n__**Worauf ist zu achten?**__ <:Astra_accept:1141303821176422460>\nAlle in unseren globalen Chats gesendeten Nachrichten werden an alle verbundenen Server unseres Globalchat weitergeleitet!\n**Unser Team** behält sich das Recht vor, diese Regeln **jederzeit** zu ändern!"
                    await new_channel.edit(slowmode_delay=5, topic=topic)
                    invite_url = await new_channel.create_invite()
                    server = {
                        "guildid": interaction.guild.id,
                        "channelid": new_channel.id,
                        "invite": invite_url
                    }
                    await self.add_server_to_db(server)
                    embed = discord.Embed(title="**Globalchat Setup erfolgreich!**",
                                          description=f"Der Globalchat kann nun in <#{new_channel.id}> genutzt werden!",
                                          color=0x56F44D)
                    await interaction.response.send_message(embed=embed)
                    await new_channel.send(embed=discord.Embed(description='*Das ist der beginn dieses Globalchat...*\nSchreibe deine erste Nachricht!', colour=0x36393F))
                else:
                    embed = discord.Embed(description="Du hast bereits einen Globalchat in deinem Server aktiv.", color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)
        elif argument == 'Ausschalten':
            if interaction.user.guild_permissions.administrator:
                if await self.guild_exists(interaction.guild.id):
                    await self.remove_server_from_db(interaction.guild.id)
                    embed = discord.Embed(title="**GlobalChat deaktiviert!**", description="Der Globalchat wurde erfolgreich entfernt.", color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)

    async def guild_exists(self, guild_id):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM gc_servers WHERE guildid = %s", (guild_id,))
                result = await cur.fetchone()
                return result is not None

    async def add_server_to_db(self, server):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT INTO gc_servers (guildid, channelid, invite) VALUES (%s, %s, %s)",
                                  (server['guildid'], server['channelid'], server['invite']))
                await conn.commit()

    async def remove_server_from_db(self, guild_id):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM gc_servers WHERE guildid = %s", (guild_id,))
                await conn.commit()

    @app_commands.command(name="removeteam")
    async def remove_team(self, interaction: discord.Interaction, user: discord.User):
        """Entferne ein Teammitglied."""
        if interaction.user.guild_permissions.administrator:
            # Hier implementierst du die Logik, um das Teammitglied zu entfernen
            embed = discord.Embed(title="Teammitglied entfernt",
                                  description=f"{user.name} wurde erfolgreich aus dem Team entfernt.",
                                  color=0xF44D4D)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="addteam")
    async def add_team(self, interaction: discord.Interaction, user: discord.User):
        """Füge ein Teammitglied hinzu."""
        if interaction.user.guild_permissions.administrator:
            # Hier implementierst du die Logik, um das Teammitglied hinzuzufügen
            embed = discord.Embed(title="Teammitglied hinzugefügt",
                                  description=f"{user.name} wurde erfolgreich zum Team hinzugefügt.",
                                  color=0x56F44D)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="banuser")
    async def ban_user(self, interaction: discord.Interaction, user: discord.User):
        """Banne einen Benutzer."""
        if interaction.user.guild_permissions.administrator:
            await interaction.guild.ban(user)
            embed = discord.Embed(title="Benutzer gebannt",
                                  description=f"{user.name} wurde erfolgreich gebannt.",
                                  color=0xF44D4D)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unbanuser")
    async def unban_user(self, interaction: discord.Interaction, user: discord.User):
        """Entbanne einen Benutzer."""
        if interaction.user.guild_permissions.administrator:
            await interaction.guild.unban(user)
            embed = discord.Embed(title="Benutzer entbannt",
                                  description=f"{user.name} wurde erfolgreich entbannt.",
                                  color=0x56F44D)
            await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GlobalChatCog(bot))
