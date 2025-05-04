import discord
from discord.ext import commands
from discord import app_commands
import asyncio, datetime, logging

FORUM_CHANNEL_ID = 1368374036240793701
ADMIN_CHANNEL_ID = 1233028223684575274

def sanitize_thread_title(title: str) -> str:
    return ''.join(c for c in title if c.isalnum() or c in " -_")[:100]

class PartnerZwischenspeicher:
    def __init__(self):
        self.cache = {}

    def set(self, user_id, data):
        self.cache[user_id] = data

    def get(self, user_id):
        return self.cache.get(user_id)

    def clear(self, user_id):
        self.cache.pop(user_id, None)

bewerbung_cache = PartnerZwischenspeicher()

def sanitize_text(text):
    return text.replace("\\n", "\n")

class ModalErsterSchritt(discord.ui.Modal, title="Partnerbewerbung – Schritt 1: Allgemeines"):
    def __init__(self, bot, projektart, darstellung):
        super().__init__()
        self.bot = bot
        self.projektart = projektart
        self.darstellung = darstellung

        self.thread_title = discord.ui.TextInput(
            label="Thread-Titel",
            style=discord.TextStyle.short,
            max_length=100,
            placeholder="Z. B. Cooles Projekt"
        )

        self.invite_link = discord.ui.TextInput(
            label="Einladungslink",
            style=discord.TextStyle.short,
            placeholder="https://discord.gg/...",
            max_length=200
        )

        self.werbekanal_id = discord.ui.TextInput(
            label="Werbekanal-ID",
            style=discord.TextStyle.short,
            placeholder="Z. B. 1234567890",
            max_length=25
        )

        self.add_item(self.thread_title)
        self.add_item(self.invite_link)
        self.add_item(self.werbekanal_id)

    async def on_submit(self, interaction: discord.Interaction):
        title = self.thread_title.value.strip()
        invite = self.invite_link.value.strip()
        werbekanal = self.werbekanal_id.value.strip()

        if not title or not invite or not werbekanal:
            await interaction.response.send_message(
                "❌ Bitte fülle alle Felder korrekt aus.", ephemeral=True
            )
            return

        bewerbung_cache.set(interaction.user.id, {
            "thread_title": title,
            "invite_link": invite,
            "werbekanal_id": werbekanal,
            "projektart": self.projektart,
            "darstellung": self.darstellung
        })

        logging.info(f"[Partnerbewerbung] Schritt 1 gespeichert für User {interaction.user.id}: {bewerbung_cache.get(interaction.user.id)}")

        view = SchrittZweiStartView(self.bot)
        await interaction.response.send_message(
            "✅ Schritt 1 abgeschlossen. Klicke auf den Button unten, um mit Schritt 2 fortzufahren:",
            view=view,
            ephemeral=True
        )

class SchrittZweiStartView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=600)
        self.bot = bot

    @discord.ui.button(label="📝 Schritt 2 starten", style=discord.ButtonStyle.secondary)
    async def weiter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalZweiterSchritt(self.bot))

class ModalZweiterSchritt(discord.ui.Modal, title="Partnerbewerbung – Schritt 2: Werbetext"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.werbetext = discord.ui.TextInput(
            label="Werbetext",
            style=discord.TextStyle.paragraph,
            placeholder="Erkläre, warum du Partner werden möchtest...",
            max_length=4000
        )
        self.add_item(self.werbetext)

    async def on_submit(self, interaction: discord.Interaction):
        werbetext = self.werbetext.value.strip()

        if not werbetext:
            await interaction.response.send_message("❌ Der Werbetext darf nicht leer sein.", ephemeral=True)
            return

        data = bewerbung_cache.get(interaction.user.id)
        if not data:
            await interaction.response.send_message("❌ Fehler beim Zwischenspeichern.", ephemeral=True)
            return

        data["werbetext"] = werbetext

        logging.info(f"[Partnerbewerbung] Schritt 2 gespeichert für {interaction.user.id}")

        if data["darstellung"] == "text":
            bewerbung_cache.clear(interaction.user.id)
            await save_and_send_bewerbung(self.bot, interaction, data, embed=False)
        else:
            view = SchrittDreiStartView(self.bot)
            await interaction.response.send_message(
                "✅ Schritt 2 abgeschlossen. Klicke unten, um zu den Embed-Einstellungen zu gelangen:",
                view=view,
                ephemeral=True
            )

class SchrittDreiStartView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=600)
        self.bot = bot

    @discord.ui.button(label="🎨 Schritt 3 starten", style=discord.ButtonStyle.secondary)
    async def weiter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalDritterSchritt(self.bot))

class ModalDritterSchritt(discord.ui.Modal, title="Schritt 3: Embed-Einstellungen"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.embed_color = discord.ui.TextInput(
            label="Farbe (#5865F2)",
            style=discord.TextStyle.short,
            required=False,
            placeholder="#5865F2",
            max_length=7
        )

        self.embed_image = discord.ui.TextInput(
            label="Bild-URL (optional)",
            style=discord.TextStyle.short,
            required=False,
            max_length=300
        )

        self.embed_thumbnail = discord.ui.TextInput(
            label="Thumbnail-URL (optional)",
            style=discord.TextStyle.short,
            required=False,
            max_length=300
        )

        self.add_item(self.embed_color)
        self.add_item(self.embed_image)
        self.add_item(self.embed_thumbnail)

    async def on_submit(self, interaction: discord.Interaction):
        color_input = self.embed_color.value.strip() or "#5865F2"
        image_url = self.embed_image.value.strip()
        thumbnail_url = self.embed_thumbnail.value.strip()

        try:
            int(color_input.replace("#", ""), 16)
        except ValueError:
            await interaction.response.send_message("❌ Ungültiger Farbcode. Beispiel: `#5865F2`", ephemeral=True)
            return

        for url, label in [(image_url, "Bild-URL"), (thumbnail_url, "Thumbnail-URL")]:
            if url and not url.startswith("http"):
                await interaction.response.send_message(f"❌ Ungültige {label}. Sie muss mit http beginnen.", ephemeral=True)
                return

        data = bewerbung_cache.get(interaction.user.id)
        if not data:
            await interaction.response.send_message("❌ Fehler beim Zwischenspeichern.", ephemeral=True)
            return

        data["embed_color"] = color_input
        data["embed_image"] = image_url or None
        data["embed_thumbnail"] = thumbnail_url or None

        bewerbung_cache.clear(interaction.user.id)

        logging.info(f"[Partnerbewerbung] Schritt 3 gespeichert für {interaction.user.id}")

        await interaction.response.defer()
        await save_and_send_bewerbung(self.bot, interaction, data, embed=True)

async def save_and_send_bewerbung(bot, interaction, data, embed):
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO partner_applications
                (user_id, thread_title, embed_title, embed_description, embed_color, embed_image, invite_link, ad_channel_id, projektart)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                interaction.user.id,
                data["thread_title"],
                data["thread_title"],
                data["werbetext"],
                data.get("embed_color") if embed else "#5865F2",
                data.get("embed_image") if embed else None,
                data["invite_link"],
                int(data["werbekanal_id"]),
                data["projektart"]
            ))
            await conn.commit()

    embed_preview = discord.Embed(title="📬 Neue Partnerbewerbung", color=discord.Color.blurple())
    embed_preview.add_field(name="Thread-Titel", value=data["thread_title"], inline=False)
    embed_preview.add_field(name="Projektart", value=data["projektart"], inline=True)
    embed_preview.add_field(name="Invite", value=data["invite_link"], inline=True)
    embed_preview.add_field(name="Werbekanal-ID", value=data["werbekanal_id"], inline=False)
    embed_preview.add_field(name="Werbetext", value=data["werbetext"][:1024], inline=False)
    if embed:
        embed_preview.add_field(name="Farbe", value=data.get("embed_color"), inline=True)
        embed_preview.add_field(name="Bild", value=data.get("embed_image") or "Keins", inline=True)
        embed_preview.add_field(name="Thumbnail", value=data.get("embed_thumbnail") or "Keins",
                                inline=True)  # HINZUGEFÜGT
        if data.get("embed_thumbnail"):  # Thumbnail wird auch visuell angezeigt
            embed_preview.set_thumbnail(url=data["embed_thumbnail"])

    view = AdminReviewView(bot, interaction.user.id)
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    await admin_channel.send(embed=embed_preview, view=view)
    await interaction.followup.send("✅ Deine Bewerbung wurde übermittelt!", ephemeral=True)


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
                await cur.execute("""
                    SELECT * FROM partner_applications 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (self.user_id,))
                row = await cur.fetchone()

        if not row:
            await interaction.response.send_message("❌ Keine Bewerbung gefunden.", ephemeral=True)
            return

        # Daten entpacken
        _, user_id, thread_title, embed_title, embed_description, embed_color, embed_image, invite, ad_channel_id, projektart, *_ = row

        forum = self.bot.get_channel(FORUM_CHANNEL_ID)
        tags = forum.available_tags
        main_tag = discord.utils.get(tags, name="Partner")
        project_tag = discord.utils.get(tags, name=projektart)

        # Tag-Reihenfolge: Partner zuerst
        used_tags = []
        if main_tag:
            used_tags.append(main_tag)
        if project_tag and project_tag != main_tag:
            used_tags.append(project_tag)

        # Embed vorbereiten
        embed = discord.Embed(
            title=embed_title,
            description=f"{embed_description.replace('\\n', '\n')}",
            color=int(embed_color.replace("#", ""), 16)
        )
        if embed_image and embed_image.startswith("http"):
            embed.set_image(url=embed_image)

        embed_thumbnail = row[11]
        if embed_thumbnail and embed_thumbnail.startswith("http"):
            embed.set_thumbnail(url=embed_thumbnail)

        # Thread im Forum erstellen
        await forum.create_thread(
            name=sanitize_thread_title(thread_title),
            content=f"{invite}",
            embed=embed,
            applied_tags=used_tags
        )

        # Astra-Werbung posten
        channel = self.bot.get_channel(int(ad_channel_id))
        if channel:
            try:
                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "SELECT title, description, invite_link, thumbnail, image FROM astra_ad_config LIMIT 1")
                        data = await cur.fetchone()
                if data:
                    a_title, a_desc, a_inv, a_thumb, a_img = data
                    astra_embed = discord.Embed(
                        title=a_title,
                        description=a_desc.replace("{invite}", a_inv),
                        color=discord.Color.blurple()
                    )
                    if a_thumb:
                        astra_embed.set_thumbnail(url=a_thumb)
                    if a_img:
                        astra_embed.set_image(url=a_img)
                    await channel.send(embed=astra_embed)
            except Exception as e:
                logging.error(f"Fehler beim Werbung posten: {e}")

        # Zeit updaten + Status speichern
        neue_zeit = int((datetime.datetime.now() + datetime.timedelta(hours=6)).timestamp())
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE partner_applications SET status = 'accepted' WHERE user_id = %s",
                                  (self.user_id,))
                await cur.execute("""
                    INSERT INTO partner_ad_config (ad_channel_id, time)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE time = %s
                """, (int(ad_channel_id), neue_zeit, neue_zeit))
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

        embed = discord.Embed(title=title, description=description.replace("\\n", "\n").replace("{invite}", invite), color=discord.Color.blurple())
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

    @app_commands.command(name="partnerbewerbung", description="Beginne deine Partnerbewerbung")
    @app_commands.choices(
        projektart=[
            app_commands.Choice(name="Discord", value="Discord"),
            app_commands.Choice(name="Bots", value="Bots"),
            app_commands.Choice(name="Webseite", value="Webseite"),
            app_commands.Choice(name="Community", value="Community")
        ],
        darstellung=[
            app_commands.Choice(name="Embed", value="embed"),
            app_commands.Choice(name="Einfacher Text", value="text")
        ]
    )
    async def partnerbewerbung(self, interaction: discord.Interaction, projektart: app_commands.Choice[str], darstellung: app_commands.Choice[str]):
        await interaction.response.send_modal(ModalErsterSchritt(self.bot, projektart.value, darstellung.value))

async def setup(bot):
    await bot.add_cog(Partner(bot))
