import discord
from discord.ext import commands
from discord import app_commands, Message, Guild, TextChannel, Permissions
import pytz
import asyncio
import logging
from typing import Literal

# Logging konfigurieren, sodass es auch in die systemd Logs geht
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')


bad_words = ['arsch', 'arschloch', 'wixer', 'wixxer', 'nigger', 'niggah', 'nigga', 'moor', 'ficken', 'gefickt', 'nudes',
             'nude', 'titten', 'vagina', 'penis', 'wagina', 'fotze', 'stripclub', 'nutte', 'nutten', 'orgasmus',
             'orgasm', 'sex toy', 'erotic', 'erotisch', 'dildo', 'doggie style', 'doggiestyle', 'doggy style',
             'doggystyle', 'blow job', 'blowjob', 'https://', 'http://', 'discord.gg/', 'www.', 'schwanz', 'Schwanz']

slowmode = []
slow_dm = []

class globalchat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user_data(self, user_id):
        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM gc_users WHERE id = (%s)", (user_id,))
                    return await cur.fetchone()
        except Exception as e:
            logger.error(f"Fehler beim Abrufen von Benutzerdaten: {e}")
            return None

    async def init_user_data(self, user_id):
        data = await self.get_user_data(user_id)
        if not data:
            try:
                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("INSERT INTO gc_users (id, lvl_points, team, banned) VALUES (%s, %s, %s, %s)",
                                           (user_id, 0, False, False))
            except Exception as e:
                logger.error(f"Fehler beim Initialisieren von Benutzerdaten: {e}")

    async def inc_lvl(self, user_id):
        await self.init_user_data(user_id)
        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE gc_users SET lvl_points = lvl_points + 1 WHERE id=%s", (user_id,))
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Levelpunkte: {e}")

    async def get_lvl(self, user_id):
        await self.init_user_data(user_id)
        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT lvl_points FROM gc_users WHERE id=%s", (user_id,))
                    points = (await cur.fetchone())[0]
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Levelpunkte: {e}")
            points = 0

        lvl = 0
        step = 5
        for level in range(1, 101):
            if level <= 3: step += 5
            elif level <= 5: step += 10
            elif level <= 10: step += 15
            elif level <= 15: step += 20
            elif level <= 20: step += 25
            elif level <= 30: step += 35
            elif level <= 40: step += 45
            elif level <= 50: step += 70
            elif level <= 75: step += 100
            elif level <= 80: step += 150
            elif level <= 90: step += 300
            else: step += 500
            if points >= step:
                lvl = level
        return lvl

    async def is_banned(self, user_id):
        data = await self.get_user_data(user_id)
        return data and data[3] == 1

    async def is_mod(self, user_id):
        data = await self.get_user_data(user_id)
        return data and data[2] == 1

    async def send_all(self, embed, message):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT guild_id, channel_id FROM gc_servers")
                rows = await cur.fetchall()
                for guild_id, channel_id in rows:
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue
                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        continue
                    perms: Permissions = channel.permissions_for(guild.get_member(self.bot.user.id))
                    if not perms.send_messages:
                        continue
                    try:
                        await channel.send(embed=embed)
                    except:
                        continue
        try:
            await message.delete()
        except:
            pass

    async def sendAll(self, message: Message):
        content = message.content
        author = message.author
        attachments = message.attachments
        de = pytz.timezone('Europe/Berlin')
        icon = author.avatar
        lvl = await self.get_lvl(author.id)
        embed = discord.Embed(title=str(author), description=content,
                              timestamp=discord.utils.utcnow().astimezone(tz=de), color=0x36393F)

        if await self.is_mod(author.id):
            embed.set_author(name=f'🛠 Staff - Level {lvl}', icon_url=icon)
        elif 1 < lvl < 5:
            embed.set_author(name=f'🌴 Beginner - Level {lvl}', icon_url=icon)
            embed.color = 0xe6de37
        elif 5 < lvl < 25:
            embed.set_author(name=f'🔥 Advanced - Level {lvl}', icon_url=icon)
            embed.color = 0xe63737
        elif 25 < lvl < 40:
            embed.set_author(name=f'⭐ Amateur - Level {lvl}', icon_url=icon)
            embed.color = 0x339be6
        elif 40 < lvl < 60:
            embed.set_author(name=f'🌹 Professional - Level {lvl}', icon_url=icon)
            embed.color = 0x33e680
        elif 60 < lvl < 80:
            embed.set_author(name=f'🥇 Master - Level {lvl}', icon_url=icon)
            embed.color = 0x5d33e6
        elif lvl > 80:
            embed.set_author(name=f'💎 Legend - Level {lvl}', icon_url=icon)
            embed.color = 0x1aecff
        else:
            embed.set_author(name=f'👥 User - Level {lvl}', icon_url=icon)

        if message.reference:
            try:
                ref_msg = message.reference.cached_message.embeds[0]
                embed.add_field(
                    name='Antwort auf:',
                    value=f'> {ref_msg.description} - [Nachricht]({message.reference.jump_url})', inline=False)
            except:
                pass

        if attachments:
            embed.set_image(url=attachments[0].url)

        if author.id in slowmode:
            await message.delete()
            if author.id not in slow_dm:
                slow_dm.append(author.id)
                try:
                    await author.send(embed=discord.Embed(description='Warte 5 Sekunden zwischen Nachrichten.', color=0xFF0000))
                except:
                    pass
                await asyncio.sleep(2)
                slow_dm.remove(author.id)
        else:
            slowmode.append(author.id)
            await self.inc_lvl(author.id)
            await self.send_all(embed, message)
            await asyncio.sleep(5)
            slowmode.remove(author.id)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        if not msg.guild:
            return
        if not msg.content.startswith("a!"):
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM gc_servers WHERE guild_id=%s AND channel_id=%s", (msg.guild.id, msg.channel.id))
                    result = await cur.fetchone()
                    if result:
                        if not any(x in msg.content.casefold() for x in bad_words):
                            if not await self.is_banned(msg.author.id):
                                await self.sendAll(msg)
                            else:
                                await msg.delete()
                                if msg.author.id not in slow_dm:
                                    slow_dm.append(msg.author.id)
                                    try:
                                        await msg.author.send(embed=discord.Embed(description='Du bist gebannt. [Support](https://discord.gg/vwh2raq2Xu)', color=0xF44D4D))
                                    except:
                                        pass
                                    slow_dm.remove(msg.author.id)
                        else:
                            try:
                                await msg.delete()
                            except:
                                pass
                            try:
                                await msg.author.send(embed=discord.Embed(description='Bitte drücke dich ordentlich aus!', color=0xF44D4D))
                            except:
                                pass

    @commands.command()
    @commands.is_owner()
    async def globalstaff(self, ctx, mode: Literal['add', 'remove'], member: discord.Member):
        if ctx.author.id == ctx.guild.owner_id or await self.is_mod(ctx.author.id):
            await self.init_user_data(member.id)
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE gc_users SET team = %s WHERE id = %s",
                                      (1 if mode == 'add' else 0, member.id))
            await ctx.send(embed=discord.Embed(
                description=f"{'✅' if mode == 'add' else '❌'} {member.mention} ist nun {'ein Teammitglied' if mode == 'add' else 'kein Teammitglied mehr'}!",
                color=0x33e680 if mode == 'add' else 0xF44D4D
            ))
        else:
            await ctx.message.delete()

    @commands.command()
    async def globalban(self, ctx, member: discord.Member):
        if await self.is_mod(ctx.author.id) or ctx.author.id == ctx.bot.owner_id:
            if member.id != ctx.author.id:
                await self.init_user_data(member.id)
                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("UPDATE gc_users SET banned = %s WHERE id = %s", (1, member.id))
                await ctx.send(
                    embed=discord.Embed(description=f'{member.mention} wurde global gebannt!', color=0xF44D4D))
            else:
                await ctx.send(embed=discord.Embed(description='Du kannst dich nicht selbst bannen!', color=0xF44D4D))
        else:
            await ctx.message.delete()

    @commands.command()
    async def globalunban(self, ctx, member: discord.Member):
        if await self.is_mod(ctx.author.id) or ctx.author.id == ctx.bot.owner_id:
            await self.init_user_data(member.id)
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE gc_users SET banned = %s WHERE id = %s", (0, member.id))
            await ctx.send(embed=discord.Embed(description=f'{member.mention} wurde entbannt!', color=0x33e680))
        else:
            await ctx.message.delete()

    @app_commands.command(name="globalchat", description="Aktiviere oder deaktiviere den Globalchat in diesem Kanal.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(option="Wähle, ob du den Globalchat aktivieren oder deaktivieren möchtest.")
    async def globalchat_toggle(self, interaction: discord.Interaction, option: Literal["an", "aus"]):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Du benötigst Administratorrechte, um diesen Befehl zu verwenden.",
                                                    ephemeral=True)
            return

        guild_id = interaction.guild.id
        channel_id = interaction.channel.id

        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if option == "an":
                        await cur.execute("SELECT * FROM gc_servers WHERE guild_id = %s", (guild_id,))
                        exists = await cur.fetchone()
                        if exists:
                            await cur.execute("UPDATE gc_servers SET channel_id = %s WHERE guild_id = %s",
                                              (channel_id, guild_id))
                            await interaction.response.send_message("✅ Globalchat wurde in diesem Kanal **aktiviert**.",
                                                                    ephemeral=True)
                        else:
                            await cur.execute("INSERT INTO gc_servers (guild_id, channel_id) VALUES (%s, %s)",
                                              (guild_id, channel_id))
                            await interaction.response.send_message("✅ Globalchat wurde in diesem Kanal **aktiviert**.",
                                                                    ephemeral=True)
                    else:
                        await cur.execute("DELETE FROM gc_servers WHERE guild_id = %s AND channel_id = %s",
                                          (guild_id, channel_id))
                        await interaction.response.send_message("❌ Globalchat wurde in diesem Kanal **deaktiviert**.",
                                                                ephemeral=True)
        except Exception as e:
            logger.error(f"Fehler beim Deaktivieren/Aktivieren des Globalchats: {e}")
            await interaction.response.send_message("Es gab ein Problem bei der Änderung des Globalchat-Status.",
                                                    ephemeral=True)


async def setup(bot):
    await bot.add_cog(globalchat(bot))
