import discord
from discord.ext import commands
from discord import app_commands
import traceback

##########

tempchannels = []


def isTempChannel(channel):
    if channel.id in tempchannels:
        return True
    else:
        return False


async def isJoinHub(self, channel):
    async with self.bot.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute(f"SELECT channel_id FROM tempchannels WHERE guild_id = {channel.guild.id}")
                result = await cursor.fetchone()
                if int(channel.id) == int(result[0]):
                    return True
                else:
                    return False

            except:
                pass


class Feedback(discord.ui.Modal, title="Umbenennen"):
    def __init__(self):
        super().__init__()

    name = discord.ui.TextInput(
        label='Name',
        style=discord.TextStyle.short,
        placeholder='Tippe den gewünschten Namen ein.',
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """The bot will display your message in an Embed."""
        await interaction.response.defer()
        await interaction.user.voice.channel.edit(name=self.name.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Etwas ist schiefgelaufen', ephemeral=True)

        # Make sure we know what the error actually is
        traceback.print_tb(error.__traceback__)


class Feedback2(discord.ui.Modal, title="Limit"):
    def __init__(self):
        super().__init__()

    limit = discord.ui.TextInput(
        label='Limit',
        style=discord.TextStyle.short,
        placeholder='Tippe das gewünschte Kanal Limit ein (1-99, 0 für Standart).',
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """The bot will display your message in an Embed."""
        await interaction.response.defer()
        if int(self.limit.value) > 99:
            await interaction.followup.send("<:Astra_x:1141303954555289600> Das Limit **muss** zwischen **0 - 99** liegen.",
                                            ephemeral=True)
        if int(self.limit.value) < 0:
            await interaction.followup.send("<:Astra_x:1141303954555289600> Das Limit **muss** zwischen **0 - 99** liegen.",
                                            ephemeral=True)
        else:
            await interaction.user.voice.channel.edit(user_limit=int(self.limit.value))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Etwas ist schiefgelaufen', ephemeral=True)

        # Make sure we know what the error actually is
        traceback.print_tb(error.__traceback__)


class tempchannel1(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, custom_id='persistent_view:lock',
                       emoji="<:Schloss_2:1141384576019730474>")
    async def lock(self, interaction: discord.Interaction, button: discord.Button):
        try:
            await interaction.response.defer()
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    voice_state = interaction.user.voice

                    if voice_state is None:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    await cur.execute(
                        "SELECT channelID, userID FROM usertempchannels WHERE guildID = (%s) AND channelID = (%s)",
                        (interaction.guild.id, interaction.user.voice.channel.id))
                    result = await cur.fetchone()
                    if not result:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    if result:
                        channel = interaction.user.voice.channel
                        channelid = channel.id
                        channelID = result[0]
                        userID = result[1]
                        if int(channelID) == int(channelid):
                            if int(userID) == int(interaction.user.id):
                                for role in interaction.guild.roles:
                                    overwrites = {
                                        interaction.guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True),
                                        role: discord.PermissionOverwrite(connect=False, view_channel=True),
                                        interaction.user: discord.PermissionOverwrite(connect=True, use_voice_activation=True, speak=True, view_channel=True),
                                        interaction.guild.me: discord.PermissionOverwrite(connect=True)
                                    }
                                await interaction.user.voice.channel.edit(overwrites=overwrites)
                            else:
                                await interaction.followup.send(
                                    "<:Astra_x:1141303954555289600> **Du kannst dies nicht tun, da du nicht der Besitzer des Kanals bist**",
                                    ephemeral=True)
                        else:
                            await interaction.followup.send(
                                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
        except:
            pass

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, custom_id='persistent_view:unlock',
                       emoji="<:Schloss:1141384573171802132>")
    async def unlock(self, interaction: discord.Interaction, button: discord.Button):
        try:
            await interaction.response.defer()
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    voice_state = interaction.user.voice

                    if voice_state is None:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    await cur.execute(
                        "SELECT channelID, userID FROM usertempchannels WHERE guildID = (%s) AND channelID = (%s)",
                        (interaction.guild.id, interaction.user.voice.channel.id))
                    result = await cur.fetchone()
                    if not result:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    if result:
                        channel = interaction.user.voice.channel
                        channelid = channel.id
                        channelID = result[0]
                        userID = result[1]
                        if int(channelID) == int(channelid):
                            if int(userID) == int(interaction.user.id):
                                for role in interaction.guild.roles:
                                    overwrites = {
                                        interaction.guild.default_role: discord.PermissionOverwrite(connect=True,
                                                                                                    view_channel=True),
                                        role: discord.PermissionOverwrite(connect=True, view_channel=True),
                                        interaction.user: discord.PermissionOverwrite(connect=True, use_voice_activation=True, speak=True, view_channel=True),
                                        interaction.guild.me: discord.PermissionOverwrite(connect=True)
                                    }
                                await interaction.user.voice.channel.edit(overwrites=overwrites)
                            else:
                                await interaction.followup.send(
                                    "<:Astra_x:1141303954555289600> **Du kannst dies nicht tun, da du nicht der Besitzer des Kanals bist**",
                                    ephemeral=True)
                        else:
                            await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
        except:
            pass

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, custom_id='persistent_view:hide',
                       emoji="<:Verstecken:1141384593438683278>")
    async def hide(self, interaction: discord.Interaction, button: discord.Button):
        try:
            await interaction.response.defer()
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    voice_state = interaction.user.voice

                    if voice_state is None:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    await cur.execute(
                        "SELECT channelID, userID FROM usertempchannels WHERE guildID = (%s) AND channelID = (%s)",
                        (interaction.guild.id, interaction.user.voice.channel.id))
                    result = await cur.fetchone()
                    if not result:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    if result:
                        channel = interaction.user.voice.channel
                        channelid = channel.id
                        channelID = result[0]
                        userID = result[1]
                        if int(channelID) == int(channelid):
                            if int(userID) == int(interaction.user.id):
                                for role in interaction.guild.roles:
                                    overwrites = {
                                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                                        role: discord.PermissionOverwrite(view_channel=False),
                                        interaction.user: discord.PermissionOverwrite(connect=True, use_voice_activation=True, speak=True, view_channel=True),
                                        interaction.guild.me: discord.PermissionOverwrite(connect=True)
                                    }
                                await interaction.user.voice.channel.edit(overwrites=overwrites)
                            else:
                                await interaction.followup.send(
                                    "<:Astra_x:1141303954555289600> **Du kannst dies nicht tun, da du nicht der Besitzer des Kanals bist**",
                                    ephemeral=True)
                        else:
                            await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
        except:
            pass

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, custom_id='persistent_view:visible',
                       emoji="<:Zeigen:1141384600384438324>")
    async def visible(self, interaction: discord.Interaction, button: discord.Button):
        try:
            await interaction.response.defer()
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    voice_state = interaction.user.voice

                    if voice_state is None:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    await cur.execute(
                        "SELECT channelID, userID FROM usertempchannels WHERE guildID = (%s) AND channelID = (%s)",
                        (interaction.guild.id, interaction.user.voice.channel.id))
                    result = await cur.fetchone()
                    if not result:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    if result:
                        channel = interaction.user.voice.channel
                        channelid = channel.id
                        channelID = result[0]
                        userID = result[1]
                        if int(channelID) == int(channelid):
                            if int(userID) == int(interaction.user.id):
                                for role in interaction.guild.roles:
                                    overwrites = {
                                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True),
                                        role: discord.PermissionOverwrite(view_channel=True),
                                        interaction.user: discord.PermissionOverwrite(connect=True, use_voice_activation=True, speak=True, view_channel=True),
                                        interaction.guild.me: discord.PermissionOverwrite(connect=True)
                                    }
                                await interaction.user.voice.channel.edit(overwrites=overwrites)
                            else:
                                await interaction.followup.send(
                                    "<:Astra_x:1141303954555289600> **Du kannst dies nicht tun, da du nicht der Besitzer des Kanals bist**",
                                    ephemeral=True)
                        else:
                            await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
        except:
            pass

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, custom_id='persistent_view:rename',
                       emoji="<:Umbenennen:1141384590494290033>")
    async def rename(self, interaction: discord.Interaction, button: discord.Button):
        try:
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    voice_state = interaction.user.voice

                    if voice_state is None:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    await cur.execute(
                        "SELECT channelID, userID FROM usertempchannels WHERE guildID = (%s) AND channelID = (%s)",
                        (interaction.guild.id, interaction.user.voice.channel.id))
                    result = await cur.fetchone()
                    if not result:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    if result:
                        channel = interaction.user.voice.channel
                        channelid = channel.id
                        channelID = result[0]
                        userID = result[1]
                        if int(channelID) == int(channelid):
                            if int(userID) == int(interaction.user.id):
                                await interaction.response.send_modal(Feedback())
                            else:
                                await interaction.followup.send(
                                    "<:Astra_x:1141303954555289600> **Du kannst dies nicht tun, da du nicht der Besitzer des Kanals bist**",
                                    ephemeral=True)
                        else:
                            await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
        except:
            pass

    @discord.ui.button(label='', style=discord.ButtonStyle.grey, custom_id='persistent_view:limit',
                       emoji="<:Limit:1141319054674636870>")
    async def limit(self, interaction: discord.Interaction, button: discord.Button):
        try:
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    voice_state = interaction.user.voice

                    if voice_state is None:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    await cur.execute(
                        "SELECT channelID, userID FROM usertempchannels WHERE guildID = (%s) AND channelID = (%s)",
                        (interaction.guild.id, interaction.user.voice.channel.id))
                    result = await cur.fetchone()
                    if not result:
                        await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
                    if result:
                        channel = interaction.user.voice.channel
                        channelid = channel.id
                        channelID = result[0]
                        userID = result[1]
                        if int(channelID) == int(channelid):
                            if int(userID) == int(interaction.user.id):
                                await interaction.response.send_modal(Feedback2())
                            else:
                                await interaction.followup.send(
                                    "<:Astra_x:1141303954555289600> **Du kannst dies nicht tun, da du nicht der Besitzer des Kanals bist**",
                                    ephemeral=True)
                        else:
                            await interaction.followup.send(
                            "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True)
        except:
            pass


class tempchannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(tempchannel1())

    @app_commands.command(name="voicesetup", description="Richte Voice-Channel-Autoerstellung auf deinem Server ein.")
    @app_commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.channel)
    @commands.has_permissions(manage_channels=True)
    async def voicesetup(self, interaction: discord.Interaction):
        """Create tempchannels for your server"""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if interaction.user.bot:
                    return
                else:
                    await cursor.execute(f"SELECT channel_id FROM tempchannels WHERE guild_id = (%s)",
                                         (interaction.guild.id))
                    result = await cursor.fetchone()
                    if result is None:
                        new_category = await interaction.guild.create_category('Private Sprachkanäle')
                        category1 = discord.utils.get(interaction.guild.categories, id=int(new_category.id))
                        vc = await interaction.guild.create_voice_channel("Join to create", category=category1,
                                                                          reason="Benutze Voicesetup Command.")
                        channel = await interaction.guild.create_text_channel(name="interface", category=category1)
                        embed5 = discord.Embed(title="Interface",
                                               description="> In diesem Interface kannst du mit den Buttons deinen Tempchannel bearbeiten. Du kannst einige dinge einstellen, probiers doch mal aus.",
                                               colour=discord.Colour.blue())
                        embed5.set_image(
                            url="https://cdn.discordapp.com/attachments/1141116983358804117/1410009910011363512/Banner_deutsch.png")
                        embed5.set_footer(text="Du kannst deinen Tempchannel mit den Buttons einstellen.",
                                          icon_url=interaction.guild.icon.url)
                        await channel.send(embed=embed5, view=tempchannel1())

                        embed = discord.Embed(colour=discord.Colour.blue(),
                                              description=f"Die Einrichtung des Sprachkanals war erfolgreich.\n{vc.mention}")
                        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                        await interaction.response.send_message(embed=embed)

                        await cursor.execute(f"INSERT INTO tempchannels (channel_id, guild_id) VALUES (%s, %s)",
                                             (vc.id, interaction.guild.id))

                    if result is not None:
                        new_category = await interaction.guild.create_category('Private Sprachkanäle')
                        category1 = discord.utils.get(interaction.guild.categories, id=int(new_category.id))
                        vc = await interaction.guild.create_voice_channel("Join to create", category=category1,
                                                                          reason="Benutze Voicesetup Command.")

                        channel = await interaction.guild.create_text_channel(name="interface", category=category1)
                        embed5 = discord.Embed(title="Interface",
                                               description="> In diesem Interface kannst du mit den Buttons deinen Temochannel bearbeiten. Du kannst einige dinge einstellen, probiers doch mal aus.",
                                               colour=discord.Colour.blue())
                        embed5.set_image(
                            url="https://cdn.discordapp.com/attachments/842039934142513152/1061417801362985000/Banner.png")
                        embed5.set_footer(text="Du kannst deinen Tempchannel mit den Buttons einstellen.",
                                          icon_url=interaction.guild.icon.url)
                        await channel.send(embed=embed5, view=tempchannel1())

                        embed = discord.Embed(colour=discord.Colour.blue(),
                                              description=f"Der Sprachkanal wurde erfolgreich geändert.\n{vc.mention}")
                        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)

                        await cursor.execute(
                            f"UPDATE tempchannels SET channel_id = (%s) WHERE guild_id = (%s)",
                            (str(vc.id), str(interaction.guild.id)))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if before.channel:
                    if isTempChannel(before.channel):
                        bchan = before.channel
                        if len(bchan.members) == 0:
                            await bchan.delete(reason="Keine User im Sprachkanal.")
                            await cur.execute("DELETE FROM usertempchannels WHERE guildID = (%s) and channelID = (%s)",
                                              (before.channel.guild.id, before.channel.id))
                    else:
                        pass
                if after.channel:
                    if await isJoinHub(self, after.channel):
                        name = f"{member.name}"
                        output = await after.channel.clone(name=name, reason="Joinhub gejoined.")

                        if output:
                            tempchannels.append(output.id)
                            await member.move_to(output, reason="Tempchannel erstellt.")
                            await cur.execute(
                                "INSERT INTO usertempchannels (guildID, userID, channelID) VALUES(%s, %s, %s)",
                                (after.channel.guild.id, member.id, output.id))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(tempchannel(bot))
