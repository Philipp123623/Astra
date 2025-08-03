import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio

COMMUNITY_GOAL_TYPES = {
    "messages": "Nachrichten",
    "voice_minutes": "Voice-Minuten",
    "xp": "XP",
    "levelups": "Level-Ups",
    "new_users": "Neue User",
    "ban_free_days": "Ban-freie Tage",
    "commands_used": "Befehle genutzt"
}

@app_commands.guild_only()
class Level(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="communitygoals",
            description="Alles rund um Communitygoals."
        )

    @app_commands.command(name="set", description="Setzt ein neues Communityziel mit mehreren Bedingungen.")
    @app_commands.describe(
        ends_in_days="Wie viele Tage soll das Ziel laufen?",
        reward="Textliche Belohnung (z.B. Rolle, Text, Emoji ...)",
        messages="Ziel: Anzahl Nachrichten",
        voice_minutes="Ziel: Voice-Minuten (gesamt)",
        xp="Ziel: XP gesamt (Levelsystem!)",
        levelups="Ziel: Anzahl Level-Ups (Levelsystem!)",
        new_users="Ziel: Neue User",
        ban_free_days="Ziel: Ban-freie Tage",
        commands_used="Ziel: Befehle genutzt"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def communitygoal_set(
            self,
            interaction: discord.Interaction,
            ends_in_days: int,
            reward: str = None,
            messages: int = None,
            voice_minutes: int = None,
            xp: int = None,
            levelups: int = None,
            new_users: int = None,
            ban_free_days: int = None,
            commands_used: int = None
    ):
        # Bedingungen prüfen
        conditions = []
        for typ, val in [
            ("messages", messages),
            ("voice_minutes", voice_minutes),
            ("xp", xp),
            ("levelups", levelups),
            ("new_users", new_users),
            ("ban_free_days", ban_free_days),
            ("commands_used", commands_used)
        ]:
            if val is not None and val > 0:
                conditions.append((typ, val))
        if not conditions:
            await interaction.response.send_message(
                "Mindestens eine Bedingung mit Wert > 0 angeben.", ephemeral=True
            )
            return

        now = datetime.utcnow()
        ends = now + timedelta(days=ends_in_days)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE community_goals SET active=0 WHERE guild_id=%s", (interaction.guild.id,))
                await cur.execute(
                    "INSERT INTO community_goals (guild_id, started_at, ends_at, reward, active) VALUES (%s, %s, %s, %s, 1)",
                    (interaction.guild.id, now, ends, reward)
                )
                goal_id = cur.lastrowid
                for typ, val in conditions:
                    await cur.execute(
                        "INSERT INTO community_goal_conditions (goal_id, type, target, progress) VALUES (%s, %s, %s, %s)",
                        (goal_id, typ, val, 0)
                    )
                await conn.commit()

        await interaction.response.send_message(
            f"🎯 Neues Community Goal erstellt:\n" +
            "\n".join(f"• {COMMUNITY_GOAL_TYPES[typ]}: {val}" for typ, val in conditions)
        )

    @app_commands.command(name="status", description="Zeigt das aktuelle Communityziel und den Fortschritt.")
    async def communitygoal_status(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM community_goals WHERE guild_id=%s AND active=1 LIMIT 1", (interaction.guild.id,)
                )
                goal = await cur.fetchone()
                if not goal:
                    await interaction.response.send_message("Kein aktives Community Goal.", ephemeral=True)
                    return
                goal_id = goal[0]
                reward = goal[4]
                ends = goal[3]
                await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s",
                                  (goal_id,))
                conds = await cur.fetchall()
                embed = discord.Embed(title="🎯 Community Goal", color=discord.Color.teal())
                finished = 0
                for typ, target, progress in conds:
                    # Progress je nach type:
                    percent = 0
                    value = 0
                    if typ == "messages":
                        value = progress
                    elif typ == "voice_minutes":
                        value = progress
                    elif typ == "commands_used":
                        value = progress
                    elif typ == "ban_free_days":
                        value = progress
                    elif typ == "levelups":
                        # Levelups = Anzahl User, die >=1 mal gelevelt haben?
                        await cur.execute(
                            "SELECT SUM(user_level) FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,)
                        )
                        sum_lvl = await cur.fetchone()
                        value = sum_lvl[0] if sum_lvl and sum_lvl[0] else 0
                    elif typ == "xp":
                        await cur.execute(
                            "SELECT SUM(user_xp) FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,)
                        )
                        sum_xp = await cur.fetchone()
                        value = sum_xp[0] if sum_xp and sum_xp[0] else 0
                    elif typ == "new_users":
                        guild = interaction.guild
                        # optional: nur Mitglieder seit Zielstart zählen
                        value = guild.member_count
                    else:
                        value = progress
                    percent = min(value / target * 100, 100) if target else 0
                    name = COMMUNITY_GOAL_TYPES.get(typ, typ)
                    embed.add_field(
                        name=f"{name}",
                        value=f"{value} / {target} ({percent:.1f}%)",
                        inline=False
                    )
                    if value >= target:
                        finished += 1
                if reward:
                    embed.add_field(name="Belohnung", value=reward, inline=False)
                embed.set_footer(
                    text=f"Ziel endet am {ends.strftime('%d.%m.%Y, %H:%M')} | {finished}/{len(conds)} Bedingungen erfüllt"
                )
                await interaction.response.send_message(embed=embed)

class CommunityGoalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_time = {}  # {guild_id: {user_id: join_timestamp}}
        self.check_ban_free_days.start()

    def cog_unload(self):
        self.check_ban_free_days.cancel()


    # Nachrichten Fortschritt
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

    # Voice Minuten Fortschritt
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.guild:
            return
        # Start/Stop-Tracking pro User
        guild_id = member.guild.id
        user_id = member.id
        now = datetime.utcnow().timestamp()
        if after.channel and not before.channel:
            # User joint Voice
            if guild_id not in self.voice_time:
                self.voice_time[guild_id] = {}
            self.voice_time[guild_id][user_id] = now
        elif before.channel and not after.channel:
            # User verlässt Voice
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

    # Befehle Fortschritt (Slash)
    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        if not interaction.guild:
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

    # Neue User Fortschritt
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

    # Ban-freie Tage Fortschritt (einmal pro Tag!)
    @tasks.loop(hours=24)
    async def check_ban_free_days(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            # Du solltest hier prüfen, ob in den letzten 24h ein Ban/Warn war!
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT g.id FROM community_goals g
                        JOIN community_goal_conditions c ON g.id = c.goal_id
                        WHERE g.guild_id=%s AND g.active=1 AND c.type='ban_free_days' LIMIT 1
                    """, (guild.id,))
                    goal = await cur.fetchone()
                    if goal:
                        # Optional: Hier solltest du echte Ban/Warning-Logik prüfen!
                        await cur.execute("""
                            UPDATE community_goal_conditions SET progress = progress + 1
                            WHERE goal_id=%s AND type='ban_free_days'
                        """, (goal[0],))
                        await conn.commit()

    # Levelups und XP werden live aus deiner Tabelle gelesen!

async def setup(bot):
    await bot.add_cog(CommunityGoalCog(bot))
