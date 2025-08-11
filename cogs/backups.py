# -*- coding: utf-8 -*-
"""
Astra Backup System – Neustart-Resistent mit Fortschritts-Embeds & Undo

Slash-Commands (guild-only):
- /backup create   → erstellt sofort ein Backup und gibt den CODE zurück (Embed)
- /backup latest   → zeigt den letzten Code dieser Guild (Embed)
- /backup load     → stellt ein Backup wieder her (nicht-destruktiv), mit Fortschritts-Embed
- /backup undo     → entfernt alles, was beim letzten Restore-Job hinzugefügt wurde
- /backup status   → zeigt den Fortschritt des letzten Jobs (Embed)
- /backup delete   → löscht ein Backup per Code (Embed)

Speichert Rollen, Channels, Kategorien, Overwrites (keine Nachrichten/Emojis).
Restore ist NICHT destruktiv. Undo löscht nur durch den letzten Restore neu angelegte Objekte.
"""

from __future__ import annotations
import asyncio
import hashlib
import time
import typing as T
import uuid

import aiohttp
import aiomysql
import discord
from discord import app_commands
from discord.ext import commands

# ---------------- JSON & Kompression ----------------
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

# ---------------- Einstellungen ----------------
BACKUP_VERSION = 1
RETENTION_DAYS = 7            # Jobs: done/error älter als X Tage löschen
BACKUP_RETENTION_DAYS = 7     # Backups älter als X Tage löschen

# ---------------- Helfer ----------------
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

def gen_backup_code() -> str:
    """Erzeugt einen eindeutigen zufälligen Backup-Code (Base58)."""
    return b58(uuid.uuid4().bytes)

async def gentle_sleep():
    await asyncio.sleep(0.3)

def progress_bar(step: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return "—" * width
    filled = int(round(width * step / max(1, total)))
    return "█" * filled + "░" * (width - filled)

def build_progress_embed(*, title: str, step: int, total: int, status: str,
                         color: discord.Color, error: str | None = None) -> discord.Embed:
    pct = 0 if total == 0 else min(100, int(step * 100 / max(1, total)))
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


# =====================================================================
# Cog: DB, Worker, Restore/Undo-Logik, Fortschritt & Aufräumen
# =====================================================================
class BackupCog(commands.Cog):
    """Hintergrund-Logik & Jobs für das Astra Backup System."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool: aiomysql.Pool = getattr(bot, "pool", None)
        if self.pool is None:
            raise RuntimeError("BackupCog benötigt bot.pool (aiomysql.Pool)")
        self.guild_locks: dict[int, asyncio.Lock] = {}
        self.job_worker_task: asyncio.Task | None = None
        self.http: aiohttp.ClientSession | None = None
        self._last_embed_edit: dict[int, float] = {}  # job_id -> last edit timestamp

    async def cog_load(self):
        await self._mark_stale_jobs()
        await self._prune_jobs_time_based()
        await self._prune_backups_time_based()
        self.job_worker_task = asyncio.create_task(self._job_worker_loop())
        self.http = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.job_worker_task:
            self.job_worker_task.cancel()
        if self.http:
            await self.http.close()

    # ---------- Pruning ----------
    async def _mark_stale_jobs(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE backup_jobs SET status='error', last_error='Bot restart' WHERE status='running'"
            )
            await conn.commit()

    async def _prune_jobs_time_based(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM backup_jobs
                WHERE status IN ('done','error')
                  AND created_at < NOW() - INTERVAL %s DAY
                """,
                (RETENTION_DAYS,),
            )
            await conn.commit()

    async def _prune_backups_time_based(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM backups
                WHERE created_at < NOW() - INTERVAL %s DAY
                """,
                (BACKUP_RETENTION_DAYS,),
            )
            await conn.commit()

    # ---------- Job-Queue ----------
    async def _queue_job(self, guild_id: int, type_: str, code: str | None,
                         *, status_channel_id: int | None = None, status_message_id: int | None = None) -> int:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO backup_jobs (guild_id, code, type, status_channel_id, status_message_id) VALUES (%s,%s,%s,%s,%s)",
                (guild_id, code, type_, status_channel_id, status_message_id)
            )
            job_id = cur.lastrowid
            await conn.commit()
            return job_id

    async def _update_job(self, job_id: int, **fields):
        if not fields:
            return
        parts = ", ".join(f"{k}=%s" for k in fields)
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f"UPDATE backup_jobs SET {parts} WHERE job_id=%s", (*fields.values(), job_id))
            await conn.commit()

    async def _delete_job_row(self, job_id: int):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM backup_jobs WHERE job_id=%s", (job_id,))
            await conn.commit()

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
                self.guild_locks.setdefault(guild_id, asyncio.Lock())
                asyncio.create_task(self._run_job(job))
            await asyncio.sleep(5)

    async def _run_job(self, job: dict):
        guild_id = job["guild_id"]
        lock = self.guild_locks.setdefault(guild_id, asyncio.Lock())
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
                    await self._edit_progress_embed(job["job_id"], final_status="Fertig", color=discord.Colour.blue())

                elif job["type"] == "undo":
                    await self._undo_restore(guild, job)
                    await self._update_job(job["job_id"], status="done")
                    await self._edit_progress_embed(job["job_id"], final_status="Undo abgeschlossen", color=discord.Colour.blue())
                    await self._delete_job_row(job["job_id"])

                elif job["type"] == "create":
                    await self._update_job(job["job_id"], status="done")
                    await self._delete_job_row(job["job_id"])

            except Exception as e:
                await self._update_job(job["job_id"], status="error", last_error=str(e))
                await self._edit_progress_embed(job["job_id"], final_status=f"Fehler: {e}", color=discord.Colour.red())
            finally:
                try:
                    await self._prune_jobs_time_based()
                    await self._prune_backups_time_based()
                except Exception:
                    pass

    # ---------- Backup I/O ----------
    async def _store_backup(self, guild_id: int, payload: dict) -> str:
        raw = dumps(payload)
        digest = blake128(raw)
        blob = zstd.ZstdCompressor(level=12).compress(raw) if _HAS_ZSTD else gzip.compress(raw)  # type: ignore

        # Garantiert eindeutiger Code (mehrere Versuche)
        for _ in range(5):
            code = gen_backup_code()
            try:
                async with self.pool.acquire() as conn, conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO backups (code, guild_id, version, size_bytes, `hash`, `data_blob`) VALUES (%s,%s,%s,%s,%s,%s)",
                        (code, guild_id, BACKUP_VERSION, len(blob), digest, blob)
                    )
                    await conn.commit()
                return code
            except aiomysql.IntegrityError as e:
                if getattr(e, "args", [None])[0] == 1062:
                    continue
                raise
        raise RuntimeError("Konnte keinen eindeutigen Backup-Code erzeugen.")

    async def _fetch_backup(self, code: str) -> tuple[dict, dict]:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM backups WHERE code=%s", (code,))
            row = await cur.fetchone()
            if not row:
                raise commands.UserInputError("Backup nicht gefunden.")
        blob = row["data_blob"]
        raw = zstd.ZstdDecompressor().decompress(blob) if _HAS_ZSTD else gzip.decompress(blob)  # type: ignore
        return loads(raw), row

    async def _fetch_latest_code(self, guild_id: int) -> str | None:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT code FROM backups WHERE guild_id=%s ORDER BY created_at DESC LIMIT 1", (guild_id,))
            row = await cur.fetchone()
            return row[0] if row else None

    # ---------- Snapshot ----------
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

    # ---------- Restore / Undo ----------
    def _build_overwrites(self, guild: discord.Guild, ow_data: list[dict]):
        overwrites: dict[discord.Role, discord.PermissionOverwrite] = {}
        for ow in (ow_data or []):
            if ow.get("target_type") == "role":
                role = discord.utils.get(guild.roles, name=ow.get("target_name"))
                if role:
                    overwrites[role] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(ow.get("allow", 0)),
                        discord.Permissions(ow.get("deny", 0))
                    )
        return overwrites

    async def _maybe_edit_progress_embed(self, job_id: int, *, running_status: str | None = None, force: bool = False):
        """Editiere das Fortschritts-Embed höchstens alle ~1.5s (oder sofort mit force=True)."""
        now = time.time()
        last = self._last_embed_edit.get(job_id, 0.0)
        if force or (now - last) >= 1.5:
            await self._edit_progress_embed(job_id, running_status=running_status)
            self._last_embed_edit[job_id] = now

    async def _restore_to_guild(self, guild: discord.Guild, data: dict, job_id: int):
        """Erstellt nur fehlende Objekte. total_steps = Anzahl der tatsächlich neu zu erstellenden Objekte."""
        created_ids = {"roles": [], "channels": []}

        # --- Step 1: Vorzählen, was wirklich fehlt (für korrekte total_steps) ---
        roles_data = data.get("roles", []) or []
        channels_data = data.get("channels", []) or []

        existing_roles = {r.name for r in guild.roles}
        roles_to_create = sum(1 for r in roles_data if r["name"] not in existing_roles)

        existing_categories = {c.name: c for c in guild.categories}
        cats_to_create = sum(1 for ch in channels_data
                             if ch["type"] == discord.ChannelType.category.value and ch["name"] not in existing_categories)

        existing_channel_names = {c.name for c in guild.channels}
        chans_to_create = sum(1 for ch in channels_data
                              if ch["type"] != discord.ChannelType.category.value and ch["name"] not in existing_channel_names)

        total = roles_to_create + cats_to_create + chans_to_create
        step = 0
        await self._update_job(job_id, step=step, total_steps=total)
        await self._maybe_edit_progress_embed(job_id, running_status="Starte Restore …", force=True)

        # --- Step 2: Rollen erzeugen ---
        for r in roles_data:
            if r["name"] not in existing_roles:
                try:
                    new_role = await guild.create_role(
                        name=r["name"],
                        permissions=discord.Permissions(r["permissions"]),
                        colour=discord.Colour(r["color"]),
                        hoist=r["hoist"],
                        mentionable=r["mentionable"],
                        reason="Astra Backup Restore"
                    )
                    created_ids["roles"].append(new_role.id)
                except discord.Forbidden:
                    pass
                finally:
                    step += 1  # Schritt zählt auch, wenn Erstellung nicht erlaubt war
                    await self._update_job(job_id, step=step)
                    await self._maybe_edit_progress_embed(job_id, running_status="Erstelle Rollen …")
                    await gentle_sleep()

        # --- Step 3: Kategorien erzeugen ---
        # update existing_categories map in case roles step changed nothing
        existing_categories = {c.name: c for c in guild.categories}
        for ch in channels_data:
            if ch["type"] == discord.ChannelType.category.value and ch["name"] not in existing_categories:
                try:
                    cat = await guild.create_category(
                        ch["name"],
                        overwrites=self._build_overwrites(guild, ch.get("overwrites", [])),
                        reason="Astra Backup Restore"
                    )
                    created_ids["channels"].append(cat.id)
                    existing_categories[cat.name] = cat
                except discord.Forbidden:
                    pass
                finally:
                    step += 1
                    await self._update_job(job_id, step=step)
                    await self._maybe_edit_progress_embed(job_id, running_status="Erstelle Kategorien …")
                    await gentle_sleep()

        # --- Step 4: Channels erzeugen ---
        existing_channel_names = {c.name for c in guild.channels}
        for ch in channels_data:
            if ch["type"] == discord.ChannelType.category.value:
                continue
            if ch["name"] not in existing_channel_names:
                parent = existing_categories.get(ch.get("parent_name")) if ch.get("parent_name") else None
                overwrites = self._build_overwrites(guild, ch.get("overwrites", []))
                ctype = discord.ChannelType(ch["type"])
                try:
                    if ctype in (discord.ChannelType.text, discord.ChannelType.news):
                        new_ch = await guild.create_text_channel(
                            name=ch["name"], topic=ch.get("topic"), nsfw=ch.get("nsfw", False),
                            category=parent, overwrites=overwrites, reason="Astra Backup Restore"
                        )
                    elif ctype is discord.ChannelType.voice:
                        new_ch = await guild.create_voice_channel(
                            name=ch["name"], category=parent, overwrites=overwrites, reason="Astra Backup Restore"
                        )
                    elif ctype is discord.ChannelType.stage_voice and hasattr(guild, "create_stage_channel"):
                        new_ch = await guild.create_stage_channel(
                            name=ch["name"], category=parent, overwrites=overwrites, reason="Astra Backup Restore"
                        )
                    elif ctype is discord.ChannelType.forum and hasattr(guild, "create_forum"):
                        new_ch = await guild.create_forum(
                            name=ch["name"], category=parent, overwrites=overwrites, reason="Astra Backup Restore"
                        )
                    else:
                        new_ch = await guild.create_text_channel(
                            name=ch["name"], topic=ch.get("topic"), nsfw=ch.get("nsfw", False),
                            category=parent, overwrites=overwrites, reason="Astra Backup Restore"
                        )
                    created_ids["channels"].append(new_ch.id)
                except discord.Forbidden:
                    pass
                finally:
                    step += 1
                    await self._update_job(job_id, step=step)
                    await self._maybe_edit_progress_embed(job_id, running_status="Erstelle Channels …")
                    await gentle_sleep()

        await self._maybe_edit_progress_embed(job_id, running_status="Abschließen …", force=True)
        return created_ids

    async def _undo_restore(self, guild: discord.Guild, job: dict):
        created_objs = loads(job["created_objects"].encode()) if job.get("created_objects") else {}
        chan_ids = list(reversed(created_objs.get("channels", [])))
        role_ids = created_objs.get("roles", [])

        total = len(chan_ids) + len(role_ids)
        step = 0
        await self._update_job(job["job_id"], step=step, total_steps=total)
        await self._maybe_edit_progress_embed(job["job_id"], running_status="Starte Undo …", force=True)

        # Channels
        for cid in chan_ids:
            ch = guild.get_channel(cid)
            if ch:
                try:
                    await ch.delete(reason="Astra Backup Undo")
                except discord.Forbidden:
                    pass
            step += 1
            await self._update_job(job["job_id"], step=step)
            await self._maybe_edit_progress_embed(job["job_id"], running_status="Lösche Channels …")
            await gentle_sleep()

        # Rollen
        for rid in role_ids:
            role = guild.get_role(rid)
            if role:
                try:
                    await role.delete(reason="Astra Backup Undo")
                except discord.Forbidden:
                    pass
            step += 1
            await self._update_job(job["job_id"], step=step)
            await self._maybe_edit_progress_embed(job["job_id"], running_status="Lösche Rollen …")
            await gentle_sleep()

        await self._maybe_edit_progress_embed(job["job_id"], running_status="Abschließen …", force=True)

    # ---------- Embed Updater ----------
    async def _edit_progress_embed(self, job_id: int, running_status: str | None = None,
                                   final_status: str | None = None, color: discord.Color | None = None):
        job = await self._fetch_job(job_id)
        if not job:
            return
        ch_id = job.get("status_channel_id")
        msg_id = job.get("status_message_id")
        if not ch_id or not msg_id:
            return
        channel = self.bot.get_channel(ch_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel,
                                    discord.StageChannel, discord.ForumChannel)):
            return
        try:
            msg = await channel.fetch_message(msg_id)
        except Exception:
            return

        status_text = final_status or running_status or job.get("status", "running")
        embed = build_progress_embed(
            title=f"Astra • Backup-Job • #{job_id} ({job.get('type')})",
            step=job.get("step", 0),
            total=job.get("total_steps", 0),
            status=status_text,
            color=color or discord.Colour.blue(),
            error=job.get("last_error")
        )
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass


# ==========================================================================================
# Slash-Command Gruppe als app_commands.Group (guild-only), außerhalb der Cog – Astra Style
# ==========================================================================================
@app_commands.guild_only()
class Backup(app_commands.Group):
    """Slash-Gruppe für Astra Backup (nur in Guilds)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(name="backup", description="Astra Backup & Restore")

    def _cog(self) -> BackupCog:
        cog = self.bot.get_cog("BackupCog")
        if cog is None:
            raise RuntimeError("BackupCog ist nicht geladen.")
        return cog

    @app_commands.command(name="create", description="Erstellt ein Server-Backup.")
    async def create(self, interaction: discord.Interaction):
        cog = self._cog()
        await interaction.response.defer(ephemeral=True)
        payload = await cog._snapshot_guild(interaction.guild)
        code = await cog._store_backup(interaction.guild_id, payload)
        emb = discord.Embed(
            title="✅ Backup erstellt",
            description=f"**Code:** `{code}`\nEnthält Rollen, Kategorien, Channels & Overwrites.",
            color=discord.Colour.blue(),
        )
        await interaction.followup.send(embed=emb, ephemeral=True)

    @app_commands.command(name="list", description="Listet alle Backups dieses Servers mit Details auf.")
    async def backup_list(self, interaction: discord.Interaction):
        cog = self._cog()

        # Alle Backups inkl. Datum & Meta holen (sortiert nach neuestem zuerst)
        async with cog.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT code, created_at, includes
                FROM backups
                WHERE guild_id = %s
                ORDER BY created_at DESC
                """,
                (interaction.guild_id,)
            )
            rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message(
                embed=discord.Embed(title="ℹ️ Keine Backups vorhanden", color=discord.Colour.blue()),
                ephemeral=True
            )
            return

        total = len(rows)

        def chunks(seq, size):
            for i in range(0, len(seq), size):
                yield seq[i:i + size]

        # Erste Embed mit Info
        first_embed = discord.Embed(
            title="🗂️ Backups",
            description=f"Anzahl: **{total}**\nSortiert nach Erstellungsdatum (neu → alt).",
            color=discord.Colour.blue()
        )
        await interaction.response.send_message(embed=first_embed, ephemeral=True)

        # Folge-Embeds mit den Listen
        for idx, block in enumerate(chunks(rows, 10), start=1):
            desc_lines = []
            for code, created_at, includes in block:
                date_str = created_at.strftime("%d.%m.%Y %H:%M")
                # Beispiel: includes könnte eine Liste oder ein String wie "roles,channels,overwrites" sein
                if isinstance(includes, (list, tuple)):
                    includes_str = ", ".join(includes)
                else:
                    includes_str = str(includes)
                desc_lines.append(f"**`{code}`**\n📅 {date_str} • Enthält: {includes_str}")

            emb = discord.Embed(
                title=f"Liste ({(idx - 1) * 10 + 1}–{(idx - 1) * 10 + len(block)})",
                description="\n\n".join(desc_lines),
                color=discord.Colour.blue()
            )
            await interaction.followup.send(embed=emb, ephemeral=True)

    @app_commands.command(name="load", description="Stellt ein Backup mithilfe eines Codes wieder her.")
    @app_commands.describe(code="Der Backup-Code, der wiederhergestellt werden soll.")
    async def load(self, interaction: discord.Interaction, code: str):
        cog = self._cog()
        try:
            await cog._fetch_backup(code)
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Ungültiger Code", description=str(e), color=discord.Colour.blue()),
                ephemeral=True
            )
            return

        start_embed = build_progress_embed(
            title="Astra • Backup-Wiederherstellung startet …",
            step=0, total=0, status="Wird in die Warteschlange gestellt …",
            color=discord.Colour.blue()
        )
        await interaction.response.send_message(embed=start_embed, ephemeral=False)
        msg = await interaction.original_response()

        job_id = await cog._queue_job(
            interaction.guild_id, "restore", code,
            status_channel_id=msg.channel.id, status_message_id=msg.id
        )
        await cog._edit_progress_embed(job_id, running_status="In Warteschlange …")
        await interaction.followup.send(
            f"♻️ Restore-Job gestartet (ID **{job_id}**). Fortschritt siehe oben oder mit `/backup status`.",
            ephemeral=True
        )

    @app_commands.command(name="undo", description="Setzt den Server auf den Stand vor der letzten Wiederherstellung zurück.")
    async def undo(self, interaction: discord.Interaction):
        cog = self._cog()
        last_restore = await cog._fetch_last_restore_job(interaction.guild_id)
        if not last_restore:
            await interaction.response.send_message(
                embed=discord.Embed(title="📭 Kein Restore-Job gefunden", color=discord.Colour.blue()),
                ephemeral=True
            )
            return

        start_embed = build_progress_embed(
            title=f"Astra • Rückgängig für Restore-Job #{last_restore['job_id']}",
            step=0, total=0, status="Lösche hinzugefügte Objekte …",
            color=discord.Colour.blue()
        )
        await interaction.response.send_message(embed=start_embed, ephemeral=False)
        msg = await interaction.original_response()

        created_objects = last_restore.get("created_objects")
        undo_job_id = await cog._queue_job(
            interaction.guild_id, "undo", last_restore.get("code"),
            status_channel_id=msg.channel.id, status_message_id=msg.id
        )
        if created_objects:
            await cog._update_job(undo_job_id, created_objects=created_objects)

        job_row = await cog._fetch_job(undo_job_id)
        asyncio.create_task(cog._run_job(job_row))

        await interaction.followup.send(
            f"⏪ Undo-Job gestartet (ID **{undo_job_id}**). Fortschritt siehe oben.",
            ephemeral=True
        )

    @app_commands.command(name="status", description="Zeigt den Fortschritt oder das Ergebnis des letzten Backup- oder Wiederherstellungsvorgangs.")
    async def status(self, interaction: discord.Interaction):
        cog = self._cog()
        job = await cog._fetch_last_job_for_guild(interaction.guild_id)
        if not job:
            await interaction.response.send_message(
                embed=discord.Embed(title="📭 Kein Job gefunden", color=discord.Colour.blue()),
                ephemeral=True
            )
            return
        emb = build_progress_embed(
            title=f"Astra • Letzter Job • #{job['job_id']} ({job['type']})",
            step=job.get("step", 0), total=job.get("total_steps", 0),
            status=job.get("status"), color=discord.Colour.blue(),
            error=job.get("last_error")
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @app_commands.command(name="delete", description="Lösche ältere Backups.")
    @app_commands.describe(code="Der Backup-Code, der gelöscht werden soll.")
    async def delete(self, interaction: discord.Interaction, code: str):
        cog = self._cog()

        async with cog.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM backups WHERE code=%s LIMIT 1", (code,))
            exists = await cur.fetchone()

        if not exists:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Backup nicht gefunden",
                    description=f"Kein Datensatz für Code `{code}`.",
                    color=discord.Colour.blue()
                ),
                ephemeral=True
            )
            return

        async with cog.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM backup_jobs WHERE code=%s AND status='running'",
                (code,)
            )
            (running_count,) = await cur.fetchone()

            await cur.execute(
                "SELECT COUNT(*) FROM backup_jobs WHERE code=%s AND status!='running'",
                (code,)
            )
            (deletable_jobs,) = await cur.fetchone()

            await cur.execute(
                "DELETE FROM backup_jobs WHERE code=%s AND status!='running'",
                (code,)
            )

            await cur.execute("DELETE FROM backups WHERE code=%s", (code,))
            await conn.commit()

        desc = [
            f"🗑️ Backup `{code}` gelöscht.",
            f"🧹 Entfernte Jobs (pending/done/error): **{deletable_jobs}**"
        ]
        if running_count:
            desc.append(f"⚠️ Laufende Jobs zum Code: **{running_count}** (nicht gelöscht)")

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Bereinigung abgeschlossen",
                description="\n".join(desc),
                color=discord.Colour.blue()
            ),
            ephemeral=True
        )


# -------------- setup: Cog + Group im Tree registrieren --------------
async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
    bot.tree.add_command(Backup(bot))
