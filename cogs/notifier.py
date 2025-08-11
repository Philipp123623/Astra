# cogs/notifier.py
import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional

import aiohttp
import aiomysql
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

# Optional: falls du lokal lädst – sonst weglassen
load_dotenv(dotenv_path="/root/Astra/.env")

# --- Settings (keine DB-ENV; Pool kommt aus bot.pool) ---
POLL_INTERVAL_MINUTES = 5
WEBHOOK_NAME = "Astra-Notifier"

YOUTUBE_USE_RSS = False  # True = kein API-Key nötig
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams?user_login={login}"
TWITCH_CHANNEL_URL = "https://twitch.tv/{login}"

# --- Astra Look & Feel ---
ASTRA_COLOR = discord.Color.from_rgb(70, 130, 180)  # steel-blue artig
TWITCH_COLOR = discord.Color.from_rgb(145, 70, 255)  # Twitch-like
YOUTUBE_COLOR = discord.Color.from_rgb(230, 33, 23)  # YouTube-like

def astra_embed(
    *,
    title: str,
    description: str = "",
    color: discord.Color = ASTRA_COLOR,
    author: Optional[discord.abc.User] = None,
    guild: Optional[discord.Guild] = None,
    url: Optional[str] = None
) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color, url=url)
    e.timestamp = datetime.now(timezone.utc)
    if author:
        e.set_author(name=str(author), icon_url=getattr(author.display_avatar, "url", discord.Embed.Empty))
    if guild and guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="Astra Notifier • powered by Astra", icon_url=getattr(author.display_avatar, "url", "") if author else discord.Embed.Empty)
    return e


# =========================
#  COG: Notifier (Logik)
# =========================
class Notifier(commands.Cog):
    """YouTube-/Twitch-Notifier. Nutzt globalen DB-Pool: bot.pool"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(bot, "pool") or not isinstance(bot.pool, aiomysql.Pool):
            raise RuntimeError("Dieses Cog erwartet einen globalen aiomysql-Pool in bot.pool")
        self.pool: aiomysql.Pool = bot.pool

        self.http: Optional[aiohttp.ClientSession] = None
        self._webhook_cache: Dict[Tuple[int, int], discord.Webhook] = {}

        # Twitch Token Cache
        self._twitch_token: Optional[str] = None
        self._twitch_token_expire: Optional[datetime] = None

        # Background Task
        self.check_for_updates.change_interval(minutes=POLL_INTERVAL_MINUTES)
        self.check_for_updates.start()

    async def cog_load(self):
        self.http = aiohttp.ClientSession()
        await self._ensure_tables()

    async def cog_unload(self):
        self.check_for_updates.cancel()
        if self.http:
            await self.http.close()

    # ---------- Öffentliche Helper, die von der Command-Group genutzt werden ----------
    async def subscribe(self, guild_id: int, platform: str, channel_id: int, content_id: str):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO subscriptions (guild_id, discord_channel_id, platform, content_id)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE content_id = VALUES(content_id)
                """,
                (str(guild_id), str(channel_id), platform, content_id),
            )
            await conn.commit()

    # ---------- Background Task ----------
    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def check_for_updates(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT guild_id, discord_channel_id, platform, content_id FROM subscriptions")
            subs = await cur.fetchall()

        for guild_id, channel_id, platform, content_id in subs:
            try:
                if platform == "youtube":
                    await self._check_youtube(content_id, int(guild_id), int(channel_id))
                elif platform == "twitch":
                    await self._check_twitch(content_id, int(guild_id), int(channel_id))
            except Exception as e:
                # hübsches Logging
                g = self.bot.get_guild(int(guild_id))
                guild_name = f"{g.name} ({g.id})" if g else str(guild_id)
                print(f"[Notifier] Fehler bei {platform}:{content_id} in {guild_name} → {e}")

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    # ---------- Plattform-Checks ----------
    async def _check_youtube(self, channel_id: str, guild_id: int, discord_channel_id: int):
        published_after = (datetime.now(timezone.utc) - timedelta(minutes=5))

        if YOUTUBE_USE_RSS:
            url = YOUTUBE_RSS_URL.format(channel_id=channel_id)
            async with self.http.get(url) as resp:
                xml = await resp.text()
            import re
            entries = re.findall(
                r"<yt:videoId>(.*?)</yt:videoId>.*?<published>(.*?)</published>.*?<title>(.*?)</title>",
                xml, flags=re.S
            )
            for vid, published, title in entries:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if pub_dt > published_after:
                    await self._send_webhook(
                        guild_id,
                        discord_channel_id,
                        title=f"🎥 Neues Video: {title}",
                        description=f"Ein neues Video ist online!",
                        thumbnail="",
                        url=YOUTUBE_VIDEO_URL.format(video_id=vid),
                        color=YOUTUBE_COLOR
                    )
        else:
            params = {
                "part": "snippet",
                "channelId": channel_id,
                "order": "date",
                "type": "video",
                "publishedAfter": published_after.isoformat().replace("+00:00", "Z"),
                "key": YOUTUBE_API_KEY,
            }
            async with self.http.get(YOUTUBE_SEARCH_URL, params=params) as resp:
                data = await resp.json()
            for item in data.get("items", []):
                vid = item["id"]["videoId"]
                title = item["snippet"]["title"]
                desc = item["snippet"].get("description", "")
                thumb = item["snippet"]["thumbnails"].get("high", item["snippet"]["thumbnails"].get("default", {})).get("url", "")
                await self._send_webhook(
                    guild_id,
                    discord_channel_id,
                    title=f"🎥 Neues Video: {title}",
                    description=desc or "Ein neues Video ist online!",
                    thumbnail=thumb,
                    url=YOUTUBE_VIDEO_URL.format(video_id=vid),
                    color=YOUTUBE_COLOR
                )

    async def _check_twitch(self, login: str, guild_id: int, discord_channel_id: int):
        token = await self._get_twitch_token()
        headers = {"Client-Id": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
        async with self.http.get(TWITCH_STREAMS_URL.format(login=login), headers=headers) as resp:
            data = await resp.json()
        streams = data.get("data", [])
        if not streams:
            return
        s = streams[0]
        title = s.get("title", f"{login} ist live!")
        thumb = s["thumbnail_url"].replace("{width}", "1920").replace("{height}", "1080")

        await self._send_webhook(
            guild_id,
            discord_channel_id,
            title=f"🟣 {login} ist jetzt LIVE",
            description=title,
            thumbnail=thumb,
            url=TWITCH_CHANNEL_URL.format(login=login),
            color=TWITCH_COLOR
        )

    # ---------- Versand ----------
    async def _send_webhook(self, guild_id: int, channel_id: int, title: str, description: str, thumbnail: str, url: str, color: discord.Color = ASTRA_COLOR):
        webhook = await self._get_or_create_webhook(guild_id, channel_id)
        # schöner Embed
        e = discord.Embed(title=title, description=(description or "")[:2000], url=url, color=color)
        e.timestamp = datetime.now(timezone.utc)
        if thumbnail:
            e.set_image(url=thumbnail)  # hero look statt kleiner thumb
        e.set_footer(text="Astra Notifier • Jetzt reinschauen!")
        await webhook.send(embed=e)

    async def _get_or_create_webhook(self, guild_id: int, channel_id: int):
        key = (guild_id, channel_id)
        if key in self._webhook_cache:
            return self._webhook_cache[key]
        guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
        channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
        for wh in await channel.webhooks():
            if wh.name == WEBHOOK_NAME:
                self._webhook_cache[key] = wh
                return wh
        wh = await channel.create_webhook(name=WEBHOOK_NAME, reason="Astra Notifier")
        self._webhook_cache[key] = wh
        return wh

    async def _get_twitch_token(self):
        now = datetime.now(timezone.utc)
        if self._twitch_token and self._twitch_token_expire and self._twitch_token_expire > now + timedelta(minutes=2):
            return self._twitch_token
        data = {"client_id": TWITCH_CLIENT_ID, "client_secret": TWITCH_CLIENT_SECRET, "grant_type": "client_credentials"}
        async with self.http.post(TWITCH_TOKEN_URL, data=data) as resp:
            token_data = await resp.json()
        self._twitch_token = token_data["access_token"]
        self._twitch_token_expire = now + timedelta(seconds=int(token_data.get("expires_in", 3600)))
        return self._twitch_token

    async def _ensure_tables(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    guild_id BIGINT,
                    discord_channel_id BIGINT,
                    platform ENUM('youtube','twitch'),
                    content_id VARCHAR(255),
                    PRIMARY KEY (guild_id, discord_channel_id, platform, content_id)
                )
            """)
            await conn.commit()


# ==========================================
#  Command-Group außerhalb des Cogs
#  /benachrichtigung youtube | twitch
# ==========================================
class Benachrichtigung(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="benachrichtigung", description="Benachrichtigungen für YouTube & Twitch")
        self.bot = bot

    @app_commands.command(name="youtube", description="YouTube-Kanal abonnieren (Channel-ID: UC...)")
    @app_commands.guild_only()
    async def youtube(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        youtube_channel_id: str
    ):
        cog: Optional[Notifier] = interaction.client.get_cog("Notifier")  # type: ignore
        if not cog:
            em = astra_embed(
                title="❌ Notifier nicht bereit",
                description="Bitte versuche es gleich erneut.",
                author=interaction.user, guild=interaction.guild
            )
            return await interaction.response.send_message(embed=em, ephemeral=True)

        await cog.subscribe(interaction.guild_id, "youtube", channel.id, youtube_channel_id)
        em = astra_embed(
            title="✅ YouTube-Abo gesetzt",
            description=(
                f"**Kanal:** `{youtube_channel_id}`\n"
                f"**Ziel:** {channel.mention}\n"
                f"**Modus:** {'RSS' if YOUTUBE_USE_RSS else 'YouTube Data API'}"
            ),
            color=YOUTUBE_COLOR,
            author=interaction.user,
            guild=interaction.guild
        )
        await interaction.response.send_message(embed=em, ephemeral=True)

    @app_commands.command(name="twitch", description="Twitch-Channel abonnieren (Login-Name)")
    @app_commands.guild_only()
    async def twitch(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        twitch_login: str
    ):
        cog: Optional[Notifier] = interaction.client.get_cog("Notifier")  # type: ignore
        if not cog:
            em = astra_embed(
                title="❌ Notifier nicht bereit",
                description="Bitte versuche es gleich erneut.",
                author=interaction.user, guild=interaction.guild
            )
            return await interaction.response.send_message(embed=em, ephemeral=True)

        await cog.subscribe(interaction.guild_id, "twitch", channel.id, twitch_login.lower())
        em = astra_embed(
            title="✅ Twitch-Abo gesetzt",
            description=(
                f"**Channel:** `{twitch_login.lower()}`\n"
                f"**Ziel:** {channel.mention}"
            ),
            color=TWITCH_COLOR,
            author=interaction.user,
            guild=interaction.guild
        )
        await interaction.response.send_message(embed=em, ephemeral=True)


# ===============
#  setup() Hook
# ===============
async def setup(bot: commands.Bot):
    # Cog mit Logik laden
    await bot.add_cog(Notifier(bot))

    # Slash-Group registrieren (außerhalb des Cogs)
    try:
        bot.tree.add_command(Benachrichtigung(bot))
    except Exception:
        # doppelte Registrierung im Reload vermeiden
        pass
