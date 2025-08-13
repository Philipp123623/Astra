import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional, Literal, List

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
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams?user_login={login}"
TWITCH_CHANNEL_URL = "https://twitch.tv/{login}"

# 1) Standardfarbe auf discord.Colour.blue() umgestellt
ASTRA_COLOR = discord.Colour.blue()
TWITCH_COLOR = discord.Colour.from_rgb(145, 70, 255)
YOUTUBE_COLOR = discord.Colour.from_rgb(230, 33, 23)


def astra_embed(*, title: str, description: str = "", color: discord.Colour = ASTRA_COLOR,
                author: Optional[discord.abc.User] = None, guild: Optional[discord.Guild] = None,
                url: Optional[str] = None) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color, url=url)
    e.timestamp = datetime.now(timezone.utc)
    if author:
        e.set_author(name=str(author), icon_url=author.display_avatar.url)
    if guild and guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    if author:
        e.set_footer(text="Astra Notifier • powered by Astra", icon_url=author.display_avatar.url)
    else:
        e.set_footer(text="Astra Notifier • powered by Astra")
    return e


# Hilfsfunktionen für YouTube
def _format_iso8601_duration(iso: str) -> str:
    # Erwartet z.B. "PT1H2M3S", "PT9M5S", "PT42S"
    hours = minutes = seconds = 0
    cur = ""
    num = ""
    for ch in iso:
        if ch.isdigit():
            num += ch
            continue
        if ch in "HMS":
            val = int(num) if num else 0
            if ch == "H":
                hours = val
            elif ch == "M":
                minutes = val
            elif ch == "S":
                seconds = val
            num = ""
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


class Notifier(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(bot, "pool") or not isinstance(bot.pool, aiomysql.Pool):
            raise RuntimeError("Dieses Cog erwartet einen globalen aiomysql-Pool in bot.pool")
        self.pool: aiomysql.Pool = bot.pool
        self.http: Optional[aiohttp.ClientSession] = None
        self._webhook_cache: Dict[Tuple[int, int], discord.Webhook] = {}
        self._twitch_token: Optional[str] = None
        self._twitch_token_expire: Optional[datetime] = None
        self.check_for_updates.change_interval(minutes=POLL_INTERVAL_MINUTES)
        self.check_for_updates.start()

    async def cog_load(self):
        self.http = aiohttp.ClientSession()

    async def cog_unload(self):
        self.check_for_updates.cancel()
        if self.http:
            await self.http.close()

    async def subscribe(self, guild_id: int, platform: str, channel_name: str, content_id: str, ping_role_id: Optional[int] = None):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO subscriptions (guild_id, discord_channel_name, platform, content_id, ping_role_id)
                VALUES (%s, %s, %s, %s, %s) AS new
                ON DUPLICATE KEY UPDATE content_id = new.content_id, ping_role_id = new.ping_role_id
                """,
                (str(guild_id), channel_name, platform, content_id, ping_role_id),
            )

    async def delete_subscription(self, guild_id: int, platform: str, channel_name: str, content_id: str) -> int:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM subscriptions WHERE guild_id=%s AND platform=%s AND discord_channel_name=%s AND content_id=%s",
                (str(guild_id), platform, channel_name, content_id),
            )
            return cur.rowcount

    async def set_enabled(self, guild_id: int, platform: str, enabled: bool):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO notifier_settings (guild_id, platform, enabled)
                VALUES (%s, %s, %s) AS new
                ON DUPLICATE KEY UPDATE enabled = new.enabled
                """,
                (str(guild_id), platform, 1 if enabled else 0),
            )

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
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT guild_id, discord_channel_name, platform, content_id, ping_role_id FROM subscriptions")
            subs = await cur.fetchall()
        for guild_id, channel_name, platform, content_id, ping_role_id in subs:
            try:
                if not await self.is_enabled(int(guild_id), platform):
                    continue
                if platform == "youtube":
                    await self._check_youtube(content_id, int(guild_id), str(channel_name), ping_role_id)
                elif platform == "twitch":
                    await self._check_twitch(content_id, int(guild_id), str(channel_name), ping_role_id)
            except Exception as e:
                g = self.bot.get_guild(int(guild_id))
                guild_name = f"{g.name} ({g.id})" if g else str(guild_id)
                print(f"[Notifier] Fehler bei {platform}:{content_id} in {guild_name} → {e}")

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    async def _resolve_text_channel(self, guild: discord.Guild, channel_name: str) -> Optional[discord.TextChannel]:
        matches = [c for c in guild.text_channels if c.name == channel_name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return sorted(matches, key=lambda c: (c.category.position if c.category else -1, c.position))[0]
        ci = [c for c in guild.text_channels if c.name.lower() == channel_name.lower()]
        if ci:
            return sorted(ci, key=lambda c: (c.category.position if c.category else -1, c.position))[0]
        return None

    async def _resolve_youtube_channel_id(self, raw: str) -> Optional[str]:
        s = raw.strip()
        if s.startswith("UC") and len(s) >= 16:
            return s
        if s.startswith("@"):
            if not YOUTUBE_API_KEY:
                return None
            params = {"part": "id", "forHandle": s, "key": YOUTUBE_API_KEY}
            async with self.http.get(YOUTUBE_CHANNELS_URL, params=params) as resp:
                data = await resp.json()
            items = data.get("items", [])
            return items[0]["id"] if items else None
        if "youtube.com" in s or "youtu.be" in s:
            from urllib.parse import urlparse
            p = urlparse(s)
            parts = [x for x in p.path.split("/") if x]
            if len(parts) >= 2 and parts[0].lower() == "channel" and parts[1].startswith("UC"):
                return parts[1]
            if parts and parts[0].startswith("@"):
                return await self._resolve_youtube_channel_id(parts[0])
        if not YOUTUBE_API_KEY:
            return None
        params = {"part": "snippet", "q": s, "type": "channel", "maxResults": 1, "key": YOUTUBE_API_KEY}
        async with self.http.get(YOUTUBE_SEARCH_URL, params=params) as resp:
            data = await resp.json()
        items = data.get("items", [])
        return items[0]["id"]["channelId"] if items else None

    # Zusätzliche Details für YouTube (Dauer/Views + Kanal-Icon)
    async def _get_youtube_video_details(self, video_id: str) -> Dict[str, str]:
        if not YOUTUBE_API_KEY:
            return {}
        params = {
            "part": "contentDetails,statistics,snippet",
            "id": video_id,
            "key": YOUTUBE_API_KEY,
            "maxResults": 1,
        }
        async with self.http.get(YOUTUBE_VIDEOS_URL, params=params) as resp:
            data = await resp.json()
        items = data.get("items", [])
        if not items:
            return {}
        it = items[0]
        details = it.get("contentDetails", {})
        stats = it.get("statistics", {})
        snip = it.get("snippet", {})
        duration = _format_iso8601_duration(details.get("duration", "")) if details.get("duration") else "—"
        views = stats.get("viewCount")
        ch_thumb = snip.get("thumbnails", {}).get("high", snip.get("thumbnails", {}).get("default", {})).get("url")
        return {"duration": duration, "views": views, "channel_thumb": ch_thumb}

    async def _check_youtube(self, yt_channel_id: str, guild_id: int, target_channel_name: str, ping_role_id: Optional[int]):
        guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
        target = await self._resolve_text_channel(guild, target_channel_name)
        if not target:
            return
        published_after = (datetime.now(timezone.utc) - timedelta(minutes=POLL_INTERVAL_MINUTES))
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
                        target,
                        title=f"🎥 Neues Video: {title}",
                        description="Ein neues Video ist online!",
                        thumbnail="",
                        url=YOUTUBE_VIDEO_URL.format(video_id=vid),
                        color=YOUTUBE_COLOR,
                        ping_role_id=ping_role_id,
                    )
        else:
            if not YOUTUBE_API_KEY:
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
                snip = item["snippet"]
                title = snip["title"]
                desc = snip.get("description", "")
                thumb = snip["thumbnails"].get("high", snip["thumbnails"].get("default", {})).get("url", "")
                channel_title = snip.get("channelTitle", "YouTube")
                published_at = snip.get("publishedAt")

                details = await self._get_youtube_video_details(vid)
                fields = {
                    "Kanal": channel_title,
                    "Veröffentlicht": published_at.replace("T", " ").replace("Z", " UTC") if published_at else "—",
                    "Dauer": details.get("duration", "—"),
                    "Aufrufe": details.get("views", "—"),
                }
                await self._send_webhook(
                    target,
                    title=f"🎥 Neues Video: {title}",
                    description=(desc or "Ein neues Video ist online!")[:500],
                    thumbnail=thumb,
                    url=YOUTUBE_VIDEO_URL.format(video_id=vid),
                    color=YOUTUBE_COLOR,
                    ping_role_id=ping_role_id,
                    author=(channel_title, details.get("channel_thumb")),
                    fields=fields,
                )

    async def _check_twitch(self, login: str, guild_id: int, target_channel_name: str, ping_role_id: Optional[int]):
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
        fields = {
            "Spiel": s.get("game_name") or "—",
            "Zuschauer": str(s.get("viewer_count", "—")),
            "Gestartet": s.get("started_at", "—").replace("T", " ").replace("Z", " UTC"),
            "Sprache": s.get("language", "—"),
        }
        await self._send_webhook(
            target,
            title=f"🟣 {login} ist jetzt LIVE",
            description=title,
            thumbnail=thumb,
            url=TWITCH_CHANNEL_URL.format(login=login),
            color=TWITCH_COLOR,
            ping_role_id=ping_role_id,
            author=(login, None),
            fields=fields,
        )

    async def _send_webhook(self, channel: discord.TextChannel, *, title: str, description: str, thumbnail: str, url: str, color: discord.Colour, ping_role_id: Optional[int] = None, author: Optional[Tuple[str, Optional[str]]] = None, fields: Optional[Dict[str, str]] = None):
        webhook = await self._get_or_create_webhook(channel.guild.id, channel.id)
        e = discord.Embed(title=title, description=(description or "")[:2000], url=url, color=color)
        e.timestamp = datetime.now(timezone.utc)
        if thumbnail:
            e.set_image(url=thumbnail)
        if author:
            name, icon = author
            if name:
                if icon:
                    e.set_author(name=name, icon_url=icon)
                else:
                    e.set_author(name=name)
        if fields:
            # schön kompakt als Inline-Felder
            for k, v in fields.items():
                e.add_field(name=str(k), value=str(v) if v is not None else "—", inline=True)
        e.set_footer(text="Astra Notifier • Jetzt reinschauen!")
        content = None
        allowed = discord.AllowedMentions(roles=True)
        if ping_role_id:
            role = channel.guild.get_role(int(ping_role_id))
            if role:
                content = role.mention
        await webhook.send(embed=e, content=content, allowed_mentions=allowed)

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
            return ""
        data = {"client_id": TWITCH_CLIENT_ID, "client_secret": TWITCH_CLIENT_SECRET, "grant_type": "client_credentials"}
        async with self.http.post(TWITCH_TOKEN_URL, data=data) as resp:
            token_data = await resp.json()
        self._twitch_token = token_data.get("access_token", "")
        self._twitch_token_expire = now + timedelta(seconds=int(token_data.get("expires_in", 3600)))
        return self._twitch_token


@app_commands.guild_only()
class Benachrichtigung(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="benachrichtigung", description="Benachrichtigungen für YouTube & Twitch")
        self.bot = bot

    @app_commands.command(name="youtube", description="YouTube-Kanal hinzufügen oder entfernen")
    @app_commands.describe( aktion="Hinzufügen oder Entfernen", channel="Discord-Kanal für Benachrichtigungen", channelname="YouTube-Channel (ID/Handle/URL/Name)", rolle="(Optional) Rolle, die gepingt wird")
    @app_commands.guild_only()
    async def youtube(self, interaction: discord.Interaction, aktion: Literal["Hinzufügen", "Entfernen"], channel: discord.TextChannel, channelname: str, rolle: Optional[discord.Role] = None):
        cog: Optional[Notifier] = interaction.client.get_cog("Notifier")  # type: ignore
        if not cog:
            return await interaction.response.send_message(embed=astra_embed(
                title="❌ Notifier nicht bereit", description="Bitte versuche es gleich erneut.",
                author=interaction.user, guild=interaction.guild
            ), ephemeral=True)

        if aktion == "Hinzufügen":
            yt_id = await cog._resolve_youtube_channel_id(channelname) or channelname
            await cog.subscribe(interaction.guild_id, "youtube", channel.name, yt_id, rolle.id if rolle else None)
            await cog.set_enabled(interaction.guild_id, "youtube", True)
            await interaction.response.send_message(embed=astra_embed(
                title="✅ YouTube-Abo hinzugefügt",
                description=f"**Channel:** `{channelname}` → `{yt_id}`\n**Ziel:** {channel.mention}\n**Ping:** {rolle.mention if rolle else '—'}\n**Modus:** {'RSS' if YOUTUBE_USE_RSS else 'YouTube Data API'}",
                color=YOUTUBE_COLOR, author=interaction.user, guild=interaction.guild
            ), ephemeral=True)
        else:
            await cog.delete_subscription(interaction.guild_id, "youtube", channel.name, channelname)
            await interaction.response.send_message(embed=astra_embed(
                title="🗑️ YouTube-Abo entfernt",
                description=f"**Channel:** `{channelname}`\n**Ziel:** {channel.mention}",
                color=YOUTUBE_COLOR, author=interaction.user, guild=interaction.guild
            ), ephemeral=True)
            return None

    @app_commands.command(name="twitch", description="Twitch-Kanal hinzufügen oder entfernen")
    @app_commands.describe(aktion="Hinzufügen oder Entfernen", channel="Discord-Kanal für Benachrichtigungen", channelname="Twitch-Channelname", rolle="(Optional) Rolle, die gepingt wird")
    @app_commands.guild_only()
    async def twitch( self, interaction: discord.Interaction, aktion: Literal["Hinzufügen", "Entfernen"], channel: discord.TextChannel, channelname: str, rolle: Optional[discord.Role] = None):
        cog: Optional[Notifier] = interaction.client.get_cog("Notifier")  # type: ignore
        if not cog:
            return await interaction.response.send_message(embed=astra_embed(
                title="❌ Notifier nicht bereit", description="Bitte versuche es gleich erneut.",
                author=interaction.user, guild=interaction.guild
            ), ephemeral=True)

        login = channelname.lower()

        if aktion == "Hinzufügen":
            await cog.subscribe(interaction.guild_id, "twitch", channel.name, login, rolle.id if rolle else None)
            await cog.set_enabled(interaction.guild_id, "twitch", True)
            await interaction.response.send_message(embed=astra_embed(
                title="✅ Twitch-Abo hinzugefügt",
                description=f"**Login:** `{login}`\n**Ziel:** {channel.mention}\n**Ping:** {rolle.mention if rolle else '—'}",
                color=TWITCH_COLOR, author=interaction.user, guild=interaction.guild
            ), ephemeral=True)
        else:
            await cog.delete_subscription(interaction.guild_id, "twitch", channel.name, login)
            await interaction.response.send_message(embed=astra_embed(
                title="🗑️ Twitch-Abo entfernt",
                description=f"**Login:** `{login}`\n**Ziel:** {channel.mention}",
                color=TWITCH_COLOR, author=interaction.user, guild=interaction.guild
            ), ephemeral=True)
            return None


async def setup(bot: commands.Bot):
    await bot.add_cog(Notifier(bot))
    try:
        bot.tree.add_command(Benachrichtigung(bot))
    except Exception:
        pass
