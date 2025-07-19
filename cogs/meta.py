import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from discord.app_commands import Group
import aiohttp
from discord.ui.button import Button
from discord.ui.view import View
import requests
import asyncio
from collections import deque


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



class meta(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="umfrage")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def poll(self, interaction: discord.Interaction, titel: str, optionen: str):
        """Erstelle eine Umfrage."""
        optionen_liste = [opt.strip() for opt in optionen.split(',')]
        reactions = ['🔵', '🟢', '🟡', '🔴', '🟠', '🟣', '🟤']
        emojis = reactions[:len(optionen_liste)]

        embed = discord.Embed(title=titel, description="Wählen Sie eine Option", color=discord.Color.blue())
        embed.add_field(
            name="Optionen",
            value='\n'.join([f"{emoji} - {option}" for emoji, option in zip(emojis, optionen_liste)]),
            inline=False
        )

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()

        for emoji in emojis:
            await message.add_reaction(emoji)

        event_queue = deque()

        def check(reaction, user):
            return (
                reaction.message.id == message.id and
                str(reaction.emoji) in emojis and
                not user.bot
            )

        async def reaction_listener():
            while True:
                done, _ = await asyncio.wait([
                    asyncio.create_task(self.bot.wait_for('reaction_add', check=check)),
                    asyncio.create_task(self.bot.wait_for('reaction_remove', check=check))
                ], return_when=asyncio.FIRST_COMPLETED)

                event_queue.append(1)  # Irgendein Event wurde erkannt

        async def updater():
            while True:
                if event_queue:
                    event_queue.clear()  # Alle "alten" Events verwerfen, nur neuester Stand zählt

                    msg = await interaction.channel.fetch_message(message.id)
                    stimmen = {emoji: 0 for emoji in emojis}

                    for reaction in msg.reactions:
                        if str(reaction.emoji) in stimmen:
                            async for user in reaction.users():
                                if not user.bot:
                                    stimmen[str(reaction.emoji)] += 1

                    total_votes = sum(stimmen.values())
                    results = []
                    for emoji in emojis:
                        votes = stimmen[emoji]
                        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                        bar = '█' * int(percentage // 10) + '░' * (10 - int(percentage // 10))
                        results.append(f"{emoji} - {votes} Stimmen | {percentage:.1f}% [{bar}]")

                    new_embed = discord.Embed(
                        title=f"Abstimmung Ergebnisse: {titel}",
                        description="Aktuelle Ergebnisse",
                        color=discord.Color.green()
                    )
                    new_embed.add_field(name="Optionen", value="\n".join(results), inline=False)
                    await msg.edit(embed=new_embed)

                await asyncio.sleep(2)  # Alle 2 Sekunden prüfen

        # Beides gleichzeitig starten
        await asyncio.gather(reaction_listener(), updater())

        
    info = Group(name='info', description="Informationen über deinen Server.")

    @info.command(name="kanal")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def channelinfo(self, interaction: discord.Interaction, textchannel: discord.TextChannel = None,
                          voicechannels: discord.VoiceChannel = None):
        """Zeigt einige Infos über einen Channel."""
        if textchannel is None:
            channels = interaction.channel
        if isinstance(textchannel, discord.TextChannel):
            channel = textchannel
            embed = discord.Embed(colour=discord.Color.green())
            embed.add_field(name=f"🆔 ID", value=f"{channel.id}", inline=False)
            embed.add_field(name="⚙️ Erstellt", value=f"{discord.utils.format_dt(channel.created_at, 'R')}",
                            inline=False)
            embed.add_field(name="🗂 Kategorie",
                            value=f"{channel.category.name if channel.category.name else 'Keine Kategorie.'}",
                            inline=False)
            embed.add_field(name="🖌 Beschreibung", value=f"{channel.topic if channel.topic else 'Keine Beschreibung.'}",
                            inline=False)
            embed.add_field(name="🔢 Position", value=f"{channel.position}",
                            inline=False)
            embed.set_author(name=f"Kanal Info {channel.name}", icon_url=interaction.user.avatar)
            await interaction.response.send_message(embed=embed)
            return
        if isinstance(voicechannels, discord.VoiceChannel):
            channel = voicechannels
            embed = discord.Embed(colour=discord.Color.green())
            embed.add_field(name=f"🆔 ID", value=f"{channel.id}", inline=False)
            embed.add_field(name="⏱️ Erstellt", value=f"{discord.utils.format_dt(channel.created_at, 'R')}",
                            inline=False)
            embed.add_field(name="🗂 Kategorie",
                            value=f"{channel.category.name if channel.category.name else 'Keine Kategorie.'}",
                            inline=False)
            if channel.user_limit == 0:
                embed.add_field(name=f"📊 Limit", value=f"Kein Limit", inline=False)
            else:
                embed.add_field(name=f"📊 Limit", value=f"{channel.user_limit}", inline=False)
            embed.add_field(name=f"🔊 Bitrate", value=f"{channel.bitrate / 1000} kbps", inline=False)
            embed.set_author(name=f"Kanal Info {channel.name}", icon_url=interaction.user.avatar)
            await interaction.response.send_message(embed=embed)
            return

    @info.command(name="user")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        """Zeigt einige Infos über einen User."""
        if member is None:
            member = interaction.user
        user = interaction.guild.get_member(member.id)
        banneruser = await interaction.client.fetch_user(member.id)
        if member.top_role.is_default():
            topRole = 'everyone'  # to prevent @everyone spam
            topRoleColour = '#000000'
        else:
            topRole = member.top_role
            topRoleColour = member.top_role.colour
        if member is not None:
            memberacc = str(discord.utils.format_dt(member.created_at, 'R'))
            joined = str(discord.utils.format_dt(member.joined_at, 'R'))
            embed = discord.Embed(color=0x3498db)
            embed.set_thumbnail(url=member.avatar)
            if banneruser.banner:
                banner_url = banneruser.banner.url
                embed.set_image(url=banner_url)
            else:
                pass
            embed.add_field(name=f"<:Astra_user2:1141303942324699206> Name", value=f"{member.name}",
                            inline=False)
            embed.add_field(name="🆔 ID", value=member.id, inline=False)
            if member.bot:
                embed.add_field(name="🤖 Bot", value="Ja", inline=False)
            else:
                embed.add_field(name="🤖 Bot", value="Nein", inline=False)
            if member.public_flags.hypesquad_balance:
                embed.add_field(name='🥇 Badges',
                                value="<:Balance:1141837380144353401>",
                                inline=False)
            elif member.public_flags.hypesquad_bravery:
                embed.add_field(name='🥇 Badges',
                                value="<:Bravery:1141837378252705842>",
                                inline=False)
            elif member.public_flags.hypesquad_brilliance:
                embed.add_field(name='🥇 Badges',
                                value="<:Brillance:1141837375354454056>",
                                inline=False)
            else:
                embed.add_field(name='🥇 Badges',
                                value="Keine Badges",
                                inline=False)
            embed.add_field(name='<:Astra_calender:1141303828625489940> Account erstellt',
                            value=memberacc,
                            inline=False)
            embed.add_field(name='<:Astra_time:1141303932061233202> Server beigetreten',
                            value=joined,
                            inline=False)
            embed.add_field(name='<:Astra_stift:1141825585836998716> Höchste Rolle',
                            value=topRole.mention,
                            inline=True)
            custom = discord.utils.get(user.activities, type=discord.ActivityType.custom)
            playing = discord.utils.get(user.activities, type=discord.ActivityType.playing)
            listening = discord.utils.get(user.activities, type=discord.ActivityType.listening)
            watching = discord.utils.get(user.activities, type=discord.ActivityType.watching)
            streaming = discord.utils.get(user.activities, type=discord.ActivityType.streaming)
            if custom and listening:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}, {listening}",
                                inline=False)
            elif custom and playing:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}, {playing.name}",
                                inline=False)
            elif custom and watching:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}, {watching}",
                                inline=False)
            elif custom and streaming:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}, {streaming}",
                                inline=False)
            elif playing and listening:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}, {playing.name}",
                                inline=False)
            elif playing and watching:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}, {playing.name}",
                                inline=False)
            elif playing and streaming:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}, {playing.name}",
                                inline=False)
            elif listening and watching:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{listening}, {watching}",
                                inline=False)
            elif listening and streaming:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{listening}, {streaming}",
                                inline=False)
            elif watching and streaming:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{watching}, {streaming}",
                                inline=False)
            elif listening:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{listening}",
                                inline=False)
            elif watching:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{watching}",
                                inline=False)
            elif custom:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{custom.name}",
                                inline=False)
            elif playing:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"{playing.name}",
                                inline=False)
            else:
                embed.add_field(name='<:Astra_stream:1141303918949838929> Status',
                                value=f"No Status",
                                inline=False)
            embed.add_field(name='<:Astra_user:1141303940365959241> Avatar link',
                            value=f"[Klick hier]({member.avatar})",
                            inline=False)
            await interaction.response.send_message(embed=embed)

    @info.command(name="server")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def serverinfo(self, interaction: discord.Interaction):
        """Zeigt einige Infos über einen Server."""
        roles = len(interaction.guild.roles)
        embed = discord.Embed(color=0x3498db)  # Golden
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.add_field(name='Name', value=f"{interaction.guild.name}", inline=True)
        embed.add_field(name='ID', value=f"{interaction.guild.id}", inline=True)
        embed.add_field(name='Inhaber', value=f"{interaction.guild.owner}",
                        inline=False)
        embed.add_field(name='<:Astra_user2:1141303942324699206> Members',
                        value=f"{interaction.guild.member_count}",
                        inline=False)
        embed.add_field(name='<:Astra_calender:1141303828625489940> Erstellt',
                        value=f"{discord.utils.format_dt(interaction.guild.created_at, 'R')}",
                        inline=False)
        embed.add_field(name="<:Astra_boost:1141303827107164270> Boosts",
                        value=f"{interaction.guild.premium_subscription_count}")
        embed.add_field(name="<:Astra_boost:1141303827107164270> Boost level",
                        value=f"{interaction.guild.premium_tier}",
                        inline=True)
        embed.add_field(name='<:Astra_time:1141303932061233202> AFK Voice Timeout',
                        value=f'{int(interaction.guild.afk_timeout / 60)} min',
                        inline=True)
        if interaction.guild.system_channel:
            embed.add_field(name='<:Astra_settings2:1141303910557040660> Standard Kanal',
                            value=f'#{interaction.guild.system_channel}',
                            inline=False)
        embed.add_field(name='<:Astra_file1:1141303837181886494> Rollen', value=f"{roles}", inline=True)
        await interaction.response.send_message(embed=embed)

    @info.command(name="servericon")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def servericon(self, interaction: discord.Interaction):
        """Zeigt das Server Profilbild."""
        guild = interaction.guild
        embed = discord.Embed(colour=discord.Colour.green(),
                              description=f"Servericon von {guild.name}")
        embed.set_author(name=f"Servericon von {guild.name}", icon_url=interaction.guild.icon)
        embed.set_image(url=guild.icon)
        await interaction.response.send_message(embed=embed)

    @info.command(name="rolle")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Get information about a role."""

        em = discord.Embed(description=f'Info über {role.name}', color=discord.Color.green())
        em.title = role.name
        thing = str(discord.utils.format_dt(role.created_at, 'R'))

        em.add_field(name="🆔 Role ID", value=f"{str(role.id)}", inline=True)
        em.add_field(name="⏱ Erstellt", value=f"Created at {thing}", inline=False)
        em.add_field(name='🖌 Farbe', value=f"{str(role.colour)}", inline=False)
        em.add_field(name='👥 Personen in der Rolle',
                     value=f"{str(len(role.members))} von {interaction.guild.member_count} Mitgliedern.", inline=True)
        await interaction.response.send_message(embed=em)

    @info.command(name="wetter")
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def weather(self, interaction: discord.Interaction, stadt: str):
        """Zeigt dir einige Infos über das Wetter einer Stadt."""
        try:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(
                        f"https://api.openweathermap.org/data/2.5/weather?appid=bf254c2299576dc022583728cfaf7971&q=" + city.replace(
                            " ", "+")) as r:
                    data = await r.json()
                    icon = data['weather'][0]['icon']
                    embed = discord.Embed(colour=discord.Colour.green(), title=f"Weather",
                                          description=f"Mal sehen...")
                    embed.add_field(name=f"🗽 Standort", value=f"{data['name']}")
                    embed.add_field(name=f"☁️ Wetter",
                                    value=f"{data['weather'][0]['main']} - {data['weather'][0]['description']}",
                                    inline=False)
                    embed.add_field(name=f"🔥 Temperatur", value=f"{int((float(data['main']['temp']))) - 273}°C")
                    embed.add_field(name=f"👆 Fühlt sich an wie",
                                    value=f"{int((float(data['main']['feels_like']))) - 273}°C")
                    embed.add_field(name=f"💧 Luftfeuchtigkeit", value=f"{int((float(data['main']['humidity'])))}%",
                                    inline=False)
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    embed.set_thumbnail(url=f"https://openweathermap.org/img/wn/{icon}@2x.png")
                    await interaction.response.send_message(embed=embed)
        except:
            embed = discord.Embed(colour=discord.Colour.red(),
                                  description=f"Stadt `{city}` nicht gefunden.")
            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
            await interaction.response.send_message(embed=embed)
            return

    @app_commands.command(name="invites")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
    async def invites(self, interaction: discord.Interaction, user: discord.Member = None):
        """Zeigt die Einladungen eines Users."""
        if user is None:
            user = interaction.user
        if user is not None:
            totalInvites = 0
            for i in await interaction.guild.invites():
                if i.inviter == user:
                    totalInvites += i.uses
            embed = discord.Embed(title="Einladungen",
                                  description=f"Der User {user.mention} hat insgesamt __**{totalInvites}**__ User auf diesen Server eingeladen.",
                                  colour=discord.Colour.blue())
            embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
            await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(meta(bot))
