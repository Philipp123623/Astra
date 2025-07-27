import discord
from discord.ext import commands
from discord import app_commands
from discord import Message, Guild, TextChannel, Permissions
import pytz
import asyncio
from typing import Literal
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger()

slowmode = []
slow_dm = []
bad_words = ['arsch', 'arschloch', 'wixer', 'wixxer', 'nigger', 'niggah', 'nigga', 'moor', 'NIGGA', 'NIGGAH', 'NIGGER',
             'ficken', 'gefickt', 'nudes', 'nude', 'titten', 'vagina', 'penis', 'wagina', 'fotze', 'stripclub', 'nutte',
             'nutten', 'orgasmus', 'orgasm', 'sex toy', 'erotic', 'erotisch', 'dildo', 'doggie style', 'doggiestyle',
             'doggy style', 'doggystyle', 'blow job', 'blowjob', 'vagina', 'https://', 'http://', 'discord.gg/', 'www.', 'schwanz',
             'Schwanz']


async def user_init_data(author_id, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM gc_users WHERE id = %s", (author_id,))
            if await cursor.fetchone():
                return False
            await cursor.execute("INSERT INTO gc_users (id, lvl_points, team, banned) VALUES (%s, %s, %s, %s)", (author_id, 0, False, False))
            await conn.commit()
            return True

async def user_get_data(pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM gc_users")
            rows = await cursor.fetchall()
            return {str(row[0]): {"lvl-points": row[1], "team": row[2], "banned": row[3]} for row in rows}

async def user_lvl(author_id, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT lvl_points FROM gc_users WHERE id = %s", (author_id,))
            row = await cursor.fetchone()
            if not row:
                return "0"
            target_lvl = row[0]

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

async def user_inc_lvl(author_id, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("UPDATE gc_users SET lvl_points = lvl_points + 1 WHERE id = %s", (author_id,))
            await conn.commit()

async def is_banned(author_id, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT banned FROM gc_users WHERE id = %s", (author_id,))
            result = await cursor.fetchone()
            return result and result[0]

async def is_mod(author_id, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT team FROM gc_users WHERE id = %s", (author_id,))
            result = await cursor.fetchone()
            return result and result[0]

async def is_owner(author_id):
    return author_id == 789555434201677824

async def guild_exists(guildid, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM gc_servers WHERE guildid = %s", (guildid,))
            return bool(await cursor.fetchone())

async def get_globalChat(guild_id, pool, channelid=None):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            if channelid:
                await cursor.execute("SELECT * FROM gc_servers WHERE guildid = %s AND channelid = %s", (guild_id, channelid))
            else:
                await cursor.execute("SELECT * FROM gc_servers WHERE guildid = %s", (guild_id,))
            return await cursor.fetchone()

async def get_globalChat_id(guild_id, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT id FROM gc_servers WHERE guildid = %s", (guild_id,))
            row = await cursor.fetchone()
            return row[0] if row else -1


##########


class globalchat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_all(self, embed, message):
        conent = message.content
        author = message.author
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT guildid, channelid FROM gc_servers")
                for guildid, channelid in await cursor.fetchall():
                    guild: Guild = self.bot.get_guild(int(guildid))
                    if guild:
                        channel: TextChannel = guild.get_channel(int(channelid))
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
                                    await channel.send(f'{author.name}: {conent}')
                                    await channel.send('Manche Rechte fehlen: `Nachrichten Senden`, `Links Einbetten`, `Dateien Anhängen`, `Externe Emojis verwenden`')
        try:
            await message.delete()
        except:
            pass

    async def sendAll(self, message: Message):
        users_data = await user_get_data(self.bot.pool)
        conent = message.content
        author = message.author
        attachments = message.attachments
        de = pytz.timezone('Europe/Berlin')
        icon = author.avatar
        author_lvl = await user_lvl(message.author.id, self.bot.pool)
        embed = discord.Embed(title=message.author, description=conent,
                              timestamp=discord.utils.utcnow().astimezone(tz=de),
                              color=0x36393F)
        embed.set_author(name=f'👥 User - Level {author_lvl}', icon_url=icon)

        if author.id == 789555434201677824:
            embed.set_author(name='💻 Astra Developer', icon_url=icon)
            embed.color = 0x1E90FF
        elif users_data[str(author.id)]["team"]:
            embed.set_author(name=f'🛠 Staff - Level {author_lvl}', icon_url=icon)
            embed.color = 0x1ABC9C
        else:
            level = int(author_lvl)
            if 1 < level < 5:
                embed.color = 0xe6de37
                embed.set_author(name=f'🌴 Beginner - Level {author_lvl}', icon_url=icon)
            elif 5 < level < 25:
                embed.color = 0xe63737
                embed.set_author(name=f'🔥 Fortgeschritten - Level {author_lvl}', icon_url=icon)
            elif 25 < level < 40:
                embed.color = 0x339be6
                embed.set_author(name=f"⭐ Amateur - Level {author_lvl}", icon_url=icon)
            elif 40 < level < 60:
                embed.color = 0x33e680
                embed.set_author(name=f"🌹 Professional - Level {author_lvl}", icon_url=icon)
            elif 60 < level < 80:
                embed.color = 0x5d33e6
                embed.set_author(name=f'🥇 Meister - Level {author_lvl}', icon_url=icon)
            elif level > 80:
                embed.color = 0x1aecff
                embed.set_author(name=f'💎 Legend - Level {author_lvl}', icon_url=icon)

        if message.reference and message.reference.cached_message:
            replied_msg = message.reference.cached_message

            # Versuche, echte Nutzerdaten aus dem Embed zu holen
            if replied_msg.embeds:
                embed_ref = replied_msg.embeds[0]
                replied_user = embed_ref.title or "Unbekannter Benutzer"
                replied_text = embed_ref.description or "*(Kein Inhalt gefunden)*"
            else:
                # Fallback, falls kein Embed
                replied_user = replied_msg.author.display_name
                replied_text = replied_msg.content or "*(Nachricht enthält nur Anhang oder Embed)*"

            if len(replied_text) > 100:
                replied_text = replied_text[:100] + "..."

            embed.add_field(
                name=f"<:Astra_messages:1141303867850641488> Antwort auf **{replied_user}**",
                value=f"> {replied_text}\n[↪ Zur Originalnachricht]({message.reference.jump_url})",
                inline=False
            )

        icon_url = message.guild.icon.url if message.guild.icon else "https://cdn.icon-icons.com/icons2/2108/PNG/512/discord_icon_130958.png"
        embed.set_thumbnail(url=icon_url)

        online = sum(1 for m in message.guild.members if str(m.status) == 'online')
        embed.set_footer(text=f'{message.guild.name} (🔋{online} - 👥{len([m for m in message.guild.members if not m.bot])} - 🤖{len([m for m in message.guild.members if m.bot])})', icon_url=icon_url)

        links = f'<:Astra_user:1141303940365959241> [Invite](https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=1899359446&scope=bot%20applications.commands) ║ '
        globalchat = await get_globalChat(message.guild.id, self.bot.pool, message.channel.id)
        if globalchat and globalchat[3]:  # Index 3 = invite
            invite = globalchat[3] if 'discord.gg' in globalchat[3] else f'https://discord.gg/{globalchat[3]}'
            links += f'<:Astra_url:1141303937056657458>  [Server Invite]({invite})'

        embed.add_field(name='Links', value=links, inline=False)

        if attachments:
            embed.set_image(url=attachments[0].url)

        if author.id in slowmode:
            await message.delete()
            try:
                if author.id not in slow_dm:
                    slow_dm.append(author.id)
                    await author.send(embed=discord.Embed(description='Du kannst nur eine Nachricht alle 5 Sekunden senden.', colour=0xFF0000))
                    await asyncio.sleep(2)
                    slow_dm.remove(author.id)
            except:
                pass
        else:
            slowmode.append(author.id)
            await user_inc_lvl(message.author.id, self.bot.pool)
            await self.send_all(embed, message)
            await asyncio.sleep(5)
            slowmode.remove(author.id)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return

        if not msg.guild or msg.content.startswith("astra!"):
            return

        if await get_globalChat(msg.guild.id, self.bot.pool, msg.channel.id):
            if not any(x in msg.content.casefold() for x in bad_words):
                author_id = msg.author.id
                await user_init_data(author_id, self.bot.pool)
                if not await is_banned(author_id, self.bot.pool):
                    await self.sendAll(msg)
                    return
                else:
                    await msg.delete()
                    if msg.author.id not in slow_dm:
                        info_msg = discord.Embed(
                            description=f'{msg.author.mention} du bist gebannt und kannst den Globalchat nicht mehr nutzen.\n--> [Support Server](https://discord.gg/vwh2raq2Xu)',
                            colour=0xF44D4D)
                        await msg.author.send(embed=info_msg)
                        slow_dm.append(msg.author.id)
                        await asyncio.sleep(2)
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

    @commands.command(name="globalban")
    async def globalban(self, ctx, member: discord.Member):
        if not await is_mod(ctx.author.id, self.bot.pool):
            await ctx.send(
                embed=discord.Embed(description='Nur Teammitglieder dürfen diesen Befehl ausführen!', colour=0xF44D4D))
            return

        if member.id == 789555434201677824 or member.id == ctx.author.id:
            await ctx.send(embed=discord.Embed(description='Du kannst den Bot Developer oder dich selbst nicht bannen!',
                                               colour=discord.Colour.blue()))
            return

        await user_init_data(member.id, self.bot.pool)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE gc_users SET banned = TRUE WHERE id = %s", (member.id,))
                await conn.commit()
        await ctx.send(embed=discord.Embed(description=f'{member.mention} wurde erfolgreich gebannt!', colour=0xF44D4D))

    @commands.command(name="setstaff")
    async def setstaff(self, ctx, member: discord.Member):
        if not await is_owner(ctx.author.id):
            await ctx.send(
                embed=discord.Embed(description='Nur der Bot-Owner darf diesen Befehl verwenden.', colour=0xF44D4D))
            return

        await user_init_data(member.id, self.bot.pool)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE gc_users SET team = TRUE WHERE id = %s", (member.id,))
                await conn.commit()
        await ctx.send(
            embed=discord.Embed(description=f'{member.mention} wurde zum Teammitglied ernannt!', colour=0x56F44D))

    @commands.command(name="setlevel")
    async def setlevel(self, ctx, member: discord.Member, level: int):
        if not await is_owner(ctx.author.id):
            await ctx.send(embed=discord.Embed(
                description="Nur der Bot-Owner darf diesen Befehl verwenden.",
                colour=0xF44D4D))
            return

        if level < 0:
            await ctx.send(embed=discord.Embed(
                description="Das Level muss positiv sein.",
                colour=0xF44D4D))
            return

        await user_init_data(member.id, self.bot.pool)

        # Punkte berechnen entsprechend deinem System
        points = 0
        step = 5
        for l in range(1, level + 1):
            if l <= 3:
                step += 5
            elif l <= 5:
                step += 10
            elif l <= 10:
                step += 15
            elif l <= 15:
                step += 20
            elif l <= 20:
                step += 25
            elif l <= 30:
                step += 35
            elif l <= 40:
                step += 45
            elif l <= 50:
                step += 70
            elif l <= 75:
                step += 100
            elif l <= 80:
                step += 150
            elif l <= 90:
                step += 300
            else:
                step += 500
            points = step

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE gc_users SET lvl_points = %s WHERE id = %s", (points, member.id))
                await conn.commit()

        await ctx.send(embed=discord.Embed(
            description=f'{member.mention} wurde auf Level {level} gesetzt!',
            colour=0x56F44D))

    @commands.command(name="removestaff")
    async def removestaff(self, ctx, member: discord.Member):
        if not await is_owner(ctx.author.id):
            await ctx.send(embed=discord.Embed(
                description='Nur der Bot-Owner darf diesen Befehl verwenden.',
                colour=0xF44D4D))
            return

        await user_init_data(member.id, self.bot.pool)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE gc_users SET team = FALSE WHERE id = %s", (member.id,))
                await conn.commit()

        await ctx.send(embed=discord.Embed(
            description=f'{member.mention} wurde aus dem Team entfernt.',
            colour=0xF44D4D))

    @app_commands.command(name="globalchat")
    @app_commands.guild_only()
    async def globalchat(self, interaction: discord.Interaction, argument: Literal['Einschalten', 'Ausschalten']):
        """Richte unseren Globalchat für deinen Server ein."""
        if argument == 'Einschalten':
            logger.info(1)
            if interaction.user.guild_permissions.administrator:
                if not await guild_exists(interaction.guild.id, self.bot.pool):
                    logger.info(2)
                    new_channel = await interaction.guild.create_text_channel('global chat')
                    topic = "__**Willkommen in diesem Globachat**__ <a:chatbox:1141318924475043971>\n" \
                            "<:Astra_moderation:1141303878541918250> Discord Guidelines\nhttps://discord.com/guidelines\n" \
                            "<:Astra_moderation:1141303878541918250> - Der Ton sollte **höflich und freundlich** sein\n" \
                            "<:Astra_moderation:1141303878541918250> - **Streitigkeiten, Beleidigungen** und **Spam** sind verboten\n" \
                            "<:Astra_moderation:1141303878541918250> - Den **Anweisungen** unseres Teams ist Folge zu leisten!\n" \
                            "<:Astra_moderation:1141303878541918250> - Sprache: **Deutsch**\n\n" \
                            "__**Wichtige Commands**__ <:Astra_file1:1141303837181886494>\n" \
                            "<:Astra_wichtig:1141303951862534224> - /globalchat\n\n" \
                            "__**Worauf ist zu achten?**__ <:Astra_accept:1141303821176422460>\n" \
                            "Alle Nachrichten werden global geteilt. Änderungen der Regeln jederzeit möglich."

                    await new_channel.edit(slowmode_delay=5, topic=topic)
                    invite = (await new_channel.create_invite()).url

                    async with self.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("INSERT INTO gc_servers (guildid, channelid, invite) VALUES (%s, %s, %s)",
                                                 (interaction.guild.id, new_channel.id, invite))
                            await conn.commit()

                    embed = discord.Embed(title="**Globalchat Setup erfolgreich!**",
                                          description=f"Der Globalchat kann nun in <#{new_channel.id}> genutzt werden!",
                                          color=0x56F44D)
                    await interaction.response.send_message(embed=embed)
                    await new_channel.send(embed=discord.Embed(
                        description='*Das ist der Beginn dieses Globalchats...*\nSchreibe deine erste Nachricht!',
                        colour=0x36393F))
                    logger.info(4)
                else:
                    embed = discord.Embed(description="Du hast bereits einen Globalchat in deinem Server aktiv.",
                                          color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)

        if argument == 'Ausschalten':
            if interaction.user.guild_permissions.administrator:
                if await guild_exists(interaction.guild.id, self.bot.pool):
                    async with self.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("DELETE FROM gc_servers WHERE guildid = %s", (interaction.guild.id,))
                            await conn.commit()
                    embed = discord.Embed(title="**GlobalChat deaktiviert!**",
                                          description="Der Globalchat wurde erfolgreich entfernt. Du kannst ihn jederzeit neu aktivieren: `/globalchat`",
                                          color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = discord.Embed(
                        description="Du hast derzeit keinen Globalchat aktiv. Richte ihn mit `/globalchat` ein!",
                        color=0xF44D4D)
                    await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(globalchat(bot))