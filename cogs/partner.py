import discord
from discord.ext import commands
from discord import app_commands
import asyncio, datetime, logging

FORUM_CHANNEL_ID = 1368374036240793701  # Ersetze mit deiner Forum-Channel-ID
ADMIN_CHANNEL_ID = 1233028223684575274  # Kanal für Admin-Review

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

        embed = discord.Embed(
            title=title,
            description=description.replace("{invite}", invite),
            color=discord.Color.blurple()
        )
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

    @app_commands.command(name="partnerbewerbung", description="Bewerbe dich als Partner.")
    @app_commands.describe(
        thread_title="Titel für den Forum-Post",
        embed_title="Titel für das Embed",
        embed_description="Beschreibung für das Embed",
        embed_color="Farbe im HEX (z.B. #5865F2)",
        embed_image="Bild-URL (optional)",
        invite_link="Einladungslink zum Server",
        werbekanal_id="Channel-ID für Werbung",
        projektart="Was ist dein Projekt?"
    )
    @app_commands.choices(
        projektart=[
            app_commands.Choice(name="Discord", value="Discord"),
            app_commands.Choice(name="Bots", value="Bots"),
            app_commands.Choice(name="Webseite", value="Webseite"),
            app_commands.Choice(name="Community", value="Community")
        ]
    )
    async def partnerbewerbung(self, interaction: discord.Interaction,
                                thread_title: str,
                                embed_title: str,
                                embed_description: str,
                                embed_color: str,
                                embed_image: str,
                                invite_link: str,
                                werbekanal_id: str,
                                projektart: app_commands.Choice[str]):
        user_id = interaction.user.id

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM partner_applications WHERE user_id = %s AND status = 'pending'", (user_id,))
                existing = await cur.fetchone()
                if existing:
                    await interaction.response.send_message("❗ Du hast bereits eine offene Bewerbung.", ephemeral=True)
                    return

                await cur.execute("""
                INSERT INTO partner_applications
                (user_id, thread_title, embed_title, embed_description, embed_color, embed_image, invite_link, ad_channel_id, projektart)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (user_id, thread_title, embed_title, embed_description, embed_color, embed_image, invite_link, int(werbekanal_id), projektart.value))
                await conn.commit()

        embed = discord.Embed(title="📬 Neue Partnerbewerbung",
                              description=(f"**Thread-Titel:** {thread_title}\n**Projektart:** {projektart.value}\n**Einladungslink:** {invite_link}\n**Werbekanal-ID:** {werbekanal_id}\n"
                                           f"**Embed:**\n**Titel:** {embed_title}\n**Beschreibung:** {embed_description}\n**Farbe:** {embed_color}\n**Bild:** {embed_image}"),
                              color=discord.Color.blurple())
        view = AdminReviewView(self.bot, user_id)
        admin_channel = self.bot.get_channel(ADMIN_CHANNEL_ID)
        await admin_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Deine Bewerbung wurde eingereicht und wird bald geprüft.", ephemeral=True)

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

        embed = discord.Embed(
            title=embed_title,
            description=f"{embed_description}\n\n[Beitreten]({invite})",
            color=int(embed_color.replace("#", ""), 16)
        )
        if embed_image:
            embed.set_image(url=embed_image)

        await forum.create_thread(
            name=thread_title,
            content=".",
            embed=embed,
            applied_tags=used_tags
        )

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
                logging.error(f"❌ Fehler beim Senden der Werbung: {e}")

        neue_zeit = int((datetime.datetime.now() + datetime.timedelta(hours=6)).timestamp())
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE partner_applications SET status = 'accepted' WHERE user_id = %s", (self.user_id,))
                await cur.execute("INSERT INTO partner_ad_config (ad_channel_id, time) VALUES (%s, %s) ON DUPLICATE KEY UPDATE time = %s", (int(ad_channel_id), neue_zeit, neue_zeit))
                await conn.commit()

        await interaction.response.send_message("✅ Bewerbung angenommen & Werbung gestartet!", ephemeral=True)
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