import discord
from discord.ext import commands
from datetime import datetime
from discord import app_commands
import traceback
from discord.ui.view import View
from typing import Literal


class Feedback(discord.ui.Modal, title="Erstelle dein eigenes Embed."):
    def __init__(self, *, color2: Literal['Rot', 'Orange', 'Gelb', 'Grün', 'Blau', 'Blurple'] = None):
        super().__init__()
        self.colour = color2

    view = View()
    name = discord.ui.TextInput(
        label='Titel',
        style=discord.TextStyle.short,
        placeholder='Tippe ein, was der Titel des Embeds sein soll...',
        required=False,
    )
    description = discord.ui.TextInput(
        label='Beschreibung',
        style=discord.TextStyle.long,
        placeholder='Tippe ein, was die Beschreibung des Embeds sein soll...',
        required=True,
        max_length=4000,
    )
    footer = discord.ui.TextInput(
        label='Footer',
        style=discord.TextStyle.short,
        placeholder='Tippe ein was der Footer des Embeds sein soll...',
        required=False,
    )
    thumbnail = discord.ui.TextInput(
        label='Thumbnail',
        style=discord.TextStyle.short,
        placeholder='Füge die Url eines Thumbnails ein...',
        required=False,
    )
    image = discord.ui.TextInput(
        label='Bild',
        style=discord.TextStyle.short,
        placeholder='Füge die Url eines Bildes ein...',
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """The bot will display your message in a Embed."""
        if self.colour == "Rot":
            embed = discord.Embed(colour=discord.Colour.red(), title=f"{self.name.value if self.name.value else ' '}",
                                  description=f"{self.description.value if self.description.value else ' '}")
        elif self.colour == "Orange":
            embed = discord.Embed(colour=discord.Colour.orange(),
                                  title=f"{self.name.value if self.name.value else ' '}",
                                  description=f"{self.description.value if self.description.value else ' '}")
        elif self.colour == "Gelb":
            embed = discord.Embed(colour=discord.Colour.yellow(),
                                  title=f"{self.name.value if self.name.value else ' '}",
                                  description=f"{self.description.value if self.description.value else ' '}")
        elif self.colour == "Grün":
            embed = discord.Embed(colour=discord.Colour.green(), title=f"{self.name.value if self.name.value else ' '}",
                                  description=f"{self.description.value if self.description.value else ' '}")
        elif self.colour == "Blau":
            embed = discord.Embed(colour=discord.Colour.blue(), title=f"{self.name.value if self.name.value else ' '}",
                                  description=f"{self.description.value if self.description.value else ' '}")
        elif self.colour == "Blurple":
            embed = discord.Embed(colour=discord.Colour.blurple(), title=f"{self.name.value if self.name.value else ' '}",
                                  description=f"{self.description.value if self.description.value else ' '}")
        else:
            embed = discord.Embed(title=f"{self.name.value if self.name.value else ' '}",
                                  description=f"{self.description.value if self.description.value else ' '}")
        if self.thumbnail.value is not None:
            embed.set_thumbnail(url=self.thumbnail.value)
        else:
            pass
        if self.image.value is not None:
            embed.set_image(url=self.image.value)
        else:
            pass
        if self.footer.value is not None:
            embed.set_footer(text=self.footer.value, icon_url=interaction.guild.icon)
        else:
            pass
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)
        return

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Etwas ist schiefgelaufen.', ephemeral=True)

        # Make sure we know what the error actually is
        traceback.print_tb(error.__traceback__)


class mod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.snipe_message_author = {}
        self.snipe_message_content = {}
        self.snipe_message_channel = {}

    @app_commands.command(name="kick")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        """Kicke einen User."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (interaction.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    channel = interaction.guild.get_channel(int(result[0]))
                    embed = discord.Embed(colour=discord.Colour.orange(),
                                          description=f"Der User {user} (`{user.id}`) wurde gekickt.")
                    embed.add_field(name=f"👤 Member:", value=f"{user.mention}", inline=False)
                    embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                    inline=False)
                    embed.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                    embed.set_author(name=user, icon_url=user.avatar)
                    await channel.send(embed=embed)
                if user.guild_permissions.kick_members:
                    embed = discord.Embed(colour=discord.Colour.red(),
                                          description=f"Der User {user.mention} kann nicht gekickt werden, da er die Rechte `Mitglieder Kicken` hat.")
                    embed.set_author(name=user, icon_url=user.avatar)
                    await interaction.response.send_message(embed=embed)
                    return
                else:
                    embed = discord.Embed(colour=discord.Colour.orange(),
                                          description=f"Der User {user} (`{user.id}`) wurde gekickt.")
                    embed.add_field(name=f"🎛️ Server:", value=f"{interaction.guild.name}", inline=False)
                    embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
                    embed.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)

                    dm = discord.Embed(colour=discord.Colour.orange(),
                                       description=f"Hey {user.mention}! \nDu wurdest vom Server **{interaction.guild.name}** gekickt! Mehr Informationen hier:")
                    dm.add_field(name=f"🎛️ Server:", value=f"{interaction.guild.name}", inline=False)
                    dm.add_field(name=f"👮 Moderator:", value=f"{interaction.user.mention}", inline=False)
                    dm.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                    dm.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    try:
                        await user.send(embed=dm)
                        await user.kick(reason=reason)
                        await interaction.response.send_message(embed=embed)
                    except:
                        await user.kick(reason=reason)
                        await interaction.response.send_message(embed=embed)
                        await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Ich konnte dem User keine Nachricht senden, da er DM's geschlossen hat**")

    @app_commands.command(name="ban")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        """Banne einen User."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT channelID FROM modlog WHERE serverID = (%s)", (interaction.guild.id))
                result = await cursor.fetchone()
                if result is None:
                    return
                if result is not None:
                    channel = interaction.guild.get_channel(int(result[0]))
                    embed = discord.Embed(colour=discord.Colour.orange(),
                                          description=f"Der User {user} (`{user.id}`) wurde gebannt.")
                    embed.add_field(name=f"👤 Member:", value=f"{user.mention}", inline=False)
                    embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)",
                                    inline=False)
                    embed.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    await channel.send(embed=embed)
                if user.guild_permissions.kick_members:
                    embed = discord.Embed(colour=discord.Colour.red(),
                                          description=f"Der User {user.mention} kann nicht gekickt werden, da er die Rechte `Mitglieder Bannen` hat.")
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    await interaction.response.send_message(embed=embed)
                    return
                else:
                    embed = discord.Embed(colour=discord.Colour.orange(),
                                          description=f"Der User {user} (`{user.id}`) wurde gebannt.")
                    embed.add_field(name=f"🎛️ Server:", value=f"{interaction.guild.name}", inline=False)
                    embed.add_field(name=f"👮 Moderator:", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
                    embed.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)

                    dm = discord.Embed(colour=discord.Colour.orange(),
                                       description=f"Hey {user.mention}! \nDu wurdest vom Server **{interaction.guild.name}** gebannt! Mehr Informationen hier:")
                    dm.add_field(name=f"🎛️ Server:", value=f"{interaction.guild.name}", inline=False)
                    dm.add_field(name=f"👮 Moderator:", value=f"{interaction.user.mention}", inline=False)
                    dm.add_field(name=f"📄 Grund:", value=f"{reason}", inline=False)
                    dm.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    try:
                        await user.send(embed=dm)
                        await user.ban(reason=reason)
                        await interaction.response.send_message(embed=embed)
                    except:
                        await user.ban(reason=reason)
                        await interaction.response.send_message(embed=embed)
                        await interaction.response.send_message("<:Astra_accept:1141303821176422460> **Ich konnte dem User keine Nachricht senden, da er DM's geschlossen hat**")

    @app_commands.command(name="clear")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, channel: discord.TextChannel, amount: int):
        """Löscht eine Bestimmte Anzahl an Nachrichten."""
        if int(amount) < 300:
            await interaction.response.send_message(f"Nachrichten werden gelöscht...", ephemeral=True)
            deleted = await channel.purge(limit=amount + 1)
            embed = discord.Embed(colour=discord.Colour.green(),
                                  description=f"{len(deleted) - 1} Nachricht{'' if (len(deleted) -1) == 1 else 'en'} gelöscht.")
            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
            message = await interaction.original_message()
            await message.edit(embed=embed, content=None)

        if int(amount) >= 300:
            embed = discord.Embed(colour=discord.Colour.red(),
                                  description="❌ Your number cannot be greater than 300.",
                                  timestamp=datetime.utcnow())
            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="embedfy")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embedfy(self, interaction: discord.Interaction,
                      color: Literal['Rot', 'Orange', 'Gelb', 'Grün', 'Blau', 'Blurple'] = None):
        """Erstelle ein schönes Embed."""
        await interaction.response.send_modal(Feedback(color2=color))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        self.snipe_message_author[message.guild.id] = message.author
        self.snipe_message_content[message.guild.id] = message.content
        self.snipe_message_channel[message.guild.id] = message.channel

    @app_commands.command(name="unban")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, usertag: str):
        """Entbanne einen User."""
        banned_users = [entry async for entry in interaction.guild.bans(limit=2000)]

        member_name, member_discriminator = usertag.split('#')
        for ban_entry in banned_users:
            user = ban_entry.user

            if (user.name, user.discriminator) == (member_name, member_discriminator):
                await interaction.guild.unban(user)
                await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> **Der User {usertag} wurde entbannt.**")
                

    @app_commands.command(name="banlist")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(ban_members=True)
    async def banlist(self, interaction: discord.Interaction):
        """Zeigt eine Liste mit gebannten Usern."""
        a = 0
        users = [entry async for entry in interaction.guild.bans(limit=2000)]
        if len(users) > 0:
            msg1 = f'__**Username**__ — __**Grund**__\n'
            for entry in users:
                userName = str(entry.user)
                if entry.user.bot:
                    userName = '🤖 ' + userName
                reason = str(entry.reason)
                msg1 += f'{userName} — {reason}\n'
                a += 1
            try:
                for chunk in [msg1[i:i + 2000] for i in range(0, len(msg1), 2000)]:
                    embed = discord.Embed(title="Bann Liste", description=f"{msg1}", color=discord.Color.red())
                    embed.set_thumbnail(url=interaction.guild.icon)
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    embed.set_footer(text=f"{a} gebannte User auf dem Server.")
                    await interaction.response.send_message(embed=embed)
            except discord.HTTPException:
                embed2 = discord.Embed(title="Bann Liste", description=f"{msg1}", color=discord.Color.red())
                embed2.set_thumbnail(url=interaction.guild.icon)
                embed2.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                embed2.set_footer(text=f"{a} gebannte User auf dem Server.")
                await interaction.response.send_message(embed=embed2)
        else:
            await interaction.response.send_message('<:Astra_x:1141303954555289600> **Hier gibt es keine gebannten User.**')


async def setup(bot: commands.Bot):
    await bot.add_cog(mod(bot))
