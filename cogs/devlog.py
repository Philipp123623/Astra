import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio

# ─────────────────────────────────────────────
# MAIN COG
# ─────────────────────────────────────────────

class DevLogDashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bg_task = bot.loop.create_task(self.weekly_task())

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    # ───────────── COMMANDS ─────────────

    @commands.command()
    async def dev(self, ctx):
        embed = discord.Embed(
            title="🧠 Astra – Dev Dashboard",
            description="Alles tracken. Alles im Blick.",
            color=0x5865F2
        )
        await ctx.send(embed=embed, view=DashboardView(self.bot))

    @commands.command()
    async def devtest(self, ctx):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        await ctx.send("✅ DevLog-System läuft korrekt")

    # ───────────── WEEKLY BACKGROUND TASK ─────────────

    async def weekly_task(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            now = datetime.now()

            days = (6 - now.weekday()) % 7
            target = (now + timedelta(days=days)).replace(
                hour=20, minute=0, second=0, microsecond=0
            )
            if target <= now:
                target += timedelta(days=7)

            await asyncio.sleep((target - now).total_seconds())
            await self.post_weekly()

    async def post_weekly(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT category, title, progress
                    FROM devlog_entries
                    WHERE YEARWEEK(created_at,1)=YEARWEEK(NOW(),1)
                      AND status!='archived'
                    ORDER BY created_at
                """)
                rows = await cur.fetchall()

        data = {"feature": [], "bug": [], "refactor": [], "note": []}
        for cat, title, prog in rows:
            if cat == "feature" and prog is not None:
                data[cat].append(f"{title} ({prog}%)")
            else:
                data[cat].append(title)

        embed = discord.Embed(
            title=f"📓 Weekly Dev Log – KW {datetime.now().isocalendar().week}",
            color=0x2ecc71
        )

        def add(name, items):
            embed.add_field(
                name=name,
                value="\n".join(f"• {x}" for x in items) if items else "—",
                inline=False
            )

        add("🚧 Features", data["feature"])
        add("🐛 Bugs", data["bug"])
        add("🔄 Refactors", data["refactor"])
        add("🧠 Notes", data["note"])

        channel = self.bot.get_channel(self.bot.config["DEVLOG_CHANNEL_ID"])
        if channel:
            await channel.send(embed=embed)

# ─────────────────────────────────────────────
# DASHBOARD VIEW
# ─────────────────────────────────────────────

class DashboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="Feature", emoji="🚧", style=discord.ButtonStyle.primary)
    async def feature(self, i, _):
        await i.response.send_modal(CreateModal(self.bot, "feature"))

    @discord.ui.button(label="Bug", emoji="🐛", style=discord.ButtonStyle.danger)
    async def bug(self, i, _):
        await i.response.send_modal(CreateModal(self.bot, "bug"))

    @discord.ui.button(label="Refactor", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refactor(self, i, _):
        await i.response.send_modal(CreateModal(self.bot, "refactor"))

    @discord.ui.button(label="Note", emoji="🧠", style=discord.ButtonStyle.success)
    async def note(self, i, _):
        await i.response.send_modal(CreateModal(self.bot, "note"))

    @discord.ui.button(label="Einträge verwalten", emoji="🗂️", style=discord.ButtonStyle.secondary, row=1)
    async def manage(self, i, _):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id, category, title, progress
                    FROM devlog_entries
                    WHERE status!='archived'
                    ORDER BY created_at DESC
                    LIMIT 25
                """)
                rows = await cur.fetchall()

        await i.response.send_message(
            "Eintrag auswählen:",
            view=ManageView(self.bot, rows),
            ephemeral=True
        )

# ─────────────────────────────────────────────
# CREATE MODAL
# ─────────────────────────────────────────────

class CreateModal(discord.ui.Modal):
    def __init__(self, bot, category):
        super().__init__(title=f"Neuer Eintrag – {category}")
        self.bot = bot
        self.category = category

        self.title_input = discord.ui.TextInput(label="Titel", required=True)
        self.desc_input = discord.ui.TextInput(
            label="Beschreibung (optional)",
            style=discord.TextStyle.long,
            required=False
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)

        if category == "feature":
            self.progress_input = discord.ui.TextInput(
                label="Fortschritt % (optional)",
                required=False
            )
            self.add_item(self.progress_input)

    async def on_submit(self, i):
        prog = None
        if hasattr(self, "progress_input") and self.progress_input.value.isdigit():
            prog = int(self.progress_input.value)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO devlog_entries (category,title,description,progress)
                    VALUES (%s,%s,%s,%s)
                """, (self.category, self.title_input.value, self.desc_input.value, prog))

        await i.response.send_message("✅ Gespeichert", ephemeral=True)

# ─────────────────────────────────────────────
# MANAGE VIEW
# ─────────────────────────────────────────────

class ManageView(discord.ui.View):
    def __init__(self, bot, rows):
        super().__init__(timeout=300)
        self.bot = bot
        self.add_item(EntrySelect(bot, rows))

class EntrySelect(discord.ui.Select):
    def __init__(self, bot, rows):
        self.bot = bot
        options = []
        for id_, cat, title, prog in rows:
            label = f"{cat.upper()}: {title}"
            if prog is not None:
                label += f" ({prog}%)"
            options.append(discord.SelectOption(label=label[:100], value=str(id_)))

        super().__init__(placeholder="Eintrag auswählen…", options=options)

    async def callback(self, i):
        await i.response.send_message(
            "Aktion wählen:",
            view=EntryActionView(self.bot, int(self.values[0])),
            ephemeral=True
        )

class EntryActionView(discord.ui.View):
    def __init__(self, bot, entry_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.entry_id = entry_id

    @discord.ui.button(label="Edit", emoji="✏️", style=discord.ButtonStyle.primary)
    async def edit(self, i, _):
        await i.response.send_modal(EditModal(self.bot, self.entry_id))

    @discord.ui.button(label="Done", emoji="✅", style=discord.ButtonStyle.success)
    async def done(self, i, _):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE devlog_entries SET status='done' WHERE id=%s",
                    (self.entry_id,)
                )
        await i.response.send_message("✅ Als erledigt markiert", ephemeral=True)

    @discord.ui.button(label="Delete", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete(self, i, _):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM devlog_entries WHERE id=%s",
                    (self.entry_id,)
                )
        await i.response.send_message("🗑️ Gelöscht", ephemeral=True)

# ─────────────────────────────────────────────
# EDIT MODAL
# ─────────────────────────────────────────────

class EditModal(discord.ui.Modal):
    def __init__(self, bot, entry_id):
        super().__init__(title="Eintrag bearbeiten")
        self.bot = bot
        self.entry_id = entry_id

        self.title_input = discord.ui.TextInput(label="Titel", required=True)
        self.desc_input = discord.ui.TextInput(
            label="Beschreibung",
            style=discord.TextStyle.long,
            required=False
        )
        self.progress_input = discord.ui.TextInput(
            label="Fortschritt % (optional)",
            required=False
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.progress_input)

    async def on_submit(self, i):
        prog = int(self.progress_input.value) if self.progress_input.value.isdigit() else None

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE devlog_entries
                    SET title=%s, description=%s, progress=%s
                    WHERE id=%s
                """, (
                    self.title_input.value,
                    self.desc_input.value,
                    prog,
                    self.entry_id
                ))

        await i.response.send_message("✏️ Aktualisiert", ephemeral=True)

# ─────────────────────────────────────────────

async def setup(bot):
    await bot.add_cog(DevLogDashboard(bot))
