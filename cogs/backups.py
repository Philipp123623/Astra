# -*- coding: utf-8 -*-
"""
Discord Backup System — Neustart-Resistent & Vollständiger Restore
- /backup create  → erstellt sofort ein Backup und gibt den CODE zurück
- /backup latest  → zeigt den letzten Code der Guild
- /backup load    → stellt über CODE wieder her (als Job, neustart-sicher)
- /backup status  → Fortschritt des Restore-Jobs
- /backup delete  → löscht ein Backup per Code

Speichert Rollen/Channels/Kategorien/Overwrites/Emojis (keine Nachrichten).
Restore ist nicht-destruktiv (fügt fehlende Objekte hinzu, löscht nichts).
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
              code VARCHAR(32),
              type ENUM('create','restore') NOT NULL,
              status ENUM('pending','running','done','error') NOT NULL DEFAULT 'pending',
              step INT NOT NULL DEFAULT 0,
              total_steps INT NOT NULL DEFAULT 0,
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

    # -------- Job-Queue (nur für Restore genutzt) --------
    async def _queue_job(self, guild_id: int, type_: str, code: str | None) -> int:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO backup_jobs (guild_id, code, type) VALUES (%s,%s,%s)",
                (guild_id, code, type_)
            )
            return cur.lastrowid

    async def _update_job(self, job_id: int, **fields):
        parts = ", ".join(f"{k}=%s" for k in fields)
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f"UPDATE backup_jobs SET {parts} WHERE job_id=%s", (*fields.values(), job_id))

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
            except Exception as e:
                await self._update_job(job["job_id"], status="error", last_error=str(e))

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
            # optional: nur 1 Backup pro Guild behalten
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

        emojis = []
        try:
            for e in await guild.fetch_emojis():
                emojis.append({"name": e.name, "animated": e.animated, "url": str(e.url)})
        except discord.Forbidden:
            pass

        return {"version": BACKUP_VERSION, "roles": roles, "channels": channels, "emojis": emojis}

    # -------- Restore --------
    async def _restore_to_guild(self, guild: discord.Guild, data: dict, job_id: int):
        total_steps = len(data.get("roles", [])) + len(data.get("channels", [])) + len(data.get("emojis", []))
        step = 0

        # 1) Rollen
        existing_roles = {r.name for r in guild.roles}
        for r in data.get("roles", []):
            if r["name"] not in existing_roles:
                await guild.create_role(
                    name=r["name"],
                    permissions=discord.Permissions(r["permissions"]),
                    colour=discord.Colour(r["color"]),
                    hoist=r["hoist"],
                    mentionable=r["mentionable"]
                )
                await gentle_sleep()
            step += 1
            await self._update_job(job_id, step=step, total_steps=total_steps)

        # 2) Kategorien
        existing_categories = {c.name: c for c in guild.categories}
        for ch in data.get("channels", []):
            if ch["type"] == discord.ChannelType.category.value:
                if ch["name"] not in existing_categories:
                    cat = await guild.create_category(
                        ch["name"],
                        overwrites=self._build_overwrites(guild, ch["overwrites"])
                    )
                    existing_categories[cat.name] = cat
                    await gentle_sleep()
                step += 1
                await self._update_job(job_id, step=step, total_steps=total_steps)

        # 3) Channels (Text/Voice/News/Stage/Forum)
        existing_channel_names = {c.name for c in guild.channels}
        for ch in data.get("channels", []):
            if ch["type"] == discord.ChannelType.category.value:
                continue

            if ch["name"] in existing_channel_names:
                step += 1
                await self._update_job(job_id, step=step, total_steps=total_steps)
                continue

            parent = existing_categories.get(ch["parent_name"]) if ch.get("parent_name") else None
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
                    # Fallback: Textchannel
                    await guild.create_text_channel(
                        name=ch["name"], topic=ch.get("topic"), nsfw=ch.get("nsfw", False),
                        category=parent, overwrites=overwrites
                    )
            except discord.Forbidden:
                pass
            await gentle_sleep()
            step += 1
            await self._update_job(job_id, step=step, total_steps=total_steps)

        # 4) Emojis
        try:
            existing_emojis = {e.name for e in await guild.fetch_emojis()}
        except discord.Forbidden:
            existing_emojis = set()

        for e in data.get("emojis", []):
            if e["name"] in existing_emojis:
                step += 1
                await self._update_job(job_id, step=step, total_steps=total_steps)
                continue
            try:
                if self.http is None:
                    break
                async with self.http.get(e["url"]) as resp:
                    img_bytes = await resp.read()
                await guild.create_custom_emoji(name=e["name"], image=img_bytes)
                await gentle_sleep()
            except Exception:
                pass
            step += 1
            await self._update_job(job_id, step=step, total_steps=total_steps)

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

    @group.command(name="load", description="Stellt ein Backup über den Code wieder her (Job)")
    @app_commands.checks.has_permissions(administrator=True)
    async def load(self, interaction: discord.Interaction, code: str):
        # validate code exists early
        try:
            await self._fetch_backup(code)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ungültiger Code: {e}", ephemeral=True)
            return

        job_id = await self._queue_job(interaction.guild_id, "restore", code)
        await interaction.response.send_message(
            f"♻️ Restore-Job gestartet (ID {job_id}). Fortschritt mit `/backup status` abrufbar.",
            ephemeral=True
        )

    @group.command(name="status", description="Zeigt den Status des letzten Backup/Restore-Jobs")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM backup_jobs WHERE guild_id=%s ORDER BY created_at DESC LIMIT 1",
                (interaction.guild_id,)
            )
            job = await cur.fetchone()
        if not job:
            await interaction.response.send_message("📭 Keine Jobs gefunden.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"📊 Letzter Job: Typ={job['type']}, Status={job['status']}, Schritt {job['step']}/{job['total_steps']}, Fehler={job['last_error']}",
                ephemeral=True
            )

    @group.command(name="delete", description="Löscht ein Backup per Code")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, code: str):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM backups WHERE code=%s", (code,))
        await interaction.response.send_message(f"🗑 Backup `{code}` gelöscht.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
    try:
        bot.tree.add_command(BackupCog.group)
    except Exception:
        pass
