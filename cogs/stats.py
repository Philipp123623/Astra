import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiomysql
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import io
from datetime import datetime, timedelta
from matplotlib.colors import LinearSegmentedColormap


# =========================================================
# VIEW
# =========================================================

class AnalyticsView(discord.ui.View):
    def __init__(self, cog, mode, target_id=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.mode = mode
        self.target_id = target_id

    @discord.ui.button(label="7 Tage", style=discord.ButtonStyle.secondary)
    async def seven(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.send_stats(interaction, self.mode, 7, self.target_id)

    @discord.ui.button(label="30 Tage", style=discord.ButtonStyle.secondary)
    async def thirty(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.send_stats(interaction, self.mode, 30, self.target_id)


# =========================================================
# COG
# =========================================================

class Analytics(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup.start()

    # =====================================================
    # CLEANUP (30 DAYS)
    # =====================================================

    @tasks.loop(hours=24)
    async def cleanup(self):
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
                    ON DUPLICATE KEY UPDATE count=count+1
                """, (message.guild.id, message.author.id,
                      message.channel.id, today))

                await cursor.execute("""
                    INSERT INTO analytics_daily_guild
                    (guild_id,date,messages)
                    VALUES (%s,%s,1)
                    ON DUPLICATE KEY UPDATE messages=messages+1
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
                        (guild_id,user_id,joined_at)
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

                    if row:
                        joined_at = row[0]
                        minutes = int((now - joined_at).total_seconds() / 60)

                        if minutes > 0:
                            today = now.date()

                            await cursor.execute("""
                                INSERT INTO analytics_voice
                                (guild_id,user_id,date,minutes)
                                VALUES (%s,%s,%s,%s)
                                ON DUPLICATE KEY UPDATE minutes=minutes+%s
                            """, (member.guild.id, member.id,
                                  today, minutes, minutes))

                            await cursor.execute("""
                                INSERT INTO analytics_daily_guild
                                (guild_id,date,voice_minutes)
                                VALUES (%s,%s,%s)
                                ON DUPLICATE KEY UPDATE voice_minutes=voice_minutes+%s
                            """, (member.guild.id, today,
                                  minutes, minutes))

                        await cursor.execute("""
                            DELETE FROM analytics_voice_sessions
                            WHERE guild_id=%s AND user_id=%s
                        """, (member.guild.id, member.id))

    # =====================================================
    # CHART ENGINE (STABLE & CLEAN)
    # =====================================================

    def create_chart(self, title, dates, msg_values, voice_values):

        msg_values = [float(v or 0) for v in msg_values]
        voice_values = [float(v or 0) for v in voice_values]

        plt.style.use("dark_background")
        fig, ax1 = plt.subplots(figsize=(12, 5))

        # background gradient
        gradient = np.linspace(0, 1, 256)
        gradient = np.vstack((gradient, gradient))
        cmap = LinearSegmentedColormap.from_list(
            "", ["#0f1419", "#0b1b24"]
        )

        max_y = max(max(msg_values + [1]),
                    max(voice_values + [1])) + 5

        ax1.imshow(
            gradient,
            aspect="auto",
            cmap=cmap,
            extent=[0, len(dates)-1, 0, max_y],
            alpha=1
        )

        x = np.arange(len(dates))
        x_smooth = np.linspace(x.min(), x.max(), 300)

        msg_smooth = np.interp(x_smooth, x, msg_values)
        voice_smooth = np.interp(x_smooth, x, voice_values)

        # Message line
        line1 = ax1.plot(
            x_smooth, msg_smooth,
            linewidth=3.5, color="#ff9f1c"
        )
        ax1.fill_between(
            x_smooth, msg_smooth,
            alpha=0.18, color="#ff9f1c"
        )

        for l in line1:
            l.set_path_effects([
                pe.Stroke(linewidth=8,
                          foreground="#ff9f1c",
                          alpha=0.35),
                pe.Normal()
            ])

        # Voice line
        line2 = ax1.plot(
            x_smooth, voice_smooth,
            linewidth=3.5, color="#00f5d4"
        )
        ax1.fill_between(
            x_smooth, voice_smooth,
            alpha=0.18, color="#00f5d4"
        )

        for l in line2:
            l.set_path_effects([
                pe.Stroke(linewidth=8,
                          foreground="#00f5d4",
                          alpha=0.35),
                pe.Normal()
            ])

        ax1.set_xticks(x)
        ax1.set_xticklabels(
            [d.strftime("%d.%m") for d in dates],
            rotation=35
        )

        ax1.grid(alpha=0.12)
        ax1.set_facecolor("#0f1419")
        fig.patch.set_facecolor("#0f1419")

        plt.title(title, fontsize=15,
                  weight="bold", pad=15)

        fig.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", dpi=320)
        buffer.seek(0)
        plt.close()

        return buffer

    # =====================================================
    # CORE FUNCTION
    # =====================================================

    async def send_stats(self, interaction,
                         mode, tage,
                         target_id=None):

        start_date = datetime.utcnow().date() - timedelta(days=tage - 1)
        prev_start = start_date - timedelta(days=tage)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:

                if mode == "server":

                    await cursor.execute("""
                        SELECT date,messages,voice_minutes
                        FROM analytics_daily_guild
                        WHERE guild_id=%s AND date >= %s
                    """, (interaction.guild.id, start_date))
                    rows = await cursor.fetchall()

                    await cursor.execute("""
                        SELECT user_id,SUM(count) as total
                        FROM analytics_messages
                        WHERE guild_id=%s AND date >= %s
                        GROUP BY user_id
                        ORDER BY total DESC
                        LIMIT 5
                    """, (interaction.guild.id, start_date))
                    top_users = await cursor.fetchall()

                    await cursor.execute("""
                        SELECT channel_id,SUM(count) as total
                        FROM analytics_messages
                        WHERE guild_id=%s AND date >= %s
                        GROUP BY channel_id
                        ORDER BY total DESC
                        LIMIT 5
                    """, (interaction.guild.id, start_date))
                    top_channels = await cursor.fetchall()

                else:

                    await cursor.execute("""
                        SELECT date,SUM(count) as messages
                        FROM analytics_messages
                        WHERE guild_id=%s AND user_id=%s
                        AND date >= %s
                        GROUP BY date
                    """, (interaction.guild.id,
                          target_id, start_date))
                    msg_rows = await cursor.fetchall()

                    await cursor.execute("""
                        SELECT date,SUM(minutes) as voice_minutes
                        FROM analytics_voice
                        WHERE guild_id=%s AND user_id=%s
                        AND date >= %s
                        GROUP BY date
                    """, (interaction.guild.id,
                          target_id, start_date))
                    voice_rows = await cursor.fetchall()

                    data = {}

                    for r in msg_rows:
                        data[r["date"]] = {
                            "messages": r["messages"] or 0,
                            "voice_minutes": 0
                        }

                    for r in voice_rows:
                        data.setdefault(r["date"], {
                            "messages": 0,
                            "voice_minutes": 0
                        })
                        data[r["date"]]["voice_minutes"] = r["voice_minutes"] or 0

                    rows = [
                        {"date": k, **v}
                        for k, v in data.items()
                    ]

                    top_users = []
                    top_channels = []

        data = {r["date"]: r for r in rows}
        dates = [start_date + timedelta(days=i)
                 for i in range(tage)]

        msg_values = [data.get(d, {}).get("messages", 0)
                      for d in dates]
        voice_values = [data.get(d, {}).get("voice_minutes", 0)
                        for d in dates]

        total_msgs = int(sum(msg_values))
        total_voice = int(sum(voice_values))

        avg_msgs = int(total_msgs / tage) if tage else 0
        avg_voice = int(total_voice / tage) if tage else 0

        # growth
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT SUM(messages) as m,
                           SUM(voice_minutes) as v
                    FROM analytics_daily_guild
                    WHERE guild_id=%s
                    AND date >= %s
                    AND date < %s
                """, (interaction.guild.id,
                      prev_start, start_date))
                prev = await cursor.fetchone()

        prev_msgs = int(prev["m"] or 0)
        prev_voice = int(prev["v"] or 0)

        def calc_growth(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) /
                          previous) * 100, 1)

        msg_growth = calc_growth(total_msgs,
                                 prev_msgs)
        voice_growth = calc_growth(total_voice,
                                   prev_voice)

        title = (
            f"{interaction.guild.name} • {tage} Tage Analytics"
            if mode == "server"
            else f"{interaction.guild.get_member(target_id).display_name} • {tage} Tage Performance"
        )

        chart = self.create_chart(
            title, dates,
            msg_values, voice_values
        )
        file = discord.File(chart,
                            filename="analytics.png")

        embed = discord.Embed(
            title="ASTRA ULTRA ANALYTICS",
            description=f"{tage} Tage Intelligence Report",
            color=0xff9f1c
        )

        embed.add_field(
            name="Nachrichten",
            value=(
                f"Gesamt: `{total_msgs:,}`\n"
                f"Ø/Tag: `{avg_msgs}`\n"
                f"Trend: `{msg_growth:+}%`"
            ),
            inline=True
        )

        embed.add_field(
            name="Voice Minuten",
            value=(
                f"Gesamt: `{total_voice:,}`\n"
                f"Ø/Tag: `{avg_voice}`\n"
                f"Trend: `{voice_growth:+}%`"
            ),
            inline=True
        )

        if mode == "server":

            if top_users:
                text = ""
                for i, row in enumerate(top_users, 1):
                    member = interaction.guild.get_member(row["user_id"])
                    if member:
                        text += (
                            f"`{i}.` {member.mention} • "
                            f"`{row['total']}`\n"
                        )
                embed.add_field(
                    name="Top 5 User",
                    value=text,
                    inline=False
                )

            if top_channels:
                text = ""
                for i, row in enumerate(top_channels, 1):
                    channel = interaction.guild.get_channel(row["channel_id"])
                    if channel:
                        text += (
                            f"`{i}.` {channel.mention} • "
                            f"`{row['total']}`\n"
                        )
                embed.add_field(
                    name="Top 5 Channels",
                    value=text,
                    inline=False
                )

        embed.set_image(url="attachment://analytics.png")
        embed.set_footer(
            text="Astra Intelligence Engine"
        )

        view = AnalyticsView(
            self, mode, target_id
        )

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
        description="Ultra Analytics System"
    )

    @statistik.command(name="server")
    async def server(self,
                     interaction: discord.Interaction):
        await interaction.response.defer()
        await self.send_stats(
            interaction,
            "server",
            7
        )

    @statistik.command(name="user")
    async def user(self,
                   interaction: discord.Interaction,
                   member: discord.Member):
        await interaction.response.defer()
        await self.send_stats(
            interaction,
            "user",
            7,
            member.id
        )

    @statistik.command(name="reset")
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def reset(self,
                    interaction: discord.Interaction):

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM analytics_messages WHERE guild_id=%s",
                    (interaction.guild.id,)
                )
                await cursor.execute(
                    "DELETE FROM analytics_voice WHERE guild_id=%s",
                    (interaction.guild.id,)
                )
                await cursor.execute(
                    "DELETE FROM analytics_daily_guild WHERE guild_id=%s",
                    (interaction.guild.id,)
                )

        await interaction.response.send_message(
            "Analytics komplett zurückgesetzt.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Analytics(bot))
