import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio
import re
from zoneinfo import ZoneInfo

GOAL_TYPES = {
    "messages": ("Nachrichten", "💬"),
    "voice_minutes": ("Voice-Minuten", "🔊"),
    "xp": ("XP", "✨"),
    "levelups": ("Level-Ups", "⬆️"),
    "new_users": ("Neue User", "👤"),
    "ban_free": ("Ban-freie Tage", "🕊️"),
    "commands_used": ("Befehle genutzt", "⚡"),
}

def overall_progress_bar(values, targets, length=24):
    if not values or not targets or sum(targets) == 0:
        percent = 0
    else:
        percent = sum(min(v, t) / t for v, t in zip(values, targets) if t > 0) / len(targets)
    percent = min(percent, 1)
    filled = int(length * percent)
    empty = length - filled
    bar = "🟩" * filled + "⬜" * empty
    return f"`{bar}` **{percent * 100:.1f}%**"

def format_goal_embed(conds, reward, ends, finished, total, reward_role: Optional[discord.Role] = None,
                      status: Optional[str] = None):
    values = [v for _, _, v in conds]
    targets = [t for _, t, _ in conds]
    embed = discord.Embed(
        title="🎯 Community Goal" if not status else status,
        description=f"Läuft noch bis **{ends.astimezone(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y, %H:%M')} Uhr (MESZ)**" if not status else None,
        color=discord.Color.blurple() if not status else (
            discord.Color.green() if status.startswith("🏁") else discord.Color.red()
        )
    )
    bar = overall_progress_bar(values, targets)
    embed.add_field(name="Fortschritt (alle Ziele)", value=bar, inline=False)
    for typ, target, value in conds:
        name, icon = GOAL_TYPES.get(typ, (typ, "❔"))
        percent = min(value / target * 100, 100) if target else 0
        embed.add_field(
            name=f"{icon} **{name}**",
            value=f"**{value:,} / {target:,}** (`{percent:.1f}%`)",
            inline=False
        )
    reward_field = reward or "*Keine Belohnung angegeben*"
    if reward_role and (not reward or reward_role.mention not in reward):
        reward_field += f"\n{reward_role.mention}"
    embed.add_field(name="🎁 Belohnung", value=reward_field, inline=False)
    embed.set_footer(text=f"{finished}/{total} Ziele erfüllt")
    return embed

# ----- Modals -----

class GoalModalPage1(discord.ui.Modal, title="Community Goal erstellen (1/2)"):
    dauer = discord.ui.TextInput(label="Dauer (Tage, 1–60)", min_length=1, max_length=2, required=True, placeholder="z.B. 14")
    belohnung = discord.ui.TextInput(label="Belohnung (Text, Emoji oder @Rolle)", required=False, placeholder="@Mitgliedschaftsrolle oder 500 Coins")
    nachrichten = discord.ui.TextInput(label="Nachrichten-Ziel (optional)", required=False, placeholder="z.B. 2500")
    voice_minuten = discord.ui.TextInput(label="Voice-Minuten-Ziel (optional)", required=False, placeholder="z.B. 1000")
    xp = discord.ui.TextInput(label="XP-Ziel (optional)", required=False, placeholder="z.B. 25000")

    def __init__(self, ziel_kanal: discord.TextChannel):
        super().__init__()
        self.ziel_kanal = ziel_kanal

    async def on_submit(self, interaction: discord.Interaction):
        data_page1 = {
            "dauer": self.dauer.value,
            "belohnung": self.belohnung.value,
            "nachrichten": self.nachrichten.value,
            "voice_minuten": self.voice_minuten.value,
            "xp": self.xp.value,
        }
        await interaction.response.send_modal(GoalModalPage2(self.ziel_kanal, data_page1))

class GoalModalPage2(discord.ui.Modal, title="Community Goal erstellen (2/2)"):
    levelups = discord.ui.TextInput(label="Level-Ups-Ziel (optional)", required=False, placeholder="z.B. 15")
    neue_mitglieder = discord.ui.TextInput(label="Neue Mitglieder-Ziel (optional)", required=False, placeholder="z.B. 12")
    banfrei = discord.ui.TextInput(label="Ban-freie Tage (optional)", required=False, placeholder="z.B. 14")
    befehle = discord.ui.TextInput(label="Befehle genutzt-Ziel (optional)", required=False, placeholder="z.B. 200")

    def __init__(self, ziel_kanal: discord.TextChannel, data_page1: dict):
        super().__init__()
        self.ziel_kanal = ziel_kanal
        self.data_page1 = data_page1

    async def on_submit(self, interaction: discord.Interaction):
        data_page2 = {
            "levelups": self.levelups.value,
            "neue_mitglieder": self.neue_mitglieder.value,
            "banfrei": self.banfrei.value,
            "befehle": self.befehle.value,
        }
        full_data = {**self.data_page1, **data_page2}
        await CommunityGoalsGroup.create_goal_from_modal(full_data, self.ziel_kanal, interaction)

# ----- Command Group -----

class CommunityGoalsGroup(app_commands.Group):
    def __init__(self, cog):
        super().__init__(name="communitygoals", description="Communityziele!")
        self.cog = cog

    @app_commands.command(
        name="erstellen",
        description="Setzt ein neues Communityziel via Modal."
    )
    @app_commands.describe(ziel_kanal="Channel für das Ziel-Embed & Updates.")
    @app_commands.checks.has_permissions(administrator=True)
    async def erstellen(self, interaction: discord.Interaction, ziel_kanal: discord.TextChannel):
        await interaction.response.send_modal(GoalModalPage1(ziel_kanal))

    @staticmethod
    async def create_goal_from_modal(goal_data, ziel_kanal, interaction: discord.Interaction):
        try:
            dauer = int(goal_data.get("dauer", 0))
            if not (1 <= dauer <= 60):
                raise ValueError
        except ValueError:
            await interaction.followup.send("Ungültige Dauer. Bitte 1–60 Tage.", ephemeral=True)
            return

        belohnung = goal_data.get("belohnung") or None

        def to_int(s):
            try:
                return int(s.replace(".", "").replace(",", "")) if s else None
            except Exception:
                return None

        nachrichten = to_int(goal_data.get("nachrichten"))
        voice_minuten = to_int(goal_data.get("voice_minuten"))
        xp = to_int(goal_data.get("xp"))
        levelups = to_int(goal_data.get("levelups"))
        neue_mitglieder = to_int(goal_data.get("neue_mitglieder"))
        banfrei = to_int(goal_data.get("banfrei"))
        befehle = to_int(goal_data.get("befehle"))

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
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        ends = now + timedelta(days=dauer)

        reward_role_id = None
        reward_role = None
        if belohnung:
            role_mention_match = re.search(r"<@&(\d+)>", belohnung)
            if role_mention_match:
                reward_role_id = int(role_mention_match.group(1))
                reward_role = interaction.guild.get_role(reward_role_id)

        cond_lines = "\n".join(
            f"{GOAL_TYPES[typ][1]} **{GOAL_TYPES[typ][0]}:** `{val:,}`"
            for typ, val in conds
        )
        embed = discord.Embed(
            title="🎯 Neues Community Goal erstellt!",
            description=f"Läuft **{dauer}** Tage\n\n{cond_lines}",
            color=discord.Color.blurple()
        )
        reward_field = belohnung or "*Keine Belohnung angegeben*"
        if reward_role and (not belohnung or reward_role.mention not in belohnung):
            reward_field += f"\n{reward_role.mention}"
        embed.add_field(name="🎁 Belohnung", value=reward_field, inline=False)

        goal_message = await ziel_kanal.send(embed=embed)
        msg_id = goal_message.id
        ziel_kanal_id = ziel_kanal.id

        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE community_goals SET active=0 WHERE guild_id=%s", (interaction.guild.id,))
                await cur.execute(
                    "INSERT INTO community_goals (guild_id, started_at, ends_at, reward, active, channel_id, msg_id) VALUES (%s, %s, %s, %s, 1, %s, %s)",
                    (interaction.guild.id, now, ends, belohnung, ziel_kanal_id, msg_id)
                )
                goal_id = cur.lastrowid if hasattr(cur, "lastrowid") else (await cur.execute("SELECT LAST_INSERT_ID()")).fetchone()[0]
                for typ, val in conds:
                    await cur.execute(
                        "INSERT INTO community_goal_conditions (goal_id, type, target, progress) VALUES (%s, %s, %s, %s)",
                        (goal_id, typ, val, 0)
                    )
                await conn.commit()

        interaction.client.loop.create_task(interaction.client.get_cog("CommunityGoalsCog").goal_end_task(goal_id, interaction.guild.id, ends, reward_role_id))
        await interaction.followup.send(f"Community Goal wurde erstellt und im Channel {ziel_kanal.mention} gepostet!", ephemeral=True)

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
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                goal_id = goal[0]
                reward = goal[4]
                ends = goal[3]
                reward_role = None
                if ends.tzinfo is None:
                    ends = ends.replace(tzinfo=timezone.utc)
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

# ----- Cog -----

class CommunityGoalsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_time = {}
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
        def all_done_checker(condlist):
            return all(val >= target for _, target, val in condlist)

        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT channel_id, msg_id FROM community_goals WHERE id=%s", (goal_id,))
                channel_row = await cur.fetchone()
                channel_id, msg_id = channel_row if channel_row else (None, None)
                while True:
                    await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                    conds_db = await cur.fetchall()
                    condlist = [(typ, target, min(progress, target)) for typ, target, progress in conds_db]
                    if all_done_checker(condlist):
                        break
                    sleep_time = (ends_at - datetime.now(timezone.utc)).total_seconds()
                    if sleep_time < 1:
                        break
                    await asyncio.sleep(min(30, sleep_time))
                await cur.execute("SELECT started_at, ends_at FROM community_goals WHERE id=%s", (goal_id,))
                started_at, ends_at_db = await cur.fetchone()
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                if ends_at_db.tzinfo is None:
                    ends_at_db = ends_at_db.replace(tzinfo=timezone.utc)
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
                ban_occurred = await self.check_ban_in_period(guild_id, started_at, ends_at_db)
                value = target if not ban_occurred else 0
            if value >= target:
                finished += 1
            conds.append((typ, target, value))

        guild = self.bot.get_guild(int(guild_id))
        status = "🏁 Community Goal **GESCHAFFT!**" if finished == len(conds) and len(conds) > 0 else "⏹️ Community Goal beendet"
        desc = (f"Alle Ziele wurden erreicht! 🎉" if finished == len(conds) and len(conds) > 0
                else f"Nicht alle Ziele wurden erreicht! **{finished}/{len(conds)}**")
        reward_role = guild.get_role(reward_role_id) if reward_role_id and guild else None
        embed = format_goal_embed(conds, reward, ends_at, finished, len(conds), reward_role, status=status)
        embed.description = desc

        if guild and channel_id and msg_id:
            channel = guild.get_channel(int(channel_id))
            try:
                if channel:
                    msg = await channel.fetch_message(int(msg_id))
                    await msg.edit(embed=embed)
            except Exception:
                pass

        if reward_role and finished == len(conds):
            for m in guild.members:
                try:
                    await m.add_roles(reward_role, reason="Community Goal abgeschlossen")
                except Exception:
                    pass

    async def check_ban_in_period(self, guild_id, started_at, ends_at):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM goal_bans WHERE guild_id=%s AND time BETWEEN %s AND %s LIMIT 1",
                    (guild_id, started_at, ends_at)
                )
                return bool(await cur.fetchone())

    # Fortschrittstracking Listener etc...
    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, reward FROM community_goals WHERE guild_id=%s AND active=1 LIMIT 1",
                    (message.guild.id,)
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

                # Progress capped!
                await cur.execute("""
                                  SELECT target, progress
                                  FROM community_goal_conditions
                                  WHERE goal_id = %s
                                    AND type = 'messages'
                                  """, (goal_id,))
                cond = await cur.fetchone()
                if cond:
                    target, progress = cond
                    if progress < target:
                        await cur.execute("""
                                          UPDATE community_goal_conditions
                                          SET progress = LEAST(progress + 1, target)
                                          WHERE goal_id = %s
                                            AND type = 'messages'
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
                                              SELECT g.id
                                              FROM community_goals g
                                                       JOIN community_goal_conditions c ON g.id = c.goal_id
                                              WHERE g.guild_id = %s
                                                AND g.active = 1
                                                AND c.type = 'voice_minutes'
                                              LIMIT 1
                                              """, (guild_id,))
                            goal = await cur.fetchone()
                            if goal:
                                await cur.execute("""
                                                  SELECT target, progress
                                                  FROM community_goal_conditions
                                                  WHERE goal_id = %s
                                                    AND type = 'voice_minutes'
                                                  """, (goal[0],))
                                cond = await cur.fetchone()
                                if cond:
                                    target, progress = cond
                                    if progress < target:
                                        add_minutes = min(minutes, target - progress)
                                        await cur.execute("""
                                                          UPDATE community_goal_conditions
                                                          SET progress = LEAST(progress + %s, target)
                                                          WHERE goal_id = %s
                                                            AND type = 'voice_minutes'
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
                                  SELECT g.id
                                  FROM community_goals g
                                           JOIN community_goal_conditions c ON g.id = c.goal_id
                                  WHERE g.guild_id = %s
                                    AND g.active = 1
                                    AND c.type = 'commands_used'
                                  LIMIT 1
                                  """, (interaction.guild.id,))
                goal = await cur.fetchone()
                if goal:
                    await cur.execute("""
                                      SELECT target, progress
                                      FROM community_goal_conditions
                                      WHERE goal_id = %s
                                        AND type = 'commands_used'
                                      """, (goal[0],))
                    cond = await cur.fetchone()
                    if cond:
                        target, progress = cond
                        if progress < target:
                            await cur.execute("""
                                              UPDATE community_goal_conditions
                                              SET progress = LEAST(progress + 1, target)
                                              WHERE goal_id = %s
                                                AND type = 'commands_used'
                                              """, (goal[0],))
                            await conn.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                                  SELECT g.id
                                  FROM community_goals g
                                           JOIN community_goal_conditions c ON g.id = c.goal_id
                                  WHERE g.guild_id = %s
                                    AND g.active = 1
                                    AND c.type = 'new_users'
                                  LIMIT 1
                                  """, (member.guild.id,))
                goal = await cur.fetchone()
                if goal:
                    await cur.execute("""
                                      SELECT target, progress
                                      FROM community_goal_conditions
                                      WHERE goal_id = %s
                                        AND type = 'new_users'
                                      """, (goal[0],))
                    cond = await cur.fetchone()
                    if cond:
                        target, progress = cond
                        if progress < target:
                            await cur.execute("""
                                              UPDATE community_goal_conditions
                                              SET progress = LEAST(progress + 1, target)
                                              WHERE goal_id = %s
                                                AND type = 'new_users'
                                              """, (goal[0],))
                            await conn.commit()

    async def count_levelup(self, guild_id):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                                  SELECT g.id
                                  FROM community_goals g
                                           JOIN community_goal_conditions c ON g.id = c.goal_id
                                  WHERE g.guild_id = %s
                                    AND g.active = 1
                                    AND c.type = 'levelups'
                                  LIMIT 1
                                  """, (guild_id,))
                goal = await cur.fetchone()
                if goal:
                    await cur.execute("""
                                      SELECT target, progress
                                      FROM community_goal_conditions
                                      WHERE goal_id = %s
                                        AND type = 'levelups'
                                      """, (goal[0],))
                    cond = await cur.fetchone()
                    if cond:
                        target, progress = cond
                        if progress < target:
                            await cur.execute("""
                                              UPDATE community_goal_conditions
                                              SET progress = LEAST(progress + 1, target)
                                              WHERE goal_id = %s
                                                AND type = 'levelups'
                                              """, (goal[0],))
                            await conn.commit()

async def setup(bot):
    cog = CommunityGoalsCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(CommunityGoalsGroup(cog))
