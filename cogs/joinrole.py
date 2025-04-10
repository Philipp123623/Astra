import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal


##########
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


async def timeline(seconds):
    result = []
    intervals = (
        ('Weeks', 604800),
        ('Days', 86400),
        ('Hours', 3600),
        ('Minutes', 60),
        ('Seconds', 1),
    )

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(int(value), name))
    return ', '.join(result)


class joinrole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"SELECT roleID FROM joinrole WHERE guildID = {member.guild.id}")
                    result = await cursor.fetchone()
                    roless = discord.utils.get(member.guild.roles, id=int(result[0]))

                    await member.add_roles(roless)
        except:
            pass

    @app_commands.command(name="joinrole")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def joinrole(self, interaction: discord.Interaction,
                       argument: Literal['Einschalten', 'Ausschalten', 'Anzeigen'],
                       role: discord.Role = None):
        """Lege eine Joinrolle für deinen Server fest."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if interaction.user.bot:
                    return
                else:
                    if argument == "Einschalten":
                        await cursor.execute(f"SELECT roleID FROM joinrole WHERE guildID = {interaction.guild.id}")
                        result = await cursor.fetchone()
                        if result is None:
                            await cursor.execute(f"INSERT INTO joinrole (roleID, guildID) VALUES (%s, %s)",
                                                 (role.id, interaction.guild.id))

                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Joinrole gesetzt auf: {role.mention}")
                            embed.set_footer(text="Stelle sicher, dass Astras Rolle über der Joinrole ist.",
                                             icon_url="https://cdn.discordapp.com/emojis/814202875387183145.png")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            await interaction.response.send_message(embed=embed)
                        if result is not None:
                            await cursor.execute(
                                f"UPDATE joinrole SET roleID = {str(role.id)} WHERE guildID = {str(interaction.guild.id)}")

                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Joinrole geändert zu: {role.mention}")
                            embed.set_footer(text="Stelle sicher, dass Astras Rolle über der Joinrole ist.",
                                             icon_url="https://cdn.discordapp.com/emojis/814202875387183145.png")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            await interaction.response.send_message(embed=embed)
                    if argument == "Ausschalten":
                        await cursor.execute(f"SELECT roleID FROM joinrole WHERE guildID = {interaction.guild.id}")
                        result = await cursor.fetchone()
                        if result is None:
                            return
                        if result is not None:
                            roleID = result
                            if int(role.id, ) in roleID:
                                await cursor.execute(
                                    f"DELETE FROM joinrole WHERE roleID = {role.id} AND guildID = {interaction.guild.id}")
                                embed = discord.Embed(colour=discord.Colour.orange(),
                                                      description=f"Joinrole entfernt: {role.mention}")
                                embed.set_footer(
                                    text="Stelle sicher, dass Astras Rolle über der Joinrole ist.",
                                    icon_url="https://cdn.discordapp.com/emojis/814202875387183145.png")
                                embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                                await interaction.response.send_message(embed=embed)
                            else:
                                embed = discord.Embed(colour=discord.Colour.orange(),
                                                      description=f"Keine Joinrole gesetzt. Füge eine mit `/joinrole add` hinzu.")
                                embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                                embed.set_footer(text="Stelle sicher, dass Astras Rolle über der Joinrole ist.",
                                                 icon_url="https://cdn.discordapp.com/emojis/814202875387183145.png")
                                await interaction.response.send_message(embed=embed)
                    if argument == "Anzeigen":
                        await cursor.execute(f"SELECT roleID FROM joinroles WHERE guildID = {interaction.guild.id}")
                        result = await cursor.fetchone()
                        if result is not None:
                            roless = discord.utils.get(interaction.guild.roles, id=int(result[0]))

                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Joinrole dieses Servers: {roless.mention}")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            embed.set_footer(text="Stelle sicher, dass Astras Rolle über der Joinrole ist.",
                                             icon_url="https://cdn.discordapp.com/emojis/814202875387183145.png")
                            await interaction.response.send_message(embed=embed)
                        if result is None:
                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Keine Joinrole gesetzt. Füge eine mit `/joinrole add` hinzu")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            embed.set_footer(text="Make sure that my role is higher than the joinrole",
                                             icon_url="https://cdn.discordapp.com/emojis/814202875387183145.png")
                            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reactionrole")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole(self, interaction: discord.Interaction, role: discord.Role, messageid: str, emoji: str):
        """Richte Reactionroles für deinen Server ein."""
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        try:
            message = await channel.fetch_message(messageid)
        except discord.NotFound:
            await interaction.followup.send("<:Astra_x:1141303954555289600> **Ich konnte deine Nachricht nicht finden.**")
            return

        try:
            await message.add_reaction(emoji)
        except:
            await interaction.followup.send("<:Astra_x:1141303954555289600> **Ich konnte das Emoji nicht finden. Das Emoji muss von einem Server stammen auf dem auch Astra ist.**\n**Wenn du das Format nicht kennst, schreib einfach `:emoji_name:`.**")
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO reactionrole (role_id, msg_id, emoji, guild_id) VALUES (%s, %s, %s, %s)",
                    (role.id, message.id, emoji, interaction.guild.id))

        embed = discord.Embed(title="Reactionrole gesetzt.", description=f"Rolle: {role.mention}\nEmoji: {emoji}",
                              color=discord.Colour.blue())

        await message.reply(embed=embed)
        await interaction.followup.send("<:Astra_accept:1141303821176422460> Reactionrole hinzugefügt.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if payload.member.bot:
                    return
                try:
                    guild = self.bot.get_guild(int(payload.guild_id))
                    await cursor.execute(
                        f"SELECT role_id, msg_id, emoji FROM reactionrole WHERE guild_id = {guild.id}")
                    result = await cursor.fetchall()
                    if result is None:
                        return
                    else:
                        await cursor.execute(
                            f"SELECT role_id FROM reactionrole WHERE guild_id = (%s) AND msg_id = (%s) AND emoji = (%s)",
                            (guild.id, payload.message_id, payload.emoji))
                        r1 = await cursor.fetchone()
                        await payload.member.add_roles(self.bot.get_guild(payload.guild_id).get_role(int(r1[0])))
                        return

                except:
                    pass

    ##########
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    guild = self.bot.get_guild(int(payload.guild_id))
                    await cursor.execute(
                        f"SELECT role_id, msg_id, emoji FROM reactionrole WHERE guild_id = {guild.id}")
                    result = await cursor.fetchall()
                    if result is None:
                        return
                    else:
                        await cursor.execute(
                            f"SELECT role_id FROM reactionrole WHERE guild_id = (%s) AND msg_id = (%s) AND emoji = (%s)",
                            (guild.id, payload.message_id, payload.emoji))
                        r1 = await cursor.fetchone()
                        await guild.get_member(payload.user_id).remove_roles(guild.get_role(int(r1[0])))
                        return
                except:
                    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(joinrole(bot))
