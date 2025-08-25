import asyncio
import logging
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Literal
import time
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
    Persistente View für das Giveaway mit Teilnahme-/Abmelde-Button.
    Nutzt self.bot statt globalem bot.
    """
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Teilnehmen",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view_allg:join_gw",
        emoji="<:Astra_gw1:1141303852889550928>",
    )
    async def join_gw(self, interaction: discord.Interaction, button: discord.Button):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await interaction.response.defer(ephemeral=True)

                # Ist der User bereits eingetragen?
                await cur.execute(
                    "SELECT userID FROM giveaway_entrys WHERE userID = %s AND guildID = %s AND channelID = %s AND messageID = %s",
                    (interaction.user.id, interaction.guild.id, interaction.channel.id, interaction.message.id),
                )
                existing = await cur.fetchone()

                # Giveaway-Infos inkl. messages_required holen
                await cur.execute(
                    "SELECT role, level, entrys, messageID, prize, winners, time, creatorID, messages_required "
                    "FROM giveaway_active WHERE guildID = %s AND channelID = %s AND messageID = %s",
                    (interaction.guild.id, interaction.channel.id, interaction.message.id),
                )
                row = await cur.fetchone()
                if not row:
                    # Sollte nicht passieren – Giveaway-Datensatz fehlt
                    return

                # ---- Werte normalisieren ----------------------------------------------------
                def _to_int_or_none(v):
                    if v is None:
                        return None
                    if isinstance(v, int):
                        return v
                    if isinstance(v, (float,)):
                        return int(v)
                    if isinstance(v, str):
                        s = v.strip()
                        if not s or s.lower() in {"not set", "none", "null", "nil"}:
                            return None
                        if s.isdigit():
                            return int(s)
                        try:
                            return int(float(s))
                        except Exception:
                            return None
                    try:
                        return int(v)
                    except Exception:
                        return None

                role_raw, level_raw, entrys, messageID, price, winners, time_unix, creatorID, msgs_req_raw = row

                roleID = _to_int_or_none(role_raw)
                level_req = _to_int_or_none(level_raw)
                messages_required = _to_int_or_none(msgs_req_raw)

                creator = self.bot.get_user(creatorID) or interaction.guild.get_member(creatorID)
                t_end = datetime.fromtimestamp(int(time_unix), tz=timezone.utc)

                # Hilfswerte / Anforderungen bestimmen
                guild = interaction.guild
                has_role_req = roleID is not None
                has_level_req = level_req is not None
                has_msg_req = (messages_required is not None) and (messages_required > 0)

                role_obj = guild.get_role(roleID) if has_role_req else None

                # Requirement-Textzeilen (für Anzeige im Embed)
                req_lines = []
                if has_role_req and role_obj:
                    req_lines.append(f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role_obj.name}` um teilzunehmen.")
                elif has_role_req and not role_obj:
                    req_lines.append("<:Astra_punkt:1141303896745201696> Die benötigte **Rolle** existiert nicht mehr.")
                if has_level_req:
                    req_lines.append(f"<:Astra_punkt:1141303896745201696> Du musst **Level {level_req}** sein um teilzunehmen.")
                if has_msg_req:
                    req_lines.append(f"<:Astra_punkt:1141303896745201696> Du brauchst **mind. {messages_required} Nachrichten** auf diesem Server.")
                req_block = ("\n" + "\n".join(req_lines)) if req_lines else ""

                # Kleine Helper um Embeds einheitlich zu bauen
                def build_public_embed(current_count: int) -> discord.Embed:
                    e = discord.Embed(
                        title=" ",
                        description=(
                            f"🏆 Preis: {price}\n"
                            "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                            "<:Astra_info:1141303860556738620> » __**Informationen:**__\n"
                            f"<:Astra_arrow:1141303823600717885> Erstellt von {getattr(creator, 'mention', interaction.user.mention)}\n"
                            f"<:Astra_arrow:1141303823600717885> **{winners}** Gewinner\n"
                            f"<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(t_end, 'R')}\n"
                            f"<:Astra_arrow:1141303823600717885> **{current_count}** Teilnehmer\n\n"
                            "<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n"
                            "<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen."
                            f"{req_block}"
                        ),
                        colour=discord.Colour.blue(),
                    )
                    if guild and guild.icon:
                        e.set_thumbnail(url=guild.icon.url)
                        e.set_footer(text="Viel Erfolg 🍀", icon_url=guild.icon.url)
                    else:
                        e.set_footer(text="Viel Erfolg 🍀")
                    return e

                def build_success_dm() -> discord.Embed:
                    e = discord.Embed(
                        title=" ",
                        description=(
                            f"🏆 Preis: {price}\n"
                            "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                            f"`🎉` Deine Teilnahme auf [{guild.name}](https://discord.com/channels/{guild.id}/{interaction.channel.id}/{messageID}) war erfolgreich.\n"
                            f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(t_end, 'R')}."
                        ),
                        colour=discord.Colour.green(),
                    )
                    if guild and guild.icon:
                        e.set_thumbnail(url=guild.icon.url)
                    return e

                def build_failure_dm(reasons: list[str]) -> discord.Embed:
                    reasons_txt = "\n".join(reasons) if reasons else "Unbekannte Gründe."
                    e = discord.Embed(
                        title=" ",
                        description=(
                            f"🏆 Preis: {price}\n"
                            "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                            f"`🎉` Deine Teilnahme auf [{guild.name}](https://discord.com/channels/{guild.id}/{interaction.channel.id}/{messageID}) war **nicht** erfolgreich.\n"
                            f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(t_end, 'R')}.\n\n"
                            "`🧨` __**Gründe**__\n"
                            f"{reasons_txt}"
                        ),
                        colour=discord.Colour.red(),
                    )
                    if guild and guild.icon:
                        e.set_thumbnail(url=guild.icon.url)
                    return e

                # ====== USER WILL TEILNEHMEN ======
                if not existing:
                    # Anforderungen prüfen – alle Gründe sammeln
                    reasons = []

                    # Rolle
                    role_ok = True
                    if has_role_req:
                        if (role_obj is None) or (role_obj not in interaction.user.roles):
                            role_ok = False
                            if role_obj:
                                reasons.append(f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{role_obj.name}`.")
                            else:
                                reasons.append("<:Astra_punkt:1141303896745201696> Die benötigte **Rolle** existiert nicht mehr.")

                    # Level
                    level_ok = True
                    if has_level_req:
                        await cur.execute(
                            "SELECT user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                            (interaction.user.id, guild.id),
                        )
                        lvl_row = await cur.fetchone()
                        if not lvl_row:
                            level_ok = False
                            reasons.append("<:Astra_punkt:1141303896745201696> Keine Level-Daten gefunden. Schreibe erst eine Nachricht und versuche es erneut.")
                        else:
                            user_level = int(lvl_row[0])
                            if int(level_req) > user_level:
                                level_ok = False
                                reasons.append(f"<:Astra_punkt:1141303896745201696> Du musst **Level {level_req}** sein (du bist Level {user_level}).")

                    # Nachrichten-Anzahl
                    msgs_ok = True
                    user_msg_count = 0
                    if has_msg_req:
                        await cur.execute(
                            "SELECT count FROM user_message_counts WHERE guildID = %s AND userID = %s",
                            (guild.id, interaction.user.id),
                        )
                        msg_row = await cur.fetchone()
                        user_msg_count = int(msg_row[0]) if msg_row else 0
                        if user_msg_count < int(messages_required):
                            msgs_ok = False
                            reasons.append(f"<:Astra_punkt:1141303896745201696> Du brauchst **mind. {messages_required} Nachrichten** (du hast {user_msg_count}).")

                    if role_ok and level_ok and msgs_ok:
                        # Teilnahme eintragen
                        new_count = int(entrys) + 1
                        public_embed = build_public_embed(new_count)

                        msg_obj = await interaction.channel.fetch_message(messageID)
                        await msg_obj.edit(embed=public_embed)

                        await cur.execute(
                            "UPDATE giveaway_active SET entrys = %s WHERE guildID = %s AND channelID = %s AND messageID = %s",
                            (new_count, guild.id, interaction.channel.id, interaction.message.id),
                        )
                        await cur.execute(
                            "INSERT INTO giveaway_entrys(guildID, channelID, userID, messageID) VALUES (%s, %s, %s, %s)",
                            (guild.id, interaction.channel.id, interaction.user.id, interaction.message.id),
                        )

                        # DM Erfolg
                        try:
                            await interaction.user.send(
                                "**<:Astra_accept:1141303821176422460> Deine Teilnahme am Gewinnspiel war erfolgreich.**",
                                embed=build_success_dm(),
                            )
                        except Exception:
                            pass
                    else:
                        # DM mit allen Gründen
                        try:
                            await interaction.user.send(
                                "**<:Astra_x:1141303954555289600> Deine Teilnahme am Gewinnspiel war nicht erfolgreich.**",
                                embed=build_failure_dm(reasons),
                            )
                        except Exception:
                            pass
                    return  # Ende "Teilnahme"

                # ====== USER IST DRIN -> ABMELDEN ======
                new_count = max(int(entrys) - 1, 0)
                await cur.execute(
                    "DELETE FROM giveaway_entrys WHERE userID = %s AND guildID = %s AND messageID = %s",
                    (interaction.user.id, guild.id, interaction.message.id),
                )
                await cur.execute(
                    "UPDATE giveaway_active SET entrys = %s WHERE channelID = %s AND guildID = %s AND messageID = %s",
                    (new_count, interaction.channel.id, guild.id, interaction.message.id),
                )

                # Embed aktualisieren (neue Teilnehmerzahl)
                msg_obj = await interaction.channel.fetch_message(messageID)
                await msg_obj.edit(embed=build_public_embed(new_count))

                # DM Bestätigung Abmeldung
                leave_embed = discord.Embed(
                    title=" ",
                    description=(
                        f"🏆 Preis: {price}\n"
                        "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                        f"`🎉` Deine Teilnahme auf [{guild.name}](https://discord.com/channels/{guild.id}/{interaction.channel.id}/{messageID}) wurde zurückgezogen.\n"
                        f"`⏰` Das Gewinnspiel endet {discord.utils.format_dt(t_end, 'R')}.\n\n"
                        "`🧨` __**Grund**__\n"
                        "<:Astra_punkt:1141303896745201696> Du hast deine Teilnahme am Gewinnspiel zurückgezogen."
                    ),
                    colour=discord.Colour.red(),
                )
                if guild and guild.icon:
                    leave_embed.set_thumbnail(url=guild.icon.url)
                try:
                    await interaction.user.send(
                        "**<:Astra_accept:1141303821176422460> Du hast deine Teilnahme am Gewinnspiel erfolgreich zurückgezogen.**",
                        embed=leave_embed,
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
    @app_commands.describe(nachrichten="Optional: Mindestanzahl an Nachrichten (serverweit) für Teilnahme.")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gw_start(self, interaction: discord.Interaction, *, preis: str, kanal: discord.TextChannel, gewinner: int,
                       zeit: str, rolle: discord.Role = None, level: int = None, nachrichten: int | None = None):
        """Startet ein Gewinnspiel."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if rolle or level:
                    if level:
                        await cur.execute("SELECT enabled FROM levelsystem WHERE guild_id = %s",
                                          (interaction.guild.id,))
                        enabled = await cur.fetchone()
                        if not enabled or enabled[0] == 0:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> Das Levelsystem ist auf diesem Server deaktiviert.",
                                ephemeral=True)
                            return

                time1 = convert(zeit)
                t1 = math.floor(discord.utils.utcnow().timestamp() + time1)
                t2 = datetime.fromtimestamp(t1, tz=timezone.utc)
                messages_required = None

                if nachrichten is not None and isinstance(nachrichten, int) and nachrichten > 0:
                    messages_required = nachrichten

                req_lines = []

                if rolle:
                    req_lines.append(
                        f"<:Astra_punkt:1141303896745201696> Du benötigst die **Rolle** `{rolle.name}` um teilzunehmen.")

                if level:
                    req_lines.append(
                        f"<:Astra_punkt:1141303896745201696> Du musst **Level {level}** sein um teilzunehmen.")

                if messages_required:
                    req_lines.append(
                        f"<:Astra_punkt:1141303896745201696> Du brauchst **mind. {messages_required} Nachrichten** auf diesem Server.")

                req_text = "\n".join(req_lines) if req_lines else ""

                if req_text:
                    req_text = f"\n{req_text}"

                embed = discord.Embed(title=" ", description=(
                    f"🏆 Preis: {preis}\n`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n<:Astra_info:1141303860556738620> » __**Informationen:**__\n<:Astra_arrow:1141303823600717885> Erstellt von {interaction.user.mention}\n<:Astra_arrow:1141303823600717885> **{gewinner}** Gewinner\n<:Astra_arrow:1141303823600717885> Gewinnspiel endet {discord.utils.format_dt(t2, 'R')}\n<:Astra_arrow:1141303823600717885> **0** Teilnehmer\n\n<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n<:Astra_arrow:1141303823600717885> **Klicke** unten auf den **Button** um am Gewinnspiel teilzunehmen." f"{req_text}"),
                                      colour=discord.Colour.blue())

                if interaction.guild and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                    embed.set_footer(text="Viel Erfolg 🍀", icon_url=interaction.guild.icon.url)

                else:
                    embed.set_footer(text="Viel Erfolg 🍀")
                msg = await kanal.send("🎉 **Neues Gewinnspiel** 🎉", embed=embed, view=GiveawayButton(self.bot))

                asyncio.create_task(gwtimes(self.bot, t2, msg.id))
                role_id = rolle.id if rolle else "Not Set"
                level_val = level if level else "Not Set"

                await cur.execute(
                    "INSERT INTO giveaway_active (guildID, creatorID, channelID, entrys, messageID, prize, winners, time, role, level, messages_required, ended) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (interaction.guild.id, interaction.user.id, kanal.id, 0, msg.id, preis, gewinner, t1, role_id,
                     level_val, messages_required, 0))
                await cur.execute("SELECT gwID FROM giveway_ids WHERE guildID = %s", (interaction.guild.id,))

                gwid_result = await cur.fetchall()
                new_gw_id = (len(gwid_result) + 1) if gwid_result else 1

                await cur.execute("INSERT INTO giveway_ids (guildID, gwID, messageID) VALUES (%s, %s, %s)",
                                  (interaction.guild.id, new_gw_id, msg.id))
                await interaction.response.send_message(
                    f"**<:Astra_accept:1141303821176422460> Das Gewinnspiel wird in {kanal.mention} stattfinden.**")

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
        """Verwalte ein Gewinnspiel (unter Beachtung von Rolle/Level/Nachrichten)."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:

                # -------- Hilfsfunktionen ----------------------------------------------------
                async def reasons_for_member(member: discord.Member | None,
                                             guild: discord.Guild,
                                             user_id: int,
                                             role_id: str | int | None,
                                             level_req: str | int | None,
                                             msgs_req: int | None) -> list[str]:
                    """Gibt alle nicht erfüllten Bedingungen (als Liste von Text-Zeilen) zurück."""
                    reasons: list[str] = []

                    # Mitglied prüfen
                    if member is None:
                        reasons.append("<:Astra_punkt:1141303896745201696> Nutzer ist nicht mehr auf dem Server.")
                        return reasons

                    # Rolle
                    if str(role_id).isnumeric():
                        role_obj = guild.get_role(int(role_id))
                        if role_obj is None:
                            reasons.append("<:Astra_punkt:1141303896745201696> Die benötigte Rolle existiert nicht mehr.")
                        elif role_obj not in member.roles:
                            reasons.append(f"<:Astra_punkt:1141303896745201696> Benötigt **Rolle** `{role_obj.name}`.")

                    # Level
                    if str(level_req).isnumeric():
                        await cur.execute(
                            "SELECT user_level FROM levelsystem WHERE client_id = %s AND guild_id = %s",
                            (user_id, guild.id),
                        )
                        lvl_row = await cur.fetchone()
                        if not lvl_row:
                            reasons.append("<:Astra_punkt:1141303896745201696> Keine Level-Daten vorhanden.")
                        else:
                            have = int(lvl_row[0])
                            need = int(level_req)
                            if have < need:
                                reasons.append(f"<:Astra_punkt:1141303896745201696> Benötigt **Level {need}** (hat {have}).")

                    # Nachrichten
                    if msgs_req is not None and int(msgs_req) > 0:
                        await cur.execute(
                            "SELECT count FROM user_message_counts WHERE guildID = %s AND userID = %s",
                            (guild.id, user_id),
                        )
                        msg_row = await cur.fetchone()
                        have = int(msg_row[0]) if msg_row else 0
                        need = int(msgs_req)
                        if have < need:
                            reasons.append(f"<:Astra_punkt:1141303896745201696> Benötigt **{need} Nachrichten** (hat {have}).")

                    return reasons

                def build_requirements_block(guild: discord.Guild, role_id, level_req, msgs_req) -> str:
                    lines = []
                    if str(role_id).isnumeric():
                        role_obj = guild.get_role(int(role_id))
                        if role_obj:
                            lines.append(f"<:Astra_punkt:1141303896745201696> **Rolle:** `{role_obj.name}`")
                        else:
                            lines.append("<:Astra_punkt:1141303896745201696> **Rolle:** (existiert nicht mehr)")
                    if str(level_req).isnumeric():
                        lines.append(f"<:Astra_punkt:1141303896745201696> **Level:** {level_req}+")
                    if msgs_req is not None and int(msgs_req) > 0:
                        lines.append(f"<:Astra_punkt:1141303896745201696> **Nachrichten:** mind. {msgs_req}")
                    return "\n".join(lines)

                # -----------------------------------------------------------------------------

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

                # ----------------------- Gewinnspiel beenden ---------------------------------
                if aktion == "Gewinnspiel beenden(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT guildID, channelID, userID FROM giveaway_entrys WHERE messageID = %s",
                        (messageid,)
                    )
                    entrys_result = await cur.fetchall()
                    await cur.execute(
                        "SELECT prize, winners, entrys, time, guildID, channelID, ended, role, level, messages_required "
                        "FROM giveaway_active WHERE messageID = %s",
                        (messageid,)
                    )
                    gw = await cur.fetchone()
                    if not gw:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Kein aktives Gewinnspiel mit dieser Nachricht gefunden.**",
                            ephemeral=True
                        )
                        return

                    preis, winners, entrys, end_time, guildID, channelID, ended, role_id, level_req, msgs_req = gw

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

                    # Keine Einträge?
                    if not entrys_result:
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
                        # Teilnehmer anhand der Bedingungen filtern
                        raw_user_ids = [row[2] for row in entrys_result]
                        valid_ids: list[int] = []
                        for uid in raw_user_ids:
                            member = guild.get_member(uid)
                            reasons = await reasons_for_member(member, guild, uid, role_id, level_req, msgs_req)
                            if reasons:
                                # Optional: pro Person könnte man DM schicken – hier bewusst still
                                pass
                            else:
                                valid_ids.append(uid)

                        if not valid_ids:
                            req_block = build_requirements_block(guild, role_id, level_req, msgs_req)
                            embed = discord.Embed(
                                title=" ",
                                description=(
                                    f"🏆 Preis: {preis}\n"
                                    "`🤖` [Astra Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands)\n\n"
                                    "<:Astra_gw_open2:1061384624951021578> » __**Wer hat das Gewinnspiel gewonnen?**__\n"
                                    "<:Astra_arrow:1141303823600717885> Niemand hat gewonnen – **keiner** erfüllte die Anforderungen.\n"
                                    f"<:Astra_arrow:1141303823600717885> Das Gewinnspiel endete {discord.utils.format_dt(time2, 'R')}\n"
                                    f"<:Astra_settings:1141303908778639490> » __**Anforderungen:**__\n{req_block if req_block else 'Keine'}"
                                ),
                                colour=discord.Colour.red()
                            )
                            await msg.edit(content="`❌` Gewinnspiel Vorbei `❌`", embed=embed, view=None)
                            await msg.reply("**Es gab keine gültigen Teilnehmer.**")
                        else:
                            winners_count = min(len(valid_ids), int(winners))
                            gewinner_ids = random.sample(valid_ids, k=winners_count)
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

                # ----------------------- Gewinnspiel neu würfeln ------------------------------
                if aktion == "Gewinnspiel neu würfeln(Nachrichten ID angeben)":
                    await cur.execute(
                        "SELECT channelID, prize, winners, entrys, time, ended, role, level, messages_required "
                        "FROM giveaway_active WHERE guildID = %s AND messageID = %s",
                        (interaction.guild.id, int(messageid))
                    )
                    gw = await cur.fetchone()
                    if not gw:
                        await interaction.response.send_message(
                            f"<:Astra_x:1141303954555289600> Es gibt kein Gewinnspiel mit der ID {messageid}!",
                            ephemeral=True
                        )
                        return

                    channelID, preis, winners, entrys, end_time, ended, role_id, level_req, msgs_req = gw
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

                    raw_user_ids = [row[0] for row in result2]

                    # filtere nach Anforderungen
                    valid_ids: list[int] = []
                    for uid in raw_user_ids:
                        member = interaction.guild.get_member(uid)
                        reasons = await reasons_for_member(member, interaction.guild, uid, role_id, level_req, msgs_req)
                        if not reasons:
                            valid_ids.append(uid)

                    winners_count = min(len(valid_ids), int(winners))
                    if winners_count < 1:
                        req_block = build_requirements_block(interaction.guild, role_id, level_req, msgs_req)
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Gewinnspiel konnte nicht neu ausgelost werden, da es keine gültigen Teilnehmer gab.**\n"
                            f"__Anforderungen:__\n{req_block if req_block else 'Keine'}",
                            ephemeral=True
                        )
                        return

                    gewinner_ids = random.sample(valid_ids, k=winners_count)
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


class MessageCounterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> (has_active, expires_at_datetime)
        self._active_giveaway_cache: dict[int, tuple[bool, datetime]] = {}
        self._cache_ttl = timedelta(seconds=60)  # Cache-Lebenszeit

    async def _has_active_giveaway(self, cur, guild_id: int) -> bool:
        now = datetime.now(timezone.utc)
        cached = self._active_giveaway_cache.get(guild_id)
        if cached and cached[1] > now:
            return cached[0]

        # Prüfe auf mindestens ein aktives Giveaway (ended=0)
        await cur.execute(
            "SELECT 1 FROM giveaway_active WHERE guildID = %s AND ended = 0 LIMIT 1",
            (guild_id,)
        )
        row = await cur.fetchone()
        has_active = bool(row)
        self._active_giveaway_cache[guild_id] = (has_active, now + self._cache_ttl)
        return has_active

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        # Bots / DMs ignorieren
        if not msg.guild or msg.author.bot:
            return

        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # 1) Erst prüfen, ob in diesem Server ein aktives Giveaway existiert
                    if not await self._has_active_giveaway(cur, msg.guild.id):
                        return

                    # 2) Nur dann hochzählen
                    await cur.execute(
                        "INSERT INTO user_message_counts (guildID, userID, count) "
                        "VALUES (%s, %s, 1) "
                        "ON DUPLICATE KEY UPDATE count = count + 1",
                        (msg.guild.id, msg.author.id)
                    )
        except Exception:
            # leise scheitern – wir wollen den Chat nicht stören
            pass


async def setup(bot: commands.Bot):  # ⬅️ richtig typisiert
    bot.add_view(GiveawayButton(bot))  # persistente View
    await bot.add_cog(MessageCounterCog(bot))
    try:
        bot.tree.remove_command("gewinnspiel", type=discord.AppCommandType.chat_input)
    except Exception:
        pass
    bot.tree.add_command(Giveaway(bot))  # Slash-Gruppe registrieren
