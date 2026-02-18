import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiomysql
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import io
from datetime import datetime, timedelta
from collections import defaultdict


# =========================================================
# VIEW
# =========================================================

class AnalyticsView(discord.ui.View):
    def __init__(self, cog, mode: str, target_id: int | None):
        super().__init__(timeout=180)
        self.cog = cog
        self.mode = mode
        self.target_id = target_id

    @discord.ui.button(label="7 Tage", style=discord.ButtonStyle.secondary)
    async def seven(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        await self.cog.send_stats(interaction, self.mode, 7, self.target_id)

    @discord.ui.button(label="30 Tage", style=discord.ButtonStyle.secondary)
    async def thirty(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        await self.cog.send_stats(interaction, self.mode, 30, self.target_id)


# =========================================================
# COG
# =========================================================

class Analytics(commands.Cog):
    """
    Astra Ultra Analytics Engine v2
    Clean • Structured • Stable
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_task.start()

    # =====================================================
    # DAILY CLEANUP (older than 30 days)
    # =====================================================

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM analytics_messages WHERE date < CURDATE() - INTERVAL 30 DAY"
                )
                await cursor.execute(
                    "DELETE FROM analytics_voice WHERE date < CURDATE() - INTERVAL 30 DAY"
                )
                await cursor.execute(
                    "DELETE FROM analytics_daily_guild WHERE date < CURDATE() - INTERVAL 30 DAY"
                )

    # =====================================================
    # MESSAGE TRACKING
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        today = datetime.utcnow().date()

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute("""
                    INSERT INTO analytics_messages
                    (guild_id, user_id, channel_id, date, count)
                    VALUES (%s,%s,%s,%s,1)
                    ON DUPLICATE KEY UPDATE count = count + 1
                """, (message.guild.id, message.author.id,
                      message.channel.id, today))

                await cursor.execute("""
                    INSERT INTO analytics_daily_guild
                    (guild_id, date, messages)
                    VALUES (%s,%s,1)
                    ON DUPLICATE KEY UPDATE messages = messages + 1
                """, (message.guild.id, today))

    # =====================================================
    # VOICE TRACKING
    # =====================================================

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        now = datetime.utcnow()

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:

                # JOIN
                if not before.channel and after.channel:
                    await cursor.execute("""
                        INSERT INTO analytics_voice_sessions
                        (guild_id, user_id, joined_at)
                        VALUES (%s,%s,%s)
                        ON DUPLICATE KEY UPDATE joined_at=%s
                    """, (member.guild.id, member.id, now, now))

                # LEAVE
                if before.channel and not after.channel:
                    await cursor.execute("""
                        SELECT joined_at FROM analytics_voice_sessions
                        WHERE guild_id=%s AND user_id=%s
                    """, (member.guild.id, member.id))

                    row = await cursor.fetchone()
                    if not row:
                        return

                    joined_at = row[0]
                    minutes = int((now - joined_at).total_seconds() / 60)

                    if minutes > 0:
                        today = now.date()

                        await cursor.execute("""
                            INSERT INTO analytics_voice
                            (guild_id,user_id,date,minutes)
                            VALUES (%s,%s,%s,%s)
                            ON DUPLICATE KEY UPDATE minutes = minutes + %s
                        """, (member.guild.id, member.id,
                              today, minutes, minutes))

                        await cursor.execute("""
                            INSERT INTO analytics_daily_guild
                            (guild_id,date,voice_minutes)
                            VALUES (%s,%s,%s)
                            ON DUPLICATE KEY UPDATE voice_minutes = voice_minutes + %s
                        """, (member.guild.id, today,
                              minutes, minutes))

                    await cursor.execute("""
                        DELETE FROM analytics_voice_sessions
                        WHERE guild_id=%s AND user_id=%s
                    """, (member.guild.id, member.id))

    # =====================================================
    # CHART ENGINE (clean & readable)
    # =====================================================

    def create_chart(self, title, dates, msg_values, voice_values):

        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(11, 4.5))

        x = mdates.date2num(dates)

        ax.plot_date(dates, msg_values, "-",
                     linewidth=3,
                     label="Nachrichten")

        ax.plot_date(dates, voice_values, "-",
                     linewidth=3,
                     label="Voice Minuten")

        ax.fill_between(dates, msg_values, alpha=0.15)
        ax.fill_between(dates, voice_values, alpha=0.15)

        ax.set_title(title, fontsize=14, weight="bold")
        ax.set_ylabel("Aktivität")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))

        ax.grid(alpha=0.2)
        ax.legend()

        fig.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", dpi=300)
        buffer.seek(0)
        plt.close()

        return buffer

    # =====================================================
    # DATA AGGREGATION
    # =====================================================

    async def fetch_server_data(self, guild_id, start_date):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                await cursor.execute("""
                    SELECT date, messages, voice_minutes
                    FROM analytics_daily_guild
                    WHERE guild_id=%s AND date >= %s
                """, (guild_id, start_date))

                return await cursor.fetchall()

    async def fetch_user_data(self, guild_id, user_id, start_date):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                await cursor.execute("""
                    SELECT date, SUM(count) as messages
                    FROM analytics_messages
                    WHERE guild_id=%s AND user_id=%s AND date >= %s
                    GROUP BY date
                """, (guild_id, user_id, start_date))
                msg_rows = await cursor.fetchall()

                await cursor.execute("""
                    SELECT date, SUM(minutes) as voice_minutes
                    FROM analytics_voice
                    WHERE guild_id=%s AND user_id=%s AND date >= %s
                    GROUP BY date
                """, (guild_id, user_id, start_date))
                voice_rows = await cursor.fetchall()

        data = defaultdict(lambda: {"messages": 0, "voice_minutes": 0})

        for r in msg_rows:
            data[r["date"]]["messages"] = r["messages"] or 0

        for r in voice_rows:
            data[r["date"]]["voice_minutes"] = r["voice_minutes"] or 0

        return [{"date": d, **v} for d, v in data.items()]

    # =====================================================
    # MAIN FUNCTION
    # =====================================================

    async def send_stats(self, interaction, mode, days, target_id=None):

        start_date = datetime.utcnow().date() - timedelta(days=days - 1)
        dates = [start_date + timedelta(days=i) for i in range(days)]

        if mode == "server":
            rows = await self.fetch_server_data(
                interaction.guild.id, start_date)
        else:
            rows = await self.fetch_user_data(
                interaction.guild.id, target_id, start_date)

        data = {r["date"]: r for r in rows}

        msg_values = [data.get(d, {}).get("messages", 0) for d in dates]
        voice_values = [data.get(d, {}).get("voice_minutes", 0) for d in dates]

        total_msgs = sum(msg_values)
        total_voice = sum(voice_values)

        avg_msgs = round(total_msgs / days, 1)
        avg_voice = round(total_voice / days, 1)

        title = (
            f"{interaction.guild.name} • {days} Tage Analytics"
            if mode == "server"
            else f"{interaction.guild.get_member(target_id).display_name} • {days} Tage Performance"
        )

        chart = self.create_chart(title, dates, msg_values, voice_values)
        file = discord.File(chart, filename="analytics.png")

        embed = discord.Embed(
            title="ASTRA ULTRA ANALYTICS",
            description=f"{days} Tage Intelligence Report",
            color=0xff9f1c
        )

        embed.add_field(
            name="Nachrichten",
            value=f"Gesamt: `{total_msgs}`\nØ/Tag: `{avg_msgs}`",
            inline=True
        )

        embed.add_field(
            name="Voice Minuten",
            value=f"Gesamt: `{total_voice}`\nØ/Tag: `{avg_voice}`",
            inline=True
        )

        embed.set_image(url="attachment://analytics.png")
        embed.set_footer(text="Astra Intelligence Engine v2")

        view = AnalyticsView(self, mode, target_id)

        await interaction.edit_original_response(
            embed=embed,
            attachments=[file],
            view=view
        )

    # =====================================================
    # COMMANDS
    # =====================================================

    statistik = app_commands.Group(
        name="statistik",
        description="Astra Analytics System"
    )

    @statistik.command(name="server")
    async def server(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.send_stats(interaction, "server", 7)

    @statistik.command(name="user")
    async def user(self, interaction: discord.Interaction, member: discord.Member=None):
        await interaction.response.defer()
        if member is None:
            member = interaction.user
        await self.send_stats(interaction, "user", 7, member.id)

    @statistik.command(name="reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction):

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM analytics_messages WHERE guild_id=%s",
                                     (interaction.guild.id,))
                await cursor.execute("DELETE FROM analytics_voice WHERE guild_id=%s",
                                     (interaction.guild.id,))
                await cursor.execute("DELETE FROM analytics_daily_guild WHERE guild_id=%s",
                                     (interaction.guild.id,))

        await interaction.response.send_message(
            "Analytics erfolgreich zurückgesetzt.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Analytics(bot))
