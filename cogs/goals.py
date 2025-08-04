import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio
import re
from datetime import datetime, timedelta, timezone
import time

GOAL_TYPES = {
    "messages": ("Nachrichten", "💬"),
    "voice_minutes": ("Voice-Minuten", "🔊"),
    "xp": ("XP", "✨"),
    "levelups": ("Level-Ups", "⬆️"),
    "new_users": ("Neue User", "👤"),
    "ban_free": ("Ban-freie Tage", "🕊️"),
    "commands_used": ("Befehle genutzt", "⚡"),
}

def parse_time_input(time_str: str) -> Optional[int]:
    """
    Parsen verschiedener Zeitformate in UNIX-Timestamp UTC.
    Erlaubt:
    - Zahl (1-60) als Tage ab jetzt
    - Datum mit optionaler Uhrzeit (z.B. 5.8.2025, 05.08.2025 18:30)
    - Nur Uhrzeit heute oder morgen (UTC)
    """
    now = datetime.now(timezone.utc)

    # 1) Zahl als Tage
    if re.fullmatch(r"\d{1,2}", time_str):
        tage = int(time_str)
        if 1 <= tage <= 60:
            return int((now + timedelta(days=tage)).timestamp())

    # 2) Datum + optionale Uhrzeit
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2})(?::(\d{1,2}))?)?", time_str)
    if m:
        tag, monat, jahr = int(m[1]), int(m[2]), int(m[3])
        stunde = int(m[4]) if m[4] else 0
        minute = int(m[5]) if m[5] else 0
        try:
            dt = datetime(jahr, monat, tag, stunde, minute, tzinfo=timezone.utc)
            if dt.timestamp() > now.timestamp():
                return int(dt.timestamp())
        except Exception:
            return None

    # 3) Nur Uhrzeit heute/morgen
    m = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?", time_str)
    if m:
        stunde = int(m[1])
        minute = int(m[2]) if m[2] else 0
        try:
            dt = now.replace(hour=stunde, minute=minute, second=0, microsecond=0)
            if dt.timestamp() <= now.timestamp():
                dt += timedelta(days=1)
            return int(dt.timestamp())
        except Exception:
            return None

    return None

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

def format_goal_embed(conds, reward_text, ends_timestamp, finished, total, reward_role: Optional[discord.Role] = None,
                      status: Optional[str] = None):
    ends = datetime.fromtimestamp(ends_timestamp, timezone.utc).astimezone()
    values = [v for _, _, v in conds]
    targets = [t for _, t, _ in conds]
    embed = discord.Embed(
        title="🎯 Community Goal" if not status else status,
        description=f"Läuft noch bis **{ends.strftime('%d.%m.%Y, %H:%M')} Uhr**",
        color=discord.Color.blurple() if not status else (
            discord.Color.green() if status and status.startswith("🏁") else discord.Color.red()
        )
    )
    bar = overall_progress_bar(values, targets)
    embed.add_field(name="Fortschritt (alle Ziele)", value=bar, inline=False)
    for typ, target, value in conds:
        name, icon = GOAL_TYPES.get(typ, (typ, "❔"))
        percent = min(value / target * 100, 100) if target else 0
        embed.add_field(
            name=f"{icon} **{name}**",
            value=f"**{value:,} / {target:,}** ({percent:.1f}%)",
            inline=False
        )
    reward_field = reward_text or "*Keine Belohnung angegeben*"
    if reward_role and (not reward_text or reward_role.mention not in reward_text):
        reward_field += f"\n{reward_role.mention}"
    embed.add_field(name="🎁 Belohnung", value=reward_field, inline=False)
    embed.set_footer(text=f"{finished}/{total} Ziele erfüllt")
    return embed

# --- Modals ---

class GoalModalPage1(discord.ui.Modal, title="Community Goal erstellen (1/2)"):
    dauer = discord.ui.TextInput(label="Ende (Tage, Datum oder Uhrzeit)", required=True,
                                placeholder="z.B. 14 oder 05.08.2025 18:00 oder 18:00")
    belohnung_text = discord.ui.TextInput(label="Belohnung (optional, Text)", required=False,
                                         placeholder="Text, z.B. '500 Coins'")
    nachrichten = discord.ui.TextInput(label="Nachrichten-Ziel (optional)", required=False, placeholder="z.B. 2500")
    voice_minuten = discord.ui.TextInput(label="Voice-Minuten-Ziel (optional)", required=False, placeholder="z.B. 1000")
    xp = discord.ui.TextInput(label="XP-Ziel (optional)", required=False, placeholder="z.B. 25000")

    def __init__(self, ziel_kanal: discord.TextChannel, reward_role: Optional[discord.Role]):
        super().__init__()
        self.ziel_kanal = ziel_kanal
        self.reward_role = reward_role

    async def on_submit(self, interaction: discord.Interaction):
        data_page1 = {
            "dauer": self.dauer.value.strip(),
            "belohnung_text": self.belohnung_text.value.strip(),
            "nachrichten": self.nachrichten.value.strip(),
            "voice_minuten": self.voice_minuten.value.strip(),
            "xp": self.xp.value.strip(),
        }
        await interaction.response.send_modal(GoalModalPage2(self.ziel_kanal, data_page1, self.reward_role))

class GoalModalPage2(discord.ui.Modal, title="Community Goal erstellen (2/2)"):
    levelups = discord.ui.TextInput(label="Level-Ups-Ziel (optional)", required=False, placeholder="z.B. 15")
    neue_mitglieder = discord.ui.TextInput(label="Neue Mitglieder-Ziel (optional)", required=False, placeholder="z.B. 12")
    banfrei = discord.ui.TextInput(label="Ban-freie Tage (optional)", required=False, placeholder="z.B. 14")
    befehle = discord.ui.TextInput(label="Befehle genutzt-Ziel (optional)", required=False, placeholder="z.B. 200")

    def __init__(self, ziel_kanal: discord.TextChannel, data_page1: dict, reward_role: Optional[discord.Role]):
        super().__init__()
        self.ziel_kanal = ziel_kanal
        self.data_page1 = data_page1
        self.reward_role = reward_role

    async def on_submit(self, interaction: discord.Interaction):
        data_page2 = {
            "levelups": self.levelups.value.strip(),
            "neue_mitglieder": self.neue_mitglieder.value.strip(),
            "banfrei": self.banfrei.value.strip(),
            "befehle": self.befehle.value.strip(),
        }
        full_data = {**self.data_page1, **data_page2}
        await CommunityGoalsGroup.create_goal_from_modal(full_data, self.ziel_kanal, interaction, self.reward_role)


class CommunityGoalsGroup(app_commands.Group):
    def __init__(self, cog):
        super().__init__(name="communitygoals", description="Communityziele!")
        self.cog = cog

    @app_commands.command(name="erstellen", description="Setzt ein neues Communityziel via Modal.")
    @app_commands.describe(
        ziel_kanal="Channel für das Ziel-Embed & Updates.",
        belohnung_rolle="Optionale Rolle als Belohnung"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def erstellen(
        self,
        interaction: discord.Interaction,
        ziel_kanal: discord.TextChannel,
        belohnung_rolle: Optional[discord.Role] = None
    ):
        await interaction.response.send_modal(GoalModalPage1(ziel_kanal, belohnung_rolle))

    @staticmethod
    async def create_goal_from_modal(goal_data, ziel_kanal, interaction: discord.Interaction, reward_role: Optional[discord.Role] = None):
        now_ts = int(time.time())
        ends_raw = goal_data.get("dauer", "")
        ends_ts = parse_time_input(ends_raw)
        if not ends_ts or ends_ts <= now_ts:
            await interaction.followup.send("Ungültiges oder vergangenes Enddatum. Bitte gib einen gültigen Wert an.", ephemeral=True)
            return

        belohnung_text = goal_data.get("belohnung_text") or None

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

        cond_lines = "\n".join(
            f"{GOAL_TYPES[typ][1]} **{GOAL_TYPES[typ][0]}:** {val:,}"
            for typ, val in conds
        )
        embed = discord.Embed(
            title="🎯 Neues Community Goal erstellt!",
            description=f"Läuft bis <t:{ends_ts}:f>\n\n{cond_lines}",
            color=discord.Color.blurple()
        )

        reward_field = belohnung_text or "*Keine Belohnung angegeben*"
        if reward_role and (not belohnung_text or reward_role.mention not in belohnung_text):
            reward_field += f"\n{reward_role.mention}"
        embed.add_field(name="🎁 Belohnung", value=reward_field, inline=False)

        goal_message = await ziel_kanal.send(embed=embed)
        msg_id = goal_message.id
        ziel_kanal_id = ziel_kanal.id

        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE community_goals SET active=FALSE WHERE guild_id=%s", (interaction.guild.id,))
                await cur.execute(
                    "INSERT INTO community_goals (guild_id, started_at, ends_at, reward_role_id, reward_text, active, channel_id, msg_id) VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)",
                    (interaction.guild.id, now_ts, ends_ts, reward_role.id if reward_role else None, belohnung_text, ziel_kanal_id, msg_id)
                )
                if hasattr(cur, "lastrowid"):
                    goal_id = cur.lastrowid
                else:
                    await cur.execute("SELECT LAST_INSERT_ID()")
                    goal_id = (await cur.fetchone())[0]
                for typ, val in conds:
                    await cur.execute(
                        "INSERT INTO community_goal_conditions (goal_id, type, target, progress) VALUES (%s, %s, %s, 0)",
                        (goal_id, typ, val)
                    )
                await conn.commit()

        interaction.client.loop.create_task(
            interaction.client.get_cog("CommunityGoalsCog").goal_end_task(goal_id, interaction.guild.id, ends_ts, reward_role.id if reward_role else None)
        )
        await interaction.followup.send(f"Community Goal wurde erstellt und im Channel {ziel_kanal.mention} gepostet!", ephemeral=True)

    @app_commands.command(name="status", description="Zeigt das aktuelle Communityziel und den Fortschritt.")
    async def status(self, interaction: discord.Interaction):
        async with self.cog.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, reward_role_id, reward_text, ends_at FROM community_goals WHERE guild_id=%s AND active=TRUE LIMIT 1",
                    (interaction.guild.id,)
                )
                goal = await cur.fetchone()
                if not goal:
                    embed = discord.Embed(
                        title="🚫 Kein aktives Community Goal",
                        description="Momentan läuft kein Ziel. Erstelle eines mit /communitygoals erstellen.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                goal_id, reward_role_id, reward_text, ends_at_ts = goal
                reward_role = interaction.guild.get_role(reward_role_id) if reward_role_id else None

                await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                conds_db = await cur.fetchall()

                conds = []
                finished = 0
                for typ, target, progress in conds_db:
                    value = min(progress, target)
                    if typ == "xp":
                        await cur.execute("SELECT SUM(user_xp) FROM levelsystem WHERE guild_id=%s", (interaction.guild.id,))
                        sum_xp = await cur.fetchone()
                        value = min(sum_xp[0] or 0, target)
                    elif typ == "new_users":
                        value = min(interaction.guild.member_count, target)
                    if value >= target:
                        finished += 1
                    conds.append((typ, target, value))

                embed = format_goal_embed(conds, reward_text, ends_at_ts, finished, len(conds), reward_role, status=None)
                await interaction.response.send_message(embed=embed)


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
                await cur.execute(
                    "SELECT id, guild_id, ends_at, reward_role_id FROM community_goals WHERE active=TRUE AND ends_at > %s",
                    (int(time.time()),)
                )
                entries = await cur.fetchall()
                for goal_id, guild_id, ends_at, reward_role_id in entries:
                    self.bot.loop.create_task(self.goal_end_task(goal_id, guild_id, ends_at, reward_role_id))

    async def goal_end_task(self, goal_id, guild_id, ends_at_ts, reward_role_id=None):
        def all_done_checker(condlist):
            return all(val >= target for _, target, val in condlist)

        now_ts = int(time.time())
        if ends_at_ts < now_ts:
            ends_at_ts = now_ts

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT channel_id, msg_id, started_at FROM community_goals WHERE id=%s", (goal_id,))
                res = await cur.fetchone()
                channel_id, msg_id, started_at_ts = (res if res else (None, None, None))

                while True:
                    await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                    conds_db = await cur.fetchall()
                    condlist = [(typ, target, min(progress, target)) for typ, target, progress in conds_db]

                    if all_done_checker(condlist):
                        break
                    now_ts = int(time.time())
                    sleep_time = ends_at_ts - now_ts
                    if sleep_time < 1:
                        break
                    await asyncio.sleep(min(30, sleep_time))

                await cur.execute("UPDATE community_goals SET active=FALSE WHERE id=%s", (goal_id,))

                await cur.execute("SELECT reward_role_id, reward_text FROM community_goals WHERE id=%s", (goal_id,))
                reward_data = await cur.fetchone()
                reward_role_id_db, reward_text = reward_data if reward_data else (None, None)

                await cur.execute("SELECT type, target, progress FROM community_goal_conditions WHERE goal_id=%s", (goal_id,))
                conds_db = await cur.fetchall()

        conds = []
        finished = 0
        started_at = datetime.fromtimestamp(started_at_ts, timezone.utc) if started_at_ts else None
        ends_at = datetime.fromtimestamp(ends_at_ts, timezone.utc)
        for typ, target, progress in conds_db:
            value = min(progress, target)
            if typ == "ban_free" and started_at and ends_at:
                ban_occurred = await self.check_ban_in_period(guild_id, started_at, ends_at)
                value = target if not ban_occurred else 0
            if value >= target:
                finished += 1
            conds.append((typ, target, value))

        guild = self.bot.get_guild(guild_id)
        status = "🏁 Community Goal **GESCHAFFT!**" if finished == len(conds) and len(conds) > 0 else "⏹️ Community Goal beendet"
        desc = f"Alle Ziele wurden erreicht! 🎉" if finished == len(conds) and len(conds) > 0 else f"Nicht alle Ziele wurden erreicht! **{finished}/{len(conds)}**"
        reward_role = guild.get_role(reward_role_id) if reward_role_id and guild else None
        embed = format_goal_embed(conds, reward_text, ends_at_ts, finished, len(conds), reward_role, status=status)
        embed.description = desc

        if guild and channel_id and msg_id:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.edit(embed=embed)
                except Exception:
                    pass

        if reward_role and finished == len(conds):
            for member in guild.members:
                try:
                    await member.add_roles(reward_role, reason="Community Goal abgeschlossen")
                except Exception:
                    pass

    async def check_ban_in_period(self, guild_id, started_at: datetime, ends_at: datetime) -> bool:
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM goal_bans WHERE guild_id=%s AND time BETWEEN %s AND %s LIMIT 1",
                    (guild_id, started_at, ends_at)
                )
                return bool(await cur.fetchone())

    # Listener etc. wie gehabt ...

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, reward_text FROM community_goals WHERE guild_id=%s AND active=TRUE LIMIT 1",
                    (message.guild.id,)
                )
                res = await cur.fetchone()
                if not res:
                    return
                goal_id, reward_text = res

                channel_limit = None
                if reward_text and "CHANNEL:" in reward_text:
                    m = re.search(r"CHANNEL:(\d+)", reward_text)
                    if m:
                        channel_limit = int(m[1])
                if channel_limit and message.channel.id != channel_limit:
                    return

                await cur.execute(
                    "SELECT target, progress FROM community_goal_conditions WHERE goal_id=%s AND type='messages'", (goal_id,)
                )
                cond = await cur.fetchone()
                if cond:
                    target, progress = cond
                    if progress < target:
                        await cur.execute(
                            "UPDATE community_goal_conditions SET progress=LEAST(progress + 1, target) WHERE goal_id=%s AND type='messages'",
                            (goal_id,)
                        )
                        await conn.commit()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if not member.guild:
            return
        guild_id = member.guild.id
        user_id = member.id
        now = time.time()
        if after.channel and not before.channel:
            self.voice_time.setdefault(guild_id, {})[user_id] = now
        elif before.channel and not after.channel:
            if guild_id in self.voice_time and user_id in self.voice_time[guild_id]:
                joined_at = self.voice_time[guild_id].pop(user_id)
                minutes = int((now - joined_at) // 60)
                if minutes > 0:
                    async with self.bot.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                """
                                SELECT g.id
                                FROM community_goals g
                                JOIN community_goal_conditions c ON g.id = c.goal_id
                                WHERE g.guild_id=%s AND g.active=TRUE AND c.type='voice_minutes'
                                LIMIT 1
                                """,
                                (guild_id,)
                            )
                            goal = await cur.fetchone()
                            if goal:
                                goal_id = goal[0]
                                await cur.execute(
                                    "SELECT target, progress FROM community_goal_conditions WHERE goal_id=%s AND type='voice_minutes'",
                                    (goal_id,)
                                )
                                cond = await cur.fetchone()
                                if cond:
                                    target, progress = cond
                                    if progress < target:
                                        add_minutes = min(minutes, target - progress)
                                        await cur.execute(
                                            "UPDATE community_goal_conditions SET progress=LEAST(progress + %s, target) WHERE goal_id=%s AND type='voice_minutes'",
                                            (add_minutes, goal_id)
                                        )
                                        await conn.commit()

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        if not interaction.guild or interaction.user.bot:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT g.id
                    FROM community_goals g
                    JOIN community_goal_conditions c ON g.id = c.goal_id
                    WHERE g.guild_id=%s AND g.active=TRUE AND c.type='commands_used'
                    LIMIT 1
                    """,
                    (interaction.guild.id,)
                )
                goal = await cur.fetchone()
                if goal:
                    goal_id = goal[0]
                    await cur.execute(
                        "SELECT target, progress FROM community_goal_conditions WHERE goal_id=%s AND type='commands_used'",
                        (goal_id,)
                    )
                    cond = await cur.fetchone()
                    if cond:
                        target, progress = cond
                        if progress < target:
                            await cur.execute(
                                "UPDATE community_goal_conditions SET progress=LEAST(progress + 1, target) WHERE goal_id=%s AND type='commands_used'",
                                (goal_id,)
                            )
                            await conn.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT g.id
                    FROM community_goals g
                    JOIN community_goal_conditions c ON g.id = c.goal_id
                    WHERE g.guild_id=%s AND g.active=TRUE AND c.type='new_users'
                    LIMIT 1
                    """,
                    (member.guild.id,)
                )
                goal = await cur.fetchone()
                if goal:
                    goal_id = goal[0]
                    await cur.execute(
                        "SELECT target, progress FROM community_goal_conditions WHERE goal_id=%s AND type='new_users'",
                        (goal_id,)
                    )
                    cond = await cur.fetchone()
                    if cond:
                        target, progress = cond
                        if progress < target:
                            await cur.execute(
                                "UPDATE community_goal_conditions SET progress=LEAST(progress + 1, target) WHERE goal_id=%s AND type='new_users'",
                                (goal_id,)
                            )
                            await conn.commit()

    async def count_levelup(self, guild_id):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT g.id
                    FROM community_goals g
                    JOIN community_goal_conditions c ON g.id = c.goal_id
                    WHERE g.guild_id=%s AND g.active=TRUE AND c.type='levelups'
                    LIMIT 1
                    """,
                    (guild_id,)
                )
                goal = await cur.fetchone()
                if goal:
                    goal_id = goal[0]
                    await cur.execute(
                        "SELECT target, progress FROM community_goal_conditions WHERE goal_id=%s AND type='levelups'",
                        (goal_id,)
                    )
                    cond = await cur.fetchone()
                    if cond:
                        target, progress = cond
                        if progress < target:
                            await cur.execute(
                                "UPDATE community_goal_conditions SET progress=LEAST(progress + 1, target) WHERE goal_id=%s AND type='levelups'",
                                (goal_id,)
                            )
                            await conn.commit()

async def setup(bot):
    cog = CommunityGoalsCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(CommunityGoalsGroup(cog))
