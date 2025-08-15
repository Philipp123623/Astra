# cogs/error_handler.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal

import traceback
import os
import re
import asyncio
import aiohttp
import tempfile
from pathlib import Path
from datetime import datetime, timezone

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
    Heuristiken für hilfreiche Tipps. (aus deiner main.py übernommen)
    """
    msg = f"{type(exc).__name__}: {str(exc)}"
    tips: list[str] = []

    # ---- Generische Python-Fehler ----
    if isinstance(exc, AttributeError):
        if "NoneType" in msg:
            tips.append("Du greifst auf ein Objekt zu, das `None` ist. Prüfe vorher `if obj is not None:` oder nutze "
                        "sichere Properties wie `user.display_avatar.url` statt `user.avatar.url`.")
        else:
            tips.append("Attribut existiert nicht. Tippfehler? Oder falscher Objekttyp? Mit `dir(obj)` prüfen.")
    if isinstance(exc, KeyError):
        m = re.search(r"KeyError: '?(.*?)'?$", msg)
        k = f"`{m.group(1)}` " if m else ""
        tips.append(f"Dict-Schlüssel {k}fehlt. Vorher `if key in d:` prüfen oder `dict.get(key)` mit Default nutzen.")
    if isinstance(exc, TypeError):
        tips.append("Falsche Typen/Argumente. Signatur der Funktion prüfen und Parameterreihenfolge/Default-Werte checken.")
    if isinstance(exc, ValueError):
        if "invalid literal for int()" in msg:
            tips.append("String → int fehlgeschlagen. Vorher mit `.isdigit()` prüfen oder `try/except` umwandeln.")
        else:
            tips.append("Ungültiger Wert. Vor Übergabe validieren; ggf. klare Fehlermeldung werfen.")
    if isinstance(exc, ZeroDivisionError):
        tips.append("Division durch 0. Nenner vorab prüfen (`if x:`) oder `max(x, 1)`/Fehlerfälle abfangen.")
    if isinstance(exc, AssertionError):
        tips.append("Assertion schlug fehl. Prüfe die Annahmen in Tests/Guards oder ersetze `assert` durch sauberes Error-Handling.")

    # ---- Async/Netzwerk ----
    if isinstance(exc, asyncio.TimeoutError):
        tips.append("Timeout. Timeout-Wert erhöhen oder Operation beschleunigen; ggf. Retry mit Backoff einbauen.")
    if isinstance(exc, aiohttp.ClientConnectorError):
        tips.append("Konnte keine Verbindung aufbauen. DNS/Host, Firewall, Proxy und Internet-Zugang prüfen.")
    if isinstance(exc, aiohttp.ClientResponseError):
        tips.append(f"HTTP-Status {exc.status}. URL/Parameter/Token prüfen. Bei 401/403: Credentials/Rechte; bei 404: Endpoint/ID; "
                    "bei 5xx: später erneut versuchen / Retry mit Backoff.")

    # ---- Discord spezifisch ----
    if isinstance(exc, discord.Forbidden):
        tips.append("Discord `Forbidden`: Dem Bot fehlen Berechtigungen (z. B. Nachrichten senden, Webhooks verwalten, Rollen erwähnen). "
                    "Rollenhierarchie/Channel-Overrides prüfen.")
    if isinstance(exc, discord.NotFound):
        tips.append("Discord `NotFound`: Objekt existiert nicht (gelöschte Nachricht/Kanal/Webhook?). IDs/Cache neu laden.")
    if isinstance(exc, discord.HTTPException):
        if getattr(exc, "status", None) == 429 or "429" in msg:
            tips.append("Rate-Limit (429). Weniger häufig senden, Requests bündeln oder Backoff/Retry einbauen.")
        else:
            tips.append("Allgemeiner Discord HTTP-Fehler. Payload/Größenlimits (Embeds, Dateien) und Rechte prüfen.")

    # ---- MySQL / MariaDB (optional) ----
    try:
        import pymysql
        if isinstance(exc, (pymysql.err.IntegrityError, pymysql.err.OperationalError, pymysql.err.ProgrammingError)):
            if "1062" in msg or "Duplicate entry" in msg:
                tips.append("MySQL 1062 Duplicate Key: PRIMARY/UNIQUE-Key verletzt. Vorher prüfen oder "
                            "`INSERT ... ON DUPLICATE KEY UPDATE` nutzen.")
            if "1052" in msg and "ambiguous" in msg.lower():
                tips.append("MySQL 1052 Ambiguous Column: Spalten qualifizieren oder `VALUES()` / Aliase sauber nutzen.")
            if "1146" in msg or "doesn't exist" in msg:
                tips.append("Tabelle existiert nicht. Migration/CREATE TABLE ausführen und DB-User-Rechte prüfen.")
            if "1054" in msg and "Unknown column" in msg:
                tips.append("Spalte existiert nicht. Migration (`ALTER TABLE ... ADD COLUMN ...`) oder Code anpassen.")
            if "1045" in msg:
                tips.append("MySQL 1045 Access denied: Benutzer/Passwort/Host prüfen; Rechte (GRANT) setzen.")
            if "1049" in msg:
                tips.append("MySQL 1049 Unknown database: DB-Name in der Config prüfen oder DB anlegen.")
    except Exception:
        pass

    # ---- Projektspezifische Hinweise ----
    if "Invalid client credentials" in msg:
        tips.append("OAuth-Credentials invalid: `TWITCH_CLIENT_ID`/`TWITCH_CLIENT_SECRET` prüfen oder Secret rotieren.")
    if "quota" in msg.lower() and "youtube" in msg.lower():
        tips.append("YouTube-Quota erreicht. API-Schlüssel prüfen, Abfragen drosseln, ggf. RSS nutzen (`YOUTUBE_USE_RSS=True`).")

    if code_line:
        tips.append(f"Zeile prüfen: `{code_line}`")

    if origin.endswith("notifier.py") and ("ambiguous" in msg.lower() or "Duplicate" in msg):
        tips.append("In `notifier.py` SQL-Query prüfen: Alias/`VALUES()`-Nutzung für Kompatibilität.")

    if not tips:
        tips.append("Fehler reproduzieren, `traceback.txt` checken und die Origin-Stelle untersuchen.")

    return tips


class ErrorHandler(commands.Cog):
    """Cog mit Slash-Command + zentralem Error-Handling für App-Commands."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Fallback, damit auch „freie“ App-Commands (falls vorhanden) über unseren Handler laufen
        self.bot.tree.on_error = self._tree_on_error

    # --- Dein Test-Command jetzt als Cog-Methode ---
    @app_commands.command(name="testfehler", description="Wirft absichtlich einen Fehler zum Testen des Error-Handlers.")
    async def testfehler(
        self,
        interaction: discord.Interaction,
        art: Literal["runtime", "zero", "nested"] = "runtime",
    ):
        if art == "runtime":
            raise RuntimeError("Absichtlich ausgelöster Testfehler (runtime).")
        elif art == "zero":
            1 / 0  # ZeroDivisionError
        elif art == "nested":
            def a():
                def b():
                    raise ValueError("Absichtlich verschachtelt (nested).")
                b()
            a()

        # Falls aus Versehen ohne Fehler aufgerufen:
        await interaction.response.send_message("Kein Fehler ausgelöst.", ephemeral=True)

    # --- Primärer Hook für alle App-Command-Fehler aus dieser Cog ---
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self._handle_error(interaction, error)

    # --- Fallback für Commands, die NICHT in einer Cog liegen (Safety-Net) ---
    async def _tree_on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self._handle_error(interaction, error)

    # --- Gemeinsame Fehlerbehandlung ---
    async def _handle_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        embed = discord.Embed(colour=discord.Colour.red())
        try:
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        except Exception:
            embed.set_author(name=str(interaction.user))

        # Bekannte Fehler kurz erklären
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

            # Trace sicher zusammensetzen
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

            # In Log-Channel posten (falls vorhanden)
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
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
