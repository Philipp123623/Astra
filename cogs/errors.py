import discord
from discord import app_commands
from discord.ext import commands
import traceback
import json
import os
import re
import asyncio
import aiohttp
import tempfile
from pathlib import Path
from datetime import datetime, timezone
import platform

PROJECT_ROOT = "/root/Astra"          # zum Filtern deiner eigenen Frames
LOG_CHANNEL_ID = 1141116983815962819  # ggf. anpassen


# ---------- kleine Hilfsfunktionen ----------
def _safe(o):
    try:
        return str(o)
    except Exception:
        return repr(o)

def _shorten_path(p: str) -> str:
    try:
        return str(Path(p).resolve()).replace(PROJECT_ROOT + "/", "")
    except Exception:
        return p


def _build_smart_tips(exc: BaseException, *, origin: str, code_line: str | None, short_exc: str) -> list[str]:
    """
    Erweitertes Tipp-System für viele Python-, Discord- und DB-Fehler.
    Immer kurz & präzise.
    """
    msg = f"{type(exc).__name__}: {str(exc)}".strip()
    tips: list[str] = []

    # ---- Python-Standardfehler ----
    if isinstance(exc, AttributeError):
        if "NoneType" in msg:
            tips.append("Objekt ist None → if obj prüfen")
        else:
            tips.append("Attribut fehlt → Tippfehler/Typ prüfen")
    if isinstance(exc, KeyError):
        m = re.search(r"KeyError: '?(.*?)'?$", msg)
        k = f"`{m.group(1)}` " if m else ""
        tips.append(f"Dict-Schlüssel {k}fehlt → if key in d prüfen")
    if isinstance(exc, TypeError):
        tips.append("Falsche Argumente → Funktionssignatur prüfen")
    if isinstance(exc, ValueError):
        if "invalid literal for int()" in msg:
            tips.append("String→int fehlgeschlagen → .isdigit() oder try/except")
        else:
            tips.append("Ungültiger Wert → Eingabe validieren")
    if isinstance(exc, ZeroDivisionError):
        tips.append("Division durch 0 → Nenner vorab prüfen")
    if isinstance(exc, AssertionError):
        tips.append("Assertion fehlgeschlagen → Bedingungen anpassen")
    if isinstance(exc, IndexError):
        tips.append("Index existiert nicht → len(seq) prüfen")
    if isinstance(exc, ImportError):
        tips.append("Modul fehlt → pip install ausführen")
    if isinstance(exc, FileNotFoundError):
        tips.append("Datei fehlt → Pfad prüfen/os.path.exists nutzen")
    if isinstance(exc, PermissionError):
        tips.append("Keine Berechtigung → chmod/chown prüfen")
    if isinstance(exc, MemoryError):
        tips.append("Speicher knapp → kleinere Datenmengen laden")

    # ---- Async/Netzwerk ----
    if isinstance(exc, asyncio.TimeoutError):
        tips.append("Timeout → Timeout erhöhen oder Retry")
    if isinstance(exc, aiohttp.ClientConnectorError):
        tips.append("Keine Verbindung → DNS/Firewall prüfen")
    if isinstance(exc, aiohttp.ClientResponseError):
        tips.append(f"HTTP {exc.status} → URL/Token prüfen")

    # ---- Discord spezifisch ----
    if isinstance(exc, discord.Forbidden):
        tips.append("Berechtigung fehlt → Rollen/Channel-Overrides prüfen")
    if isinstance(exc, discord.NotFound):
        tips.append("Objekt existiert nicht → ID/Caches prüfen")
    if isinstance(exc, discord.HTTPException):
        if getattr(exc, "status", None) == 429 or "429" in msg:
            tips.append("Rate-Limit → Delay/Retry einbauen")
        else:
            tips.append("HTTP-Fehler → Payloadgröße & Rechte prüfen")

    # ---- Datenbankfehler ----
    try:
        import pymysql
        if isinstance(exc, (pymysql.err.IntegrityError, pymysql.err.OperationalError, pymysql.err.ProgrammingError)):
            if "1062" in msg:
                tips.append("Duplicate Key → vorher Existenz prüfen")
            if "1052" in msg and "ambiguous" in msg.lower():
                tips.append("Ambiguous Column → Spaltennamen qualifizieren")
            if "1146" in msg:
                tips.append("Tabelle fehlt → CREATE TABLE ausführen")
            if "1054" in msg:
                tips.append("Spalte fehlt → ALTER TABLE ADD COLUMN")
            if "1045" in msg:
                tips.append("Access denied → User/Pass/Host prüfen")
            if "1049" in msg:
                tips.append("DB fehlt → CREATE DATABASE ausführen")
    except Exception:
        pass

    # ---- Zusätzliche generische Tipps ----
    if code_line:
        tips.append(f"Codezeile prüfen: `{code_line}`")
    if origin and origin != "unbekannt":
        tips.append(f"Datei: {origin}")

    # Begrenzen auf maximal 6 Tipps
    if not tips:
        tips.append("Fehler reproduzieren und Stacktrace prüfen")
    return tips[:6]


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # WICHTIG: In einer Cog nutzt man einen Event-Listener, nicht @bot.tree.error
    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        embed = discord.Embed(colour=discord.Colour.red())
        try:
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        except Exception:
            embed.set_author(name=str(interaction.user))

        # Bekannte Fehlerfälle kurz erklären
        if isinstance(error, app_commands.MissingPermissions):
            embed.title = "Fehlende Berechtigungen"
            embed.description = "❌ Du hast nicht die nötigen Berechtigungen."
        elif isinstance(error, app_commands.BotMissingPermissions):
            embed.title = "Bot hat keine Berechtigung"
            embed.description = "❌ Mir fehlen die nötigen Berechtigungen."
        elif isinstance(error, app_commands.CommandOnCooldown):
            embed.title = "Cooldown aktiv"
            embed.description = f"⏳ Bitte warte {round(error.retry_after, 2)} Sekunden."
        elif isinstance(error, app_commands.CommandNotFound):
            embed.title = "Unbekannter Befehl"
            embed.description = "❌ Dieser Slash-Command existiert nicht."
        elif isinstance(error, app_commands.CheckFailure):
            embed.title = "Zugriff verweigert"
            embed.description = "❌ Voraussetzungen für diesen Befehl nicht erfüllt."
        elif isinstance(error, app_commands.MissingRole):
            embed.title = "Fehlende Rolle"
            embed.description = "❌ Du brauchst eine bestimmte Rolle."
        elif isinstance(error, app_commands.MissingAnyRole):
            embed.title = "Fehlende Rollen"
            embed.description = "❌ Du brauchst mindestens eine der Rollen."
        elif isinstance(error, app_commands.TransformerError):
            embed.title = "Ungültige Eingabe"
            embed.description = "❌ Ungültige Argumente oder Umwandlung fehlgeschlagen."
        else:
            # Unbekannter/ungehandelter Fehler → Log mit Trace & Tipps
            embed.title = "Unbekannter Fehler"
            embed.description = "❌ Fehler geloggt!"

            exc = error.original if isinstance(error, app_commands.CommandInvokeError) and getattr(error, "original", None) else error

            # Trace sammeln (robust, auch wenn __traceback__ None ist)
            try:
                full_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            except Exception:
                full_trace = f"{type(exc).__name__}: {exc}"

            tb_list = traceback.extract_tb(getattr(exc, "__traceback__", None)) or []
            origin = "unbekannt"
            code_line = None

            # eigene Frames bevorzugen
            project_frames = [f for f in tb_list if str(f.filename).startswith(PROJECT_ROOT)]
            chosen = project_frames[-1] if project_frames else (tb_list[-1] if tb_list else None)
            if chosen:
                origin = f"{_shorten_path(chosen.filename)}:{chosen.lineno} in {chosen.name}()"
                code_line = (chosen.line or "").strip()

            short_exc = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            tips = _build_smart_tips(exc, origin=origin, code_line=code_line, short_exc=short_exc)

            # In Logchannel posten (falls vorhanden)
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                error_embed = discord.Embed(
                    title="SlashCommand Error",
                    colour=discord.Colour.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                error_embed.add_field(name="Ort", value=origin, inline=False)
                error_embed.add_field(name="Fehler", value=f"```{short_exc}```", inline=False)
                if tips:
                    error_embed.add_field(name="Tipps", value="\n".join(f"• {t}" for t in tips), inline=False)

                trace_tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt")
                try:
                    trace_tmp.write(full_trace)
                finally:
                    trace_tmp.close()

                try:
                    await log_channel.send(embed=error_embed, file=discord.File(trace_tmp.name, filename="traceback.txt"))
                except Exception:
                    # Wenn selbst das Loggen fehlschlägt, nichts crashen lassen
                    pass
                finally:
                    try:
                        os.remove(trace_tmp.name)
                    except Exception:
                        pass

        # Antwort an den User (immer ephemer)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            pass
        except Exception:
            # Nichts mehr tun, wenn Antworten komplett fehlschlägt
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
