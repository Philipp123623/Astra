import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Union
import asyncio
import re

GOAL_TYPES = {
    "messages":      ("Nachrichten", "💬"),
    "voice_minutes": ("Voice-Minuten", "🔊"),
    "xp":            ("XP", "✨"),
    "levelups":      ("Level-Ups", "⬆️"),
    "new_users":     ("Neue User", "👤"),
    "ban_free":      ("Ban-freie Tage", "🕊️"),
    "commands_used": ("Befehle genutzt", "⚡"),
}

def progress_bar(current, target, length=18):
    percent = min(current / target, 1) if target else 0
    filled = int(length * percent)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"`{bar}`"

def format_goal_embed(conds, reward, ends, finished, total, reward_role: Optional[discord.Role] = None):
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
    if reward_role:
        embed.add_field(
            name="🎁 Belohnung",
            value=f"{reward or '*Keine Belohnung angegeben*'}\n{reward_role.mention}",
            inline=False
        )
    else:
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
        name="erstellen",
        description="Setzt ein neues Communityziel mit frei wählbaren Bedingungen."
    )
    @app_commands.describe(
        dauer="Wie viele Tage soll das Ziel laufen? (1–60)",
        belohnung="Belohnung (Text, Emoji etc. oder @Rolle)",
        nachrichten="Wie viele Nachrichten sollen geschrieben werden?",
        nachrichten_kanal="Optional: Nachrichten zählen nur in diesem Kanal.",
        voice_minuten="Wie viele Voice-Minuten sollen gesammelt werden?",
        xp="Wie viele XP sollen gesammelt werden?",
        levelups="Wie viele Level-Ups insgesamt?",
        neue_mitglieder="Wie viele neue Mitglieder sollen joinen?",
        banfrei="Wie viele Tage ohne Ban/Warn?",
        befehle="Wie viele Slash-Befehle sollen genutzt werden?"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def erstellen(
        self,
        interaction: discord.Interaction,
        dauer: app_commands.Range[int, 1, 60],
        belohnung: Optional[str] = None,
        nachrichten: Optional[app_commands.Range[int, 1, 1000000]] = None,
        nachrichten_kanal: Optional[discord.TextChannel] = None,
        voice_minuten: Optional[app_commands.Range[int, 1, 1000000]] = None,
        xp: Optional[app_commands.Range[int, 1, 10000000]] = None,
        levelups: Optional[app_commands.Range[int, 1, 10000]] = None,
        neue_mitglieder: Optional[app_commands.Range[int, 1, 10000]] = None,
        banfrei: Optional[app_commands.Range[int, 1, 60]] = None,
        befehle: Optional[app_commands.Range[int, 1, 100000]] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        conds = []
        mapping = [
            ("messages", nachrichten),
            ("voice_minutes", voice_minuten),
            ("xp", xp),
            ("levelups", levelups),
            ("new_users", neue_mitglieder),
            ("ban_free", banfrei),
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
        ends = now + timedelta(days=dauer)

        # --- Belohnung: Support für Rollenextraktion (@Rolle im belohnung-Text)
        reward_role_id = None
        reward_role = None
        if belohnung:
            role_mention_match = re.search(r"<@&(\d+)>", belohnung)
            if role_mention_match:
                reward_role_id = int(role_mention_match.group(1))
                reward_role = interaction.guild.get_role(reward_role_id)

        # Optional: Nachrichten-Kanal setzen
        channel_id = nachrichten_kanal.id if nachrichten_kanal else None

        async with self.cog.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE community_goals SET active=0 WHERE guild_id=%s", (interaction.guild.id,))
                await cur.execute(
                    "INSERT INTO community_goals (guild_id, started_at, ends_at, reward, active) VALUES (%s, %s, %s, %s, 1)",
                    (interaction.guild.id, now, ends, belohnung)
                )
                goal_id = cur.lastrowid if hasattr(cur, "lastrowid") else (await cur.execute("SELECT LAST_INSERT_ID()")).fetchone()[0]
                for typ, val in conds:
                    await cur.execute(
                        "INSERT INTO community_goal_conditions (goal_id, type, target, progress) VALUES (%s, %s, %s, %s)",
                        (goal_id, typ, val, 0)
                    )
                # Kanal für Nachrichten-Ziel extra speichern
                if channel_id and nachrichten:
                    await cur.execute(
                        "UPDATE community_goals SET reward=%s WHERE id=%s", (f"{belohnung}|CHANNEL:{channel_id}", goal_id)
                    )
                await conn.commit()
        # Starte Task für Zeitablauf
        self.cog.bot.loop.create_task(self.cog.goal_end_task(goal_id, interaction.guild.id, ends, reward_role_id))
        cond_lines = "\n".join(
            f"{GOAL_TYPES[typ][1]} **{GOAL_TYPES[typ][0]}:** `{val:,}`"
            for typ, val in conds
        )
        embed = discord.Embed(
            title="🎯 Neues Community Goal erstellt!",
            description=f"Läuft **{dauer}** Tage\n\n{cond_lines}",
            color=discord.Color.blurple()
        )
        if belohnung:
            embed.add_field(name="🎁 Belohnung", value=belohnung, inline=False)
        if reward_role:
            embed.add_field(name="🎁 Rollenbelohnung", value=reward_role.mention, inline=False)
        if nachrichten_kanal:
            embed.add_field(name="📝 Nachrichten-Kanal", value=nachrichten_kanal.mention, inline=False)
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
                        description="Momentan läuft kein Ziel. Erstelle eines mit `/communitygoals erstellen`.",
                        color=discord.Color.red()
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
                goal_id = goal[0]
                reward = goal[4]
                ends = goal[3]
                # Belohnungsrolle herausfinden
                reward_role = None
                role_mention_match = re.search(r"<@&(\d+)>", reward or "")
                if role_mention_match:
                    reward_role_id = int(role_mention_match.group(1))
                    reward_role = interaction.guild.get_role(reward_role_id)
                await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                conds_db = await cur.fetchall()
                conds = []
                finished = 0
                for typ, target, progress in conds_db:
                    value = min(progress, target)
                    if typ == "xp":
                        await cur.execute("SELECT SUM(user_xp) FROM levelsystem WHERE guild_id = %s", (interaction.guild.id,))
                        sum_xp = await cur.fetchone()
                        value = min(sum_xp[0] if sum_xp and sum_xp[0] else 0, target)
                    elif typ == "new_users":
                        value = min(interaction.guild.member_count, target)
                    if value >= target:
                        finished += 1
                    conds.append((typ, target, value))
                embed = format_goal_embed(conds, reward, ends, finished, len(conds), reward_role)
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
                await cur.execute("SELECT id, guild_id, ends_at, reward FROM community_goals WHERE active=1 AND ends_at > NOW()")
                entries = await cur.fetchall()
                for goal_id, guild_id, ends_at, reward in entries:
                    reward_role_id = None
                    role_mention_match = re.search(r"<@&(\d+)>", reward or "")
                    if role_mention_match:
                        reward_role_id = int(role_mention_match.group(1))
                    ends_at_dt = ends_at if isinstance(ends_at, datetime) else datetime.strptime(str(ends_at), "%Y-%m-%d %H:%M:%S")
                    self.bot.loop.create_task(self.goal_end_task(goal_id, guild_id, ends_at_dt, reward_role_id))

    async def goal_end_task(self, goal_id, guild_id, ends_at, reward_role_id=None):
        # Task kann früher beendet werden!
        def all_done_checker(condlist):
            return all(val >= target for _, target, val in condlist)

        now = datetime.utcnow()
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Frühzeitig beenden, falls bereits abgeschlossen
                while True:
                    await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                    conds_db = await cur.fetchall()
                    # cappe alle values für den check!
                    condlist = []
                    for typ, target, progress in conds_db:
                        value = min(progress, target)
                        condlist.append((typ, target, value))
                    if all_done_checker(condlist):
                        break
                    sleep_time = (ends_at - datetime.utcnow()).total_seconds()
                    if sleep_time < 1:
                        break
                    await asyncio.sleep(min(30, sleep_time))
                # Beende das Ziel
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
                    value = min(progress, target)
                    if typ == "ban_free":
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
        reward_role = None
        if reward_role_id and guild:
            reward_role = guild.get_role(reward_role_id)
        for typ, target, value in conds:
            name, icon = GOAL_TYPES.get(typ, (typ, "❔"))
            bar = progress_bar(value, target)
            percent = min(value / target * 100, 100) if target else 0
            embed.add_field(
                name=f"{icon} **{name}**",
                value=f"{bar}\n**{value:,} / {target:,}** (`{percent:.1f}%`)",
                inline=False
            )
        if reward_role:
            embed.add_field(
                name="🎁 Belohnung",
                value=f"{reward or '*Keine Belohnung angegeben*'}\n{reward_role.mention}",
                inline=False
            )
        else:
            embed.add_field(
                name="🎁 Belohnung",
                value=reward or "*Keine Belohnung angegeben*",
                inline=False
            )
        # Sende die Nachricht
        if guild and guild.system_channel:
            await guild.system_channel.send(embed=embed)
        # Rollenbelohnung an alle verteilen, falls vorhanden und Ziel geschafft
        if reward_role and finished == len(conds):
            # Gib die Rolle allen Membern
            for m in guild.members:
                try:
                    await m.add_roles(reward_role, reason="Community Goal abgeschlossen")
                except Exception:
                    pass

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
        # --- Kanal-Limitierung beachten!
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, reward FROM community_goals WHERE guild_id=%s AND active=1 LIMIT 1", (message.guild.id,)
                )
                res = await cur.fetchone()
                if not res:
                    return
                goal_id, reward = res
                channel_limit = None
                if reward and "CHANNEL:" in reward:
                    match = re.search(r"CHANNEL:(\d+)", reward)
                    if match:
                        channel_limit = int(match.group(1))
                if channel_limit and message.channel.id != channel_limit:
                    return  # Nachricht in anderem Kanal ignorieren

                await cur.execute("""
                    SELECT target, progress FROM community_goal_conditions
                    WHERE goal_id=%s AND type='messages'
                """, (goal_id,))
                cond = await cur.fetchone()
                if cond:
                    target, progress = cond
                    if progress < target:
                        await cur.execute("""
                            UPDATE community_goal_conditions SET progress = progress + 1
                            WHERE goal_id=%s AND type='messages'
                        """, (goal_id,))
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
                                    SELECT target, progress FROM community_goal_conditions
                                    WHERE goal_id=%s AND type='voice_minutes'
                                """, (goal[0],))
                                cond = await cur.fetchone()
                                if cond and cond[1] < cond[0]:
                                    add_minutes = min(minutes, cond[0] - cond[1])
                                    await cur.execute("""
                                        UPDATE community_goal_conditions SET progress = progress + %s
                                        WHERE goal_id=%s AND type='voice_minutes'
                                    """, (add_minutes, goal[0]))
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
                        SELECT target, progress FROM community_goal_conditions
                        WHERE goal_id=%s AND type='commands_used'
                    """, (goal[0],))
                    cond = await cur.fetchone()
                    if cond and cond[1] < cond[0]:
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
                        SELECT target, progress FROM community_goal_conditions
                        WHERE goal_id=%s AND type='new_users'
                    """, (goal[0],))
                    cond = await cur.fetchone()
                    if cond and cond[1] < cond[0]:
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
                        SELECT target, progress FROM community_goal_conditions
                        WHERE goal_id=%s AND type='levelups'
                    """, (goal[0],))
                    cond = await cur.fetchone()
                    if cond and cond[1] < cond[0]:
                        await cur.execute("""
                            UPDATE community_goal_conditions SET progress = progress + 1
                            WHERE goal_id=%s AND type='levelups'
                        """, (goal[0],))
                        await conn.commit()

async def setup(bot):
    cog = CommunityGoalsCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(CommunityGoalsGroup(cog))
