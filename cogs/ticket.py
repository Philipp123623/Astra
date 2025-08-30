# -*- coding: utf-8 -*-
import os
import io
import re
import html
import asyncio
from typing import Optional, Literal, List, Tuple

import discord
from discord.ext import commands, tasks
from discord import app_commands

ASTRA_BLUE = discord.Colour.blue()

# =========================================================
#                      HELPERS
# =========================================================

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


class SetupWizardView(discord.ui.View):
    """Geführter Wizard: Kanal/Kategorie/Rolle → Modal → Erstellen"""

    def __init__(self, bot: commands.Bot, invoker: discord.User):
        super().__init__(timeout=600)
        self.bot = bot
        self.invoker = invoker

        # State
        self.target_channel: Optional[discord.TextChannel] = None
        self.category: Optional[discord.CategoryChannel] = None
        self.role: Optional[discord.Role] = None
        self.panel_title: Optional[str] = None
        self.panel_desc: Optional[str] = None

        self.btn_next.disabled = True
        self.btn_create.disabled = True

    # ---------- Selects (discord.py-kompatibel) ----------

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Wähle Ziel-Kanal (Text)",
        channel_types=[discord.ChannelType.text],
        min_values=1, max_values=1,
        custom_id="ticket_setup:channel",
    )
    async def sel_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.target_channel = select.values[0]  # type: ignore
        await self._redraw(interaction)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Wähle Ticket-Kategorie",
        channel_types=[discord.ChannelType.category],
        min_values=1, max_values=1,
        custom_id="ticket_setup:category",
    )
    async def sel_category(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.category = select.values[0]  # type: ignore
        await self._redraw(interaction)

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Wähle Support-Rolle",
        min_values=1, max_values=1,
        custom_id="ticket_setup:role",
    )
    async def sel_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.role = select.values[0]
        await self._redraw(interaction)

    # ---------- Buttons ----------

    @discord.ui.button(label="Weiter (Titel & Beschreibung)", style=discord.ButtonStyle.blurple,
                       custom_id="ticket_setup:next")
    async def btn_next(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.invoker.id:
            return await interaction.response.send_message("Nur der Ersteller darf diesen Wizard bedienen.", ephemeral=True)
        await interaction.response.send_modal(PanelTextModal(self._after_texts))

    @discord.ui.button(label="Erstellen", style=discord.ButtonStyle.green,
                       custom_id="ticket_setup:create")
    async def btn_create(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.invoker.id:
            return await interaction.response.send_message("Nur der Ersteller darf diesen Wizard bedienen.",
                                                           ephemeral=True)

        assert self.target_channel and self.category and self.role and self.panel_title and self.panel_desc

        # ⬇️ Wrapper -> echte Objekte
        guild = interaction.guild
        chan = guild.get_channel(int(self.target_channel.id)) or await guild.fetch_channel(int(self.target_channel.id))
        cat = guild.get_channel(int(self.category.id))  # nur für Anzeige/Validierung
        role = guild.get_role(int(self.role.id))

        if not isinstance(chan, discord.TextChannel):
            return await interaction.response.send_message("Der gewählte Kanal ist kein Textkanal.", ephemeral=True)
        if not isinstance(cat, discord.CategoryChannel):
            return await interaction.response.send_message("Die gewählte Kategorie existiert nicht mehr.",
                                                           ephemeral=True)
        if role is None:
            return await interaction.response.send_message("Die gewählte Rolle existiert nicht mehr.", ephemeral=True)

        # DB schreiben
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO ticketsystem(guildID, channelID, thema, roleID, categoryID) VALUES(%s, %s, %s, %s, %s)",
                    (guild.id, chan.id, self.panel_title, role.id, cat.id),
                )

        # Panel posten
        panel = mk_embed(
            title=self.panel_title,
            description=self.panel_desc,
            color=ASTRA_BLUE,
            thumb=guild.icon.url if guild and guild.icon else None,
            footer="Klicke auf den Button, um ein Ticket zu erstellen!",
        )
        await chan.send(embed=panel, view=TicketOpenView(self.bot))

        # Abschlussmeldung
        done = mk_embed(
            title="✅ Ticket-Panel erstellt",
            description=(
                f"**Kanal:** <#{chan.id}>\n"
                f"**Kategorie:** {cat.name}\n"
                f"**Support-Rolle:** {role.mention}\n\n"
                "Du kannst diesen Wizard jetzt schließen."
            ),
            color=discord.Colour.green(),
        )
        await interaction.response.edit_message(embed=done, view=None)
        return None

    @discord.ui.button(label="Abbrechen", style=discord.ButtonStyle.red,
                       custom_id="ticket_setup:cancel")
    async def btn_cancel(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.invoker.id:
            return await interaction.response.send_message("Nur der Ersteller darf diesen Wizard bedienen.", ephemeral=True)
        await interaction.response.edit_message(
            embed=mk_embed(title="❌ Abgebrochen", description="Der Setup-Wizard wurde beendet."),
            view=None
        )

    # ---------- Helpers (umbenannt!) ----------

    def build_embed(self) -> discord.Embed:
        def lbl_channel(ch):
            return ch.mention if isinstance(ch, discord.TextChannel) else "Nicht gesetzt"

        def lbl_cat(cat):
            return cat.name if isinstance(cat, discord.CategoryChannel) else "Nicht gesetzt"

        def lbl_role(r):
            return r.mention if isinstance(r, discord.Role) else "Nicht gesetzt"

        lines = []
        lines.append("**So funktioniert's:**")
        lines.append("1️⃣ Wähle **Ziel-Kanal**, **Kategorie** und **Support-Rolle** über die Menüs.")
        lines.append("2️⃣ Klicke **Weiter**, um Titel & Beschreibung einzutragen.")
        lines.append("3️⃣ Klicke **Erstellen**, um das Panel zu posten.\n")
        lines.append("**Aktuelle Auswahl:**")
        lines.append(f"• Kanal: {lbl_channel(self.target_channel)}")
        lines.append(f"• Kategorie: {lbl_cat(self.category)}")
        lines.append(f"• Support-Rolle: {lbl_role(self.role)}")
        if self.panel_title or self.panel_desc:
            lines.append(f"• Titel: {self.panel_title or 'Nicht gesetzt'}")
            if self.panel_desc:
                short = self.panel_desc[:80] + ("…" if len(self.panel_desc) > 80 else "")
                lines.append(f"• Beschreibung: {short}")
            else:
                lines.append("• Beschreibung: Nicht gesetzt")

        return mk_embed(title="🎟️ Ticket-Setup-Wizard", description="\n".join(lines), color=ASTRA_BLUE)

    async def _after_texts(self, interaction: discord.Interaction, title: str, desc: str):
        self.panel_title = title.strip()
        self.panel_desc = desc.strip()
        self.btn_create.disabled = not (self.panel_title and self.panel_desc)
        await self._redraw(interaction)

    async def _redraw(self, interaction: discord.Interaction):
        self.btn_next.disabled = not (self.target_channel and self.category and self.role)
        self.btn_create.disabled = not (self.panel_title and self.panel_desc)
        embed = self.build_embed()

        try:
            # Falls die Response noch nicht benutzt wurde:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.InteractionResponded:
            # Wenn schon geantwortet: Original-Message updaten
            await interaction.edit_original_response(embed=embed, view=self)


# =========================================================
#                  IN-TICKET VIEWS (CLAIM/CLOSE)
# =========================================================

class ReopenView(discord.ui.View):
    """Button im Log, um innerhalb X Stunden das Ticket neu zu öffnen."""
    def __init__(self, bot: commands.Bot, guild_id: int, opener_id: int, thema: str, category_id: int, role_id: int, expires_ts: int):
        super().__init__(timeout=expires_ts - int(discord.utils.utcnow().timestamp()))
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

        await interaction.response.send_message(f"✅ Ticket neu geöffnet: {new_channel.mention}", ephemeral=True)


class TicketButtons(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Schließen", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket:close")
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
            return await interaction.response.send_message("Dieses Ticket ist keinem Panel zugeordnet.", ephemeral=True)
        role_id, thema = int(row[0]), row[1]
        role = guild.get_role(role_id)
        if role not in user.roles:
            return await interaction.response.send_message("Nur Mitglieder mit der Support-Rolle dürfen Tickets schließen.", ephemeral=True)

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
                if reason_text:
                    header_lines.append(f"Schließ-Grund: {reason_text}")
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

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, emoji="👮‍♂️", custom_id="ticket:claim")
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
            return await interaction.response.send_message("Dieses Ticket ist keinem Panel zugeordnet.", ephemeral=True)

        role_id, thematext = int(row[0]), row[1]
        role = guild.get_role(role_id)
        if role not in member.roles:
            return await interaction.response.send_message("Nur Mitglieder mit der Support-Rolle dürfen Tickets claimen.", ephemeral=True)

        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("SELECT msgID, opened FROM ticketsystem_channels WHERE channelID=%s", (channel.id,))
                row2 = await cur.fetchone()
                if not row2:
                    return await interaction.response.send_message("Interner Fehler (kein DB-Eintrag).", ephemeral=True)
                msg_id, opened_id = row2
                await cur.execute("UPDATE ticketsystem_channels SET claimed=%s WHERE channelID=%s", (member.id, channel.id))

        msg = await channel.fetch_message(int(msg_id))
        opener = interaction.client.get_user(int(opened_id))

        # Schönes Embed + Button lokal deaktivieren
        embed = mk_embed(
            title=f"Ticket von {opener.name}",
            description=f"Hallo {opener.mention}, {member.mention} kümmert sich um dein Anliegen. "
                        f"Bitte beschreibe kurz dein Problem.",
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

    @discord.ui.button(label="Ticket öffnen", style=discord.ButtonStyle.green, emoji="🎫", custom_id="ticket_panel:open")
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
            return await interaction.response.send_message("Für diesen Kanal ist kein Ticket-Panel hinterlegt.", ephemeral=True)

        category_id, thema, role_id = int(row[0]), row[1], int(row[2])
        category = guild.get_channel(category_id)
        role = guild.get_role(role_id)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message("Die hinterlegte Ticket-Kategorie existiert nicht mehr.", ephemeral=True)

        # Schon ein Ticket?
        for ch in category.text_channels:
            if ch.topic == str(user.id):
                return await interaction.response.send_message("Du hast bereits ein offenes Ticket in dieser Kategorie.", ephemeral=True)

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

        await interaction.response.send_message(f"✅ Dein Ticket wurde erstellt: {new_channel.mention}", ephemeral=True)

# =========================================================
#                     SLASH COMMANDS
# =========================================================

@app_commands.guild_only()
class Ticket(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(name="ticket", description="Alles rund ums Ticketsystem.")

    @app_commands.command(name="setup", description="Starte den Setup-Wizard für ein Ticket-Panel.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def ticket_setup(self, interaction: discord.Interaction):
        view = SetupWizardView(self.bot, interaction.user)
        # KEINE Defaults setzen – alles bleibt None

        # Embed aus dem View selbst generieren
        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True
        )

    # Panels auflisten
    @app_commands.command(name="anzeigen", description="Listet alle Ticket-Panels dieses Servers auf.")
    @app_commands.checks.has_permissions(administrator=True)
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

    # Panel löschen
    @app_commands.command(name="löschen", description="Lösche ein Ticket-Panel.")
    @app_commands.describe(channel="Kanal mit dem Ticket-Panel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def ticket_delete(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM ticketsystem WHERE channelID=%s AND guildID=%s", (channel.id, interaction.guild.id))
        await interaction.response.send_message("✅ Panel gelöscht.", ephemeral=True)

    # Ticket-Log konfigurieren
    @app_commands.command(name="log", description="Richte einen Ticket-Log-Kanal ein/aus.")
    @app_commands.describe(argument="Einschalten oder Ausschalten.", channel="Log-Kanal")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketlog(self, interaction: discord.Interaction, argument: Literal["Einschalten", "Ausschalten"], channel: Optional[discord.TextChannel] = None):
        async with self.bot.pool.acquire() as conn:  # type: ignore[attr-defined]
            async with conn.cursor() as cur:
                if argument == "Einschalten":
                    if not channel:
                        return await interaction.response.send_message("Bitte einen Log-Kanal angeben.", ephemeral=True)
                    await cur.execute("REPLACE INTO ticketlog (guildID, channelID) VALUES (%s,%s)", (interaction.guild.id, channel.id))
                    await interaction.response.send_message(f"✅ Ticket-Log aktiviert: {channel.mention}", ephemeral=True)
                else:
                    await cur.execute("DELETE FROM ticketlog WHERE guildID=%s", (interaction.guild.id,))
                    await interaction.response.send_message("✅ Ticket-Log deaktiviert.", ephemeral=True)

    # Konfiguration: Auto-Close & Reminder & Reopen
    @app_commands.command(name="config", description="Konfiguriere Auto-Close/Reminder/Reopen.")
    @app_commands.describe(
        autoclose_hours="Stunden bis Auto-Close (0=aus)",
        remind_minutes="Minuten bis Reminder (0=aus)",
        reopen_hours="Stunden, in denen Reopen möglich ist",
        ping_throttle_minutes="(Reserviert) Minuten für Ping-Throttle"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_config(
        self,
        interaction: discord.Interaction,
        autoclose_hours: Optional[int] = None,
        remind_minutes: Optional[int] = None,
        reopen_hours: Optional[int] = None,
        ping_throttle_minutes: Optional[int] = None,
    ):
        updates = {}
        for k, v in dict(
            autoclose_hours=autoclose_hours,
            remind_minutes=remind_minutes,
            reopen_hours=reopen_hours,
            ping_throttle_minutes=ping_throttle_minutes,
        ).items():
            if v is not None and v >= 0:
                updates[k] = v
        if updates:
            await set_guild_config(self.bot.pool, interaction.guild.id, **updates)  # type: ignore[attr-defined]
        cfg = await get_guild_config(self.bot.pool, interaction.guild.id)  # type: ignore[attr-defined]

        e = mk_embed(
            title="⚙️ Ticket-Konfiguration",
            description=(
                f"**Auto-Close:** {cfg['autoclose_hours']} h\n"
                f"**Reminder:** {cfg['remind_minutes']} min\n"
                f"**Reopen:** {cfg['reopen_hours']} h\n"
                f"**Ping-Throttle:** {cfg['ping_throttle_minutes']} min"
            ),
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

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
                            await ch.send("⏰ Erinnerung: Bitte gib uns ein Update, sonst wird dieses Ticket automatisch geschlossen.")
                            await cur.execute("REPLACE INTO ticket_autoclose_state (channelID, reminded) VALUES (%s, %s)", (ch.id, 1))

            # Auto-Close?
            if autoclose_h > 0 and delta.total_seconds() > autoclose_h * 3600:
                # Simples Close ohne Log-Reopen (Task-Kontext) – ruft Button-Logik nicht erneut
                try:
                    await ch.send("🔒 Dieses Ticket wurde wegen Inaktivität geschlossen.")
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
