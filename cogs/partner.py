import discord
from discord.ext import commands
from discord import app_commands
import asyncio, datetime, logging, re

FORUM_CHANNEL_ID = 1368374036240793701
ADMIN_CHANNEL_ID = 1233028223684575274

class BewerbungModalEmbed(discord.ui.Modal, title="Partnerbewerbung – Embed"):
    thread_title = discord.ui.TextInput(label="Thread-Titel", required=True, max_length=100)
    embed_title = discord.ui.TextInput(label="Embed-Titel", required=True, max_length=256)
    embed_description = discord.ui.TextInput(label="Beschreibung", style=discord.TextStyle.paragraph, required=True)
    embed_color = discord.ui.TextInput(label="Farbe (HEX z. B. #5865F2)", required=False, default="#5865F2")
    embed_image = discord.ui.TextInput(label="Bild-URL (optional)", required=False)
    invite_link = discord.ui.TextInput(label="Einladungslink zum Server", required=True)
    werbekanal_id = discord.ui.TextInput(label="Channel-ID für unsere Werbung", required=True)

    def __init__(self, bot, projektart):
        super().__init__()
        self.bot = bot
        self.projektart = projektart

    async def on_submit(self, interaction: discord.Interaction):
        if self.embed_image.value and not re.match(r"https?://", self.embed_image.value):
            await interaction.response.send_message("❌ Ungültige Bild-URL. Bitte mit http:// oder https://", ephemeral=True)
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO partner_applications
                    (user_id, thread_title, embed_title, embed_description, embed_color, embed_image, invite_link, ad_channel_id, projektart)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    interaction.user.id,
                    self.thread_title.value,
                    self.embed_title.value,
                    self.embed_description.value,
                    self.embed_color.value,
                    self.embed_image.value,
                    self.invite_link.value,
                    int(self.werbekanal_id.value),
                    self.projektart
                ))
                await conn.commit()

        embed = discord.Embed(title="📬 Neue Partnerbewerbung (Embed)", color=discord.Color.blurple())
        embed.add_field(name="Thread-Titel", value=self.thread_title.value, inline=False)
        embed.add_field(name="Projektart", value=self.projektart, inline=True)
        embed.add_field(name="Einladung", value=self.invite_link.value, inline=True)
        embed.add_field(name="Werbekanal-ID", value=self.werbekanal_id.value, inline=False)
        embed.add_field(name="Embed-Titel", value=self.embed_title.value, inline=False)
        embed.add_field(name="Beschreibung", value=self.embed_description.value, inline=False)
        embed.add_field(name="Farbe", value=self.embed_color.value, inline=True)
        embed.add_field(name="Bild", value=self.embed_image.value or "Keins", inline=True)

        view = AdminReviewView(self.bot, interaction.user.id)
        admin_channel = self.bot.get_channel(ADMIN_CHANNEL_ID)
        await admin_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Deine Bewerbung wurde eingereicht und wird geprüft.", ephemeral=True)

class BewerbungModalText(discord.ui.Modal, title="Partnerbewerbung – Text"):
    thread_title = discord.ui.TextInput(label="Thread-Titel", required=True, max_length=100)
    beschreibung = discord.ui.TextInput(label="Beschreibung (Text im Thread)", style=discord.TextStyle.paragraph, required=True)
    invite_link = discord.ui.TextInput(label="Einladungslink zum Server", required=True)
    werbekanal_id = discord.ui.TextInput(label="Channel-ID für unsere Werbung", required=True)

    def __init__(self, bot, projektart):
        super().__init__()
        self.bot = bot
        self.projektart = projektart

    async def on_submit(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO partner_applications
                    (user_id, thread_title, embed_title, embed_description, embed_color, embed_image, invite_link, ad_channel_id, projektart)
                    VALUES (%s,%s,NULL,%s,NULL,NULL,%s,%s,%s)
                """, (
                    interaction.user.id,
                    self.thread_title.value,
                    self.beschreibung.value,
                    self.invite_link.value,
                    int(self.werbekanal_id.value),
                    self.projektart
                ))
                await conn.commit()

        embed = discord.Embed(title="📬 Neue Partnerbewerbung (Text)", color=discord.Color.blurple())
        embed.add_field(name="Thread-Titel", value=self.thread_title.value, inline=False)
        embed.add_field(name="Projektart", value=self.projektart, inline=True)
        embed.add_field(name="Einladung", value=self.invite_link.value, inline=True)
        embed.add_field(name="Werbekanal-ID", value=self.werbekanal_id.value, inline=False)
        embed.add_field(name="Text-Inhalt", value=self.beschreibung.value, inline=False)

        view = AdminReviewView(self.bot, interaction.user.id)
        admin_channel = self.bot.get_channel(ADMIN_CHANNEL_ID)
        await admin_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Deine Bewerbung wurde eingereicht und wird geprüft.", ephemeral=True)

class Partner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autopost_tasks_started = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.autopost_tasks_started:
            self.autopost_tasks_started = True
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                    CREATE TABLE IF NOT EXISTS partner_applications (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT,
                        thread_title TEXT,
                        embed_title TEXT,
                        embed_description TEXT,
                        embed_color TEXT,
                        embed_image TEXT,
                        invite_link TEXT,
                        ad_channel_id BIGINT,
                        projektart TEXT,
                        status ENUM('pending','accepted','declined') DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                    await cur.execute("""
                    CREATE TABLE IF NOT EXISTS partner_ad_config (
                        ad_channel_id BIGINT PRIMARY KEY,
                        time BIGINT
                    )
                    """)
                    await cur.execute("""
                    CREATE TABLE IF NOT EXISTS astra_ad_config (
                        id INT PRIMARY KEY DEFAULT 1,
                        title TEXT,
                        description TEXT,
                        invite_link TEXT,
                        thumbnail TEXT,
                        image TEXT
                    )
                    """)
                    await cur.execute("SELECT ad_channel_id, time FROM partner_ad_config")
                    eintraege = await cur.fetchall()

                    async def starte_autopost_tasks():
                        for ad_channel_id, time_ts in eintraege:
                            try:
                                when = datetime.datetime.fromtimestamp(int(time_ts))
                                asyncio.create_task(self.sende_werbung(when, int(ad_channel_id)))
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                logging.error(f"❌ Werbung-Task Fehler: {e}")

                    asyncio.create_task(starte_autopost_tasks())

    async def sende_werbung(self, when: datetime.datetime, ad_channel_id: int):
        await self.bot.wait_until_ready()
        await discord.utils.sleep_until(when)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT title, description, invite_link, thumbnail, image FROM astra_ad_config LIMIT 1")
                data = await cur.fetchone()
                if not data:
                    return
                title, description, invite, thumbnail, image = data

        embed = discord.Embed(title=title, description=description.replace("{invite}", invite), color=discord.Color.blurple())
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        if image:
            embed.set_image(url=image)

        channel = self.bot.get_channel(ad_channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logging.error(f"Fehler beim automatischen Posten in {ad_channel_id}: {e}")

        neue_zeit = int((datetime.datetime.now() + datetime.timedelta(hours=6)).timestamp())
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE partner_ad_config SET time = %s WHERE ad_channel_id = %s", (neue_zeit, ad_channel_id))
                await conn.commit()

        asyncio.create_task(self.sende_werbung(datetime.datetime.fromtimestamp(neue_zeit), ad_channel_id))

    @app_commands.command(name="partnerbewerbung", description="Starte eine Partnerbewerbung mit Embed oder Text")
    @app_commands.choices(
        projektart=[
            app_commands.Choice(name="Discord", value="Discord"),
            app_commands.Choice(name="Bots", value="Bots"),
            app_commands.Choice(name="Webseite", value="Webseite"),
            app_commands.Choice(name="Community", value="Community")
        ],
        darstellung=[
            app_commands.Choice(name="Embed", value="embed"),
            app_commands.Choice(name="Text", value="text")
        ]
    )
    async def partnerbewerbung(self, interaction: discord.Interaction,
                                projektart: app_commands.Choice[str],
                                darstellung: app_commands.Choice[str]):
        if darstellung.value == "embed":
            await interaction.response.send_modal(BewerbungModalEmbed(self.bot, projektart.value))
        else:
            await interaction.response.send_modal(BewerbungModalText(self.bot, projektart.value))

class AdminReviewView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id

    def disable_all_items(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success)
    async def annehmen(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM partner_applications WHERE user_id = %s", (self.user_id,))
                row = await cur.fetchone()

        if not row:
            await interaction.response.send_message("❌ Keine Bewerbung gefunden.", ephemeral=True)
            return

        _, _, thread_title, embed_title, embed_description, embed_color, embed_image, invite, ad_channel_id, projektart, *_ = row

        forum = self.bot.get_channel(FORUM_CHANNEL_ID)
        tags = forum.available_tags
        main_tag = discord.utils.get(tags, name="Partner")
        project_tag = discord.utils.get(tags, name=projektart)
        used_tags = [t for t in [main_tag, project_tag] if t]

        if embed_title:
            embed = discord.Embed(title=embed_title, description=f"{embed_description}\n\n[Beitreten]({invite})", color=int(embed_color.replace("#", ""), 16))
            if embed_image:
                embed.set_image(url=embed_image)
            await forum.create_thread(name=thread_title, content=".", embed=embed, applied_tags=used_tags)
        else:
            await forum.create_thread(name=thread_title, content=f"**{projektart}**\n{embed_description}\n\n[Beitreten]({invite})", applied_tags=used_tags)

        channel = self.bot.get_channel(int(ad_channel_id))
        if channel:
            try:
                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT title, description, invite_link, thumbnail, image FROM astra_ad_config LIMIT 1")
                        data = await cur.fetchone()
                if data:
                    a_title, a_desc, a_inv, a_thumb, a_img = data
                    astra_embed = discord.Embed(title=a_title, description=a_desc.replace("{invite}", a_inv), color=discord.Color.blurple())
                    if a_thumb:
                        astra_embed.set_thumbnail(url=a_thumb)
                    if a_img:
                        astra_embed.set_image(url=a_img)
                    await channel.send(embed=astra_embed)
            except Exception as e:
                logging.error(f"Fehler beim Werbung posten: {e}")

        neue_zeit = int((datetime.datetime.now() + datetime.timedelta(hours=6)).timestamp())
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE partner_applications SET status = 'accepted' WHERE user_id = %s", (self.user_id,))
                await cur.execute("INSERT INTO partner_ad_config (ad_channel_id, time) VALUES (%s, %s) ON DUPLICATE KEY UPDATE time = %s", (int(ad_channel_id), neue_zeit, neue_zeit))
                await conn.commit()

        await interaction.response.send_message("✅ Partner angenommen & Werbung gestartet!", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger)
    async def ablehnen(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE partner_applications SET status = 'declined' WHERE user_id = %s", (self.user_id,))
                await conn.commit()

        await interaction.response.send_message("❌ Bewerbung abgelehnt.", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

async def setup(bot):
    await bot.add_cog(Partner(bot))