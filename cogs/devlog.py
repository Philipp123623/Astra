import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio

class DevLogDashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bg_task = bot.loop.create_task(self.weekly_background_task())

    async def cog_check(self, ctx):
        return ctx.author.id == self.bot.owner_id

    # ───────────── DASHBOARD COMMAND ─────────────

    @commands.command()
    async def dev(self, ctx):
        embed = discord.Embed(
            title="🧠 Astra – Dev Dashboard",
            description="Wähle, was du tracken willst.",
            color=0x5865F2
        )
        await ctx.send(embed=embed, view=DevDashboardView(self.bot))

    # ───────────── BACKGROUND TASK ─────────────

    async def weekly_background_task(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            now = datetime.now()

            # nächsten Sonntag 20:00 berechnen
            days_ahead = (6 - now.weekday()) % 7
            next_sunday = now + timedelta(days=days_ahead)
            target = next_sunday.replace(hour=20, minute=0, second=0, microsecond=0)

            # wenn heute Sonntag nach 20:00 → nächste Woche
            if target <= now:
                target += timedelta(days=7)

            sleep_seconds = (target - now).total_seconds()
            await asyncio.sleep(sleep_seconds)

            await self.post_weekly_log()

    async def post_weekly_log(self):
        now = datetime.now()
        week = now.isocalendar().week

        async with self.bot.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT category, title
                    FROM devlog_entries
                    WHERE YEARWEEK(created_at, 1) = YEARWEEK(NOW(), 1)
                      AND status != 'archived'
                    ORDER BY created_at ASC
                """)
                rows = await cur.fetchall()

        data = {"feature": [], "bug": [], "refactor": [], "note": []}
        for cat, title in rows:
            data[cat].append(title)

        embed = discord.Embed(
            title=f"📓 Weekly Dev Log – KW {week}",
            color=0x2ecc71
        )

        features = [f"• {x}" for x in data["feature"] if x and x.strip()]
        bugs = [f"• {x}" for x in data["bug"] if x and x.strip()]
        refactors = [f"• {x}" for x in data["refactor"] if x and x.strip()]
        notes = [f"• {x}" for x in data["note"] if x and x.strip()]

        embed.add_field(
            name="🚧 Features",
            value="\n".join(features) if features else "—",
            inline=False
        )
        embed.add_field(
            name="🐛 Bugs",
            value="\n".join(bugs) if bugs else "—",
            inline=False
        )
        embed.add_field(
            name="🔄 Refactors",
            value="\n".join(refactors) if refactors else "—",
            inline=False
        )
        embed.add_field(
            name="🧠 Notes",
            value="\n".join(notes) if notes else "—",
            inline=False
        )

        embed.set_footer(text="Automatisches Dev-Tagebuch · Astra")

        channel = self.bot.get_channel(self.bot.config["1463209410795929914"])
        if channel:
            await channel.send(embed=embed)

# ───────────── UI ─────────────

class DevDashboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="Feature", emoji="🚧", style=discord.ButtonStyle.primary)
    async def feature(self, interaction, _):
        await interaction.response.send_modal(DevModal(self.bot, "feature"))

    @discord.ui.button(label="Bug", emoji="🐛", style=discord.ButtonStyle.danger)
    async def bug(self, interaction, _):
        await interaction.response.send_modal(DevModal(self.bot, "bug"))

    @discord.ui.button(label="Refactor", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refactor(self, interaction, _):
        await interaction.response.send_modal(DevModal(self.bot, "refactor"))

    @discord.ui.button(label="Note", emoji="🧠", style=discord.ButtonStyle.success)
    async def note(self, interaction, _):
        await interaction.response.send_modal(DevModal(self.bot, "note"))

class DevModal(discord.ui.Modal):
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

    async def on_submit(self, interaction):
        async with self.bot.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO devlog_entries (category, title, description) VALUES (%s,%s,%s)",
                    (self.category, self.title_input.value, self.desc_input.value)
                )

        await interaction.response.send_message("✅ Gespeichert", ephemeral=True)

async def setup(bot):
    await bot.add_cog(DevLogDashboard(bot))
