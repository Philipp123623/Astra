import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Literal
from discord.app_commands import Group
import os


class ticket_buttons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Schließen', style=discord.ButtonStyle.red, custom_id='persistent_view_allg:close',
                       emoji="🔒")
    async def close_alg(self, interaction: discord.Interaction, button: discord.Button):
        guild = interaction.guild
        member = interaction.user
        channel = interaction.channel
        channelid = channel.id
        cat = channel.category.id
        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT roleID FROM ticketsystem WHERE categoryID = (%s)", (cat))
                result1 = await cur.fetchone()
                roleID = result1[0]
                suprole = guild.get_role(roleID)
                if suprole in member.roles:
                    await cur.execute("SELECT channelID FROM ticketsystem_channels WHERE channelID = (%s)", (channelid))
                    result = await cur.fetchall()
                    for eintrag in result:
                        channelID = eintrag[0]

                        if channelID == channelid:
                            await cur.execute("UPDATE ticketsystem_channels SET closed = (%s) WHERE channelID = (%s)",
                                              (interaction.user.id, channelID))
                            await cur.execute(
                                "SELECT closed FROM ticketsystem_channels WHERE channelID = (%s)",
                                (channelID))
                            result1 = await cur.fetchone()
                            closed = result1[0]
                            await cur.execute(
                                "SELECT claimed, opened, time FROM ticketsystem_channels WHERE channelID = (%s)",
                                (channelID))
                            result5 = await cur.fetchall()
                            await cur.execute("SELECT thema FROM ticketsystem WHERE roleID = (%s)", (roleID))
                            result6 = await cur.fetchone()
                            for eintrag in result5:
                                claimed = eintrag[0]
                                opened = eintrag[1]
                                time = eintrag[2]
                                thema = result6[0]
                                user = interaction.client.get_user(int(opened))

                                if claimed == "Not Set":
                                    user_claimed = "Nicht geclaimed."
                                else:
                                    user_claimed = interaction.client.get_user(int(claimed))
                                user_closed = interaction.client.get_user(int(closed))
                                await cur.execute(f"SELECT channelID FROM ticketlog WHERE guildID = (%s)",
                                                  (interaction.guild.id))
                                result7 = await cur.fetchone()
                                if result7 == "None":
                                    await interaction.response.send_message(
                                        "<:Astra_info:1141303860556738620> **Das Ticket wird in 5 Sekunden geschlossen.**")
                                    await asyncio.sleep(5)
                                    await channel.delete()
                                    await cur.execute(
                                        "DELETE FROM ticketsystem_channels WHERE channelID = (%s) and guildID = (%s)",
                                        (channelid, guild.id))
                                if result7:
                                    channelID = result7[0]
                                    log_channel = interaction.client.get_channel(channelID)
                                    filename = f"{interaction.channel.id}.log"
                                    with open(filename, "w", encoding='utf-8') as file:
                                        if user_claimed == "Nicht geclaimed":
                                            file.write(
                                                f"Ticket: {interaction.channel.name}\nUser: {user.name}#{user.discriminator} ({member.id})\nModerator: Kein Moderator hat geclaimed.\n\n")
                                        if user_claimed != "Nicht geclaimed":
                                            file.write(
                                                f"Ticket: {interaction.channel.name}\nUser: {user.name}#{user.discriminator} ({member.id})\nModerator: {user_claimed.name}#{user_claimed.discriminator}\n\n")
                                        async for msg in interaction.channel.history(limit=None, oldest_first=True):
                                            file.write(
                                                f"{msg.created_at.strftime('%d.%m.%Y, %H:%M Uhr')} - {msg.author.name}: {msg.content}\n")
                                    log_embed = discord.Embed(title="Ticket geschlossen",
                                                              description=f"Ticket-Log für ``{interaction.channel.name}``",
                                                              colour=discord.Colour.blue())
                                    log_embed.add_field(name="<:opened:1142025945369280563> Geöffnet von",
                                                        value=user.mention,
                                                        inline=False)
                                    log_embed.add_field(name="<:closed:1142026076898480188> Geschlossen von ",
                                                        value=user_closed.mention, inline=False)
                                    try:
                                        log_embed.add_field(name="<:claimed:1142026074432208926> Geclaimed von",
                                                            value=user_claimed.mention, inline=False)
                                    except:
                                        log_embed.add_field(name="<:claimed:1142026074432208926> Geclaimed von",
                                                            value="Nicht geclaimed", inline=False)
                                    log_embed.add_field(name="<:time:1142026081688363059> Ticket geöffnet", value=time,
                                                        inline=False)
                                    log_embed.add_field(name="<:grund:1142026078542630983> Thema", value=thema,
                                                        inline=False)
                                    await log_channel.send(embed=log_embed, file=discord.File(f'{filename}'))
                                    os.remove(filename)
                                await interaction.response.send_message(
                                        "<:Astra_info:1141303860556738620> **Das Ticket wird in 5 Sekunden geschlossen.**")
                                await asyncio.sleep(5)
                                await channel.delete()
                                await cur.execute(
                                    "DELETE FROM ticketsystem_channels WHERE channelID = (%s) and guildID = (%s)",
                                    (channelid, guild.id))
                else:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Nur User mit der Supportrolle sind berechtigt Tickets zu schließen.**",
                        ephemeral=True)

    @discord.ui.button(label='Claim', style=discord.ButtonStyle.green, custom_id='persistent_view_allg:take',
                       emoji="👮‍♂️")
    async def take_allg(self, interaction: discord.Interaction, button: discord.Button):
        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                guild = interaction.guild
                member = interaction.user
                channel = interaction.channel
                channelid = channel.id
                cat = channel.category.id
                await cur.execute("SELECT roleID FROM ticketsystem WHERE categoryID = (%s)", (cat))
                roleid = await cur.fetchone()
                roleID = roleid[0]
                suprole = guild.get_role(roleID)
                if suprole in member.roles:
                    await cur.execute("SELECT channelID FROM ticketsystem_channels WHERE channelID = (%s)",
                                      channelid)
                    result = await cur.fetchall()
                    for eintrag in result:
                        channelID = eintrag[0]

                        if channelID == channelid:
                            await cur.execute("SELECT msgID FROM ticketsystem_channels WHERE channelID = (%s)",
                                              (channelID))
                            result2 = await cur.fetchone()
                            msgID = result2[0]
                            msg = await channel.fetch_message(msgID)

                            await cur.execute(
                                "UPDATE ticketsystem_channels SET claimed = (%s) WHERE channelID = (%s)",
                                (interaction.user.id, channelID))
                            button.disabled = True
                            await cur.execute("SELECT opened FROM ticketsystem_channels WHERE channelID = (%s)",
                                              (channelID))
                            result3 = await cur.fetchone()
                            open_member_id = result3[0]
                            await cur.execute("SELECT thema FROM ticketsystem WHERE roleID = (%s)", (suprole.id))
                            result4 = await cur.fetchone()
                            title = result4[0]
                            open_member = interaction.client.get_user(open_member_id)
                            embed = discord.Embed(title=f"Ticket von {member.name}",
                                                  description=f"Hallo, {member.mention} ein Teammitglied wird sich bald um dich kümmern. Bitte beschreibe in dieser Zeit dein Problem.",
                                                  colour=discord.Colour.blue())
                            embed.set_author(name=open_member, icon_url=open_member.avatar)
                            embed.add_field(name="Thema", value=title)
                            embed.add_field(name="Geclaimed von", value=interaction.user.mention)
                            await msg.edit(embed=embed, view=self)
                            await interaction.response.send_message(
                                f"<:Astra_info:1141303860556738620> **{interaction.user.mention} hat das Ticket geclaimed**")
                else:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Nur User mit der Supportrolle sind berechtigt Tickets zu claimen.**",
                        ephemeral=True)


class ticket_open(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Ticket Öffnen', style=discord.ButtonStyle.green, custom_id='persistent_view_kaufen:take',
                       emoji="<:Astra_ticket:1061392302444126271>")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.Button):
        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                guild = interaction.guild
                memberid = interaction.user.id
                member = interaction.user
                await cur.execute("SELECT categoryID, thema, roleID FROM ticketsystem WHERE channelID = (%s)",
                                  interaction.channel.id)
                result = await cur.fetchall()
                for eintrag in result:
                    categoryID = eintrag[0]
                    thema = eintrag[1]
                    roleID = eintrag[2]
                    suprole = guild.get_role(roleID)
                    category = discord.utils.get(guild.categories, id=categoryID)
                    send2 = interaction.response.send_message
                    overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        interaction.user: discord.PermissionOverwrite(view_channel=True),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True),
                        suprole: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    }
                    for channel in category.text_channels:
                        if str(memberid) == channel.topic:
                            await interaction.response.send_message("<:Astra_x:1141303954555289600> **Du hast bereits ein offenes Ticket.**", ephemeral=True)
                            return
                        else:
                            overwrites = {
                                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                                interaction.user: discord.PermissionOverwrite(view_channel=True),
                                interaction.guild.me: discord.PermissionOverwrite(view_channel=True),
                                suprole: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                            }
                    ticketchannel = await interaction.guild.create_text_channel(
                        f'ticket-{interaction.user.name}',
                        category=category, overwrites=overwrites,
                        topic=f"{member.id}")
                    await interaction.response.send_message(
                        f"<:Astra_accept:1141303821176422460> **Dein Ticket: {ticketchannel.mention} wurde erstellt.**",
                        ephemeral=True)
                    butterfly = interaction.client.get_emoji(1017431196378083338)
                    embed = discord.Embed(title=f"Ticket von {member.name}",
                                                  description=f"Hallo, {member.mention} ein Teammitglied wird sich bald um dich kümmern. Bitte beschreibe in dieser Zeit dein Problem.",
                                                  colour=discord.Colour.blue())
                    embed.set_author(name=member, icon_url=member.avatar)
                    embed.add_field(name="Thema", value=thema)
                    embed.add_field(name="Geclaimed von", value="Nicht geclaimed")
                    msg = await ticketchannel.send(f"{suprole.mention} | {interaction.user.mention}", embed=embed,
                                                   view=ticket_buttons())
                    await cur.execute(
                        "INSERT INTO ticketsystem_channels(guildID, channelID, msgID, opened, claimed, closed, time) VALUES(%s, %s, %s, %s, %s, %s, %s)",
                        (guild.id, ticketchannel.id, msg.id, interaction.user.id, "Not Set", "Not Set",
                         discord.utils.format_dt(ticketchannel.created_at, 'F')))
                    await cur.execute("UPDATE ticketsystem_channels SET opened = (%s) WHERE channelID = (%s)",
                                      (member.id, ticketchannel.id))
                    await cur.execute("UPDATE ticketsystem_channels SET msgID = (%s) WHERE channelID = (%s)",
                                      (msg.id, ticketchannel.id))

@app_commands.guild_only()
class Ticket(app_commands.Group):
    def __init__(self, bot):
        self.bot = bot  # <--- Hinzufügen!
        super().__init__(
            name="ticket",
            description="Alles rund ums Ticketsystem."
        )

    @app_commands.command(name="setup")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str,
                           description: str, supportrole: discord.Role, categorie: discord.CategoryChannel):
        """Erstelle ein Ticket-Panel."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO ticketsystem(guildID, channelID, thema, roleID, categoryID) VALUES(%s, %s, %s, %s, %s)",
                    (interaction.guild.id, channel.id, title, supportrole.id, categorie.id))
                embed = discord.Embed(title=title,
                                      description=description,
                                      colour=discord.Colour.blue())
                embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text="Klicke auf den Button um ein Ticket zu erstellen!",
                                 icon_url=interaction.guild.icon)
                await channel.send(embed=embed, view=ticket_open(bot=self.bot))
                em = discord.Embed(title="Ticketsystem", description="Dein Panel wurde erstellt",
                                   colour=discord.Colour.blue())
                em.add_field(name="Kanal:", value=channel.mention)
                em.add_field(name="Embed-Tiitel:", value=title, inline=False)
                em.add_field(name="Embed-Beschreibung", value=description, inline=True)
                em.add_field(name="Support-Rolle:", value=supportrole.mention, inline=True)
                em.add_field(name="Ticket-Kategorie:", value=categorie.name, inline=False)
                await interaction.response.send_message(f"{interaction.user.mention} | Dein Panel wurde erstellt.",
                                                        embed=em, ephemeral=True)

    @app_commands.command(name="löschen")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_delete(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Lösche ein Ticket-Panel."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM ticketsystem WHERE channelID = (%s)", (channel.id))
                await interaction.response.send_message(
                    "<:Astra_accept:1141303821176422460> **Das Ticket-Panel wurde gelöscht.**", ephemeral=True)

    @app_commands.command(name="anzeigen")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_list(self, interaction: discord.Interaction):
        """Listet alle Ticket-Panels deines Servers auf."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"SELECT channelID, thema FROM ticketsystem WHERE guildID = (%s)", (interaction.guild.id,))
                result = await cursor.fetchall()
                if not result:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Keine Ticket-Panels in diesem Server aktiv.**",
                        ephemeral=True)
                if result:

                    embed = discord.Embed(title="Aktuelle Ticket-Panels",
                                          description=f"Um Ticket-Panels zu löschen nutze `/ticket delete`.",
                                          color=discord.Color.green())

                    for eintrag in result:
                        channelID = eintrag[0]
                        thema = eintrag[1]

                        try:
                            ch = interaction.guild.get_channel(int(channelID))
                        except:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Keine Ticket-Panels in diesem Server aktiv.**",
                                ephemeral=True)

                        embed.add_field(name=ch.mention, value=thema, inline=True)
                    await interaction.response.send_message(embed=embed)

    @app_commands.command(name="log")
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketlog(self, interaction: discord.Interaction,
                        argument: Literal['Einschalten', 'Ausschalten'],
                        channel: discord.TextChannel):
        """Setup a Ticketlog for your Server!"""
        print(1)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if argument == "Einschalten":
                    await cursor.execute(f"SELECT channelID FROM ticketlog WHERE guildID = (%s)",
                                         (interaction.guild.id))
                    server2 = await cursor.fetchone()
                    await cursor.execute(f"SELECT guildID FROM ticketlog WHERE guildID = (%s)", (channel.id))
                    channel2 = await cursor.fetchone()
                    if server2 is None and channel2 is None:
                        await cursor.execute("INSERT INTO ticketlog (guildID, channelID) VALUES (%s, %s)",
                                             (interaction.guild.id, channel.id))

                        embed1 = discord.Embed(title="Ticket-Log Aktiviert",
                                               description=f"Der Ticket-Log wird in {channel.mention} stattfinden.",
                                               color=discord.Color.blue())
                        await interaction.response.send_message(embed=embed1)

                    else:
                        try:
                            ch = interaction.guild.get_channel(int(server2[0]))
                        except:
                            return
                        embed = discord.Embed(title="Der Ticket-Log ist bereits aktiv",
                                              description=f"Um den Ticket-Log zu ändern nutze `/ticket log`.",
                                              color=discord.Color.green())
                        embed.add_field(name="Kanal", value=ch, inline=False)
                        await interaction.response.send_message(embed=embed)
                elif argument == "Ausschalten":
                    await cursor.execute(f"SELECT channelID FROM ticketlog WHERE guildID = (%s)",
                                         (interaction.guild.id))
                    result = await cursor.fetchone()
                    if result is None:
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> **Der Ticket-Log wurde erfolgreich für diesen Server deaktiviert.**",
                            ephemeral=True)
                    if result is not None:
                        (channelID,) = result
                        if channel.id == channelID:
                            await cursor.execute(
                                f"DELETE FROM ticketlog WHERE channelID = (%s) AND guildID = (%s)",
                                (channel.id, interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Ticket-Log wurde erfolgreich für diesen Server deaktiviert.**",
                                ephemeral=True)
                        else:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Der Ticket-Log ist für diesen Server bereits deaktiviert.**",
                                ephemeral=True)
                            return

class ticket(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(ticket_open(bot=self.bot))
        self.bot.add_view(ticket_buttons())


async def setup(bot: commands.Bot):
    await bot.add_cog(ticket(bot))
    bot.tree.add_command(Ticket(bot))
