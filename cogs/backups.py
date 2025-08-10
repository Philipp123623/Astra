# -*- coding: utf-8 -*-
"""
Astra Backup System – Neustart-Resistent mit Fortschritts-Embeds & Undo
- /backup create   → erstellt sofort ein Backup und gibt den CODE zurück
- /backup latest   → zeigt den letzten Code dieser Guild
- /backup load     → stellt ein Backup wieder her (nicht-destruktiv), mit Fortschritts-Embed
- /backup undo     → entfernt alles, was beim letzten Restore-Job hinzugefügt wurde
- /backup status   → zeigt den Fortschritt des letzten Jobs
- /backup delete   → löscht ein Backup per Code
Speichert Rollen, Channels, Kategorien, Overwrites (keine Nachrichten, keine Emojis)
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

# Helpers
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
        self.http: aiohttp.ClientSession | None = None

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
              created_objects JSON NULL,
              status_channel_id BIGINT NULL,
              status_message_id BIGINT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              last_error TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

    async def _mark_stale_jobs(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE backup_jobs SET status='error', last_error='Bot restart' WHERE status='running'"
            )

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

    async def _fetch_last_restore_job(self, guild_id: int) -> dict | None:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM backup_jobs WHERE guild_id=%s AND type='restore' ORDER BY created_at DESC LIMIT 1",
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
                    data, _ = await self._fetch_backup(job["code"])
                    created_objs = await self._restore_to_guild(guild, data, job["job_id"])
                    await self._update_job(job["job_id"], status="done", created_objects=dumps(created_objs).decode())
                elif job["type"] == "undo":
                    await self._undo_restore(guild, job)
                    await self._update_job(job["job_id"], status="done")
            except Exception as e:
                await self._update_job(job["job_id"], status="error", last_error=str(e))

    async def _store_backup(self, guild_id: int, payload: dict) -> str:
        raw = dumps(payload)
        digest = blake128(raw)
        code = b58(digest + now_ts().to_bytes(4, "big"))[:22]
        blob = zstd.ZstdCompressor(level=12).compress(raw) if _HAS_ZSTD else gzip.compress(raw)  # type: ignore
        async with self.pool.acquire() as conn, conn.cursor() as cur:
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
        raw = zstd.ZstdDecompressor().decompress(blob) if _HAS_ZSTD else gzip.decompress(blob)  # type: ignore
        return loads(raw), row

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
        return {"version": BACKUP_VERSION, "roles": roles, "channels": channels}

    async def _restore_to_guild(self, guild: discord.Guild, data: dict, job_id: int):
        created_ids = {"roles": [], "channels": []}
        total_steps = len(data.get("roles", [])) + len(data.get("channels", []))
        step = 0

        existing_roles = {r.name for r in guild.roles}
        for r in data.get("roles", []):
            if r["name"] not in existing_roles:
                new_role = await guild.create_role(
                    name=r["name"],
                    permissions=discord.Permissions(r["permissions"]),
                    colour=discord.Colour(r["color"]),
                    hoist=r["hoist"],
                    mentionable=r["mentionable"]
                )
                created_ids["roles"].append(new_role.id)
                await gentle_sleep()
            step += 1
            await self._update_job(job_id, step=step, total_steps=total_steps)

        existing_categories = {c.name: c for c in guild.categories}
        for ch in data.get("channels", []):
            if ch["type"] == discord.ChannelType.category.value and ch["name"] not in existing_categories:
                cat = await guild.create_category(
                    ch["name"], overwrites=self._build_overwrites(guild, ch.get("overwrites", []))
                )
                created_ids["channels"].append(cat.id)
                existing_categories[cat.name] = cat
                await gentle_sleep()
            step += 1
            await self._update_job(job_id, step=step, total_steps=total_steps)

        existing_channel_names = {c.name for c in guild.channels}
        for ch in data.get("channels", []):
            if ch["type"] != discord.ChannelType.category.value and ch["name"] not in existing_channel_names:
                parent = existing_categories.get(ch.get("parent_name"))
                ctype = discord.ChannelType(ch["type"])
                new_ch = await guild.create_text_channel(
                    name=ch["name"], topic=ch.get("topic"), nsfw=ch.get("nsfw", False),
                    category=parent, overwrites=self._build_overwrites(guild, ch.get("overwrites", []))
                )
                created_ids["channels"].append(new_ch.id)
                await gentle_sleep()
            step += 1
            await self._update_job(job_id, step=step, total_steps=total_steps)

        return created_ids

    async def _undo_restore(self, guild: discord.Guild, job: dict):
        created_objs = loads(job["created_objects"].encode()) if job.get("created_objects") else {}
        for cid in created_objs.get("channels", []):
            ch = guild.get_channel(cid)
            if ch:
                await ch.delete(reason="Undo Backup Restore")
                await gentle_sleep()
        for rid in created_objs.get("roles", []):
            role = guild.get_role(rid)
            if role:
                await role.delete(reason="Undo Backup Restore")
                await gentle_sleep()

    def _build_overwrites(self, guild: discord.Guild, ow_data: list[dict]):
        overwrites = {}
        for ow in (ow_data or []):
            if ow["target_type"] == "role":
                role = discord.utils.get(guild.roles, name=ow["target_name"])
                if role:
                    overwrites[role] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(ow["allow"]), discord.Permissions(ow["deny"])
                    )
        return overwrites

    # Commands
    @group.command(name="create", description="Erstellt sofort ein Backup und gibt den Code zurück")
    async def create_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = await self._snapshot_guild(interaction.guild)
        code = await self._store_backup(interaction.guild_id, payload)
        emb = discord.Embed(title="✅ Backup erstellt", description=f"**Code:** `{code}`", color=discord.Color.blue())
        await interaction.followup.send(embed=emb, ephemeral=True)

    @group.command(name="latest", description="Zeigt den letzten Backup-Code dieser Guild")
    async def latest_cmd(self, interaction: discord.Interaction):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT code FROM backups WHERE guild_id=%s ORDER BY created_at DESC LIMIT 1", (interaction.guild_id,))
            row = await cur.fetchone()
        if not row:
            await interaction.response.send_message(embed=discord.Embed(title="ℹ️ Kein Backup vorhanden", color=discord.Color.blue()), ephemeral=True)
        else:
            await interaction.response.send_message(embed=discord.Embed(title="🧾 Letzter Backup-Code", description=f"`{row[0]}`", color=discord.Color.blue()), ephemeral=True)

    @group.command(name="load", description="Stellt ein Backup wieder her (nicht-destruktiv)")
    async def load_cmd(self, interaction: discord.Interaction, code: str):
        await interaction.response.send_message(embed=discord.Embed(title="Backup-Restore gestartet", color=discord.Color.blue()), ephemeral=False)
        msg = await interaction.original_response()
        job_id = await self._queue_job(interaction.guild_id, "restore", code, status_channel_id=msg.channel.id, status_message_id=msg.id)
        await interaction.followup.send(f"♻️ Restore-Job gestartet (ID {job_id})", ephemeral=True)

    @group.command(name="undo", description="Entfernt alles, was beim letzten Restore-Job hinzugefügt wurde")
    async def undo_cmd(self, interaction: discord.Interaction):
        job = await self._fetch_last_restore_job(interaction.guild_id)
        if not job:
            await interaction.response.send_message(embed=discord.Embed(title="📭 Kein Restore-Job gefunden", color=discord.Color.blue()), ephemeral=True)
            return
        await interaction.response.send_message(embed=discord.Embed(title="⏪ Undo Restore gestartet", color=discord.Color.blue()), ephemeral=False)
        await self._undo_restore(interaction.guild, job)
        await interaction.followup.send(embed=discord.Embed(title="✅ Undo Restore abgeschlossen", color=discord.Color.blue()), ephemeral=False)

    @group.command(name="status", description="Zeigt den Status des letzten Jobs")
    async def status_cmd(self, interaction: discord.Interaction):
        job = await self._fetch_last_restore_job(interaction.guild_id)
        if not job:
            await interaction.response.send_message(embed=discord.Embed(title="📭 Kein Job gefunden", color=discord.Color.blue()), ephemeral=True)
            return
        emb = build_progress_embed(title=f"Job #{job['job_id']}", step=job['step'], total=job['total_steps'], status=job['status'], color=discord.Color.blue())
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @group.command(name="delete", description="Löscht ein Backup per Code")
    async def delete_cmd(self, interaction: discord.Interaction, code: str):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM backups WHERE code=%s", (code,))
        await interaction.response.send_message(embed=discord.Embed(title=f"🗑 Backup `{code}` gelöscht", color=discord.Color.blue()), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
