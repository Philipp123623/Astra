import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")

def _next_midnight(dt: Optional[datetime] = None) -> datetime:
    now = dt or datetime.now(TZ)
    tomorrow = (now + timedelta(days=1)).date()
    return datetime.combine(tomorrow, datetime.min.time(), tzinfo=TZ)

def _last_midnight(dt: Optional[datetime] = None) -> datetime:
    now = dt or datetime.now(TZ)
    today = now.date()
    return datetime.combine(today, datetime.min.time(), tzinfo=TZ)

def _calc_next_epoch(day: int, month: int, ref: Optional[datetime] = None) -> int:
    now = ref or datetime.now(TZ)
    y = now.year
    while True:
        try:
            cand = datetime(y, month, day, 9, 0, tzinfo=TZ)  # 09:00 lokale Zeit
            if cand <= now:
                y += 1
                continue
            return int(cand.timestamp())
        except ValueError:
            # 29.02 in Nicht-Schaltjahr, Jahr hochzählen
            y += 1

class Birthday(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = asyncio.create_task(self._midnight_loop())

    def cog_unload(self):
        self._task.cancel()

    # ---------------------- BACKGROUND TASK ----------------------
    async def _midnight_loop(self):
        await self.bot.wait_until_ready()
        # Resume für den aktuellen Tag direkt beim Start
        try:
            await self._run_for_window(_last_midnight(), _next_midnight())
        except Exception as e:
            print(f"[Birthday] initial run error: {e}")

        while not self.bot.is_closed():
            when = _next_midnight()
            try:
                await discord.utils.sleep_until(when)
                await self._run_for_window(when, when + timedelta(days=1))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Birthday] loop error: {e}")
                await asyncio.sleep(60)

    async def _run_for_window(self, start: datetime, end: datetime):
        start_ts, end_ts = int(start.timestamp()), int(end.timestamp())
        # 1) Geburtstage, die in diesem Fenster liegen
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT user_id, birth_str, day, month, year, next_epoch "
                    "FROM birthdays WHERE next_epoch >= %s AND next_epoch < %s",
                    (start_ts, end_ts)
                )
                rows = await cur.fetchall()

        if not rows:
            return

        # 2) pro Guild den Zielkanal laden (eine Query)
        guild_channels = {}
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT guild_id, channel_id FROM birthday_settings")
                for g_id, ch_id in await cur.fetchall():
                    guild_channels[int(g_id)] = int(ch_id)

        # 3) Glückwünsche in den Guild-Channels senden (DMs entfernt)
        for user_id, birth_str, d, m, y, next_epoch in rows:
            for guild in self.bot.guilds:
                ch_id = guild_channels.get(guild.id)
                if not ch_id:
                    continue
                channel = guild.get_channel(ch_id)
                if not isinstance(channel, discord.TextChannel):
                    continue
                member = guild.get_member(int(user_id))
                # Member evtl. nicht auf dem Server -> skip
                if not member:
                    continue
                embed = discord.Embed(
                    title="🎂 Geburtstag heute!",
                    description=f"Lasst uns {member.mention} gratulieren! 🎉",
                    colour=discord.Colour.green(),
                    timestamp=datetime.now(TZ)
                )
                embed.add_field(name="Geburtsdatum", value=birth_str, inline=True)
                embed.add_field(name="Feierzeit", value=f"<t:{next_epoch}:D>", inline=True)
                embed.set_footer(text="Alles Gute!")
                try:
                    await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
                except Exception:
                    pass

            # 4) next_epoch auf den nächsten Geburtstag hochsetzen
            new_epoch = _calc_next_epoch(d, m, ref=datetime.now(TZ))
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE birthdays SET next_epoch=%s WHERE user_id=%s",
                        (new_epoch, int(user_id))
                    )

    async def _try_fetch_user(self, uid: int) -> Optional[discord.User]:
        try:
            return await self.bot.fetch_user(uid)
        except Exception:
            return None

    # ---------------------- ONE COMMAND TO RULE THEM ALL ----------------------
    @app_commands.command(name="birthday", description="Einrichten/anzeigen/ändern/löschen + Server-Channel")
    @app_commands.describe(
        aktion="Wähle, was du tun möchtest",
        datum="TT.MM.JJJJ (z. B. 11.08.2005) – für Setzen/Ändern",
        channel="Zielkanal für Glückwünsche – nur für 'Channel Setzen'"
    )
    async def birthday(
        self,
        interaction: discord.Interaction,
        aktion: Literal["Setzen","Anzeigen","Ändern","Löschen","Channel Setzen","Channel Anzeigen"],
        datum: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        uid = interaction.user.id
        tz_now = datetime.now(TZ)

        # ------- Datenbankverbindung -------
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # ========== ANZEIGEN ==========
                if aktion == "Anzeigen":
                    await cur.execute("SELECT birth_str, day, month, year, next_epoch FROM birthdays WHERE user_id=%s", (uid,))
                    row = await cur.fetchone()
                    if not row:
                        embed = discord.Embed(
                            title="🎂 Kein Eintrag",
                            description="Du hast noch keinen Geburtstag gespeichert. Nutze `/birthday` mit **Setzen**.",
                            colour=discord.Colour.red()
                        )
                        embed.set_footer(text=f"Angefragt von {interaction.user}", icon_url=interaction.user.display_avatar.url)
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
                    birth_str, d, m, y, next_epoch = row
                    embed = discord.Embed(title="<:Astra_gw1:1141303852889550928>  Dein Geburtstag", colour=discord.Colour.blurple())
                    embed.add_field(name="<:Astra_calender:1141303828625489940> Gespeichert als", value=birth_str, inline=False)
                    embed.add_field(name="<:Astra_time:1141303932061233202> Nächster Geburtstag", value=f"<t:{next_epoch}:D> • <t:{next_epoch}:R>", inline=False)
                    embed.set_footer(text=f"Angefragt von {interaction.user}", icon_url=interaction.user.display_avatar.url)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # ========== CHANNEL ANZEIGEN ==========
                if aktion == "Channel Anzeigen":
                    guild = interaction.guild
                    if not guild:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> Nur in Servern verfügbar.", ephemeral=True)
                        return
                    await cur.execute("SELECT channel_id FROM birthday_settings WHERE guild_id=%s", (guild.id,))
                    row = await cur.fetchone()
                    if not row:
                        await interaction.response.send_message("<:Astra_wichtig:1141303951862534224> Kein Geburtstagskanal gesetzt. Nutze `/birthday` mit **Channel Setzen**.", ephemeral=True)
                        return
                    ch_id = int(row[0])
                    ch = guild.get_channel(ch_id)
                    await interaction.response.send_message(f"<:Astra_news:1141303885533827072> Aktueller Geburtstagskanal: {ch.mention if ch else f'<#{ch_id}>'}", ephemeral=True)
                    return

                # ========== CHANNEL SETZEN ==========
                if aktion == "Channel Setzen":
                    guild = interaction.guild
                    if not guild:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> Nur in Servern verfügbar.", ephemeral=True)
                        return
                    if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.manage_channels):
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> Dir fehlen Rechte: `Server verwalten` oder `Kanäle verwalten`.", ephemeral=True)
                        return
                    if not channel:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte einen Textkanal angeben.", ephemeral=True)
                        return
                    await cur.execute(
                        "INSERT INTO birthday_settings (guild_id, channel_id) VALUES (%s,%s) "
                        "ON DUPLICATE KEY UPDATE channel_id=VALUES(channel_id)",
                        (guild.id, channel.id)
                    )
                    await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> Geburtstagskanal gesetzt auf {channel.mention}", ephemeral=True)
                    return

                # ========== LÖSCHEN ==========
                if aktion == "Löschen":
                    await cur.execute("DELETE FROM birthdays WHERE user_id=%s", (uid,))
                    await interaction.response.send_message("<:Astra_accept:1141303821176422460> Dein Geburtstagseintrag wurde gelöscht.", ephemeral=True)
                    return

                # Ab hier: Setzen/Ändern → Datum nötig
                if aktion in ("Setzen","Ändern"):
                    if not datum:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte ein Datum angeben: **TT.MM.JJJJ** (z. B. `11.08.2005`).", ephemeral=True)
                        return
                    # Parse
                    try:
                        born = datetime.strptime(datum.strip(), "%d.%m.%Y")
                    except ValueError:
                        await interaction.response.send_message("<:Astra_x:1141303954555289600> Falsches Format. Bitte **TT.MM.JJJJ** nutzen (z. B. `11.08.2005`).", ephemeral=True)
                        return
                    d, m, y = born.day, born.month, born.year
                    next_epoch = _calc_next_epoch(d, m, tz_now)

                    if aktion == "Setzen":
                        # Nur eintragen, wenn noch nicht vorhanden
                        await cur.execute("SELECT 1 FROM birthdays WHERE user_id=%s", (uid,))
                        if await cur.fetchone():
                            await interaction.response.send_message("<:Astra_wichtig:1141303951862534224> Du hast schon einen Geburtstag gespeichert. Nutze **Ändern**.", ephemeral=True)
                            return
                        # Hinweis: dm_enabled wird nicht mehr genutzt; falls Spalte existiert, auf 0 setzen
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
                        return

                    if aktion == "Ändern":
                        await cur.execute("SELECT 1 FROM birthdays WHERE user_id=%s", (uid,))
                        if not await cur.fetchone():
                            await interaction.response.send_message("<:Astra_x:1141303954555289600> Kein Eintrag vorhanden. Nutze **Setzen**.", ephemeral=True)
                            return
                        await cur.execute(
                            "UPDATE birthdays SET birth_str=%s, day=%s, month=%s, year=%s, next_epoch=%s WHERE user_id=%s",
                            (datum.strip(), d, m, y, next_epoch, uid)
                        )
                        embed = discord.Embed(title="Geburtstag aktualisiert", colour=discord.Colour.green())
                        embed.add_field(name="<:Astra_calender:1141303828625489940>  Neues Geburtsdatum", value=datum.strip(), inline=False)
                        embed.add_field(name="<:Astra_time:1141303932061233202>Nächster Geburtstag", value=f"<t:{next_epoch}:D> • <t:{next_epoch}:R>", inline=False)
                        embed.set_footer(text=f"Aktualisiert von {interaction.user}", icon_url=interaction.user.display_avatar.url)
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return

async def setup(bot: commands.Bot):
    await bot.add_cog(Birthday(bot))
