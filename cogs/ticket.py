# -*- coding: utf-8 -*-
import os
import io
import re
import html
import asyncio
from typing import Optional, Literal, List, Tuple
from discord import ui
import discord
from discord.ext import commands, tasks
from discord import app_commands

ASTRA_BLUE = discord.Colour.blue()

# =========================================================
#                      HELPERS
# =========================================================

# Globale Presets (passen für alle Felder)
# Values sind „Input-Strings“, die der Parser versteht.
GLOBAL_PRESETS = [
    ("Deaktiviert (0)", "0"),
    ("15 Minuten", "15m"),
    ("30 Minuten", "30m"),
    ("1 Stunde", "1h"),
    ("2 Stunden", "2h"),
    ("4 Stunden", "4h"),
    ("8 Stunden", "8h"),
    ("12 Stunden", "12h"),
    ("1 Tag", "1d"),
    ("2 Tage", "2d"),
    ("3 Tage", "3d"),
    ("1 Woche", "1w"),
    ("2 Wochen", "2w"),
]

def _plural(n: int, s: str, p: str) -> str:
    return f"{n} {s if n == 1 else p}"

def format_native_value(key: str, native: int) -> str:
    """
    Macht aus einem gespeicherten NATIVEN Wert (h oder min) eine hübsche Anzeige
    mit der "größten sinnvollen" Einheit.
    """
    # In Sekunden normalisieren:
    if key.endswith("_hours"):
        seconds = native * 3600
    else:
        seconds = native * 60

    # Größte passende Einheit wählen (w>d>h>m> s)
    if seconds % (7 * 24 * 3600) == 0 and seconds >= 7 * 24 * 3600:
        w = seconds // (7 * 24 * 3600)
        return _plural(w, "Woche", "Wochen")
    if seconds % (24 * 3600) == 0 and seconds >= 24 * 3600:
        d = seconds // (24 * 3600)
        return _plural(d, "Tag", "Tage")
    if seconds % 3600 == 0 and seconds >= 3600:
        h = seconds // 3600
        return _plural(h, "Stunde", "Stunden")
    if seconds % 60 == 0 and seconds >= 60:
        m = seconds // 60
        return _plural(m, "Minute", "Minuten")
    return _plural(int(seconds), "Sekunde", "Sekunden")

def human_cfg(cfg: dict) -> str:
    """Schöne Zusammenfassung fürs Embed."""
    lines = []
    lines.append(f"<:Astra_locked:1141824745243942912> **Auto-Close:** {format_native_value('autoclose_hours', cfg['autoclose_hours'])}")
    lines.append(f"<:Astra_time:1141303932061233202> **Reminder:** {format_native_value('remind_minutes', cfg['remind_minutes'])}")
    lines.append(f"<:Astra_file1:1141303837181886494> **Reopen-Fenster:** {format_native_value('reopen_hours', cfg['reopen_hours'])}")
    lines.append(f"<:Astra_support:1141303923752325210> **Ping-Throttle:** {format_native_value('ping_throttle_minutes', cfg['ping_throttle_minutes'])}")
    return "\n".join(lines)

def parse_duration_to_native(key: str, value: str, unit_hint: Optional[str]) -> int:
    """
    Parse flexible Dauer-Strings in die NATIVE Einheit des Felds.
    Unterstützt Kombinationen:  '1w2d3h30m20s'
    Unterstützte Einheiten: s, m, h, d, w  (Sekunden, Minuten, Stunden, Tage, Wochen)
    Nativ:
      *_hours   -> Stunden (int, rundet mathematisch)
      *_minutes -> Minuten (int, rundet mathematisch)
    """
    raw = (value or "").strip().lower().replace(" ", "")
    native_is_hours = key.endswith("_hours")

    import re
    token_re = re.compile(r"(\d+)([smhdw])")
    seconds_total = 0

    # 1) kombinierte Tokens einsammeln
    tokens = token_re.findall(raw)
    if tokens:
        for num_s, unit in tokens:
            num = int(num_s)
            if unit == "s":
                seconds_total += num
            elif unit == "m":
                seconds_total += num * 60
            elif unit == "h":
                seconds_total += num * 3600
            elif unit == "d":
                seconds_total += num * 86400
            elif unit == "w":
                seconds_total += num * 604800
        # in Nativeinheit konvertieren
        if native_is_hours:
            return round(seconds_total / 3600)
        else:
            return round(seconds_total / 60)

    # 2) nackte Zahl -> Einheit aus Hint bzw. nativ
    if raw.isdigit():
        num = int(raw)
        if unit_hint in ("s", "sec", "secs"):
            seconds_total = num
        elif unit_hint in ("m", "min", "mins"):
            seconds_total = num * 60
        elif unit_hint in ("h", "hr", "hrs"):
            seconds_total = num * 3600
        elif unit_hint in ("d", "day", "days"):
            seconds_total = num * 86400
        elif unit_hint in ("w", "wk", "wks"):
            seconds_total = num * 604800
        else:
            # Default: native Einheit
            if native_is_hours:
                return num
            else:
                return num
        # mit Hint angegeben:
        if native_is_hours:
            return round(seconds_total / 3600)
        else:
            return round(seconds_total / 60)

    # 3) Fallback: einzelne Zahl mit Einheiten-Suffix (z. B. "120m", "2h")
    m = re.fullmatch(r"(\d+)([smhdw])", raw)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "s":
            seconds_total = num
        elif unit == "m":
            seconds_total = num * 60
        elif unit == "h":
            seconds_total = num * 3600
        elif unit == "d":
            seconds_total = num * 86400
        elif unit == "w":
            seconds_total = num * 604800
        if native_is_hours:
            return round(seconds_total / 3600)
        else:
            return round(seconds_total / 60)

    raise ValueError("Ungültiges Dauerformat.")

def mk_embed(
    *,
    title: str,
    description: str = "",
    color: discord.Colour = ASTRA_BLUE,
    thumb: Optional[str] = None,
    footer: Optional[str] = None,
) -> discord.Embed:
    e = discord.Embed(title=title, description=description, colour=color)
    if thumb:
        e.set_thumbnail(url=thumb)
    if footer:
        e.set_footer(text=footer)
    return e

def fmt_user(u: discord.abc.User) -> str:
    return f"{u.name}#{u.discriminator}"

def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", name)[:60]

# =========================================================
#                    DB INIT / CONFIG
# =========================================================


DEFAULT_CFG = dict(autoclose_hours=0, remind_minutes=0, reopen_hours=24, ping_throttle_minutes=0)

async def get_guild_config(pool, guild_id: int) -> dict:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT autoclose_hours, remind_minutes, reopen_hours, ping_throttle_minutes FROM ticket_config WHERE guildID=%s", (guild_id,))
            row = await cur.fetchone()
            if not row:
                await cur.execute("INSERT INTO ticket_config (guildID) VALUES (%s)", (guild_id,))
                return DEFAULT_CFG.copy()
    return dict(autoclose_hours=row[0], remind_minutes=row[1], reopen_hours=row[2], ping_throttle_minutes=row[3])

async def set_guild_config(pool, guild_id: int, **kwargs):
    fields = []
    vals: List = []
    for k, v in kwargs.items():
        if k in DEFAULT_CFG:
            fields.append(f"{k}=%s")
            vals.append(int(v))
    if not fields:
        return
    vals.append(guild_id)
    q = f"UPDATE ticket_config SET {', '.join(fields)} WHERE guildID=%s"
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(q, tuple(vals))

# =========================================================
#                 SETUP WIZARD (VIEWS/MODAL)
# =========================================================

class PanelTextModal(discord.ui.Modal, title="Ticket-Panel Texte"):
    def __init__(self, cb_submit):
        super().__init__(timeout=180)
        self._cb_submit = cb_submit
        self.inp_title = discord.ui.TextInput(
            label="Panel-Titel",
            placeholder="z. B. Support, Teamkontakt, Bewerben …",
            max_length=100,
            required=True,
        )
        self.inp_desc = discord.ui.TextInput(
            label="Panel-Beschreibung",
            style=discord.TextStyle.paragraph,
            placeholder="Beschreibe kurz, wofür dieses Ticket gedacht ist.",
            max_length=1024,
            required=True,
        )
        self.add_item(self.inp_title)
        self.add_item(self.inp_desc)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._cb_submit(interaction, str(self.inp_title.value), str(self.inp_desc.value))


class SetupWizardView(ui.LayoutView):

    TOTAL_STEPS = 4

    def __init__(self, bot: commands.Bot, invoker: discord.User):
        super().__init__(timeout=None)
        self.bot = bot
        self.invoker = invoker
        self.page = 0

        self.target_channel = None
        self.category = None
        self.role = None
        self.panel_title = None
        self.panel_desc = None

        # 🔥 Cache für Config (Fix für await Problem)
        self.cached_config = {}

        self._build()

    # =========================================================
    # BUILD
    # =========================================================

    def _progress_bar(self):
        filled = int((self.page + 1) / self.TOTAL_STEPS * 12)
        empty = 12 - filled
        return "█" * filled + "░" * empty

    def _build(self):
        self.clear_items()
        children = []

        # ================= HEADER =================
        children.append(
            discord.ui.TextDisplay(
                f"# 🎫 Ticket Setup\n"
                f"**Schritt {self.page+1} von {self.TOTAL_STEPS}**\n"
                f"`{self._progress_bar()}`"
            )
        )

        children.append(discord.ui.Separator())

        # ================= STATUS =================
        def fmt(x):
            if not x:
                return "`Nicht gesetzt`"
            return getattr(x, "mention", getattr(x, "name", "Gesetzt"))

        children.append(
            discord.ui.TextDisplay(
                "## 📌 Aktuelle Konfiguration\n"
                f"**Kanal:** {fmt(self.target_channel)}\n"
                f"**Kategorie:** {fmt(self.category)}\n"
                f"**Support-Rolle:** {fmt(self.role)}\n\n"
                f"**Titel:** {self.panel_title or '`Nicht gesetzt`'}\n"
                f"**Beschreibung:** {'Gesetzt' if self.panel_desc else '`Nicht gesetzt`'}"
            )
        )

        children.append(discord.ui.Separator())

        # =========================================================
        # PAGE 0
        # =========================================================
        if self.page == 0:

            children.append(
                discord.ui.TextDisplay(
                    "## 🚀 Willkommen\n"
                    "Dieser Assistent hilft dir, dein Ticketsystem sauber einzurichten.\n"
                    "Folge einfach den Schritten."
                )
            )

            start = discord.ui.Button(
                label="Setup starten",
                emoji="🚀",
                style=discord.ButtonStyle.success
            )

            async def start_cb(interaction):
                await self._switch(interaction, 1)

            start.callback = start_cb
            children.append(discord.ui.ActionRow(start))

        # =========================================================
        # PAGE 1
        # =========================================================
        elif self.page == 1:

            children.append(
                discord.ui.TextDisplay(
                    "## 📦 Panel Einstellungen\n"
                    "Definiere, wo das Panel erscheint und wer Tickets bearbeiten darf."
                )
            )

            ch = discord.ui.ChannelSelect(
                placeholder="📢 Kanal für das Ticket-Panel auswählen",
                channel_types=[discord.ChannelType.text]
            )

            async def ch_cb(interaction):
                self.target_channel = ch.values[0]
                await self._switch(interaction, self.page)

            ch.callback = ch_cb
            children.append(discord.ui.ActionRow(ch))

            cat = discord.ui.ChannelSelect(
                placeholder="🗂 Kategorie auswählen, in der Tickets erstellt werden",
                channel_types=[discord.ChannelType.category]
            )

            async def cat_cb(interaction):
                self.category = cat.values[0]
                await self._switch(interaction, self.page)

            cat.callback = cat_cb
            children.append(discord.ui.ActionRow(cat))

            role = discord.ui.RoleSelect(
                placeholder="🛡 Support-Rolle auswählen (darf Tickets sehen & schließen)"
            )

            async def role_cb(interaction):
                self.role = role.values[0]
                await self._switch(interaction, self.page)

            role.callback = role_cb
            children.append(discord.ui.ActionRow(role))

            text_btn = discord.ui.Button(
                label="Titel & Beschreibung setzen",
                emoji="📝",
                style=discord.ButtonStyle.primary
            )

            async def text_cb(interaction):

                class PanelModal(discord.ui.Modal, title="Panel Texte"):
                    title_input = discord.ui.TextInput(
                        label="Panel Titel",
                        required=True
                    )
                    desc_input = discord.ui.TextInput(
                        label="Panel Beschreibung",
                        style=discord.TextStyle.paragraph,
                        required=True
                    )

                    async def on_submit(modal_self, inter2):
                        self.panel_title = str(modal_self.title_input.value)
                        self.panel_desc = str(modal_self.desc_input.value)
                        await inter2.response.edit_message(view=self)

                await interaction.response.send_modal(PanelModal())

            text_btn.callback = text_cb
            children.append(discord.ui.ActionRow(text_btn))

        # =========================================================
        # PAGE 2
        # =========================================================
        elif self.page == 2:

            children.append(
                discord.ui.TextDisplay(
                    "## ⚙ System Optionen\n"
                    "Optional: Automatische Funktionen konfigurieren."
                )
            )

            select = discord.ui.Select(
                placeholder="🔧 Einstellung auswählen",
                options=[
                    discord.SelectOption(
                        label="Auto-Close",
                        description="Schließt inaktive Tickets automatisch",
                        value="autoclose_hours"
                    ),
                    discord.SelectOption(
                        label="Reminder",
                        description="Sendet Erinnerung bei Inaktivität",
                        value="remind_minutes"
                    ),
                    discord.SelectOption(
                        label="Reopen",
                        description="Zeitfenster zum Wiederöffnen",
                        value="reopen_hours"
                    ),
                    discord.SelectOption(
                        label="Ping-Throttle",
                        description="Limit für Support-Pings",
                        value="ping_throttle_minutes"
                    ),
                ]
            )

            async def select_cb(interaction):
                key = select.values[0]

                class ConfigModal(discord.ui.Modal, title="Wert setzen"):
                    value = discord.ui.TextInput(label="Zeitwert")

                    async def on_submit(modal_self, inter2):
                        try:
                            new_val = parse_duration_to_native(
                                key,
                                str(modal_self.value.value),
                                None
                            )
                        except Exception:
                            return await inter2.response.send_message(
                                "Ungültiges Format.",
                                ephemeral=True
                            )

                        await set_guild_config(
                            self.bot.pool,
                            inter2.guild.id,
                            **{key: new_val}
                        )

                        await inter2.response.send_message("Gespeichert.", ephemeral=True)

                await interaction.response.send_modal(ConfigModal())

            select.callback = select_cb
            children.append(discord.ui.ActionRow(select))

        # =========================================================
        # PAGE 3 – FINAL CONFIG PANEL (FIXED)
        # =========================================================
        elif self.page == 3:

            cfg = self.cached_config or {}

            def show(key):
                val = cfg.get(key, 0)
                return "`Deaktiviert`" if not val else f"`{val}`"

            children.append(
                discord.ui.TextDisplay(
                    "## ⚙ Erweiterte Einstellungen\n\n"
                    f"**Auto-Close:** {show('autoclose_hours')}\n"
                    f"**Reminder:** {show('remind_minutes')}\n"
                    f"**Reopen:** {show('reopen_hours')}\n"
                    f"**Ping-Throttle:** {show('ping_throttle_minutes')}"
                )
            )

        # =========================================================
        # NAVIGATION + CANCEL
        # =========================================================
        nav = []

        if self.page > 0:
            back = discord.ui.Button(label="Zurück", emoji="⬅", style=discord.ButtonStyle.secondary)

            async def back_cb(interaction):
                await self._switch(interaction, self.page - 1)

            back.callback = back_cb
            nav.append(back)

        if self.page < self.TOTAL_STEPS - 1:
            nxt = discord.ui.Button(label="Weiter", emoji="➡", style=discord.ButtonStyle.primary)

            async def next_cb(interaction):
                await self._switch(interaction, self.page + 1)

            nxt.callback = next_cb
            nav.append(nxt)

        cancel = discord.ui.Button(
            label="Setup abbrechen",
            emoji="❌",
            style=discord.ButtonStyle.danger
        )

        async def cancel_cb(interaction):
            await interaction.response.edit_message(
                content="❌ **Setup abgebrochen**",
                view=None
            )

        cancel.callback = cancel_cb
        nav.append(cancel)

        children.append(discord.ui.ActionRow(*nav))

        # =========================================================
        # ROOT CONTAINER
        # =========================================================
        self.add_item(
            discord.ui.Container(
                *children,
                accent_color=discord.Colour.blue().value
            )
        )

    # =========================================================
    # SWITCH (ASYNC SAFE)
    # =========================================================
    async def _switch(self, interaction, page: int):
        self.page = page

        # 🔥 Config async laden NUR hier
        if self.page == 3 and hasattr(self.bot, "pool"):
            self.cached_config = await get_guild_config(
                self.bot.pool,
                interaction.guild.id
            )

        self._build()
        await interaction.response.edit_message(view=self)

    async def validate(self):
        return all([
            self.target_channel,
            self.category,
            self.role,
            self.panel_title,
            self.panel_desc
        ])

    async def interaction_check(self, interaction):
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Nur der Ersteller darf diesen Wizard bedienen.",
                ephemeral=True
            )
            return False
        return True


# =========================================================
#                  IN-TICKET VIEWS (CLAIM/CLOSE)
# =========================================================

class ReopenView(discord.ui.View):
    """Button im Log, um innerhalb X Stunden das Ticket neu zu öffnen."""
    def __init__(self, bot: commands.Bot, guild_id: int, opener_id: int, thema: str, category_id: int, role_id: int, expires_ts: int):
        super().__init__(timeout=None)  # <-- statt dynamischem Timeout
        self.bot = bot
        self.guild_id = guild_id
        self.opener_id = opener_id
        self.thema = thema
        self.category_id = category_id
        self.role_id = role_id
        self.expires_ts = expires_ts

    @discord.ui.button(label="Ticket erneut öffnen", style=discord.ButtonStyle.green, emoji="🔁", custom_id="ticket:reopen")
    async def reopen(self, interaction: discord.Interaction, _button: discord.ui.Button):
        now = int(discord.utils.utcnow().timestamp())
        if now > self.expires_ts:
            return await interaction.response.send_message("Reopen abgelaufen.", ephemeral=True)

        guild = interaction.client.get_guild(self.guild_id)
        if not guild:
            return await interaction.response.send_message("Guild nicht gefunden.", ephemeral=True)

        opener = guild.get_member(self.opener_id) or interaction.client.get_user(self.opener_id)
        category = guild.get_channel(self.category_id)
        role = guild.get_role(self.role_id)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message("Kategorie existiert nicht mehr.", ephemeral=True)

        # Channel erstellen
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if opener:
            overwrites[opener] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        new_channel = await guild.create_text_channel(
            name=f"ticket-{sanitize_filename(opener.name if opener else 'user')}",
            category=category,
            overwrites=overwrites,
            topic=str(self.opener_id),
            reason="Ticket reopen",
        )

        # Begrüßungs-Embed
        e = mk_embed(
            title=f"Ticket von {fmt_user(opener) if opener else 'User'}",
            description=f"Ticket wurde erneut geöffnet. Bitte schildere dein Anliegen erneut.",
            color=ASTRA_BLUE,
        )
        e.add_field(name="Thema", value=self.thema or "—")
        e.add_field(name="Geclaimed von", value="Nicht geclaimed")
        msg = await new_channel.send(f"{role.mention if role else ''} {opener.mention if opener else ''}".strip(), embed=e, view=TicketButtons(self.bot))

        # DB anlegen
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO ticketsystem_channels(guildID, channelID, msgID, opened, claimed, closed, time) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (guild.id, new_channel.id, msg.id, self.opener_id, "Not Set", "Not Set", discord.utils.format_dt(new_channel.created_at, "F")),
                )

        await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> Das folgende Ticket: {new_channel.mention} wurde wieder geöffnet.", ephemeral=True)
        return None


class TicketButtons(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Schließen", style=discord.ButtonStyle.red, emoji="<:Astra_locked:1141824745243942912>", custom_id="ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, _button: discord.Button):
        channel: discord.TextChannel = interaction.channel  # type: ignore
        guild = interaction.guild
        user = interaction.user

        # Support-Rolle für diese Kategorie
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("SELECT roleID, thema FROM ticketsystem WHERE categoryID=%s", (channel.category.id,))
                row = await cur.fetchone()
        if not row:
            return await interaction.response.send_message("<:Astra_x:1141303954555289600> Dieses Ticket ist keinem Panel zugeordnet.", ephemeral=True)
        role_id, thema = int(row[0]), row[1]
        role = guild.get_role(role_id)
        if role not in user.roles:
            return await interaction.response.send_message("<:Astra_x:1141303954555289600> Nur Mitglieder mit der Support-Rolle dürfen Tickets schließen.", ephemeral=True)

        # Grund per Modal
        class CloseReason(discord.ui.Modal, title="Ticket schließen"):
            reason = discord.ui.TextInput(label="Schließ-Grund (optional)", style=discord.TextStyle.paragraph, required=False, max_length=500)
            async def on_submit(self, inter: discord.Interaction):
                await self._do_close(inter, str(self.reason.value))

            async def _do_close(self, inter: discord.Interaction, reason_text: str):
                # ---------------- DB-Infos laden & schließen markieren ----------------
                async with inter.client.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "SELECT msgID, opened, claimed, time FROM ticketsystem_channels WHERE channelID=%s",
                            (channel.id,),
                        )
                        row2 = await cur.fetchone()
                        if not row2:
                            return await inter.response.send_message("Interner Fehler (kein DB-Eintrag).",
                                                                     ephemeral=True)

                        msg_id, opened_id, claimed, time_open = row2
                        await cur.execute(
                            "UPDATE ticketsystem_channels SET closed=%s WHERE channelID=%s",
                            (inter.user.id, channel.id),
                        )

                        # Log-Kanal holen (kann None sein)
                        await cur.execute("SELECT channelID FROM ticketlog WHERE guildID=%s", (guild.id,))
                        logrow = await cur.fetchone()

                opener = inter.client.get_user(int(opened_id))
                claimer = None if claimed == "Not Set" else inter.client.get_user(int(claimed))
                closer = inter.user

                # ---------------- Transkript (nur .log, hübsch & robust) ----------------
                txt_name = f"{channel.id}.log"

                def _clean_mentions(raw: str, msg: discord.Message) -> str:
                    if not raw:
                        return ""
                    # User-Mentions -> @Displayname
                    for u in msg.mentions:
                        raw = raw.replace(f"<@{u.id}>", f"@{u.display_name}")
                        raw = raw.replace(f"<@!{u.id}>", f"@{u.display_name}")
                    # Rollen-Mentions -> @Rollenname
                    for r in msg.role_mentions:
                        raw = raw.replace(f"<@&{r.id}>", f"@{r.name}")
                    # Kanal-Mentions -> #kanalname
                    for ch_ in msg.channel_mentions:
                        raw = raw.replace(f"<#{ch_.id}>", f"#{ch_.name}")
                    return raw

                header_lines = [
                    "====================  TICKET TRANSKRIPT  ====================",
                    f"Ticket: {channel.name}  (ID: {channel.id})",
                    f"Server: {guild.name}  (ID: {guild.id})",
                    f"Erstellt: {channel.created_at.strftime('%d.%m.%Y %H:%M:%S UTC')}",
                    "",
                    f"Geöffnet von: {fmt_user(opener)} (ID: {opener.id})" if opener else "Geöffnet von: Unbekannt",
                    f"Geclaimed von: {fmt_user(claimer)} (ID: {claimer.id})" if claimer else "Geclaimed von: Keiner",
                    f"Geschlossen von: {fmt_user(closer)} (ID: {closer.id})",
                ]
                final_reason = reason_text.strip() or "Kein Grund angegeben"
                header_lines.append(f"Schließ-Grund: {final_reason}")
                header_lines += [
                    "============================================================",
                    "",
                ]

                txt_buf = io.StringIO()
                txt_buf.write("\n".join(header_lines))

                msg_count = 0
                attach_count = 0

                async for msg in channel.history(limit=None, oldest_first=True):
                    msg_count += 1
                    ts = msg.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                    author = f"{fmt_user(msg.author)} (ID: {msg.author.id})"

                    content = _clean_mentions(msg.content or "", msg)
                    content_to_write = content if content.strip() else "—"

                    txt_buf.write(f"[{ts}] {author}\n")
                    txt_buf.write(content_to_write + "\n")

                    if msg.attachments:
                        for a in msg.attachments:
                            attach_count += 1
                            txt_buf.write(f"  [Anhang] {a.filename}: {a.url}\n")

                    txt_buf.write("-" * 60 + "\n")

                txt_buf.write(
                    f"\nNachrichten insgesamt: {msg_count} | Anhänge: {attach_count}\n"
                    "======================  ENDE TRANSKRIPT  ======================\n"
                )
                txt_bytes = io.BytesIO(txt_buf.getvalue().encode("utf-8"))

                # ---------------- Log-Embed (ohne „Thema“-Feld) + Reopen ----------------
                if logrow:
                    log_channel = inter.client.get_channel(int(logrow[0]))
                    emb = mk_embed(
                        title="Ticket geschlossen",
                        description=f"Transkript für `{channel.name}`",
                        color=ASTRA_BLUE,
                    )
                    if opener:
                        emb.add_field(name="Geöffnet von", value=opener.mention, inline=False)
                    emb.add_field(name="Geschlossen von", value=closer.mention, inline=False)
                    emb.add_field(
                        name="Geclaimed von",
                        value=(claimer.mention if claimer else "Nicht geclaimed"),
                        inline=False,
                    )
                    emb.add_field(name="Geöffnet am", value=time_open, inline=False)
                    if reason_text:
                        emb.add_field(name="Grund", value=reason_text, inline=False)

                    cfg = await get_guild_config(inter.client.pool, guild.id)
                    expires_ts = int(discord.utils.utcnow().timestamp()) + int(cfg.get("reopen_hours", 24)) * 3600

                    await log_channel.send(
                        embed=emb,
                        files=[discord.File(fp=txt_bytes, filename=txt_name, description="Text-Transkript")],
                        view=ReopenView(
                            inter.client,
                            guild.id,
                            int(opened_id),
                            thema,  # Thema bleibt nur für Reopen-Context erhalten, NICHT im Embed anzeigen
                            channel.category.id,
                            role_id,
                            expires_ts,
                        ),
                    )

                # ---------------- Channel schließen & DB säubern ----------------
                await inter.response.send_message("Das Ticket wird in **5 Sekunden** geschlossen …")
                await asyncio.sleep(5)
                try:
                    await channel.delete()
                finally:
                    async with inter.client.pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "DELETE FROM ticketsystem_channels WHERE channelID=%s AND guildID=%s",
                                (channel.id, guild.id),
                            )
                            await cur.execute(
                                "DELETE FROM ticket_autoclose_state WHERE channelID=%s",
                                (channel.id,),
                            )

        await interaction.response.send_modal(CloseReason())
        return None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, emoji="<:Astra_user2:1141303942324699206>", custom_id="ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.Button):
        channel: discord.TextChannel = interaction.channel  # type: ignore
        guild = interaction.guild
        member = interaction.user

        # Support-Rolle check
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("SELECT roleID, thema FROM ticketsystem WHERE categoryID=%s", (channel.category.id,))
                row = await cur.fetchone()
        if not row:
            return await interaction.response.send_message("<:Astra_x:1141303954555289600> Dieses Ticket ist keinem Panel zugeordnet.", ephemeral=True)

        role_id, thematext = int(row[0]), row[1]
        role = guild.get_role(role_id)
        if role not in member.roles:
            return await interaction.response.send_message("<:Astra_x:1141303954555289600> Nur Mitglieder mit der Support-Rolle dürfen Tickets claimen.", ephemeral=True)

        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("SELECT msgID, opened FROM ticketsystem_channels WHERE channelID=%s", (channel.id,))
                row2 = await cur.fetchone()
                if not row2:
                    return await interaction.response.send_message("<:Astra_x:1141303954555289600> Interner Fehler (kein DB-Eintrag).", ephemeral=True)
                msg_id, opened_id = row2
                await cur.execute("UPDATE ticketsystem_channels SET claimed=%s WHERE channelID=%s", (member.id, channel.id))

        msg = await channel.fetch_message(int(msg_id))
        opener = interaction.client.get_user(int(opened_id))

        # Schönes Embed + Button lokal deaktivieren
        embed = mk_embed(
            title=f"Ticket von {opener.name}",
            description=f"Hallo {opener.mention}!\n{member.mention} wird sich nun um dein Anliegen kümmern. Bitte beschreibe kurz dein Problem.",
            color=ASTRA_BLUE,
        )
        embed.set_author(name=str(opener), icon_url=opener.display_avatar.url)
        embed.add_field(name="Thema", value=thematext or "—")
        embed.add_field(name="Geclaimed von", value=member.mention)

        button.disabled = True
        await msg.edit(embed=embed, view=self)

        # Bonus: Channel-Rename
        try:
            new_name = f"ticket-claimed-{sanitize_filename(member.name)}".lower()
            await channel.edit(name=new_name, reason="Ticket geclaimed")
        except Exception:
            pass

        await interaction.response.send_message(f"{member.mention} hat das Ticket geclaimed.", suppress_embeds=True)

# =========================================================
#                      PANEL VIEW
# =========================================================

class TicketOpenView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Ticket öffnen", style=discord.ButtonStyle.green, emoji="<:Astra_ticket:1141833836204937347>", custom_id="ticket_panel:open")
    async def open_ticket(self, interaction: discord.Interaction, _button: discord.Button):
        guild = interaction.guild
        user = interaction.user
        panel_channel: discord.TextChannel = interaction.channel  # type: ignore

        # Panel-Config
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("SELECT categoryID, thema, roleID FROM ticketsystem WHERE channelID=%s", (panel_channel.id,))
                row = await cur.fetchone()
        if not row:
            return await interaction.response.send_message("<:Astra_x:1141303954555289600> Für diesen Kanal ist kein Ticket-Panel hinterlegt.", ephemeral=True)

        category_id, thema, role_id = int(row[0]), row[1], int(row[2])
        category = guild.get_channel(category_id)
        role = guild.get_role(role_id)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message("<:Astra_x:1141303954555289600> Die hinterlegte Ticket-Kategorie existiert nicht mehr.", ephemeral=True)

        # Schon ein Ticket?
        for ch in category.text_channels:
            if ch.topic == str(user.id):
                return await interaction.response.send_message("<:Astra_x:1141303954555289600> Du hast bereits ein offenes Ticket in dieser Kategorie.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        new_channel = await guild.create_text_channel(
            name=f"ticket-{sanitize_filename(user.name)}".lower(),
            category=category,
            overwrites=overwrites,
            topic=str(user.id),
            reason="Ticket eröffnet",
        )

        e = mk_embed(
            title=f"Ticket von {user.name}",
            description=f"Hallo {user.mention}! Ein Teammitglied meldet sich gleich. "
                        f"Bitte beschreibe in der Zwischenzeit dein Anliegen.",
            color=ASTRA_BLUE,
        )
        e.set_author(name=str(user), icon_url=user.display_avatar.url)
        e.add_field(name="Thema", value=thema or "—")
        e.add_field(name="Geclaimed von", value="Nicht geclaimed")

        msg = await new_channel.send(
            f"{role.mention if role else ''} {user.mention}".strip(),  # Ping nur beim Erstellen
            embed=e,
            view=TicketButtons(self.bot)
        )

        # DB
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO ticketsystem_channels(guildID, channelID, msgID, opened, claimed, closed, time) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (guild.id, new_channel.id, msg.id, user.id, "Not Set", "Not Set", discord.utils.format_dt(new_channel.created_at, "F")),
                )

        await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> Dein Ticket wurde erstellt: {new_channel.mention}", ephemeral=True)
        return None


# =========================================================
#                     SLASH COMMANDS
# =========================================================

@app_commands.guild_only()
class Ticket(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(name="ticket", description="Alles rund ums Ticketsystem.")

    @app_commands.command(name="setup", description="Starte den Setup-Wizard für ein Ticket-Panel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def ticket_setup(self, interaction: discord.Interaction):
        view = SetupWizardView(self.bot, interaction.user)

        await interaction.response.send_message(
            view=view,
            ephemeral=True  # wichtig → nur der User sieht den Wizard
        )

    # Panels auflisten
    @app_commands.command(name="anzeigen", description="Listet alle Ticket-Panels dieses Servers auf.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def ticket_list(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("SELECT channelID, thema FROM ticketsystem WHERE guildID=%s", (interaction.guild.id,))
                rows = await cur.fetchall()
        if not rows:
            return await interaction.response.send_message("Keine Ticket-Panels aktiv.", ephemeral=True)

        e = mk_embed(title="Aktive Ticket-Panels", color=discord.Colour.green())
        for ch_id, thema in rows:
            ch = interaction.guild.get_channel(int(ch_id))
            e.add_field(name=ch.mention if ch else f"#{ch_id}", value=thema or "—", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)
        return None

    # Panel löschen
    @app_commands.command(name="löschen", description="Lösche ein Ticket-Panel.")
    @app_commands.describe(channel="Kanal mit dem Ticket-Panel")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def ticket_delete(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM ticketsystem WHERE channelID=%s AND guildID=%s", (channel.id, interaction.guild.id))
        await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> Das Panel aus {channel.mention} wurde erfolgreich gelöscht.", ephemeral=True)

    # Ticket-Log konfigurieren
    @app_commands.command(name="log", description="Richte einen Ticket-Log-Kanal ein/aus.")
    @app_commands.describe(argument="Einschalten oder Ausschalten.", channel="Log-Kanal")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticketlog(self, interaction: discord.Interaction, argument: Literal["Einschalten", "Ausschalten"], channel: Optional[discord.TextChannel] = None):
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                if argument == "Einschalten":
                    if not channel:
                        return await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte gib einen Log-Kanal an.", ephemeral=True)
                    await cur.execute("REPLACE INTO ticketlog (guildID, channelID) VALUES (%s,%s)", (interaction.guild.id, channel.id))
                    await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> Der Ticket-Log ist nun in: {channel.mention} aktiv.", ephemeral=True)
                    return None
                else:
                    await cur.execute("DELETE FROM ticketlog WHERE guildID=%s", (interaction.guild.id,))
                    await interaction.response.send_message("<:Astra_accept:1141303821176422460> Der Ticket Log ist nun nicht mehr aktiv.", ephemeral=True)
                    return None

    # Konfiguration: Auto-Close & Reminder & Reopen
    @app_commands.command(name="config", description="Zeigt oder ändert Ticket-Einstellungen.")
    @app_commands.describe(modus="Was möchtest du tun?")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_config(
            self,
            interaction: discord.Interaction,
            modus: Literal["Anzeigen", "Setzen"],
    ):
        cfg = await get_guild_config(self.bot.pool, interaction.guild.id)  # type: ignore[attr-defined]

        if modus == "Anzeigen":
            e = mk_embed(
                title="Ticket-Konfiguration",
                description=human_cfg(cfg),
            )
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # ====== Setzen: interaktive View ======
        class ConfigView(discord.ui.View):
            def __init__(self, bot):
                super().__init__(timeout=180)
                self.bot = bot
                self.selected_key: Optional[str] = None

            @discord.ui.select(
                placeholder="⚙️ Wähle eine Einstellung …",
                min_values=1, max_values=1,
                options=[
                    discord.SelectOption(
                        label="<:Astra_locked:1141824745243942912> Auto-Close",
                        value="autoclose_hours",
                        description="Nach wie viel Zeit Tickets automatisch geschlossen werden",
                    ),
                    discord.SelectOption(
                        label="<:Astra_time:1141303932061233202> Reminder",
                        value="remind_minutes",
                        description="Nach wie viel Zeit eine Erinnerung im Ticket gepostet wird",
                    ),
                    discord.SelectOption(
                        label="<:Astra_file1:1141303837181886494> Reopen",
                        value="reopen_hours",
                        description="Wie lange nach dem Schließen ein Reopen möglich ist",
                    ),
                    discord.SelectOption(
                        label="<:Astra_support:1141303923752325210> Ping-Throttle",
                        value="ping_throttle_minutes",
                        description="Mindestabstand zwischen erlaubten Pings (Spam-Schutz)",
                    ),
                ]
            )
            async def select_setting(self, inter: discord.Interaction, select: discord.ui.Select):
                self.selected_key = select.values[0]
                pretty_map = {
                    "autoclose_hours": "<:Astra_locked:1141824745243942912> Auto-Close",
                    "remind_minutes": "<:Astra_time:1141303932061233202> Reminder",
                    "reopen_hours": "<:Astra_file1:1141303837181886494> Reopen",
                    "ping_throttle_minutes": "<:Astra_support:1141303923752325210> Ping-Throttle",
                }
                picked = pretty_map.get(self.selected_key, self.selected_key)

                await inter.response.edit_message(
                    embed=mk_embed(
                        title="Konfiguration ändern",
                        description=(
                            f"Ausgewählt: **{picked}**\n\n"
                            "Wähle einen der **Schnell-Werte** unten oder klicke **Eigenen Wert**.\n"
                            "Format für eigene Werte: `30m`, `2h`, `1d`, `1w2d3h20m10s` …\n"
                            "_Hinweis:_ Reminder & Ping-Throttle werden in **Minuten**, Auto-Close & Reopen in **Stunden** gespeichert."
                        ),
                        color=ASTRA_BLUE
                    ),
                    view=self
                )

            # Presets – passen für beide „Arten“ (werden intern umgerechnet)
            @discord.ui.button(label="15 Minuten", style=discord.ButtonStyle.secondary, custom_id="cfg:15m")
            async def btn_15m(self, inter: discord.Interaction, _):
                await self._apply(inter, "15m")

            @discord.ui.button(label="1 Stunde", style=discord.ButtonStyle.secondary, custom_id="cfg:1h")
            async def btn_1h(self, inter: discord.Interaction, _):
                await self._apply(inter, "1h")

            @discord.ui.button(label="1 Tag", style=discord.ButtonStyle.secondary, custom_id="cfg:1d")
            async def btn_1d(self, inter: discord.Interaction, _):
                await self._apply(inter, "1d")

            @discord.ui.button(label="1 Woche", style=discord.ButtonStyle.secondary, custom_id="cfg:1w")
            async def btn_1w(self, inter: discord.Interaction, _):
                await self._apply(inter, "1w")

            @discord.ui.button(label="Eigenen Wert", style=discord.ButtonStyle.primary, custom_id="cfg:custom")
            async def btn_custom(self, inter: discord.Interaction, _):
                if not self.selected_key:
                    return await inter.response.send_message("⚠️ Bitte zuerst eine Einstellung wählen.", ephemeral=True)

                class ValueModal(discord.ui.Modal, title="Eigenen Wert setzen"):
                    value = discord.ui.TextInput(
                        label="Zeit (z. B. 30m, 2h, 1d, 1w2d3h20m10s, 0=Aus)",
                        required=True,
                        max_length=40,
                    )

                    async def on_submit(self, inter2: discord.Interaction):
                        await self.view._apply(inter2, str(self.value.value))  # type: ignore

                await inter.response.send_modal(ValueModal())

            async def _apply(self, inter: discord.Interaction, value_str: str):
                if not self.selected_key:
                    return await inter.response.send_message("<:Astra_x:1141303954555289600> Bitte zuerst eine Einstellung wählen.", ephemeral=True)
                try:
                    new_val = parse_duration_to_native(self.selected_key, value_str, None)
                except Exception:
                    return await inter.response.send_message(
                        "<:Astra_x:1141303954555289600> Ungültiges Format. Beispiele: `30m`, `2h`, `1d`, `1w2d3h20m10s`, `0` (Aus).",
                        ephemeral=True
                    )

                await set_guild_config(self.bot.pool, inter.guild.id,
                                       **{self.selected_key: new_val})  # type: ignore[attr-defined]
                cfg2 = await get_guild_config(self.bot.pool, inter.guild.id)  # type: ignore[attr-defined]

                e = mk_embed(
                    title="Einstellung gespeichert",
                    description=f"**{self.selected_key}** → `{format_native_value(self.selected_key, new_val)}`\n\n{human_cfg(cfg2)}",
                    color=discord.Colour.green(),
                )
                await inter.response.send_message(embed=e, ephemeral=True)
                return None

        e = mk_embed(
            title="Ticket-Konfiguration",
            description=human_cfg(cfg),
        )
        await interaction.response.send_message(embed=e, view=ConfigView(self.bot), ephemeral=True)
        return None


# =========================================================
#                         COG
# =========================================================

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.autoclose_task.start()

    @commands.Cog.listener()
    async def on_ready(self):
        # Persistente Views (alle relevanten Buttons dauerhaft verfügbar machen)
        self.bot.add_view(TicketOpenView(self.bot))  # 🎫 Ticket öffnen
        self.bot.add_view(TicketButtons(self.bot))  # 🔒 Claim / Schließen

        # Für ReopenView brauchen wir keine festen Parameter, daher Dummy mit None
        # Discord ignoriert die Parameter beim Registrieren, solange die custom_ids gleich bleiben
        self.bot.add_view(
            ReopenView(
                self.bot,
                guild_id=0,
                opener_id=0,
                thema="",
                category_id=0,
                role_id=0,
                expires_ts=int(discord.utils.utcnow().timestamp()) + 3600
            )
        )

    # ---------------- AUTO-CLOSE & REMINDER ----------------

    @tasks.loop(minutes=5)
    async def autoclose_task(self):
        await self.bot.wait_until_ready()
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("SELECT guildID, channelID FROM ticketsystem_channels")
                rows = await cur.fetchall()

        for guild_id, channel_id in rows:
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            ch = guild.get_channel(int(channel_id))
            if not isinstance(ch, discord.TextChannel):
                continue

            cfg = await get_guild_config(self.bot.pool, guild.id)  # type: ignore[attr-defined]
            autoclose_h = int(cfg.get("autoclose_hours", 0))
            remind_m = int(cfg.get("remind_minutes", 0))

            if autoclose_h <= 0 and remind_m <= 0:
                continue

            try:
                last_msg = await ch.fetch_message(ch.last_message_id) if ch.last_message_id else None
            except Exception:
                last_msg = None

            last_time = last_msg.created_at if last_msg else ch.created_at
            delta = discord.utils.utcnow() - last_time

            # Reminder?
            if remind_m > 0 and delta.total_seconds() > remind_m * 60:
                # Check if reminded already
                async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT reminded FROM ticket_autoclose_state WHERE channelID=%s", (ch.id,))
                        r = await cur.fetchone()
                        if not r or r[0] == 0:
                            await ch.send("<:Astra_time:1141303932061233202> Erinnerung: Bitte gib uns ein Update, sonst wird dieses Ticket automatisch geschlossen.")
                            await cur.execute("REPLACE INTO ticket_autoclose_state (channelID, reminded) VALUES (%s, %s)", (ch.id, 1))

            # Auto-Close?
            if autoclose_h > 0 and delta.total_seconds() > autoclose_h * 3600:
                # Simples Close ohne Log-Reopen (Task-Kontext) – ruft Button-Logik nicht erneut
                try:
                    await ch.send("<:Astra_locked:1141824745243942912> Dieses Ticket wurde wegen Inaktivität geschlossen.")
                except Exception:
                    pass
                try:
                    await ch.delete()
                except Exception:
                    pass
                async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
                    async with conn.cursor() as cur:
                        await cur.execute("DELETE FROM ticketsystem_channels WHERE channelID=%s", (ch.id,))
                        await cur.execute("DELETE FROM ticket_autoclose_state WHERE channelID=%s", (ch.id,))

    @autoclose_task.before_loop
    async def before_autoclose(self):
        await self.bot.wait_until_ready()

# =========================================================
#                      SETUP ENTRY
# =========================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
    # Slash-Gruppe registrieren
    bot.tree.add_command(Ticket(bot))
