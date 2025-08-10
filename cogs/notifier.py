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

load_dotenv(dotenv_path="/root/Astra/.env")
# Einstellungen
POLL_INTERVAL_MINUTES = 5
WEBHOOK_NAME = "Astra-Notifier"

YOUTUBE_USE_RSS = False  # Falls False, YOUTUBE_API_KEY nutzen
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams?user_login={login}"
TWITCH_CHANNEL_URL = "https://twitch.tv/{login}"


class Notifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool: aiomysql.Pool = bot.pool
        self.http: Optional[aiohttp.ClientSession] = None
        self._webhook_cache: Dict[Tuple[int, int], discord.Webhook] = {}
        self._twitch_token = None
        self._twitch_token_expire = None
        self.check_for_updates.start()

    async def cog_load(self):
        self.http = aiohttp.ClientSession()
        await self._ensure_tables()

    async def cog_unload(self):
        self.check_for_updates.cancel()
        if self.http:
            await self.http.close()

    @app_commands.command(name="subscribe_youtube")
    async def subscribe_youtube(self, interaction: discord.Interaction, channel: discord.TextChannel, youtube_channel_id: str):
        await self._subscribe(interaction, "youtube", channel.id, youtube_channel_id)

    @app_commands.command(name="subscribe_twitch")
    async def subscribe_twitch(self, interaction: discord.Interaction, channel: discord.TextChannel, twitch_login: str):
        await self._subscribe(interaction, "twitch", channel.id, twitch_login.lower())

    async def _subscribe(self, interaction, platform, channel_id, content_id):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO subscriptions (guild_id, discord_channel_id, platform, content_id)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE content_id = VALUES(content_id)
            """, (str(interaction.guild_id), str(channel_id), platform, content_id))
            await conn.commit()
        await interaction.response.send_message(f"✅ {platform} Abo für `{content_id}` gesetzt → <#{channel_id}>", ephemeral=True)

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
                print(f"[Notifier] Fehler: {e}")

    async def _check_youtube(self, channel_id, guild_id, discord_channel_id):
        published_after = (datetime.now(timezone.utc) - timedelta(minutes=5))
        if YOUTUBE_USE_RSS:
            url = YOUTUBE_RSS_URL.format(channel_id=channel_id)
            async with self.http.get(url) as resp:
                xml = await resp.text()
            import re
            entries = re.findall(
                r"<yt:videoId>(.*?)</yt:videoId>.*?<published>(.*?)</published>.*?<title>(.*?)</title>",
                xml, flags=re.S)
            for vid, published, title in entries:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if pub_dt > published_after:
                    await self._send_webhook(guild_id, discord_channel_id, title, "", "", YOUTUBE_VIDEO_URL.format(video_id=vid))
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
                thumb = item["snippet"]["thumbnails"]["high"]["url"]
                await self._send_webhook(guild_id, discord_channel_id, title, desc, thumb, YOUTUBE_VIDEO_URL.format(video_id=vid))

    async def _check_twitch(self, login, guild_id, discord_channel_id):
        token = await self._get_twitch_token()
        headers = {"Client-Id": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
        async with self.http.get(TWITCH_STREAMS_URL.format(login=login), headers=headers) as resp:
            data = await resp.json()
        streams = data.get("data", [])
        if streams:
            s = streams[0]
            title = s["title"]
            thumb = s["thumbnail_url"].replace("{width}", "1920").replace("{height}", "1080")
            await self._send_webhook(guild_id, discord_channel_id, title, "Streamer ist live!", thumb, TWITCH_CHANNEL_URL.format(login=login))

    async def _send_webhook(self, guild_id, channel_id, title, description, thumbnail, url):
        webhook = await self._get_or_create_webhook(guild_id, channel_id)
        embed = discord.Embed(title=title, description=description[:2000], url=url, color=discord.Color.blurple())
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        await webhook.send(embed=embed)

    async def _get_or_create_webhook(self, guild_id, channel_id):
        key = (guild_id, channel_id)
        if key in self._webhook_cache:
            return self._webhook_cache[key]
        guild = self.bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id)
        for wh in await channel.webhooks():
            if wh.name == WEBHOOK_NAME:
                self._webhook_cache[key] = wh
                return wh
        wh = await channel.create_webhook(name=WEBHOOK_NAME)
        self._webhook_cache[key] = wh
        return wh

    async def _get_twitch_token(self):
        if self._twitch_token and self._twitch_token_expire > datetime.now(timezone.utc):
            return self._twitch_token
        data = {"client_id": TWITCH_CLIENT_ID, "client_secret": TWITCH_CLIENT_SECRET, "grant_type": "client_credentials"}
        async with self.http.post(TWITCH_TOKEN_URL, data=data) as resp:
            token_data = await resp.json()
        self._twitch_token = token_data["access_token"]
        self._twitch_token_expire = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])
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
                )""")
            await conn.commit()


async def setup(bot):
    await bot.add_cog(Notifier(bot))
