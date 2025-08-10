# -*- coding: utf-8 -*-
"""
Discord Backup System — Neustart-Resistent & Fortschritts-Embeds
- /backup create  → erstellt sofort ein Backup und gibt den CODE zurück (ephemeral)
- /backup latest  → zeigt den letzten Code der Guild (ephemeral)
- /backup load    → stellt über CODE wieder her (als Job), postet/aktualisiert ein Fortschritts-Embed
- /backup status  → zeigt Fortschritts-Embed des letzten Jobs
- /backup delete  → löscht ein Backup per Code

Speichert Rollen/Channels/Kategorien/Overwrites (keine Nachrichten, KEINE Emojis).
Restore ist NICHT-destruktiv (fügt fehlende Objekte hinzu).
"""

from __future__ import annotations
import asyncio
import hashlib
import time
import typing as T

import aiohttp
import aiomysql
import discord
from discord import app_commands
from discord.ext import commands

# -------- JSON & Kompression --------
try:
    import orjson
    def dumps(obj: T.Any) -> bytes:
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    def loads(b: bytes) -> T.Any:
        return orjson.loads(b)
except ImportError:
    import json
    def dumps(obj: T.Any) -> bytes:
        return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()
    def loads(b: bytes) -> T.Any:
        return json.loads(b.decode())

try:
    import zstandard as zstd
    _HAS_ZSTD = True
except ImportError:
    import gzip
    _HAS_ZSTD = False

BACKUP_VERSION = 1

# -------- Helpers --------
def b58(b: bytes) -> str:
    alphabet = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    n = int.from_bytes(b, 'big')
    out = bytearray()
    while n:
        n, r = divmod(n, 58)
        out.append(alphabet[r])
    return out[::-1].decode() or "1"

def blake128(b: bytes) -> bytes:
    return hashlib.blake2b(b, digest_size=16).digest()

def now_ts() -> int:
    return int(time.time())

async def gentle_sleep():
    await asyncio.sleep(0.3)

def progress_bar(step: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return "—" * width
    filled = int(round(width * step / total))
    return "█" * filled + "░" * (width - filled)

def build_progress_embed(*, title: str, step: int, total: int, status: str, color: discord.Color, error: str | None = None) -> discord.Embed:
    pct = 0 if total == 0 else min(100, int(step * 100 / total))
    emb = discord.Embed(
        title=title,
        description=f"{progress_bar(step, total)}  **{pct}%**",
        color=color
    )
    emb.add_field(name="Status", value=status, inline=False)
    emb.add_field(name="Fortschritt", value=f"{step} / {total} Schritte", inline=True)
    if error:
        emb.add_field(name="Hinweis", value=error[:1000], inline=False)
    emb.set_footer(text="Backup-Restore läuft – ich aktualisiere dieses Embed automatisch.")
    return emb


class BackupCog(commands.Cog):
    group = app_commands.Group(name="backup", description="Server-Backups (Konfiguration)")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool: aiomysql.Pool = getattr(bot, "pool", None)
        if self.pool is None:
            raise RuntimeError("BackupCog benötigt bot.pool (aiomysql.Pool)")
        self.guild_locks: dict[int, asyncio.Lock] = {}
        self.job_worker_task: asyncio.Task | None = None
        self.http: aiohttp.ClientSession | None = None  # aktuell nicht benötigt, aber sauber gehalten

    async def cog_load(self):
        await self._ensure_schema()
        await self._mark_stale_jobs()
        self.job_worker_task = asyncio.create_task(self._job_worker_loop())
        self.http = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.job_worker_task:
            self.job_worker_task.cancel()
        if self.http:
            await self.http.close()

    # -------- Schema --------
    async def _ensure_schema(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DROP TABLE backups;")
            await cur.execute("DROP TABLE backup_jobs;")

            await cur.execute("""
            CREATE TABLE IF NOT EXISTS backups (
              code VARCHAR(32) PRIMARY KEY,
              guild_id BIGINT NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              version INT NOT NULL,
              size_bytes INT NOT NULL,
              `hash` BINARY(16) NOT NULL,
              `data_blob` LONGBLOB NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS backup_jobs (
              job_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              guild_id BIGINT NOT NULL,
              code VARCHAR(64),
              type ENUM('create','restore') NOT NULL,
              status ENUM('pending','running','done','error') NOT NULL DEFAULT 'pending',
              step INT NOT NULL DEFAULT 0,
              total_steps INT NOT NULL DEFAULT 0,
              status_channel_id BIGINT NULL,
              status_message_id BIGINT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              last_error TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            # Falls Spalten in bestehenden DBs fehlen:
            try:
                await cur.execute("ALTER TABLE backup_jobs ADD COLUMN status_channel_id BIGINT NULL")
            except Exception:
                pass
            try:
                await cur.execute("ALTER TABLE backup_jobs ADD COLUMN status_message_id BIGINT NULL")
            except Exception:
                pass

    async def _mark_stale_jobs(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE backup_jobs SET status='error', last_error='Bot restart' WHERE status='running'"
            )

    # -------- Job-Queue (Restore) --------
    async def _queue_job(self, guild_id: int, type_: str, code: str | None,
                         *, status_channel_id: int | None = None, status_message_id: int | None = None) -> int:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO backup_jobs (guild_id, code, type, status_channel_id, status_message_id) VALUES (%s,%s,%s,%s,%s)",
                (guild_id, code, type_, status_channel_id, status_message_id)
            )
            return cur.lastrowid

    async def _update_job(self, job_id: int, **fields):
        if not fields:
            return
        parts = ", ".join(f"{k}=%s" for k in fields)
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f"UPDATE backup_jobs SET {parts} WHERE job_id=%s", (*fields.values(), job_id))

    async def _fetch_job(self, job_id: int) -> dict | None:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM backup_jobs WHERE job_id=%s", (job_id,))
            return await cur.fetchone()

    async def _fetch_last_job_for_guild(self, guild_id: int) -> dict | None:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM backup_jobs WHERE guild_id=%s ORDER BY created_at DESC LIMIT 1",
                (guild_id,)
            )
            return await cur.fetchone()

    async def _fetch_pending_jobs(self) -> list[dict]:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM backup_jobs WHERE status='pending' ORDER BY created_at ASC")
            return await cur.fetchall()

    async def _job_worker_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            jobs = await self._fetch_pending_jobs()
            for job in jobs:
                guild_id = job["guild_id"]
                if guild_id not in self.guild_locks:
                    self.guild_locks[guild_id] = asyncio.Lock()
                asyncio.create_task(self._run_job(job))
            await asyncio.sleep(5)

    async def _run_job(self, job: dict):
        guild_id = job["guild_id"]
        lock = self.guild_locks[guild_id]
        async with lock:
            await self._update_job(job["job_id"], status="running")
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    raise RuntimeError("Guild nicht gefunden oder Bot nicht drauf.")

                if job["type"] == "restore":
                    data, _meta = await self._fetch_backup(job["code"])
                    await self._restore_to_guild(guild, data, job["job_id"])
                    await self._update_job(job["job_id"], status="done")
                    await self._edit_progress_embed(job["job_id"], final_status="Fertig", color=discord.Color.green())
            except Exception as e:
                await self._update_job(job["job_id"], status="error", last_error=str(e))
                await self._edit_progress_embed(job["job_id"], final_status=f"Fehler: {e}", color=discord.Color.red())

    # -------- Backup speichern/laden --------
    async def _store_backup(self, guild_id: int, payload: dict) -> str:
        raw = dumps(payload)
        digest = blake128(raw)
        code = b58(digest + now_ts().to_bytes(4, "big"))[:22]
        if _HAS_ZSTD:
            blob = zstd.ZstdCompressor(level=12).compress(raw)
        else:
            blob = gzip.compress(raw)  # type: ignore
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            # nur 1 Backup pro Guild behalten (spart Platz)
            await cur.execute("DELETE FROM backups WHERE guild_id=%s", (guild_id,))
            await cur.execute(
                "INSERT INTO backups (code, guild_id, version, size_bytes, `hash`, `data_blob`) VALUES (%s,%s,%s,%s,%s,%s)",
                (code, guild_id, BACKUP_VERSION, len(blob), digest, blob)
            )
        return code

    async def _fetch_backup(self, code: str) -> tuple[dict, dict]:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM backups WHERE code=%s", (code,))
            row = await cur.fetchone()
            if not row:
                raise commands.UserInputError("Backup nicht gefunden.")
        blob = row["data_blob"]
        if _HAS_ZSTD:
            raw = zstd.ZstdDecompressor().decompress(blob)
        else:
            raw = gzip.decompress(blob)  # type: ignore
        return loads(raw), row

    async def _fetch_latest_code(self, guild_id: int) -> str | None:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT code FROM backups WHERE guild_id=%s ORDER BY created_at DESC LIMIT 1",
                (guild_id,)
            )
            row = await cur.fetchone()
            return row[0] if row else None

    # -------- Snapshot --------
    async def _snapshot_guild(self, guild: discord.Guild) -> dict:
        roles = [{
            "name": r.name,
            "color": r.color.value,
            "permissions": r.permissions.value,
            "position": r.position,
            "hoist": r.hoist,
            "mentionable": r.mentionable
        } for r in sorted(guild.roles, key=lambda x: x.position)]

        channels = []
        for ch in sorted(guild.channels, key=lambda x: (0 if isinstance(x, discord.CategoryChannel) else 1, x.position)):
            overwrites = []
            for target, po in ch.overwrites.items():
                allow, deny = po.pair()
                overwrites.append({
                    "target_name": target.name,
                    "target_type": "role" if isinstance(target, discord.Role) else "member",
                    "allow": allow.value,
                    "deny": deny.value
                })
            channels.append({
                "type": int(ch.type.value),
                "parent_name": ch.category.name if ch.category else None,
                "name": ch.name,
                "topic": getattr(ch, "topic", None),
                "position": ch.position,
                "nsfw": getattr(ch, "nsfw", False),
                "overwrites": overwrites
            })

        # Emojis bewusst NICHT gesichert/wiederhergestellt (Ratelimit-Vermeidung)
        return {"version": BACKUP_VERSION, "roles": roles, "channels": channels, "emojis": []}

    # -------- Restore (ohne Emojis) --------
    async def _restore_to_guild(self, guild: discord.Guild, data: dict, job_id: int):
        total_steps = len(data.get("roles", [])) + len(data.get("channels", []))
        step = 0
        await self._update_job(job_id, step=step, total_steps=total_steps)

        # 1) Rollen
        existing_roles = {r.name for r in guild.roles}
        for r in data.get("roles", []):
            if r["name"] not in existing_roles:
                try:
                    await guild.create_role(
                        name=r["name"],
                        permissions=discord.Permissions(r["permissions"]),
                        colour=discord.Colour(r["color"]),
                        hoist=r["hoist"],
                        mentionable=r["mentionable"]
                    )
                except discord.Forbidden:
                    pass
                await gentle_sleep()
            step += 1
            await self._update_job(job_id, step=step)
            await self._edit_progress_embed(job_id, running_status="Erstelle Rollen ...")

        # 2) Kategorien
        existing_categories = {c.name: c for c in guild.categories}
        for ch in data.get("channels", []):
            if ch["type"] == discord.ChannelType.category.value:
                if ch["name"] not in existing_categories:
                    try:
                        cat = await guild.create_category(
                            ch["name"],
                            overwrites=self._build_overwrites(guild, ch.get("overwrites", []))
                        )
                        existing_categories[cat.name] = cat
                    except discord.Forbidden:
                        pass
                    await gentle_sleep()
                step += 1
                await self._update_job(job_id, step=step)
                await self._edit_progress_embed(job_id, running_status="Erstelle Kategorien ...")

        # 3) Channels
        existing_channel_names = {c.name for c in guild.channels}
        for ch in data.get("channels", []):
            if ch["type"] == discord.ChannelType.category.value:
                continue

            if ch["name"] not in existing_channel_names:
                parent = existing_categories.get(ch.get("parent_name")) if ch.get("parent_name") else None
                overwrites = self._build_overwrites(guild, ch.get("overwrites", []))
                ctype = discord.ChannelType(ch["type"])
                try:
                    if ctype in (discord.ChannelType.text, discord.ChannelType.news):
                        await guild.create_text_channel(
                            name=ch["name"], topic=ch.get("topic"), nsfw=ch.get("nsfw", False),
                            category=parent, overwrites=overwrites
                        )
                    elif ctype is discord.ChannelType.voice:
                        await guild.create_voice_channel(
                            name=ch["name"], category=parent, overwrites=overwrites
                        )
                    elif ctype is discord.ChannelType.stage_voice and hasattr(guild, "create_stage_channel"):
                        await guild.create_stage_channel(
                            name=ch["name"], category=parent, overwrites=overwrites
                        )
                    elif ctype is discord.ChannelType.forum and hasattr(guild, "create_forum"):
                        await guild.create_forum(
                            name=ch["name"], category=parent, overwrites=overwrites
                        )
                    else:
                        await guild.create_text_channel(
                            name=ch["name"], topic=ch.get("topic"), nsfw=ch.get("nsfw", False),
                            category=parent, overwrites=overwrites
                        )
                except discord.Forbidden:
                    pass
                await gentle_sleep()

            step += 1
            await self._update_job(job_id, step=step)
            await self._edit_progress_embed(job_id, running_status="Erstelle Channels ...")

    def _build_overwrites(self, guild: discord.Guild, ow_data: list[dict]):
        overwrites: dict[discord.Role, discord.PermissionOverwrite] = {}
        for ow in (ow_data or []):
            if ow.get("target_type") == "role":
                role = discord.utils.get(guild.roles, name=ow.get("target_name"))
                if role:
                    overwrites[role] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(ow.get("allow", 0)), discord.Permissions(ow.get("deny", 0))
                    )
        return overwrites

    # -------- Embed Updater --------
    async def _edit_progress_embed(self, job_id: int, running_status: str | None = None, final_status: str | None = None, color: discord.Color | None = None):
        job = await self._fetch_job(job_id)
        if not job:
            return
        ch_id = job.get("status_channel_id")
        msg_id = job.get("status_message_id")
        if not ch_id or not msg_id:
            return
        channel = self.bot.get_channel(ch_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.StageChannel, discord.VoiceChannel, discord.ForumChannel)):
            return
        try:
            msg = await channel.fetch_message(msg_id)
        except Exception:
            return

        status = final_status or running_status or job.get("status", "running")
        embed = build_progress_embed(
            title=f"Backup-Restore • Job #{job_id}",
            step=job.get("step", 0),
            total=job.get("total_steps", 0),
            status=status,
            color=color or (discord.Color.blurple() if job.get("status") == "running" else discord.Color.green()),
            error=job.get("last_error")
        )
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass

    # -------- Slash Commands --------
    @group.command(name="create", description="Erstellt JETZT ein Backup und gibt den Code zurück")
    @app_commands.checks.has_permissions(administrator=True)
    async def create(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = await self._snapshot_guild(interaction.guild)
        code = await self._store_backup(interaction.guild_id, payload)
        approx_kb = len(dumps(payload)) // 1024
        await interaction.followup.send(
            f"✅ Backup erstellt.\n**Code:** `{code}`\nUnkomprimiert ca. {approx_kb} KB.",
            ephemeral=True
        )

    @group.command(name="latest", description="Zeigt den letzten Backup-Code dieser Guild")
    @app_commands.checks.has_permissions(administrator=True)
    async def latest(self, interaction: discord.Interaction):
        code = await self._fetch_latest_code(interaction.guild_id)
        if not code:
            await interaction.response.send_message("ℹ️ Für diese Guild existiert noch kein Backup.", ephemeral=True)
        else:
            await interaction.response.send_message(f"🧾 Letzter Backup-Code: `{code}`", ephemeral=True)

    @group.command(name="load", description="Stellt ein Backup über den Code wieder her (Job mit Fortschritts-Embed)")
    @app_commands.checks.has_permissions(administrator=True)
    async def load(self, interaction: discord.Interaction, code: str):
        # Code prüfen
        try:
            await self._fetch_backup(code)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ungültiger Code: {e}", ephemeral=True)
            return

        # Öffentliche Progress-Nachricht im aktuellen Kanal posten
        progress_embed = build_progress_embed(
            title="Backup-Restore wird gestartet ...",
            step=0, total=0, status="Warte auf Worker ...", color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=progress_embed, ephemeral=False)
        progress_message = await interaction.original_response()
        # Job in Queue mit Message/Channel-IDs
        job_id = await self._queue_job(
            interaction.guild_id, "restore", code,
            status_channel_id=progress_message.channel.id,
            status_message_id=progress_message.id
        )
        # Erste Aktualisierung
        await self._edit_progress_embed(job_id, running_status="In Warteschlange ...")
        # Kleines Info-Reply (ephemeral), damit der User weiß, was Sache ist
        await interaction.followup.send(f"♻️ Restore-Job gestartet (ID {job_id}). Fortschritt siehst du oben oder mit `/backup status`.", ephemeral=True)

    @group.command(name="status", description="Zeigt den Status des letzten Jobs dieser Guild")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        job = await self._fetch_last_job_for_guild(interaction.guild_id)
        if not job:
            await interaction.response.send_message("📭 Keine Jobs gefunden.", ephemeral=True)
            return
        embed = build_progress_embed(
            title=f"Letzter Job • #{job['job_id']} ({job['type']})",
            step=job.get("step", 0),
            total=job.get("total_steps", 0),
            status=job.get("status"),
            color=(discord.Color.red() if job.get("status") == "error" else discord.Color.blurple()),
            error=job.get("last_error")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @group.command(name="delete", description="Löscht ein Backup per Code")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, code: str):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM backups WHERE code=%s", (code,))
        await interaction.response.send_message(f"🗑 Backup `{code}` gelöscht.", ephemeral=True)


# ---- setup ----
async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
    try:
        bot.tree.add_command(BackupCog.group)
    except Exception:
        pass
