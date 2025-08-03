import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta

# Emoji-Codes kannst du durch eigene ersetzen
COMMUNITY_GOAL_TYPES = {
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

@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
class Goals(app_commands.Group):
    def __init__(self, bot):
        self.bot = bot
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
    async def set(
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
            embed = discord.Embed(
                title="🚫 Fehler",
                description="Mindestens eine Bedingung mit Wert > 0 angeben.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        now = datetime.utcnow()
        ends = now + timedelta(days=ends_in_days)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Vorheriges Ziel beenden
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

        cond_lines = "\n".join(
            f"{COMMUNITY_GOAL_TYPES[typ][1]} **{COMMUNITY_GOAL_TYPES[typ][0]}:** `{val:,}`"
            for typ, val in conditions
        )
        embed = discord.Embed(
            title="🎯 Neues Community Goal erstellt!",
            description=f"Läuft **{ends_in_days}** Tage\n\n{cond_lines}",
            color=discord.Color.blurple()
        )
        if reward:
            embed.add_field(name="🎁 Belohnung", value=reward, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="status", description="Zeigt das aktuelle Communityziel und den Fortschritt.")
    async def status(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
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
                conds = await cur.fetchall()

                embed = discord.Embed(
                    title="🎯 Community Goal",
                    description=f"Läuft noch bis **{ends.strftime('%d.%m.%Y, %H:%M')}**",
                    color=discord.Color.blurple()
                )
                finished = 0

                for typ, target, progress in conds:
                    if typ == "xp":
                        await cur.execute(
                            "SELECT SUM(user_xp) FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,)
                        )
                        sum_xp = await cur.fetchone()
                        value = sum_xp[0] if sum_xp and sum_xp[0] else 0
                    elif typ == "levelups":
                        value = progress
                    elif typ == "new_users":
                        value = interaction.guild.member_count
                    else:
                        value = progress

                    percent = min(value / target * 100, 100) if target else 0
                    name, icon = COMMUNITY_GOAL_TYPES.get(typ, (typ, ""))
                    bar = progress_bar(value, target)
                    embed.add_field(
                        name=f"{icon} **{name}**",
                        value=f"{bar}\n**{value:,} / {target:,}** (`{percent:.1f}%`)",
                        inline=False
                    )
                    if value >= target:
                        finished += 1

                embed.add_field(
                    name="🎁 Belohnung",
                    value=reward or "*Keine Belohnung angegeben*",
                    inline=False
                )
                embed.set_footer(
                    text=f"{finished}/{len(conds)} Ziele erfüllt"
                )
                await interaction.response.send_message(embed=embed)

# COG für automatische Fortschritt-Listener
class CommunityGoalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_time = {}  # {guild_id: {user_id: join_timestamp}}
        self.check_ban_free_days.start()

    def cog_unload(self):
        self.check_ban_free_days.cancel()

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
        # Besser: Nur echte Userbefehle zählen, nicht jede Systemaktion
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

    @tasks.loop(hours=24)
    async def check_ban_free_days(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            # Hier solltest du wirklich auf echte Bans prüfen!
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT g.id FROM community_goals g
                        JOIN community_goal_conditions c ON g.id = c.goal_id
                        WHERE g.guild_id=%s AND g.active=1 AND c.type='ban_free_days' LIMIT 1
                    """, (guild.id,))
                    goal = await cur.fetchone()
                    if goal:
                        # Optional: Nur +1, wenn kein Ban
                        await cur.execute("""
                            UPDATE community_goal_conditions SET progress = progress + 1
                            WHERE goal_id=%s AND type='ban_free_days'
                        """, (goal[0],))
                        await conn.commit()

    # Das hier bitte im Levelsystem bei jedem Levelup aufrufen!
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
    await bot.add_cog(CommunityGoalCog(bot))
    bot.tree.add_command(Goals(bot))
