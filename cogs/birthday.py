# geburtstag_system.py
import asyncio
from typing import Optional, Tuple

import discord
from discord.ext import commands
from discord import app_commands

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
STD_MSG = "Lasst uns {mention} zum Geburtstag gratulieren! 🎉"

# ========== Utils ==========

def _parse_hhmm(s: str) -> Optional[Tuple[int, int]]:
    try:
        s = s.strip()
        if len(s) != 5 or s[2] != ":":
            return None
        hh = int(s[:2])
        mm = int(s[3:])
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm
        return None
    except Exception:
        return None

def _calc_next_epoch(day: int, month: int, ref: Optional[datetime], hour: int, minute: int) -> int:
    now = ref or datetime.now(TZ)
    hour = max(0, min(23, int(hour)))
    minute = max(0, min(59, int(minute)))
    y = now.year
    while True:
        try:
            cand = datetime(y, month, day, hour, minute, tzinfo=TZ)
            if cand <= now:
                y += 1
                continue
            return int(cand.timestamp())
        except ValueError:
            # 29.02 etc.
            y += 1

# ========== Cog: Ticker/Versand ==========

class Birthday(commands.Cog):
    """
    Prüft minütlich auf fällige Geburtstage (next_epoch) und postet in den
    pro Guild konfigurierten Channel mit Vorlage & Uhrzeit.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = asyncio.create_task(self._ticker())

    def cog_unload(self):
        self._task.cancel()

    async def _ticker(self):
        await self.bot.wait_until_ready()
        last_ts = int(datetime.now(TZ).timestamp())
        while not self.bot.is_closed():
            try:
                await asyncio.sleep(60)
                now_ts = int(datetime.now(TZ).timestamp()) + 1
                # fällige Geburtstage
                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "SELECT user_id, birth_str, day, month, year, next_epoch "
                            "FROM birthdays WHERE next_epoch >= %s AND next_epoch < %s",
                            (last_ts, now_ts)
                        )
                        rows = await cur.fetchall()

                if rows:
                    # guild settings
                    settings = {}
                    async with self.bot.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "SELECT guild_id, COALESCE(channel_id,0), "
                                "COALESCE(message_template,''), COALESCE(send_hour,9), COALESCE(send_minute,0) "
                                "FROM birthday_settings"
                            )
                            for g_id, ch_id, tpl, hr, mn in await cur.fetchall():
                                settings[int(g_id)] = (int(ch_id), tpl or "", int(hr), int(mn))

                    for user_id, birth_str, d, m, y, next_epoch in rows:
                        for guild in list(self.bot.guilds):
                            ch_id, tpl, _hr, _mn = settings.get(guild.id, (0, "", 9, 0))
                            if not ch_id:
                                continue
                            ch = guild.get_channel(ch_id)
                            if not isinstance(ch, discord.TextChannel):
                                continue
                            member = guild.get_member(int(user_id))
                            if not member:
                                continue

                            msg = (tpl.strip() or STD_MSG)\
                                .replace("{mention}", member.mention)\
                                .replace("{user_id}", str(member.id))\
                                .replace("{tag}", str(member))\
                                .replace("{name}", member.display_name)

                            embed = discord.Embed(
                                title="🎂 Geburtstag heute!",
                                description=msg,
                                colour=discord.Colour.green(),
                                timestamp=datetime.now(TZ),
                            )
                            embed.add_field(name="Geburtsdatum", value=birth_str, inline=True)
                            embed.add_field(name="Feierzeit", value=f"<t:{next_epoch}:D>", inline=True)
                            embed.set_footer(text="Alles Gute!")

                            try:
                                await ch.send(
                                    embed=embed,
                                    allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False)
                                )
                            except Exception:
                                pass

                        # next_epoch neu setzen (erste Guild, in der der User ist, bestimmt Zeit)
                        send_hour, send_minute = 9, 0
                        for guild in list(self.bot.guilds):
                            if guild.get_member(int(user_id)) and guild.id in settings:
                                _, _, send_hour, send_minute = settings[guild.id]
                                break
                        new_epoch = _calc_next_epoch(d, m, datetime.now(TZ), send_hour, send_minute)
                        async with self.bot.pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(
                                    "UPDATE birthdays SET next_epoch=%s WHERE user_id=%s",
                                    (new_epoch, int(user_id))
                                )

                last_ts = now_ts
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Birthday] ticker error: {e}")

# ========== Slash-Commands Gruppe außerhalb des Cogs ==========

@app_commands.guild_only()
class Geburtstag(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="geburtstag", description="Geburtstag einrichten/anzeigen & Server-Setup")
        self.bot = bot

    # -------- User: setzen/anzeigen/löschen --------

    @app_commands.command(name="setzen", description="Dein Geburtsdatum speichern (TT.MM.JJJJ)")
    @app_commands.describe(datum="Format: TT.MM.JJJJ (z. B. 11.08.2005)")
    async def setzen(self, interaction: discord.Interaction, datum: str):
        uid = interaction.user.id
        try:
            born = datetime.strptime(datum.strip(), "%d.%m.%Y")
        except ValueError:
            await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> Falsches Format. Bitte **TT.MM.JJJJ** (z. B. `11.08.2005`).",
                ephemeral=True
            )
            return

        d, m, y = born.day, born.month, born.year
        # Uhrzeit der Guild oder 09:00
        send_hour, send_minute = 9, 0
        if interaction.guild:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT COALESCE(send_hour,9), COALESCE(send_minute,0) FROM birthday_settings WHERE guild_id=%s",
                        (interaction.guild.id,)
                    )
                    row = await cur.fetchone()
                    if row:
                        send_hour, send_minute = int(row[0]), int(row[1])

        next_epoch = _calc_next_epoch(d, m, datetime.now(TZ), send_hour, send_minute)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM birthdays WHERE user_id=%s", (uid,))
                if await cur.fetchone():
                    await interaction.response.send_message(
                        "<:Astra_wichtig:1141303951862534224> Du hast bereits einen Eintrag. Nutze **/geburtstag löschen** und dann **/geburtstag setzen**.",
                        ephemeral=True
                    )
                    return
                await cur.execute(
                    "INSERT INTO birthdays (user_id, birth_str, day, month, year, next_epoch, dm_enabled) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (uid, datum.strip(), d, m, y, next_epoch, 0)
                )

        embed = discord.Embed(title="Geburtstag gespeichert", colour=discord.Colour.green())
        embed.add_field(name="<:Astra_calender:1141303828625489940> Geburtsdatum", value=datum.strip(), inline=False)
        embed.add_field(name="<:Astra_time:1141303932061233202> Nächster Geburtstag", value=f"<t:{next_epoch}:D> • <t:{next_epoch}:R>", inline=False)
        embed.set_footer(text=f"Gespeichert von {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="anzeigen", description="Zeigt deinen gespeicherten Geburtstag")
    async def anzeigen(self, interaction: discord.Interaction):
        uid = interaction.user.id
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT birth_str, next_epoch FROM birthdays WHERE user_id=%s", (uid,))
                row = await cur.fetchone()

        if not row:
            await interaction.response.send_message(
                "🎂 Du hast noch keinen Geburtstag gespeichert. Nutze **/geburtstag setzen**.",
                ephemeral=True
            )
            return

        birth_str, next_epoch = row
        embed = discord.Embed(title="<:Astra_gw1:1141303852889550928>  Dein Geburtstag", colour=discord.Colour.blurple())
        embed.add_field(name="<:Astra_calender:1141303828625489940> Gespeichert als", value=birth_str, inline=False)
        embed.add_field(name="<:Astra_time:1141303932061233202> Nächster Geburtstag", value=f"<t:{next_epoch}:D> • <t:{next_epoch}:R>", inline=False)
        embed.set_footer(text=f"Angefragt von {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="löschen", description="Löscht deinen Geburtstagseintrag")
    async def loeschen(self, interaction: discord.Interaction):
        uid = interaction.user.id
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM birthdays WHERE user_id=%s", (uid,))
        await interaction.response.send_message(
            "<:Astra_accept:1141303821176422460> Dein Geburtstagseintrag wurde gelöscht.",
            ephemeral=True
        )

    # -------- Admin-Setup: channel/uhrzeit/nachricht --------

    @app_commands.command(name="setup", description="Admin: Channel, Uhrzeit (HH:mm) & Nachrichtenvorlage setzen/anzeigen")
    @app_commands.describe(
        channel="Discord-Textkanal für Glückwünsche",
        uhrzeit="Uhrzeit im Format HH:mm (Serverzeit)",
        nachricht="Vorlage mit Platzhaltern {mention}, {user_id}, {tag}, {name}"
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        uhrzeit: Optional[str] = None,
        nachricht: Optional[str] = None
    ):
        if not interaction.guild:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Nur in Servern verfügbar.", ephemeral=True)
            return
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.manage_channels):
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Dir fehlen Rechte: `Server verwalten` oder `Kanäle verwalten`.", ephemeral=True)
            return

        gid = interaction.guild.id

        # Uhrzeit parsen (optional)
        parsed_time = None
        if uhrzeit is not None:
            parsed_time = _parse_hhmm(uhrzeit)
            if parsed_time is None:
                await interaction.response.send_message(
                    "<:Astra_x:1141303954555289600> Ungültige Uhrzeit. Bitte **HH:mm** (z. B. `09:00` oder `18:30`).",
                    ephemeral=True
                )
                return

        # Upsert + selektive Updates
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # sicherstellen, dass es einen Datensatz gibt
                await cur.execute(
                    "INSERT INTO birthday_settings (guild_id, channel_id, message_template, send_hour, send_minute) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE guild_id=guild_id",
                    (gid, channel.id if channel else None, nachricht or "", 9, 0)
                )
                if channel is not None:
                    await cur.execute("UPDATE birthday_settings SET channel_id=%s WHERE guild_id=%s", (channel.id, gid))
                if parsed_time is not None:
                    hh, mm = parsed_time
                    await cur.execute("UPDATE birthday_settings SET send_hour=%s, send_minute=%s WHERE guild_id=%s", (hh, mm, gid))
                if nachricht is not None:
                    await cur.execute("UPDATE birthday_settings SET message_template=%s WHERE guild_id=%s", (nachricht, gid))
                # aktuelle Werte holen
                await cur.execute(
                    "SELECT COALESCE(channel_id,0), COALESCE(message_template,''), COALESCE(send_hour,9), COALESCE(send_minute,0) "
                    "FROM birthday_settings WHERE guild_id=%s",
                    (gid,)
                )
                ch_id, tpl, hour, minute = await cur.fetchone()

        ch_mention = f"<#{ch_id}>" if ch_id else "—"
        tpl_eff = tpl or STD_MSG
        hhmm = f"{int(hour):02d}:{int(minute):02d}"
        embed = discord.Embed(title="🎛️ Geburtstag-Setup", colour=discord.Colour.blurple())
        embed.add_field(name="Channel", value=ch_mention, inline=True)
        embed.add_field(name="Uhrzeit", value=hhmm, inline=True)
        embed.add_field(name="Nachrichtenvorlage", value=f"`{tpl_eff}`", inline=False)
        embed.set_footer(text="Platzhalter: {mention}, {user_id}, {tag}, {name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== Bot-Hooks ==========

async def setup(bot: commands.Bot):
    await bot.add_cog(Birthday(bot))
    bot.tree.add_command(Geburtstag(bot))
