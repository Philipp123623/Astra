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


class botrole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.bot:
            return
        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"SELECT roleID FROM botrole WHERE guildID = {member.guild.id}")
                    result = await cursor.fetchone()
                    roless = discord.utils.get(member.guild.roles, id=int(result[0]))

                    await member.add_roles(roless)
        except:
            pass

    @app_commands.command(name="botrole")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(argument="Möchtest Botrollen hinzufügem, entfernen oder Anzeigen lassen.", role="Role")
    async def botrole(self, interaction: discord.Interaction,
                       argument: Literal['Einschalten', 'Ausschalten', 'Anzeigen'],
                       role: discord.Role = None):
        """Stelle eine Botrole für deinen Server ein."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if interaction.user.bot:
                    return
                else:
                    if argument == "Einschalten":
                        await cursor.execute(f"SELECT roleID FROM botrole WHERE guildID = {interaction.guild.id}")
                        result = await cursor.fetchone()
                        if result is None:
                            await cursor.execute(f"INSERT INTO botrole (roleID, guildID) VALUES (%s, %s)",
                                                 (role.id, interaction.guild.id))

                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Botrole auf {role.mention} gesetzt.")
                            embed.set_footer(text="Stelle sicher, dass die Rolle von Astra über der Botrole steht.")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            await interaction.response.send_message(embed=embed)
                        if result is not None:
                            await cursor.execute(
                                f"UPDATE botrole SET roleID = {str(role.id)} WHERE guildID = {str(interaction.guild.id)}")

                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Botrole geändert zu: {role.mention}")
                            embed.set_footer(text="Stelle sicher, dass die Rolle von Astra über der Botrole steht.")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            await interaction.response.send_message(embed=embed)
                    if argument == "Ausschalten":
                        await cursor.execute(f"SELECT roleID FROM botrole WHERE guildID = {interaction.guild.id}")
                        result = await cursor.fetchone()
                        if result is None:
                            return
                        if result is not None:
                            roleID = result
                            if int(role.id, ) in roleID:
                                await cursor.execute(
                                    f"DELETE FROM botrole WHERE roleID = {role.id} AND guildID = {interaction.guild.id}")
                                embed = discord.Embed(colour=discord.Colour.orange(),
                                                      description=f"Botrole gelöscht: {role.mention}")
                                embed.set_footer(
                                    text="Stelle sicher, dass die Rolle von Astra über der Botrole steht.")
                                embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                                await interaction.response.send_message(embed=embed)
                            else:
                                embed = discord.Embed(colour=discord.Colour.orange(),
                                                      description=f"Keine gesetzte Botrole. Füge eine mit `/botrole add` hinzu.")
                                embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                                embed.set_footer(text="Make sure that my role is higher than the joinrole")
                                await interaction.response.send_message(embed=embed)
                    if argument == "Anzeigen":
                        await cursor.execute(f"SELECT roleID FROM botrole WHERE guildID = {interaction.guild.id}")
                        result = await cursor.fetchone()
                        if result is not None:
                            roless = discord.utils.get(interaction.guild.roles, id=int(result[0]))

                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Aktuelle Botrole: {roless.mention}")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            embed.set_footer(text="Stelle sicher, dass die Rolle von Astra über der Botrole steht.")
                            await interaction.response.send_message(embed=embed)
                        if result is None:
                            embed = discord.Embed(colour=discord.Colour.orange(),
                                                  description=f"Keine gesetzte Botrole. Füge eine mit `/botrole add` hinzu.")
                            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                            embed.set_footer(text="Stelle sicher, dass die Rolle von Astra über der Botrole steht.")
                            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(botrole(bot))