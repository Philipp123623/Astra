import asyncio
import logging
import math
import random
from datetime import datetime, timezone
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands


def convert(time_str: str) -> int:
    """
    Konvertiert eine Zeitangabe wie '10m', '2h', '3d' in Sekunden.
    Rückgabe: -1 bei ungültiger Einheit, -2 bei Value-Fehler.
    """
    pos = ["s", "m", "h", "d", "w"]
    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24, "w": 3600 * 24 * 7}
    unit = time_str[-1]
    if unit not in pos:
        return -1
    try:
        val = int(time_str[:-1])
    except Exception:
        return -2
    return val * time_dict[unit]


async def gwtimes(bot: commands.Bot, when: datetime, messageid: int):
    """
    Wartet bis 'when' und beendet dann das Giveaway mit der Message-ID 'messageid'.
    1:1 deine Logik – nur mit explizitem 'bot' Parameter, damit das in einer Cog sauber ist.
    """
    await bot.wait_until_ready()
    await discord.utils.sleep_until(when=when)

    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT guildID, channelID, userID, messageID FROM giveaway_entrys WHERE messageID = %s",
                (messageid,),
            )
            result = await cur.fetchall()

            await cur.execute(
                "SELECT ended, prize, winners, entrys, time, guildID, channelID "
                "FROM giveaway_active WHERE messageID = %s",
                (messageid,),
            )
            result3 = await cur.fetchone()
            if not result3:
                return

            ended = result3[0]
            price = result3[1]
            winners = result3[2]
            entrys = result3[3]
            time_unix = result3[4]
            guildID = result3[5]
            channelID = result3[6]

            # == SICHERHEITSCHECKS für Guild & Channel ==
            guild = bot.get_guild(int(guildID))
            if guild is None:
                logging.error(f"Guild {guildID} not found for giveaway {messageid}!")
                return

            channel = guild.get_channel(int(channelID))
            if channel is None:
                logging.error(f"Channel {channelID} not found in guild {guildID} for giveaway {messageid}!")
                return

            try:
                msg = await channel.fetch_message(messageid)
            except Exception as e:
                logging.error(
                    f"Giveaway message {messageid} not found in channel {channelID} in guild {guildID}: {e}"
                )
                return

            time2 = datetime.fromtimestamp(int(time_unix), tz=timezone.utc)

            # Niemand hat teilgenommen
            if not result:
                if int(ended) == 1:
                    return
                if int(ended) == 0:
                    embed = discord.Embed(
                        title=" ",
                        description=(
                            f"🏆 Preis: {price}\n"
                            "`🤖` [Astra Einladen]"
                            "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                            "<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                            "<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n"
                            f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                            "<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer."
                        ),
                        colour=discord.Colour.red(),
                    )
                    await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                    await msg.reply(
                        "<:Astra_x:1141303954555289600> **Es gab nicht genügend Teilnehmer. Niemand hat das Gewinnspiel gewonnen.**"
                    )
                    await cur.execute(
                        "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s and messageID = %s",
                        (1, guild.id, channel.id, messageid),
                    )
                    await cur.execute("DELETE FROM giveway_ids WHERE messageID = %s", (messageid,))

            # Es gibt Teilnehmer
            if result:
                guildID = result[0][0]
                channelID = result[0][1]
                await cur.execute(
                    "SELECT ended, prize, winners, entrys, time "
                    "FROM giveaway_active WHERE guildID = %s AND channelID = %s AND messageID = %s",
                    (guildID, channelID, messageid),
                )
                result2 = await cur.fetchone()
                ended = result2[0]
                if int(ended) == 1:
                    return
                if int(ended) == 0:
                    price = result2[1]
                    winners_amount = int(result2[2])
                    entrys = result2[3]
                    time_unix = result2[4]
                    time2 = datetime.fromtimestamp(int(time_unix), tz=timezone.utc)
                    participants = [row[2] for row in result]

                    # Gewinner bestimmen (Anzahl nie höher als Teilnehmer)
                    chosen_winners = []
                    if len(participants) > 0:
                        to_pick = min(len(participants), winners_amount)
                        chosen_winners = random.sample(participants, k=to_pick)

                    users = []
                    for uid in chosen_winners:
                        idwinners = bot.get_user(uid)
                        winembed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                f"`🎉` Du hast ein Gewinnspiel auf [{guild.name}]"
                                f"(https://discord.com/channels/{guild.id}/{channel.id}/{msg.id}) gewonnen.\n"
                                f"`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}"
                            ),
                            colour=discord.Colour.yellow(),
                        )
                        if guild.icon:
                            winembed.set_thumbnail(url=guild.icon.url)
                        try:
                            await idwinners.send(
                                "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                embed=winembed,
                            )
                        except Exception:
                            pass
                        users.append(idwinners)

                    mentions = ", ".join(user.mention for user in users if user)
                    if entrys < 1 or not users:
                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                                "<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n"
                                f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                                "<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer."
                            ),
                            colour=discord.Colour.red(),
                        )
                        await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                        await msg.reply(
                            "<:Astra_x:1141303954555289600> Es gab nicht genügend Teilnehmer. Niemand hat das Gewinnspiel gewonnen."
                        )
                        await cur.execute(
                            "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s and messageID = %s",
                            (1, guildID, channelID, messageid),
                        )
                        await cur.execute("DELETE FROM giveway_ids WHERE messageID = %s", (messageid,))
                    else:
                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_gw_open2:1141303850125504533> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                                f"<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n"
                                f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer."
                            ),
                            colour=discord.Colour.red(),
                        )
                        await msg.edit(content="`❌` Giveaway Ended `❌`", embed=embed, view=None)
                        await msg.reply(
                            f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen! Herzlichen Glückwunsch."
                        )
                        await cur.execute(
                            "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s and messageID = %s",
                            (1, guildID, channelID, messageid),
                        )
                        await cur.execute("DELETE FROM giveway_ids WHERE messageID = %s", (messageid,))


class GiveawayButton(discord.ui.View):
    """
    1:1 deine View-Logik; nur so umgebaut, dass sie self.bot benutzt statt globalem bot.
    custom_id bleibt identisch.
    """
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label='Teilnehmen',
        style=discord.ButtonStyle.green,
        custom_id='persistent_view_allg:join_gw',
        emoji="🎉"
    )
    async def join_gw(self, interaction: discord.Interaction, button: discord.Button):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await interaction.response.defer(ephemeral=True)

                await cur.execute(
                    "SELECT userID FROM giveaway_entrys WHERE userID = %s AND guildID = %s AND channelID = %s AND messageID = %s",
                    (interaction.user.id, interaction.guild.id, interaction.channel.id, interaction.message.id)
                )
                result = await cur.fetchone()

                await cur.execute(
                    "SELECT role, level, entrys, messageID, prize, winners, time, creatorID "
                    "FROM giveaway_active WHERE guildID = %s AND channelID = %s AND messageID = %s",
                    (interaction.guild.id, interaction.channel.id, interaction.message.id)
                )
                result2 = await cur.fetchone()
                roleID = result2[0]
                level = result2[1]
                entrys = result2[2]
                messageID = result2[3]
                price = result2[4]
                winners = result2[5]
                time_unix = result2[6]
                creatorID = result2[7]

                creator = self.bot.get_user(creatorID)
                time2 = datetime.fromtimestamp(int(time_unix), tz=timezone.utc)

                # TEILNAHME (User ist NICHT drin)
                if not result:
                    # KEINE Anforderungen
                    if str(roleID) == "Not Set" and str(level) == "Not Set":
                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                                f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n"
                                "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen."
                            ),
                            colour=discord.Colour.blue()
                        )
                        if interaction.guild and interaction.guild.icon:
                            embed.set_thumbnail(url=interaction.guild.icon.url)
                            embed.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embed)
                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                            (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                        )
                        await cur.execute(
                            "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                            (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                        )
                        successemb = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n"
                                f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}."
                            ),
                            colour=discord.Colour.green()
                        )
                        if interaction.guild and interaction.guild.icon:
                            successemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                embed=successemb
                            )
                        except Exception:
                            pass

                    # NUR ROLLE
                    if str(roleID).isnumeric() and level == "Not Set":
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        if role in interaction.user.roles:
                            embe = discord.Embed(
                                title=" ",
                                description=(
                                    f"🏆 Preis: {price}\n"
                                    "`🤖` [Astra Einladen]"
                                    "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                    "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                                    f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                    f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                    f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                    f"<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n"
                                    "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                    "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n"
                                    f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen."
                                ),
                                colour=discord.Colour.blue()
                            )
                            if interaction.guild and interaction.guild.icon:
                                embe.set_thumbnail(url=interaction.guild.icon.url)
                                embe.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                            msg = await interaction.channel.fetch_message(messageID)
                            await msg.edit(embed=embe)
                            await cur.execute(
                                "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                                (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                            )
                            await cur.execute(
                                "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                            )
                            successemb = discord.Embed(
                                title=" ",
                                description=(
                                    f"🏆 Preis: {price}\n"
                                    "`🤖` [Astra Einladen]"
                                    "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                    f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                    f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n"
                                    f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}."
                                ),
                                colour=discord.Colour.green()
                            )
                            if interaction.guild and interaction.guild.icon:
                                successemb.set_thumbnail(url=interaction.guild.icon.url)
                            try:
                                await interaction.user.send(
                                    "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                    embed=successemb
                                )
                            except Exception:
                                pass
                        else:
                            failemb = discord.Embed(
                                title=" ",
                                description=(
                                    f"🏆 Preis: {price}\n"
                                    "`🤖` [Invite Astra here]"
                                    "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                    f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                    f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n"
                                    f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n"
                                    "`🧨` __**Grund**__\n"
                                    f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen."
                                ),
                                colour=discord.Colour.red()
                            )
                            if interaction.guild and interaction.guild.icon:
                                failemb.set_thumbnail(url=interaction.guild.icon.url)
                            try:
                                await interaction.user.send(
                                    "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                    embed=failemb
                                )
                            except Exception:
                                pass

                    # NUR LEVEL
                    if roleID == "Not Set" and str(level).isnumeric():
                        await cur.execute(
                            "SELECT user_xp, user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                            (interaction.user.id, interaction.guild.id)
                        )
                        result_level = await cur.fetchone()
                        if not result_level:
                            try:
                                await interaction.user.send(
                                    "<:Astra_x:1141303954555289600> **Wir haben leider keine Einträge über dich gefunden. "
                                    "Schreibe erst eine Nachricht und versuche es erneut.**"
                                )
                            except Exception:
                                pass
                        else:
                            lvl_start = result_level[1]
                            if int(level) <= int(lvl_start):
                                emb = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {price}\n"
                                        "`🤖` [Astra Einladen]"
                                        "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        "<:Astra_info:1141303860556738620>__**Informationen:**__\n"
                                        f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                        f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                        f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                        f"<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n"
                                        "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                        "<:Astra_arrow:1141303823600717885> Klicke unten auf den **Button** um am Gewinnspiel teilzunehmen.\n"
                                        f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen."
                                    ),
                                    colour=discord.Colour.blue()
                                )
                                if interaction.guild and interaction.guild.icon:
                                    emb.set_thumbnail(url=interaction.guild.icon.url)
                                    emb.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                                msg = await interaction.channel.fetch_message(messageID)
                                await msg.edit(embed=emb)
                                await cur.execute(
                                    "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                                    (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                                )
                                await cur.execute(
                                    "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                    (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                                )
                                successemb = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {price}\n"
                                        "`🤖` [Astra Einladen]"
                                        "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                        f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n"
                                        f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}."
                                    ),
                                    colour=discord.Colour.green()
                                )
                                if interaction.guild and interaction.guild.icon:
                                    successemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                        embed=successemb
                                    )
                                except Exception:
                                    pass
                            else:
                                failemb = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {price}\n"
                                        "`🤖` [Astra Einladen]"
                                        "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                        f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n"
                                        f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n"
                                        "`🧨` __**Grund**__\n"
                                        f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen."
                                    ),
                                    colour=discord.Colour.red()
                                )
                                if interaction.guild and interaction.guild.icon:
                                    failemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                        embed=failemb
                                    )
                                except Exception:
                                    pass

                    # BEIDES (Rolle + Level)
                    if str(roleID).isnumeric() and str(level).isnumeric():
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        await cur.execute(
                            "SELECT user_xp, user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                            (interaction.user.id, interaction.guild.id)
                        )
                        result5 = await cur.fetchone()
                        if not result5:
                            try:
                                await interaction.user.send(
                                    "<:Astra_x:1141303954555289600> **Wir haben leider keine Einträge über dich gefunden. "
                                    "Schreibe erst eine Nachricht und versuche es erneut.**"
                                )
                            except Exception:
                                pass
                        else:
                            lvl_start = result5[1]
                            if int(level) <= int(lvl_start) and role in interaction.user.roles:
                                em = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {price}\n"
                                        "`🤖` [Astra Einladen]"
                                        "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                                        f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                        f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                        f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                        f"<:Astra_arrow:1141303823600717885> **{(int(entrys) + 1)}** Teilnehmer\n\n"
                                        "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                        "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n"
                                        f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n"
                                        f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen."
                                    ),
                                    colour=discord.Colour.blue()
                                )
                                if interaction.guild and interaction.guild.icon:
                                    em.set_thumbnail(url=interaction.guild.icon.url)
                                    em.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                                msg = await interaction.channel.fetch_message(messageID)
                                await msg.edit(embed=em)
                                await cur.execute(
                                    "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                                    (int(entrys) + 1, interaction.guild.id, interaction.channel.id, interaction.message.id)
                                )
                                await cur.execute(
                                    "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES(%s, %s, %s, %s)",
                                    (interaction.guild.id, interaction.channel.id, interaction.user.id, interaction.message.id)
                                )
                                successemb = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {price}\n"
                                        "`🤖` [Astra Einladen]"
                                        "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                        f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war erfolgreich.\n"
                                        f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}."
                                    ),
                                    colour=discord.Colour.green()
                                )
                                if interaction.guild and interaction.guild.icon:
                                    successemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                        embed=successemb
                                    )
                                except Exception:
                                    pass
                            else:
                                failemb = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {price}\n"
                                        "`🤖` [Astra Einladen]"
                                        "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                        f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n"
                                        f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n"
                                        "`🧨` __**Grund**__\n"
                                        f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` und **Level {level}** um teilzunehmen."
                                    ),
                                    colour=discord.Colour.red()
                                )
                                if interaction.guild and interaction.guild.icon:
                                    failemb.set_thumbnail(url=interaction.guild.icon.url)
                                try:
                                    await interaction.user.send(
                                        "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                        embed=failemb
                                    )
                                except Exception:
                                    pass

                # ABMELDEN (User ist bereits drin)
                if result:
                    await cur.execute(
                        "DELETE FROM giveaway_entrys WHERE userID = %s AND guildID = %s AND messageID = %s",
                        (interaction.user.id, interaction.guild.id, interaction.message.id)
                    )
                    await cur.execute(
                        "UPDATE giveaway_active SET entrys = %s WHERE channelID = %s AND guildID = %s AND messageID = %s",
                        (max(int(entrys) - 1, 0), interaction.channel.id, interaction.guild.id, interaction.message.id)
                    )

                    # Embed aktualisieren (Teilnehmer-1)
                    if str(roleID).isnumeric() and str(level).isnumeric():
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        em = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                                f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n"
                                "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n"
                                f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen.\n"
                                f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen."
                            ),
                            colour=discord.Colour.blue()
                        )
                        if interaction.guild and interaction.guild.icon:
                            em.set_thumbnail(url=interaction.guild.icon.url)
                            em.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=em)

                        failemb = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n"
                                f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n"
                                "`🧨` __**Grund**__\n"
                                "<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen."
                            ),
                            colour=discord.Colour.red()
                        )
                        if interaction.guild and interaction.guild.icon:
                            failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass

                    if str(roleID) == "Not Set" and str(level) == "Not Set":
                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                                f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n"
                                "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen."
                            ),
                            colour=discord.Colour.blue()
                        )
                        if interaction.guild and interaction.guild.icon:
                            embed.set_thumbnail(url=interaction.guild.icon.url)
                            embed.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embed)

                        failemb = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Invite Astra here]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n"
                                f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n"
                                "`🧨` __**Grund**__\n"
                                "<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen."
                            ),
                            colour=discord.Colour.red()
                        )
                        if interaction.guild and interaction.guild.icon:
                            failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass

                    if roleID == "Not Set" and str(level).isnumeric():
                        emb = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                                f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n"
                                "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n"
                                f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen."
                            ),
                            colour=discord.Colour.blue()
                        )
                        if interaction.guild and interaction.guild.icon:
                            emb.set_thumbnail(url=interaction.guild.icon.url)
                            emb.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=emb)

                        failemb = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n"
                                f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n"
                                "`🧨` __**Grund**__\n"
                                "<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen."
                            ),
                            colour=discord.Colour.red()
                        )
                        if interaction.guild and interaction.guild.icon:
                            failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass

                    if str(roleID).isnumeric() and level == "Not Set":
                        role = discord.utils.get(interaction.guild.roles, id=int(roleID))
                        embe = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                                f"<:Astra_arrow:1141303823600717885> Erstellt von {creator.mention}\n"
                                f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                                f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> **{(int(entrys) - 1)}** Teilnehmer\n\n"
                                "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                                "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen.\n"
                                f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role.name}` um teilzunehmen."
                            ),
                            colour=discord.Colour.blue()
                        )
                        if interaction.guild and interaction.guild.icon:
                            embe.set_thumbnail(url=interaction.guild.icon.url)
                            embe.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                        msg = await interaction.channel.fetch_message(messageID)
                        await msg.edit(embed=embe)

                        failemb = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {price}\n"
                                "`🤖` [Astra Einladen]"
                                "(https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                f"`🎉` Deine Teilnahme auf [{interaction.guild.name}]"
                                f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{interaction.message.id}) war **nicht** erfolgreich.\n"
                                f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(time2, 'R')}.\n\n"
                                "`🧨` __**Grund**__\n"
                                "<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen."
                            ),
                            colour=discord.Colour.red()
                        )
                        if interaction.guild and interaction.guild.icon:
                            failemb.set_thumbnail(url=interaction.guild.icon.url)
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                                embed=failemb
                            )
                        except Exception:
                            pass

@app_commands.guild_only()
class Giveaway(app_commands.Group):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            name="gewinnspiel",
            description="Alles rund um Gewinnspiele."
        )

    @app_commands.command(name="starten", description="Startet ein Gewinnspiel.")
    @app_commands.describe(preis="Der Preis des Gewinnspiels.")
    @app_commands.describe(kanal="Der Kanal, in dem das Gewinnspiel stattfinden soll.")
    @app_commands.describe(gewinner="Anzahl der Gewinner.")
    @app_commands.describe(zeit="Dauer des Gewinnspiels (z.B. 10m, 2h, 3d).")
    @app_commands.describe(rolle="Optional: Rolle, die teilnehmen darf.")
    @app_commands.describe(level="Optional: Mindestlevel für Teilnahme.")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gw_start(
        self,
        interaction: discord.Interaction,
        *,
        preis: str,
        kanal: discord.TextChannel,
        gewinner: int,
        zeit: str,
        rolle: discord.Role = None,
        level: int = None
    ):
        """Startet ein Gewinnspiel."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Validierung Levelsystem (wenn benötigt)
                if (rolle or level):
                    if level:
                        await cur.execute("SELECT enabled FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,))
                        enabled = await cur.fetchone()
                        if not enabled or enabled[0] == 0:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> Das Levelsystem ist auf diesem Server deaktiviert.",
                                ephemeral=True
                            )
                            return

                # Zeit umrechnen
                time1 = convert(zeit)  # Sekunden (z. B. 43200 für 12h)
                t1 = math.floor(discord.utils.utcnow().timestamp() + time1)  # korrekter Unix-Timestamp
                t2 = datetime.fromtimestamp(t1, tz=timezone.utc)            # Zeitzone-aware

                # Embed-Description bauen (abhängig von Anforderungen)
                req_lines = []
                if rolle:
                    req_lines.append(f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{rolle.name}` um teilzunehmen.")
                if level:
                    req_lines.append(f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.")

                req_text = "\n".join(req_lines) if req_lines else ""
                if req_text:
                    req_text = f"\n{req_text}"

                embed = discord.Embed(
                    title=" ",
                    description=(
                        f"🏆 Preis: {preis}\n"
                        "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                        "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                        f"<:Astra_arrow:1141303823600717885> Erstellt von {interaction.user.mention}\n"
                        f"<:Astra_arrow:1141303823600717885> **{gewinner}** Gewinner\n"
                        f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(t2, 'R')}\n"
                        f"<:Astra_arrow:1141303823600717885> **0** Teilnehmer\n\n"
                        "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                        "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen."
                        f"{req_text}"
                    ),
                    colour=discord.Colour.blue()
                )
                if interaction.guild and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                    embed.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)
                else:
                    embed.set_footer(text="Viel Erfolg 🍀")
                msg = await kanal.send("🎉 **Neues Gewinnspiel** 🎉", embed=embed, view=GiveawayButton(self.bot))

                # Task zum Beenden planen (aus Teil 2)
                asyncio.create_task(gwtimes(t2, msg.id))

                # Einträge für Rolle und Level
                role_id = rolle.id if rolle else "Not Set"
                level_val = level if level else "Not Set"

                await cur.execute(
                    "INSERT INTO giveaway_active(guildID, creatorID, channelID, entrys, messageID, prize, winners, time, role, level, ended) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (interaction.guild.id, interaction.user.id, kanal.id, 0, msg.id, preis, gewinner, t1, role_id, level_val, 0)
                )

                # gwID Management
                await cur.execute("SELECT gwID FROM giveway_ids WHERE guildID = %s", (interaction.guild.id,))
                gwid_result = await cur.fetchall()
                new_gw_id = (len(gwid_result) + 1) if gwid_result else 1
                await cur.execute(
                    "INSERT INTO giveway_ids(guildID, gwID, messageID) VALUES (%s, %s, %s)",
                    (interaction.guild.id, new_gw_id, msg.id)
                )

                await interaction.response.send_message(
                    f"**<:Astra_accept:1141303821176422460> Das Gewinnspiel wird in {kanal.mention} stattfinden.**"
                )

    @app_commands.command(name="verwalten", description="Verwalte ein Gewinnspiel.")
    @app_commands.describe(aktion="Aktion, die durchgeführt werden soll.")
    @app_commands.describe(messageid="Nachrichten-ID des Gewinnspiels (falls benötigt).")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gw_verwalten(
        self,
        interaction: discord.Interaction,
        *,
        aktion: Literal[
            'Gewinnspiel beenden(Nachrichten ID angeben)',
            'Gewinnspiel neu würfeln(Nachrichten ID angeben)',
            'Gewinnspiele Anzeigen'
        ],
        messageid: str = None
    ):
        """Verwalte ein Gewinnspiel."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:

                if aktion == "Gewinnspiele Anzeigen":
                    await cur.execute(
                        "SELECT gwID, messageID FROM giveway_ids WHERE guildID = %s",
                        (interaction.guild.id,)
                    )
                    result = await cur.fetchall()
                    if not result:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Es gibt keine aktiven Gewinnspiele auf diesem Server.**",
                            ephemeral=True
                        )
                        return

                    embed = discord.Embed(
                        title=f"Alle Gewinnspiele auf {interaction.guild.name}",
                        description="Um ein Gewinnspiel zu erstellen, nutze `/gewinnspiel starten`.",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    if interaction.user.avatar:
                        embed.set_author(name=str(interaction.user), icon_url=interaction.user.avatar.url)
                    else:
                        embed.set_author(name=str(interaction.user))

                    for gwid, mid in result:
                        await cur.execute(
                            "SELECT time FROM giveaway_active WHERE guildID = %s AND messageID = %s",
                            (interaction.guild.id, mid)
                        )
                        time_result = await cur.fetchone()
                        if time_result:
                            unix_time = int(time_result[0])
                            embed.add_field(
                                name=f"ID: {gwid}",
                                value=f"<:Astra_time:1141303932061233202> Das Gewinnspiel endet: <t:{unix_time}:F>",
                                inline=False
                            )

                    await interaction.response.send_message(embed=embed)
                    return

                if not messageid:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Bitte gib eine Nachrichten-ID an!**",
                        ephemeral=True
                    )
                    return

                if aktion == "Gewinnspiel beenden(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT guildID, channelID, userID FROM giveaway_entrys WHERE messageID = %s",
                        (messageid,)
                    )
                    entrys_result = await cur.fetchall()
                    await cur.execute(
                        "SELECT prize, winners, entrys, time, guildID, channelID, ended FROM giveaway_active WHERE messageID = %s",
                        (messageid,)
                    )
                    gw = await cur.fetchone()
                    if not gw:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Kein aktives Gewinnspiel mit dieser Nachricht gefunden.**",
                            ephemeral=True
                        )
                        return

                    preis, winners, entrys, end_time, guildID, channelID, ended = gw

                    guild = self.bot.get_guild(guildID)
                    if guild is None:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Guild nicht gefunden.**",
                            ephemeral=True
                        )
                        return

                    channel = guild.get_channel(channelID)
                    if channel is None:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Channel nicht gefunden.**",
                            ephemeral=True
                        )
                        return

                    try:
                        msg = await channel.fetch_message(int(messageid))
                    except Exception:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Nachricht nicht gefunden.**",
                            ephemeral=True
                        )
                        return

                    time2 = datetime.fromtimestamp(int(end_time), tz=timezone.utc)

                    if ended:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Gewinnspiel ist bereits beendet!**",
                            ephemeral=True
                        )
                        return

                    if not entrys_result:
                        # Niemand hat teilgenommen
                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {preis}\n"
                                "`🤖` [Invite Astra here](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                                "<:Astra_arrow:1141303823600717885> Niemand hat das Gewinnspiel gewonnen.\n"
                                f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                                "<:Astra_arrow:1141303823600717885> Es gab **0** Teilnehmer."
                            ),
                            colour=discord.Colour.red()
                        )
                        await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                        await msg.reply(
                            "<:Astra_x:1141303954555289600> **Es gab nicht genügend Teilnehmer. Niemand hat das Gewinnspiel gewonnen.**"
                        )
                    else:
                        # Gewinner ziehen
                        teilnehmer = [row[2] for row in entrys_result]
                        winners_count = min(len(teilnehmer), int(winners))
                        gewinner_ids = random.sample(teilnehmer, k=winners_count)
                        users = [self.bot.get_user(uid) for uid in gewinner_ids]
                        mentions = ", ".join(user.mention for user in users if user)

                        # Gewinnenachricht an die User schicken
                        for user in users:
                            if user:
                                winembed = discord.Embed(
                                    title=" ",
                                    description=(
                                        f"🏆 Preis: {preis}\n"
                                        "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                        f"`🎉` Du hast ein Gewinnspiel auf [{guild.name}](https://discord.com/channels/{guild.id}/{channel.id}/{msg.id}) gewonnen.\n"
                                        f"`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}"
                                    ),
                                    colour=discord.Colour.yellow()
                                )
                                if guild.icon:
                                    winembed.set_thumbnail(url=guild.icon.url)
                                try:
                                    await user.send(
                                        "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                        embed=winembed
                                    )
                                except Exception:
                                    pass  # User hat DMs geschlossen

                        embed = discord.Embed(
                            title=" ",
                            description=(
                                f"🏆 Preis: {preis}\n"
                                "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                "<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                                f"<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n"
                                f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                                f"<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer."
                            ),
                            colour=discord.Colour.red()
                        )
                        await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                        await msg.reply(
                            f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen. Herzlichen Glückwunsch."
                        )

                    # Giveaway als beendet markieren und ID entfernen
                    await cur.execute(
                        "UPDATE giveaway_active SET ended = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                        (1, guildID, channelID, messageid)
                    )
                    await cur.execute("DELETE FROM giveway_ids WHERE messageID = %s", (messageid,))
                    await interaction.response.send_message(
                        "<:Astra_accept:1141303821176422460> **Das Gewinnspiel wurde erfolgreich beendet.**",
                        ephemeral=True
                    )
                    return

                if aktion == "Gewinnspiel neu würfeln(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT channelID, prize, winners, entrys, time, ended FROM giveaway_active WHERE guildID = %s AND messageID = %s",
                        (interaction.guild.id, int(messageid))
                    )
                    gw = await cur.fetchone()
                    if not gw:
                        await interaction.response.send_message(
                            f"<:Astra_x:1141303954555289600> Es gibt kein Gewinnspiel mit der ID {messageid}!",
                            ephemeral=True
                        )
                        return

                    channelID, preis, winners, entrys, end_time, ended = gw
                    if not ended:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Gewinnspiel läuft noch!**",
                            ephemeral=True
                        )
                        return

                    channel = interaction.guild.get_channel(channelID)
                    msg = await channel.fetch_message(int(messageid))

                    await cur.execute(
                        "SELECT userID FROM giveaway_entrys WHERE messageID = %s AND guildID = %s AND channelID = %s",
                        (int(messageid), interaction.guild.id, channelID)
                    )
                    result2 = await cur.fetchall()

                    teilnehmer = [row[0] for row in result2]
                    winners_count = min(len(teilnehmer), int(winners))
                    if winners_count < 1:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Gewinnspiel konnte nicht neu ausgelost werden, da es nicht genügend Teilnehmer gab.**",
                            ephemeral=True
                        )
                        return

                    gewinner_ids = random.sample(teilnehmer, k=winners_count)
                    users = [self.bot.get_user(uid) for uid in gewinner_ids]
                    mentions = ", ".join(user.mention for user in users if user)

                    time2 = datetime.fromtimestamp(int(end_time), tz=timezone.utc)
                    # Gewinne-Embed verschicken
                    for user in users:
                        if user:
                            winembed = discord.Embed(
                                title=" ",
                                description=(
                                    f"🏆 Preis: {preis}\n"
                                    "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                    f"`🎉` Du hast ein Gewinnspiel auf [{interaction.guild.name}](https://discord.com/channels/{interaction.guild.id}/{channel.id}/{msg.id}) gewonnen.\n"
                                    f"`⏰` Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}"
                                ),
                                colour=discord.Colour.yellow()
                            )
                            if interaction.guild.icon:
                                winembed.set_thumbnail(url=interaction.guild.icon.url)
                            try:
                                await user.send(
                                    "<:Astra_herz:1141303857855594527> **Du hast ein Gewinnspiel gewonnen! Herzlichen Glückwunsch.**",
                                    embed=winembed
                                )
                            except Exception:
                                pass

                    embed = discord.Embed(
                        title=" ",
                        description=(
                            f"🏆 Preis: {preis}\n"
                            "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                            "<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                            f"<:Astra_arrow:1141303823600717885> {mentions} hat das Gewinnspiel gewonnen.\n"
                            f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                            f"<:Astra_arrow:1141303823600717885> Es gab **{entrys}** Teilnehmer."
                        ),
                        colour=discord.Colour.red()
                    )
                    await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                    await msg.reply(
                        f"<:Astra_gw1:1141303852889550928> {mentions} hat das Gewinnspiel gewonnen. Herzlichen Glückwunsch."
                    )

                    await interaction.response.send_message(
                        f"<:Astra_accept:1141303821176422460> **Ich habe das Gewinnspiel neu ausgelost, die neuen Gewinner sind {mentions}.**",
                        ephemeral=True
                    )

async def setup(bot: commands.Bot):  # ⬅️ richtig typisiert
    bot.add_view(GiveawayButton(bot))  # persistente View
    try:
        bot.tree.remove_command("gewinnspiel", type=discord.AppCommandType.chat_input)
    except Exception:
        pass
    bot.tree.add_command(Giveaway(bot))  # Slash-Gruppe registrieren
