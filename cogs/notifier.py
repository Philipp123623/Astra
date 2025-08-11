import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional, Literal

import aiohttp
import aiomysql
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

load_dotenv(dotenv_path="/root/Astra/.env")

POLL_INTERVAL_MINUTES = 5
WEBHOOK_NAME = "Astra-Notifier"

YOUTUBE_USE_RSS = False
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams?user_login={login}"
TWITCH_CHANNEL_URL = "https://twitch.tv/{login}"

ASTRA_COLOR = discord.Color.from_rgb(70, 130, 180)
TWITCH_COLOR = discord.Color.from_rgb(145, 70, 255)
YOUTUBE_COLOR = discord.Color.from_rgb(230, 33, 23)

def astra_embed(
    *, title: str, description: str = "", color: discord.Color = ASTRA_COLOR,
    author: Optional[discord.abc.User] = None, guild: Optional[discord.Guild] = None, url: Optional[str] = None
) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color, url=url)
    e.timestamp = datetime.now(timezone.utc)
    if author:
        e.set_author(name=str(author), icon_url=getattr(author.display_avatar, "url", discord.Embed.Empty))
    if guild and guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="Astra Notifier • powered by Astra",
                 icon_url=getattr(author.display_avatar, "url", "") if author else discord.Embed.Empty)
    return e


class Notifier(commands.Cog):

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

    async def subscribe(self, guild_id: int, platform: str, channel_name: str, content_id: str):
        """Speichert Abo (per Channel-Name)."""
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO subscriptions (guild_id, discord_channel_name, platform, content_id)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE content_id = VALUES(content_id)
                """,
                (str(guild_id), channel_name, platform, content_id),
            )
            await conn.commit()

    async def set_enabled(self, guild_id: int, platform: str, enabled: bool):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO notifier_settings (guild_id, platform, enabled)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE enabled = VALUES(enabled)
                """,
                (str(guild_id), platform, 1 if enabled else 0),
            )
            await conn.commit()

    async def is_enabled(self, guild_id: int, platform: str) -> bool:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT enabled FROM notifier_settings WHERE guild_id=%s AND platform=%s",
                (str(guild_id), platform),
            )
            row = await cur.fetchone()
        return True if row is None else bool(row[0])

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def check_for_updates(self):
        # alle Abos laden
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT guild_id, discord_channel_name, platform, content_id FROM subscriptions")
            subs = await cur.fetchall()

        for guild_id, channel_name, platform, content_id in subs:
            try:
                if not await self.is_enabled(int(guild_id), platform):
                    continue
                if platform == "youtube":
                    await self._check_youtube(content_id, int(guild_id), str(channel_name))
                elif platform == "twitch":
                    await self._check_twitch(content_id, int(guild_id), str(channel_name))
            except Exception as e:
                g = self.bot.get_guild(int(guild_id))
                guild_name = f"{g.name} ({g.id})" if g else str(guild_id)
                print(f"[Notifier] Fehler bei {platform}:{content_id} in {guild_name} → {e}")

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    async def _resolve_text_channel(self, guild: discord.Guild, channel_name: str) -> Optional[discord.TextChannel]:
        # exakte Übereinstimmung zuerst
        matches = [c for c in guild.text_channels if c.name == channel_name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # nimm die mit geringster Position (oben in der Liste)
            return sorted(matches, key=lambda c: (c.category.position if c.category else -1, c.position))[0]
        # case-insensitive fallback
        ci = [c for c in guild.text_channels if c.name.lower() == channel_name.lower()]
        if ci:
            return sorted(ci, key=lambda c: (c.category.position if c.category else -1, c.position))[0]
        return None

    async def _check_youtube(self, yt_channel_id: str, guild_id: int, target_channel_name: str):
        guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
        target = await self._resolve_text_channel(guild, target_channel_name)
        if not target:
            return  # Kanal existiert nicht (mehr)

        published_after = (datetime.now(timezone.utc) - timedelta(minutes=5))

        if YOUTUBE_USE_RSS:
            url = YOUTUBE_RSS_URL.format(channel_id=yt_channel_id)
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
                        target, title=f"🎥 Neues Video: {title}",
                        description="Ein neues Video ist online!",
                        thumbnail="",
                        url=YOUTUBE_VIDEO_URL.format(video_id=vid),
                        color=YOUTUBE_COLOR
                    )
        else:
            if not YOUTUBE_API_KEY:
                # Keine API-Creds -> nichts tun
                return
            params = {
                "part": "snippet",
                "channelId": yt_channel_id,
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
                    target, title=f"🎥 Neues Video: {title}",
                    description=desc or "Ein neues Video ist online!",
                    thumbnail=thumb, url=YOUTUBE_VIDEO_URL.format(video_id=vid),
                    color=YOUTUBE_COLOR
                )

    async def _check_twitch(self, login: str, guild_id: int, target_channel_name: str):
        guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
        target = await self._resolve_text_channel(guild, target_channel_name)
        if not target:
            return

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
            target,
            title=f"🟣 {login} ist jetzt LIVE",
            description=title,
            thumbnail=thumb,
            url=TWITCH_CHANNEL_URL.format(login=login),
            color=TWITCH_COLOR
        )

    async def _send_webhook(self, channel: discord.TextChannel, *, title: str, description: str, thumbnail: str, url: str, color: discord.Color):
        webhook = await self._get_or_create_webhook(channel.guild.id, channel.id)
        e = discord.Embed(title=title, description=(description or "")[:2000], url=url, color=color)
        e.timestamp = datetime.now(timezone.utc)
        if thumbnail:
            e.set_image(url=thumbnail)
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
        if not (TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET):
            return ""  # kein Twitch
        data = {"client_id": TWITCH_CLIENT_ID, "client_secret": TWITCH_CLIENT_SECRET, "grant_type": "client_credentials"}
        async with self.http.post(TWITCH_TOKEN_URL, data=data) as resp:
            token_data = await resp.json()
        self._twitch_token = token_data.get("access_token", "")
        self._twitch_token_expire = now + timedelta(seconds=int(token_data.get("expires_in", 3600)))
        return self._twitch_token

    async def _ensure_tables(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            # Channel-Name statt ID speichern
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    guild_id BIGINT NOT NULL,
                    discord_channel_name VARCHAR(255) NOT NULL,
                    platform ENUM('youtube','twitch') NOT NULL,
                    content_id VARCHAR(255) NOT NULL,
                    PRIMARY KEY (guild_id, discord_channel_name, platform, content_id)
                )
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS notifier_settings (
                    guild_id BIGINT NOT NULL,
                    platform ENUM('youtube','twitch') NOT NULL,
                    enabled TINYINT(1) NOT NULL DEFAULT 1,
                    PRIMARY KEY (guild_id, platform)
                )
            """)
            await conn.commit()

class Benachrichtigung(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="benachrichtigung", description="Benachrichtigungen für YouTube & Twitch")
        self.bot = bot

    @app_commands.command(name="youtube", description="YouTube-Kanal abonnieren (Channel-ID: UC...)")
    @app_commands.guild_only()
    async def youtube(
        self,
        interaction: discord.Interaction,
        channel_name: str,
        youtube_channel_id: str
    ):
        cog: Optional[Notifier] = interaction.client.get_cog("Notifier")  # type: ignore
        if not cog:
            em = astra_embed(title="❌ Notifier nicht bereit", description="Bitte versuche es gleich erneut.",
                             author=interaction.user, guild=interaction.guild)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        # Validierung: gibt's den Kanal?
        target = await cog._resolve_text_channel(interaction.guild, channel_name)
        if not target:
            em = astra_embed(title="❌ Kanal nicht gefunden",
                             description=f"Ich konnte keinen Textkanal namens **#{channel_name}** finden.",
                             author=interaction.user, guild=interaction.guild)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        await cog.subscribe(interaction.guild_id, "youtube", channel_name, youtube_channel_id)
        em = astra_embed(
            title="✅ YouTube-Abo gesetzt",
            description=(f"**Kanal-ID:** `{youtube_channel_id}`\n**Ziel:** {target.mention}\n"
                         f"**Modus:** {'RSS' if YOUTUBE_USE_RSS else 'YouTube Data API'}"),
            color=YOUTUBE_COLOR, author=interaction.user, guild=interaction.guild
        )
        await interaction.response.send_message(embed=em, ephemeral=True)
        return None

    @app_commands.command(name="twitch", description="Twitch-Channel abonnieren (Login-Name)")
    @app_commands.guild_only()
    async def twitch(
        self,
        interaction: discord.Interaction,
        channel_name: str,
        twitch_login: str
    ):
        cog: Optional[Notifier] = interaction.client.get_cog("Notifier")  # type: ignore
        if not cog:
            em = astra_embed(title="❌ Notifier nicht bereit", description="Bitte versuche es gleich erneut.",
                             author=interaction.user, guild=interaction.guild)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        target = await cog._resolve_text_channel(interaction.guild, channel_name)
        if not target:
            em = astra_embed(title="❌ Kanal nicht gefunden",
                             description=f"Ich konnte keinen Textkanal namens **#{channel_name}** finden.",
                             author=interaction.user, guild=interaction.guild)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        await cog.subscribe(interaction.guild_id, "twitch", channel_name, twitch_login.lower())
        em = astra_embed(
            title="✅ Twitch-Abo gesetzt",
            description=(f"**Login:** `{twitch_login.lower()}`\n**Ziel:** {target.mention}"),
            color=TWITCH_COLOR, author=interaction.user, guild=interaction.guild
        )
        await interaction.response.send_message(embed=em, ephemeral=True)
        return None

    @app_commands.command(name="schalter", description="Notifier pro Plattform ein-/ausschalten")
    @app_commands.guild_only()
    async def schalter(
        self,
        interaction: discord.Interaction,
        platform: Literal["youtube", "twitch"],
        status: Literal["an", "aus"]
    ):
        cog: Optional[Notifier] = interaction.client.get_cog("Notifier")  # type: ignore
        if not cog:
            em = astra_embed(title="❌ Notifier nicht bereit", description="Bitte versuche es gleich erneut.",
                             author=interaction.user, guild=interaction.guild)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        enabled = (status == "an")
        await cog.set_enabled(interaction.guild_id, platform, enabled)

        color = YOUTUBE_COLOR if platform == "youtube" else TWITCH_COLOR
        em = astra_embed(
            title=f"🔧 {platform.capitalize()} Benachrichtigungen",
            description=f"**Status:** {'🟢 Aktiv' if enabled else '🔴 Deaktiviert'}",
            color=color, author=interaction.user, guild=interaction.guild
        )
        await interaction.response.send_message(embed=em, ephemeral=True)
        return None


async def setup(bot: commands.Bot):
    await bot.add_cog(Notifier(bot))
    try:
        bot.tree.add_command(Benachrichtigung(bot))
    except Exception:
        pass
