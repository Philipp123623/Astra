import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional
import asyncio

GOAL_TYPES = {
    "messages":      ("Nachrichten", "💬"),
    "voice_minutes": ("Voice-Minuten", "🔊"),
    "xp":            ("XP", "✨"),
    "levelups":      ("Level-Ups", "⬆️"),
    "new_users":     ("Neue User", "👤"),
    "ban_free_days": ("Ban-freie Tage", "🕊️"),
    "commands_used": ("Befehle genutzt", "⚡"),
}

def progress_bar(current, target, length=18):
    percent = min(current / target, 1) if target else 0
    filled = int(length * percent)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"`{bar}`"

def format_goal_embed(conds, reward, ends, finished, total):
    embed = discord.Embed(
        title="🎯 Community Goal",
        description=f"Läuft noch bis **{ends.strftime('%d.%m.%Y, %H:%M')}**",
        color=discord.Color.blurple()
    )
    for typ, target, value in conds:
        name, icon = GOAL_TYPES.get(typ, (typ, "❔"))
        bar = progress_bar(value, target)
        percent = min(value / target * 100, 100) if target else 0
        embed.add_field(
            name=f"{icon} **{name}**",
            value=f"{bar}\n**{value:,} / {target:,}** (`{percent:.1f}%`)",
            inline=False
        )
    embed.add_field(
        name="🎁 Belohnung",
        value=reward or "*Keine Belohnung angegeben*",
        inline=False
    )
    embed.set_footer(text=f"{finished}/{total} Ziele erfüllt")
    return embed

class CommunityGoalsGroup(app_commands.Group):
    def __init__(self, cog):
        super().__init__(name="communitygoals", description="Communityziele!")
        self.cog = cog

    @app_commands.command(
        name="set",
        description="Setzt ein neues Communityziel mit frei wählbaren Bedingungen."
    )
    @app_commands.describe(
        ends_in_days="Wie viele Tage soll das Ziel laufen? (1–60)",
        reward="Belohnung (Text, Rolle, Emoji etc.)",
        nachrichten="Wie viele Nachrichten sollen insgesamt geschrieben werden?",
        voice_minuten="Wie viele Voice-Minuten sollen gesammelt werden?",
        xp="Wie viele XP sollen gesammelt werden?",
        levelups="Wie viele Level-Ups insgesamt?",
        neue_user="Wie viele neue User sollen dem Server joinen?",
        ban_free_days="Wie viele Tage ohne Ban/Warn?",
        befehle="Wie viele Slash-Befehle sollen genutzt werden?"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set(
        self,
        interaction: discord.Interaction,
        ends_in_days: app_commands.Range[int, 1, 60],
        reward: Optional[str] = None,
        nachrichten: Optional[app_commands.Range[int, 1, 1000000]] = None,
        voice_minuten: Optional[app_commands.Range[int, 1, 1000000]] = None,
        xp: Optional[app_commands.Range[int, 1, 10000000]] = None,
        levelups: Optional[app_commands.Range[int, 1, 10000]] = None,
        neue_user: Optional[app_commands.Range[int, 1, 10000]] = None,
        ban_free_days: Optional[app_commands.Range[int, 1, 60]] = None,
        befehle: Optional[app_commands.Range[int, 1, 100000]] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        conds = []
        mapping = [
            ("messages", nachrichten),
            ("voice_minutes", voice_minuten),
            ("xp", xp),
            ("levelups", levelups),
            ("new_users", neue_user),
            ("ban_free_days", ban_free_days),
            ("commands_used", befehle),
        ]
        for key, val in mapping:
            if val is not None and val > 0:
                conds.append((key, val))
        if not conds:
            embed = discord.Embed(
                title="🚫 Fehler",
                description="Mindestens eine Bedingung mit Wert > 0 angeben.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        now = datetime.utcnow()
        ends = now + timedelta(days=ends_in_days)
        async with self.cog.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE community_goals SET active=0 WHERE guild_id=%s", (interaction.guild.id,))
                await cur.execute(
                    "INSERT INTO community_goals (guild_id, started_at, ends_at, reward, active) VALUES (%s, %s, %s, %s, 1)",
                    (interaction.guild.id, now, ends, reward)
                )
                goal_id = cur.lastrowid if hasattr(cur, "lastrowid") else (await cur.execute("SELECT LAST_INSERT_ID()")).fetchone()[0]
                for typ, val in conds:
                    await cur.execute(
                        "INSERT INTO community_goal_conditions (goal_id, type, target, progress) VALUES (%s, %s, %s, %s)",
                        (goal_id, typ, val, 0)
                    )
                await conn.commit()
        self.cog.bot.loop.create_task(self.cog.goal_end_task(goal_id, interaction.guild.id, ends))
        cond_lines = "\n".join(
            f"{GOAL_TYPES[typ][1]} **{GOAL_TYPES[typ][0]}:** `{val:,}`"
            for typ, val in conds
        )
        embed = discord.Embed(
            title="🎯 Neues Community Goal erstellt!",
            description=f"Läuft **{ends_in_days}** Tage\n\n{cond_lines}",
            color=discord.Color.blurple()
        )
        if reward:
            embed.add_field(name="🎁 Belohnung", value=reward, inline=False)
        await interaction.followup.send(embed=embed)
        return None

    @app_commands.command(name="status", description="Zeigt das aktuelle Communityziel und den Fortschritt.")
    async def status(self, interaction: discord.Interaction):
        async with self.cog.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM community_goals WHERE guild_id=%s AND active=1 LIMIT 1", (interaction.guild.id,)
                )
                goal = await cur.fetchone()
                if not goal:
                    embed = discord.Embed(
                        title="🚫 Kein aktives Community Goal",
                        description="Momentan läuft kein Ziel. Erstelle eines mit `/communitygoals set`.",
                        color=discord.Color.red()
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
                goal_id = goal[0]
                reward = goal[4]
                ends = goal[3]
                await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                conds_db = await cur.fetchall()
                conds = []
                finished = 0
                for typ, target, progress in conds_db:
                    value = progress
                    if typ == "xp":
                        await cur.execute("SELECT SUM(user_xp) FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,))
                        sum_xp = await cur.fetchone()
                        value = sum_xp[0] if sum_xp and sum_xp[0] else 0
                    elif typ == "new_users":
                        value = interaction.guild.member_count
                    if value >= target:
                        finished += 1
                    conds.append((typ, target, value))
                embed = format_goal_embed(conds, reward, ends, finished, len(conds))
                await interaction.response.send_message(embed=embed)
                return None

class CommunityGoalsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_time = {}  # {guild_id: {user_id: join_timestamp}}
        self.goal_tasks_started = False
        bot.loop.create_task(self.schedule_goal_end_tasks())

    async def schedule_goal_end_tasks(self):
        await self.bot.wait_until_ready()
        if self.goal_tasks_started:
            return
        self.goal_tasks_started = True
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT id, guild_id, ends_at FROM community_goals WHERE active=1 AND ends_at > NOW()")
                entries = await cur.fetchall()
                for goal_id, guild_id, ends_at in entries:
                    ends_at_dt = ends_at if isinstance(ends_at, datetime) else datetime.strptime(str(ends_at), "%Y-%m-%d %H:%M:%S")
                    self.bot.loop.create_task(self.goal_end_task(goal_id, guild_id, ends_at_dt))

    async def goal_end_task(self, goal_id, guild_id, ends_at):
        now = datetime.utcnow()
        sleep_seconds = (ends_at - now).total_seconds()
        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT started_at, ends_at FROM community_goals WHERE id=%s", (goal_id,))
                started_at, ends_at = await cur.fetchone()
                await cur.execute("UPDATE community_goals SET active=0 WHERE id=%s", (goal_id,))
                await cur.execute("SELECT reward FROM community_goals WHERE id=%s", (goal_id,))
                reward = (await cur.fetchone() or [None])[0]
                await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                conds_db = await cur.fetchall()
                conds = []
                finished = 0
                for typ, target, progress in conds_db:
                    value = progress
                    if typ == "ban_free_days":
                        ban_occurred = await self.check_ban_in_period(guild_id, started_at, ends_at)
                        value = target if not ban_occurred else 0
                    if value >= target:
                        finished += 1
                    conds.append((typ, target, value))
        guild = self.bot.get_guild(int(guild_id))
        color = discord.Color.green() if finished == len(conds) and len(conds) > 0 else discord.Color.red()
        title = "🏁 Community Goal **GESCHAFFT!**" if finished == len(conds) and len(conds) > 0 else "⏹️ Community Goal beendet"
        desc = (f"Alle Ziele wurden erreicht! 🎉" if finished == len(conds) and len(conds) > 0
                else f"Nicht alle Ziele wurden erreicht! **{finished}/{len(conds)}**")
        embed = discord.Embed(
            title=title,
            description=desc,
            color=color
        )
        for typ, target, value in conds:
            name, icon = GOAL_TYPES.get(typ, (typ, "❔"))
            bar = progress_bar(value, target)
            percent = min(value / target * 100, 100) if target else 0
            embed.add_field(
                name=f"{icon} **{name}**",
                value=f"{bar}\n**{value:,} / {target:,}** (`{percent:.1f}%`)",
                inline=False
            )
        embed.add_field(
            name="🎁 Belohnung",
            value=reward or "*Keine Belohnung angegeben*",
            inline=False
        )
        if guild and guild.system_channel:
            await guild.system_channel.send(embed=embed)

    async def check_ban_in_period(self, guild_id, started_at, ends_at):
        # Gibt True zurück, wenn im Zeitraum ein Ban war, sonst False.
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM goal_bans WHERE guild_id=%s AND time BETWEEN %s AND %s LIMIT 1",
                    (guild_id, started_at, ends_at)
                )
                return bool(await cur.fetchone())

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        # Bans werden sofort in goal_bans gespeichert (restartfest!)
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO goal_bans (guild_id, user_id, mod_id, time) VALUES (%s, %s, %s, %s)",
                    (guild.id, user.id, None, datetime.utcnow())
                )
                await conn.commit()

    # Fortschrittstracking Listener
    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT g.id FROM community_goals g
                    JOIN community_goal_conditions c ON g.id = c.goal_id
                    WHERE g.guild_id=%s AND g.active=1 AND c.type='messages' LIMIT 1
                """, (message.guild.id,))
                goal = await cur.fetchone()
                if goal:
                    await cur.execute("""
                        UPDATE community_goal_conditions SET progress = progress + 1
                        WHERE goal_id=%s AND type='messages'
                    """, (goal[0],))
                    await conn.commit()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.guild:
            return
        guild_id = member.guild.id
        user_id = member.id
        now = datetime.utcnow().timestamp()
        if after.channel and not before.channel:
            if guild_id not in self.voice_time:
                self.voice_time[guild_id] = {}
            self.voice_time[guild_id][user_id] = now
        elif before.channel and not after.channel:
            if guild_id in self.voice_time and user_id in self.voice_time[guild_id]:
                joined_at = self.voice_time[guild_id][user_id]
                minutes = int((now - joined_at) // 60)
                if minutes > 0:
                    async with self.bot.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute("""
                                SELECT g.id FROM community_goals g
                                JOIN community_goal_conditions c ON g.id = c.goal_id
                                WHERE g.guild_id=%s AND g.active=1 AND c.type='voice_minutes' LIMIT 1
                            """, (guild_id,))
                            goal = await cur.fetchone()
                            if goal:
                                await cur.execute("""
                                    UPDATE community_goal_conditions SET progress = progress + %s
                                    WHERE goal_id=%s AND type='voice_minutes'
                                """, (minutes, goal[0]))
                                await conn.commit()
                del self.voice_time[guild_id][user_id]

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        if not interaction.guild or interaction.user.bot:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT g.id FROM community_goals g
                    JOIN community_goal_conditions c ON g.id = c.goal_id
                    WHERE g.guild_id=%s AND g.active=1 AND c.type='commands_used' LIMIT 1
                """, (interaction.guild.id,))
                goal = await cur.fetchone()
                if goal:
                    await cur.execute("""
                        UPDATE community_goal_conditions SET progress = progress + 1
                        WHERE goal_id=%s AND type='commands_used'
                    """, (goal[0],))
                    await conn.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT g.id FROM community_goals g
                    JOIN community_goal_conditions c ON g.id = c.goal_id
                    WHERE g.guild_id=%s AND g.active=1 AND c.type='new_users' LIMIT 1
                """, (member.guild.id,))
                goal = await cur.fetchone()
                if goal:
                    await cur.execute("""
                        UPDATE community_goal_conditions SET progress = progress + 1
                        WHERE goal_id=%s AND type='new_users'
                    """, (goal[0],))
                    await conn.commit()

    async def count_levelup(self, guild_id):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT g.id FROM community_goals g
                    JOIN community_goal_conditions c ON g.id = c.goal_id
                    WHERE g.guild_id=%s AND g.active=1 AND c.type='levelups' LIMIT 1
                """, (guild_id,))
                goal = await cur.fetchone()
                if goal:
                    await cur.execute("""
                        UPDATE community_goal_conditions SET progress = progress + 1
                        WHERE goal_id=%s AND type='levelups'
                    """, (goal[0],))
                    await conn.commit()

async def setup(bot):
    cog = CommunityGoalsCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(CommunityGoalsGroup(cog))
