import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import timedelta
from typing import Literal
import asyncio


# =========================================================
# ================= AUTOMOD SETUP VIEW ====================
# =========================================================

class AutomodSetupView(discord.ui.LayoutView):

    TOTAL_STEPS = 4

    def __init__(self, bot: commands.Bot, invoker: discord.User):
        super().__init__(timeout=900)

        self.bot = bot
        self.invoker = invoker
        self.page = 0

        # Warn-System
        self.warn_rules: list[tuple[int, str, int | None]] = []

        # Caps
        self.caps_enabled: bool = False
        self.caps_percent: int = 50

        # Blacklist
        self.blacklist_words: list[str] = []

        self._build()

    # =========================================================
    # PROGRESS BAR
    # =========================================================

    def _progress_bar(self):
        if self.page == 0:
            return "░" * 14
        filled = int(self.page / self.TOTAL_STEPS * 14)
        return "█" * filled + "░" * (14 - filled)

    # =========================================================
    # BUILD
    # =========================================================

    def _build(self):
        self.clear_items()

        container = discord.ui.Container(
            accent_color=discord.Colour.orange().value
        )

        # =====================================================
        # HEADER SECTION
        # =====================================================

        container.add_item(discord.ui.TextDisplay(
            "# 🤖 Automod Setup\n"
            f"**Schritt {self.page}/{self.TOTAL_STEPS}**\n"
            f"`{self._progress_bar()}`"
        ))
        container.add_item(discord.ui.Separator())

        # =====================================================
        # PAGE 0 – WILLKOMMEN
        # =====================================================

        if self.page == 0:

            container.add_item(discord.ui.TextDisplay(
                "## Überblick\n\n"
                "<:Astra_punkt:1141303896745201696> **Warn-System konfigurieren**\n"
                "<:Astra_punkt:1141303896745201696> **Caps-Filter einstellen**\n"
                "<:Astra_punkt:1141303896745201696> **Blacklist verwalten**\n\n"
                "<:Astra_light_on:1141303864134467675> "
                "Alle Moderationsfunktionen werden hier zentral eingerichtet."
            ))

            container.add_item(discord.ui.Separator())

            start = discord.ui.Button(
                label="Setup starten",
                emoji="<:Astra_boost:1141303827107164270>",
                style=discord.ButtonStyle.success
            )

            async def start_cb(interaction):
                await self._switch(interaction, 1)

            start.callback = start_cb
            container.add_item(discord.ui.ActionRow(start))

        # =====================================================
        # PAGE 1 – WARN SYSTEM
        # =====================================================

        elif self.page == 1:

            rules_text = (
                "\n".join(
                    f"<:Astra_punkt:1141303896745201696> "
                    f"**{warns} Warns** → {action}"
                    + (f" (`{timeout}s Timeout`)" if timeout else "")
                    for warns, action, timeout in self.warn_rules
                )
                if self.warn_rules
                else "<:Astra_x:1141303954555289600> Keine Regeln gesetzt."
            )

            container.add_item(discord.ui.TextDisplay(
                "## Warn-System\n\n"
                f"{rules_text}\n\n"
                "<:Astra_light_on:1141303864134467675> "
                "Du kannst mehrere Eskalationsstufen definieren."
            ))

            container.add_item(discord.ui.Separator())

            add_btn = discord.ui.Button(
                label="Regel hinzufügen",
                emoji="<:Astra_accept:1141303821176422460>",
                style=discord.ButtonStyle.success
            )

            async def add_cb(interaction):

                class WarnModal(discord.ui.Modal, title="Neue Warn-Regel"):

                    warns = discord.ui.TextInput(label="Warn Grenze (1-10)")
                    action = discord.ui.TextInput(label="Aktion (Kick/Ban/Timeout)")
                    timeout_input = discord.ui.TextInput(
                        label="Timeout Sekunden (optional)",
                        required=False
                    )

                    def __init__(self, parent):
                        super().__init__()
                        self.parent = parent

                    async def on_submit(self, inter):

                        try:
                            warns_val = int(self.warns.value)
                        except:
                            return await inter.response.send_message(
                                "<:Astra_x:1141303954555289600> Ungültige Warn-Zahl.",
                                ephemeral=True
                            )

                        timeout_val = (
                            int(self.timeout_input.value)
                            if self.timeout_input.value else None
                        )

                        self.parent.warn_rules.append(
                            (warns_val, self.action.value.strip(), timeout_val)
                        )

                        self.parent._build()
                        await inter.response.edit_message(view=self.parent)

                await interaction.response.send_modal(WarnModal(self))

            add_btn.callback = add_cb
            container.add_item(discord.ui.ActionRow(add_btn))

        # =====================================================
        # PAGE 2 – CAPS FILTER
        # =====================================================

        elif self.page == 2:

            active = self.caps_enabled

            status_emoji = (
                "<:Astra_accept:1141303821176422460>"
                if active else
                "<:Astra_x:1141303954555289600>"
            )

            status_text = "Aktiv" if active else "Deaktiviert"

            toggle_label = "Ein" if not active else "Aus"
            toggle_style = (
                discord.ButtonStyle.success
                if not active else
                discord.ButtonStyle.danger
            )

            toggle_btn = discord.ui.Button(
                label=toggle_label,
                style=toggle_style
            )

            async def toggle_cb(interaction):
                self.caps_enabled = not self.caps_enabled
                self._build()
                await interaction.response.edit_message(view=self)

            toggle_btn.callback = toggle_cb

            section = discord.ui.Section(
                discord.ui.TextDisplay(
                    "## Caps-Filter\n\n"
                    f"{status_emoji} **Status:** {status_text}\n"
                    f"<:Astra_punkt:1141303896745201696> "
                    f"Limit: **{self.caps_percent}% Großbuchstaben**\n\n"
                    "<:Astra_light_on:1141303864134467675> "
                    "Nach Überschreitung wird die Nachricht gelöscht."
                ),
                accessory=toggle_btn
            )

            container.add_item(section)
            container.add_item(discord.ui.Separator())

            percent_select = discord.ui.Select(
                placeholder="Caps-Limit ändern",
                options=[
                    discord.SelectOption(label=f"{i}%", value=str(i))
                    for i in range(10, 101, 10)
                ]
            )

            async def percent_cb(interaction):
                self.caps_percent = int(percent_select.values[0])
                self._build()
                await interaction.response.edit_message(view=self)

            percent_select.callback = percent_cb
            container.add_item(discord.ui.ActionRow(percent_select))

        # =====================================================
        # PAGE 3 – BLACKLIST
        # =====================================================

        elif self.page == 3:

            words_text = (
                "\n".join(
                    f"<:Astra_punkt:1141303896745201696> `{w}`"
                    for w in self.blacklist_words
                )
                if self.blacklist_words
                else "<:Astra_x:1141303954555289600> Keine Wörter gesetzt."
            )

            container.add_item(discord.ui.TextDisplay(
                "## Blacklist\n\n"
                f"{words_text}\n\n"
                "<:Astra_light_on:1141303864134467675> "
                "Mehrere Wörter mit `,` trennen."
            ))

            container.add_item(discord.ui.Separator())

            add_btn = discord.ui.Button(
                label="Wörter hinzufügen",
                emoji="<:Astra_accept:1141303821176422460>",
                style=discord.ButtonStyle.primary
            )

            async def add_cb(interaction):

                class WordModal(discord.ui.Modal, title="Blacklist Wörter"):

                    words = discord.ui.TextInput(
                        label="Wörter (mit , trennen)"
                    )

                    def __init__(self, parent):
                        super().__init__()
                        self.parent = parent

                    async def on_submit(self, inter):

                        entries = [
                            w.strip().lower()
                            for w in self.words.value.split(",")
                            if w.strip()
                        ]

                        self.parent.blacklist_words.extend(entries)
                        self.parent._build()
                        await inter.response.edit_message(view=self.parent)

                await interaction.response.send_modal(WordModal(self))

            add_btn.callback = add_cb
            container.add_item(discord.ui.ActionRow(add_btn))

        # =====================================================
        # PAGE 4 – ÜBERSICHT & SPEICHERN
        # =====================================================

        elif self.page == 4:

            container.add_item(discord.ui.TextDisplay(
                "## Abschluss & Übersicht\n\n"
                f"<:Astra_punkt:1141303896745201696> "
                f"Warn-Regeln: **{len(self.warn_rules)}**\n"
                f"<:Astra_punkt:1141303896745201696> "
                f"Caps: **{'Aktiv' if self.caps_enabled else 'Deaktiviert'} "
                f"({self.caps_percent}%)**\n"
                f"<:Astra_punkt:1141303896745201696> "
                f"Blacklist: **{len(self.blacklist_words)} Wörter**\n\n"
                "<:Astra_accept:1141303821176422460> "
                "Wenn alles korrekt ist, kann gespeichert werden."
            ))

            container.add_item(discord.ui.Separator())

            save = discord.ui.Button(
                label="Automod speichern",
                emoji="<:Astra_accept:1141303821176422460>",
                style=discord.ButtonStyle.success
            )

            async def save_cb(interaction):

                if interaction.user.id != self.invoker.id:
                    return await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> "
                        "Nur der Ersteller darf speichern.",
                        ephemeral=True
                    )

                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cursor:

                        await cursor.execute(
                            "DELETE FROM automod WHERE guildID=%s",
                            (interaction.guild.id,)
                        )

                        await cursor.execute(
                            "DELETE FROM capslock WHERE guildID=%s",
                            (interaction.guild.id,)
                        )

                        await cursor.execute(
                            "DELETE FROM blacklist WHERE serverID=%s",
                            (interaction.guild.id,)
                        )

                        for warns, action, timeout in self.warn_rules:
                            await cursor.execute(
                                "INSERT INTO automod "
                                "(guildID, warns, action, timeout_seconds) "
                                "VALUES (%s,%s,%s,%s)",
                                (interaction.guild.id, warns, action, timeout)
                            )

                        if self.caps_enabled:
                            await cursor.execute(
                                "INSERT INTO capslock (guildID, percent) "
                                "VALUES (%s,%s)",
                                (interaction.guild.id, self.caps_percent)
                            )

                        for word in self.blacklist_words:
                            await cursor.execute(
                                "INSERT INTO blacklist (serverID, word) "
                                "VALUES (%s,%s)",
                                (interaction.guild.id, word)
                            )

                success_view = discord.ui.LayoutView()

                success_container = discord.ui.Container(
                    accent_color=discord.Colour.green().value
                )

                success_container.add_item(discord.ui.TextDisplay(
                    "## <:Astra_accept:1141303821176422460> Automod eingerichtet\n\n"
                    "Die Konfiguration wurde erfolgreich gespeichert.\n\n"
                    "Alle Moderationsfunktionen sind nun aktiv."
                ))

                success_view.add_item(success_container)

                await interaction.response.defer()

                await interaction.edit_original_response(
                    view=success_view
                )

            save.callback = save_cb
            container.add_item(discord.ui.ActionRow(save))

        # =====================================================
        # NAVIGATION
        # =====================================================

        nav = []

        if self.page > 0:
            back = discord.ui.Button(
                label="Zurück",
                emoji="<:Astra_arrow_backwards:1392540551546671348>",
                style=discord.ButtonStyle.secondary
            )

            async def back_cb(interaction):
                await self._switch(interaction, self.page - 1)

            back.callback = back_cb
            nav.append(back)

        if self.page < self.TOTAL_STEPS:
            nxt = discord.ui.Button(
                label="Weiter",
                emoji="<:Astra_arrow:1141303823600717885>",
                style=discord.ButtonStyle.primary
            )

            async def next_cb(interaction):
                await self._switch(interaction, self.page + 1)

            nxt.callback = next_cb
            nav.append(nxt)

        cancel = discord.ui.Button(
            label="Abbrechen",
            emoji="<:Astra_x:1141303954555289600>",
            style=discord.ButtonStyle.danger
        )

        async def cancel_cb(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()

        cancel.callback = cancel_cb
        nav.append(cancel)

        container.add_item(discord.ui.ActionRow(*nav))
        self.add_item(container)

    async def _switch(self, interaction, page: int):
        self.page = page
        self._build()
        await interaction.response.edit_message(view=self)


class AutomodConfigView(discord.ui.LayoutView):

    def __init__(self, bot: commands.Bot, invoker: discord.User, guild: discord.Guild):
        super().__init__(timeout=600)

        self.bot = bot
        self.invoker = invoker
        self.guild = guild

        self.warn_rules: list[tuple[int, str, int | None]] = []
        self.caps_percent: int | None = None
        self.words: list[str] = []

    # =========================================================
    # START
    # =========================================================

    async def start(self, interaction: discord.Interaction):
        await self._load_data()
        self._build()
        await interaction.response.send_message(view=self, ephemeral=True)

    # =========================================================
    # LOAD DATA
    # =========================================================

    async def _load_data(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute(
                    "SELECT warns, action, timeout_seconds FROM automod WHERE guildID=%s",
                    (self.guild.id,)
                )
                self.warn_rules = await cursor.fetchall()

                await cursor.execute(
                    "SELECT percent FROM capslock WHERE guildID=%s",
                    (self.guild.id,)
                )
                caps = await cursor.fetchone()
                self.caps_percent = caps[0] if caps else None

                await cursor.execute(
                    "SELECT word FROM blacklist WHERE serverID=%s",
                    (self.guild.id,)
                )
                words = await cursor.fetchall()
                self.words = [w[0] for w in words]

    # =========================================================
    # PERMISSION CHECK
    # =========================================================

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> "
                "Nur der Command-Ersteller darf dieses Panel bedienen.",
                ephemeral=True
            )
            return False
        return True

    # =========================================================
    # BUILD
    # =========================================================

    def _build(self):
        self.clear_items()

        container = discord.ui.Container(
            accent_color=discord.Colour.blurple().value
        )

        # =====================================================
        # HEADER SECTION
        # =====================================================

        container.add_item(discord.ui.TextDisplay(
            "# ⚙️ Automod Konfiguration\n\n"
                "<:Astra_light_on:1141303864134467675> "
                "Hier kannst du bestehende Moderations-Regeln anpassen."
        ))

        container.add_item(discord.ui.Separator())

        # =====================================================
        # WARN SYSTEM
        # =====================================================

        warn_text = (
            "\n".join(
                f"<:Astra_punkt:1141303896745201696> "
                f"**{w} Warns** → {a}"
                + (f" (`{t}s Timeout`)" if t else "")
                for w, a, t in self.warn_rules
            )
            if self.warn_rules
            else "<:Astra_x:1141303954555289600> Keine Regeln gesetzt."
        )

        container.add_item(discord.ui.TextDisplay(
            "## Warn-System\n\n"
            f"{warn_text}\n\n"
            "<:Astra_light_on:1141303864134467675> "
            "Regeln werden bei Erreichen der Warn-Grenze ausgelöst."
        ))

        container.add_item(discord.ui.Separator())

        add_rule = discord.ui.Button(
            label="Regel hinzufügen",
            emoji="<:Astra_accept:1141303821176422460>",
            style=discord.ButtonStyle.success
        )

        remove_rule = discord.ui.Button(
            label="Regel entfernen",
            emoji="<:Astra_x:1141303954555289600>",
            style=discord.ButtonStyle.danger
        )

        async def add_rule_cb(interaction):

            class RuleModal(discord.ui.Modal, title="Neue Warn-Regel"):

                warns = discord.ui.TextInput(label="Warn Grenze (1-10)")
                action = discord.ui.TextInput(label="Aktion (Kick/Ban/Timeout)")
                timeout_input = discord.ui.TextInput(
                    label="Timeout Sekunden (optional)",
                    required=False
                )

                def __init__(self, parent):
                    super().__init__()
                    self.parent = parent

                async def on_submit(self, inter):

                    timeout_val = (
                        int(self.timeout_input.value)
                        if self.timeout_input.value else None
                    )

                    async with self.parent.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "INSERT INTO automod "
                                "(guildID, warns, action, timeout_seconds) "
                                "VALUES (%s,%s,%s,%s)",
                                (
                                    self.parent.guild.id,
                                    self.warns.value,
                                    self.action.value,
                                    timeout_val
                                )
                            )

                    await self.parent.refresh_view(inter)

            await interaction.response.send_modal(RuleModal(self))

        async def remove_rule_cb(interaction):

            class RemoveModal(discord.ui.Modal, title="Warn-Regel entfernen"):

                warns = discord.ui.TextInput(label="Warn Grenze")

                def __init__(self, parent):
                    super().__init__()
                    self.parent = parent

                async def on_submit(self, inter):
                    async with self.parent.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "DELETE FROM automod "
                                "WHERE guildID=%s AND warns=%s",
                                (self.parent.guild.id, self.warns.value)
                            )

                    await self.parent.refresh_view(inter)

            await interaction.response.send_modal(RemoveModal(self))

        add_rule.callback = add_rule_cb
        remove_rule.callback = remove_rule_cb

        container.add_item(discord.ui.ActionRow(add_rule, remove_rule))
        container.add_item(discord.ui.Separator())

        # =====================================================
        # CAPS FILTER
        # =====================================================

        caps_enabled = self.caps_percent is not None

        status_emoji = (
            "<:Astra_accept:1141303821176422460>"
            if caps_enabled else
            "<:Astra_x:1141303954555289600>"
        )

        status_text = "Aktiv" if caps_enabled else "Deaktiviert"

        toggle_label = "Ein" if not caps_enabled else "Aus"
        toggle_style = (
            discord.ButtonStyle.success
            if not caps_enabled else
            discord.ButtonStyle.danger
        )

        toggle_btn = discord.ui.Button(
            label=toggle_label,
            style=toggle_style
        )

        async def toggle_caps(interaction):
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    if caps_enabled:
                        await cursor.execute(
                            "DELETE FROM capslock WHERE guildID=%s",
                            (self.guild.id,)
                        )
                    else:
                        await cursor.execute(
                            "INSERT INTO capslock (guildID, percent) "
                            "VALUES (%s,%s)",
                            (self.guild.id, 50)
                        )

            await self.refresh_view(interaction)

        toggle_btn.callback = toggle_caps

        section = discord.ui.Section(
            discord.ui.TextDisplay(
                "## Caps-Filter\n\n"
                f"{status_emoji} **Status:** {status_text}\n"
                f"<:Astra_punkt:1141303896745201696> "
                f"Limit: **{self.caps_percent or 50}%**\n\n"
                "<:Astra_light_on:1141303864134467675> "
                "Nach Überschreitung wird die Nachricht entfernt."
            ),
            accessory=toggle_btn
        )

        container.add_item(section)

        set_percent = discord.ui.Button(
            label="Prozent ändern",
            emoji="<:Astra_arrow:1141303823600717885>",
            style=discord.ButtonStyle.primary,
            disabled=not caps_enabled  # <-- DAS IST DIE LÖSUNG
        )

        async def percent_cb(interaction):

            class PercentModal(discord.ui.Modal, title="Caps Prozent ändern"):

                percent = discord.ui.TextInput(label="Neuer Prozentwert")

                def __init__(self, parent):
                    super().__init__()
                    self.parent = parent

                async def on_submit(self, inter):
                    async with self.parent.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "UPDATE capslock SET percent=%s "
                                "WHERE guildID=%s",
                                (self.percent.value, self.parent.guild.id)
                            )

                    await self.parent.refresh_view(inter)

            await interaction.response.send_modal(PercentModal(self))

        set_percent.callback = percent_cb

        container.add_item(discord.ui.ActionRow(set_percent))
        container.add_item(discord.ui.Separator())

        # =====================================================
        # BLACKLIST
        # =====================================================

        # Status getrennt vom Wort-Inhalt behandeln
        blacklist_enabled = "__enabled__" in self.words
        real_words = [w for w in self.words if w != "__enabled__"]

        status_emoji = (
            "<:Astra_accept:1141303821176422460>"
            if blacklist_enabled else
            "<:Astra_x:1141303954555289600>"
        )

        status_text = "Aktiv" if blacklist_enabled else "Deaktiviert"

        words_text = (
            "\n".join(
                f"<:Astra_punkt:1141303896745201696> `{w}`"
                for w in real_words
            )
            if real_words
            else "<:Astra_x:1141303954555289600> Keine Wörter gesetzt."
        )

        # ---------- TOGGLE BUTTON ----------

        toggle_label = "Aus" if blacklist_enabled else "Ein"

        toggle_style = (
            discord.ButtonStyle.danger  # Rot wenn aktiv
            if blacklist_enabled else
            discord.ButtonStyle.success  # Grün wenn deaktiviert
        )

        toggle_blacklist = discord.ui.Button(
            label=toggle_label,
            style=toggle_style
        )

        async def toggle_blacklist_cb(interaction):

            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:

                    if blacklist_enabled:
                        # deaktivieren → alles löschen
                        await cursor.execute(
                            "DELETE FROM blacklist WHERE serverID=%s",
                            (self.guild.id,)
                        )
                    else:
                        # aktivieren → Status-Eintrag setzen
                        await cursor.execute(
                            "INSERT INTO blacklist (serverID, word) VALUES (%s,%s)",
                            (self.guild.id, "__enabled__")
                        )

            await self.refresh_view(interaction)

        toggle_blacklist.callback = toggle_blacklist_cb

        # ---------- SECTION ----------

        blacklist_section = discord.ui.Section(
            discord.ui.TextDisplay(
                "## Blacklist\n\n"
                f"{status_emoji} Status: **{status_text}**\n\n"
                f"{words_text}\n\n"
                "<:Astra_light_on:1141303864134467675> "
                "Nachrichten mit diesen Wörtern werden automatisch gelöscht."
            ),
            accessory=toggle_blacklist
        )

        container.add_item(blacklist_section)
        container.add_item(discord.ui.Separator())

        # ---------- BUTTONS ----------

        add_word = discord.ui.Button(
            label="Wörter hinzufügen",
            emoji="<:Astra_accept:1141303821176422460>",
            style=discord.ButtonStyle.success,
            disabled=not blacklist_enabled
        )

        remove_word = discord.ui.Button(
            label="Wort entfernen",
            emoji="<:Astra_x:1141303954555289600>",
            style=discord.ButtonStyle.danger,
            disabled=not blacklist_enabled
        )

        # ---------- ADD WORD ----------

        async def add_word_cb(interaction):

            class AddWord(discord.ui.Modal, title="Blacklist Wörter hinzufügen"):
                words = discord.ui.TextInput(
                    label="Wörter (mit , trennen)"
                )

                def __init__(self, parent):
                    super().__init__()
                    self.parent = parent

                async def on_submit(self, inter):

                    entries = [
                        w.strip().lower()
                        for w in self.words.value.split(",")
                        if w.strip()
                    ]

                    async with self.parent.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:

                            # sicherstellen dass Status existiert
                            await cursor.execute(
                                "INSERT IGNORE INTO blacklist (serverID, word) VALUES (%s,%s)",
                                (self.parent.guild.id, "__enabled__")
                            )

                            for word in entries:
                                if word == "__enabled__":
                                    continue

                                await cursor.execute(
                                    "INSERT INTO blacklist (serverID, word) VALUES (%s,%s)",
                                    (self.parent.guild.id, word)
                                )

                    await self.parent.refresh_view(inter)

            await interaction.response.send_modal(AddWord(self))

        # ---------- REMOVE WORD ----------

        async def remove_word_cb(interaction):

            class RemoveWord(discord.ui.Modal, title="Blacklist Wort entfernen"):
                word = discord.ui.TextInput(label="Wort")

                def __init__(self, parent):
                    super().__init__()
                    self.parent = parent

                async def on_submit(self, inter):
                    async with self.parent.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "DELETE FROM blacklist "
                                "WHERE serverID=%s AND word=%s AND word != '__enabled__'",
                                (self.parent.guild.id, self.word.value.lower())
                            )

                    await self.parent.refresh_view(inter)

            await interaction.response.send_modal(RemoveWord(self))

        add_word.callback = add_word_cb
        remove_word.callback = remove_word_cb

        container.add_item(discord.ui.ActionRow(add_word, remove_word))
        self.add_item(container)

    # =========================================================
    # REFRESH
    # =========================================================

    async def refresh_view(self, interaction: discord.Interaction):
        await self._load_data()
        self._build()
        await interaction.response.edit_message(view=self)


@app_commands.guild_only()
class Automod(app_commands.Group):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(
            name="automod",
            description="Konfiguriere das Automod-System"
        )

    # =====================================================
    # SETUP
    # =====================================================

    @app_commands.command(
        name="setup",
        description="Starte das interaktive Automod Setup."
    )
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction):

        view = AutomodSetupView(self.bot, interaction.user)

        await interaction.response.send_message(
            view=view,
            ephemeral=True
        )

        # ── MODLOG ──
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = %s",
                    (interaction.guild.id,)
                )
                modlog = await cursor.fetchone()

                if modlog:
                    channel = interaction.guild.get_channel(int(modlog[0]))
                    if channel:
                        embed = discord.Embed(
                            title="⚙️ Automod Setup gestartet",
                            description=f"{interaction.user} (`{interaction.user.id}`) hat das Setup gestartet.",
                            colour=discord.Colour.orange(),
                            timestamp=discord.utils.utcnow()
                        )
                        await channel.send(embed=embed)

    # =====================================================
    # CONFIG
    # =====================================================

    @app_commands.command(
        name="config",
        description="Öffne das Automod Kontrollpanel."
    )
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config(self, interaction: discord.Interaction):

        view = AutomodConfigView(
            self.bot,
            interaction.user,
            interaction.guild
        )

        await view.start(interaction)

        # ── MODLOG ──
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT channelID FROM modlog WHERE serverID = %s",
                    (interaction.guild.id,)
                )
                modlog = await cursor.fetchone()

                if modlog:
                    channel = interaction.guild.get_channel(int(modlog[0]))
                    if channel:
                        embed = discord.Embed(
                            title="⚙️ Automod Config geöffnet",
                            description=f"{interaction.user} (`{interaction.user.id}`) hat das Config-Panel geöffnet.",
                            colour=discord.Colour.blurple(),
                            timestamp=discord.utils.utcnow()
                        )
                        await channel.send(embed=embed)

    # =====================================================
    # RESET
    # =====================================================

    @app_commands.command(
        name="reset",
        description="Setze das gesamte Automod-System zurück."
    )
    @app_commands.checks.cooldown(1, 10, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction):

        class ConfirmReset(ui.View):

            def __init__(self, bot):
                super().__init__(timeout=30)
                self.bot = bot

            @ui.button(label="Bestätigen", style=discord.ButtonStyle.danger)
            async def confirm(self, inter: discord.Interaction, button: ui.Button):

                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("DELETE FROM automod WHERE guildID=%s", (inter.guild.id,))
                        await cursor.execute("DELETE FROM capslock WHERE guildID=%s", (inter.guild.id,))
                        await cursor.execute("DELETE FROM blacklist WHERE serverID=%s", (inter.guild.id,))

                await inter.response.edit_message(
                    content="🗑️ Automod wurde vollständig zurückgesetzt.",
                    view=None
                )

                # ── MODLOG ──
                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "SELECT channelID FROM modlog WHERE serverID = %s",
                            (inter.guild.id,)
                        )
                        modlog = await cursor.fetchone()

                        if modlog:
                            channel = inter.guild.get_channel(int(modlog[0]))
                            if channel:
                                embed = discord.Embed(
                                    title="🗑️ Automod Reset",
                                    description=f"{inter.user} (`{inter.user.id}`) hat Automod zurückgesetzt.",
                                    colour=discord.Colour.red(),
                                    timestamp=discord.utils.utcnow()
                                )
                                await channel.send(embed=embed)

            @ui.button(label="Abbrechen", style=discord.ButtonStyle.secondary)
            async def cancel(self, inter: discord.Interaction, button: ui.Button):
                await inter.response.edit_message(
                    content="Reset abgebrochen.",
                    view=None
                )

        await interaction.response.send_message(
            "⚠️ Möchtest du wirklich ALLE Automod-Regeln löschen?",
            view=ConfirmReset(self.bot),
            ephemeral=True
        )
# =========================================================
# ===================== AUTOMOD COG =======================
# =========================================================



class Warn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="Warne einen User.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        """Warne einen User."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT reason FROM warns WHERE userID = (%s) AND guildID = (%s)",
                    (member.id, interaction.guild.id)
                )
                result = await cursor.fetchall()

                # ─────────────────────────────
                # ERSTE VERWARNUNG
                # ─────────────────────────────
                if result == ():
                    warnid = 1
                    await cursor.execute(
                        "INSERT INTO warns (guildID, userID, reason, warnID) VALUES (%s, %s, %s, %s)",
                        (interaction.guild.id, member.id, reason, 1)
                    )

                    embed = discord.Embed(
                        title="Neue Verwarnung",
                        description=(
                            f"Der User {member.mention} wurde mit der Warn-ID ``{warnid}`` "
                            f"für folgenden Grund verwarnt:\n\n"
                            f"📄 **Grund:** `{reason}`\n\n"
                            f"Nutze `/warn`, um weitere Verwarnungen auszusprechen."
                        ),
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed)

                    await cursor.execute(
                        "SELECT channelID FROM modlog WHERE serverID = (%s)",
                        (interaction.guild.id,)
                    )
                    modlog = await cursor.fetchone()

                    if modlog is not None:
                        channel = interaction.guild.get_channel(int(modlog[0]))
                        log_embed = discord.Embed(
                            colour=discord.Colour.orange(),
                            description=f"Der User {member} (`{member.id}`) wurde verwarnt."
                        )
                        log_embed.add_field(name="👤 Member", value=member.mention, inline=False)
                        log_embed.add_field(
                            name="👮 Moderator",
                            value=f"{interaction.user} (`{interaction.user.id}`)",
                            inline=False
                        )
                        log_embed.add_field(name="📄 Grund", value=reason, inline=False)
                        log_embed.set_author(name=member, icon_url=member.avatar)
                        await channel.send(embed=log_embed)

                # ─────────────────────────────
                # WEITERE VERWARNUNGEN
                # ─────────────────────────────
                if result:
                    warnid = len(result) + 1
                    await cursor.execute(
                        "INSERT INTO warns (guildID, userID, reason, warnID) VALUES (%s, %s, %s, %s)",
                        (interaction.guild.id, member.id, reason, warnid)
                    )

                    embed2 = discord.Embed(
                        title="Verwarnung hinzugefügt",
                        description=(
                            f"Der User {member.mention} wurde erfolgreich verwarnt.\n\n"
                            f"🆔 **Warn-ID:** ``{warnid}``\n"
                            f"📄 **Grund:** `{reason}`\n\n"
                            f"Nutze `/warn`, um weitere Verwarnungen zu vergeben."
                        ),
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed2)

                    await cursor.execute(
                        "SELECT channelID FROM modlog WHERE serverID = (%s)",
                        (interaction.guild.id,)
                    )
                    modlog = await cursor.fetchone()

                    if modlog is not None:
                        channel = interaction.guild.get_channel(int(modlog[0]))
                        log_embed = discord.Embed(
                            colour=discord.Colour.orange(),
                            description=f"Der User {member} (`{member.id}`) wurde erneut verwarnt."
                        )
                        log_embed.add_field(name="👤 Member", value=member.mention, inline=False)
                        log_embed.add_field(
                            name="👮 Moderator",
                            value=f"{interaction.user} (`{interaction.user.id}`)",
                            inline=False
                        )
                        log_embed.add_field(name="📄 Grund", value=reason, inline=False)
                        log_embed.set_author(name=member, icon_url=member.avatar)
                        await channel.send(embed=log_embed)

                # ─────────────────────────────
                # AUTOMOD CHECK
                # ─────────────────────────────
                await cursor.execute(
                    "SELECT action, warns FROM automod WHERE guildID = (%s)",
                    (interaction.guild.id,)
                )
                result3 = await cursor.fetchall()

                if result3:
                    await cursor.execute(
                        "SELECT max(warnID) FROM warns WHERE guildID = (%s) AND userID = (%s)",
                        (interaction.guild.id, member.id)
                    )
                    warnings = await cursor.fetchone()
                    warns2 = warnings[0]

                    for eintrag in result3:
                        action = eintrag[0]
                        warns = eintrag[1]

                        if int(warns2) >= int(warns):
                            await cursor.execute(
                                "SELECT channelID FROM modlog WHERE serverID = (%s)",
                                (interaction.guild.id,)
                            )
                            modlog = await cursor.fetchone()

                            # ── AUTOMOD LOG ──
                            if modlog is not None:
                                channel = interaction.guild.get_channel(int(modlog[0]))
                                auto_embed = discord.Embed(
                                    title="🤖 Automod ausgelöst",
                                    colour=discord.Colour.dark_orange(),
                                    timestamp=discord.utils.utcnow()
                                )
                                auto_embed.add_field(name="👤 Member", value=member.mention, inline=False)
                                auto_embed.add_field(
                                    name="📊 Verwarnungen",
                                    value=f"{warns2} / {warns}",
                                    inline=True
                                )
                                auto_embed.add_field(name="⚙️ Aktion", value=action, inline=True)
                                auto_embed.add_field(name="🔔 Auslöser", value="Warn-System", inline=False)
                                await channel.send(embed=auto_embed)

                            # ── AKTION ──
                            if action == "Kick":
                                await member.kick(reason="Automod")

                            if action == "Ban":
                                await member.ban(reason="Automod")

                            if action == "Timeout":
                                await member.timeout(
                                    timedelta(seconds=30),
                                    reason="Automod"
                                )

    @app_commands.command(name="unwarn", description="Entferne Warns von einem User.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member, warnid: int):
        """Entferne Warns von einem User.."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT warnID, userID FROM warns WHERE guildID = (%s)", (interaction.guild.id))
                result = await cursor.fetchall()

                if result:
                    await cursor.execute("DELETE FROM warns WHERE guildID = (%s) AND warnID = (%s) AND userID = (%s)",
                                         (interaction.guild.id, warnid, member.id))
                    embed2 = discord.Embed(title="Verwarnung gelöscht",
                                           description=f"Die Verwarnung des Users {member.mention} mit der ID: ``{warnid}``wurde gelöscht.\nUm jemanden zu warnen nutze `/warn`.",
                                           color=discord.Color.green())
                    await interaction.response.send_message(embed=embed2)
                if not result:
                    embed2 = discord.Embed(title="Keine Aktuellen erwarnungen",
                                           description=f"Es gibt aktuell keine Verwarnungen für den User {member.mention} mit der WarnID: ``{warnid}``!\nUm jemanden zu warnen nutze `/warn`.",
                                           color=discord.Color.green())
                    await interaction.response.send_message(embed=embed2)

    @app_commands.command(name="warns", description="Erhalte eine Liste mit allen Warns eines Users.")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warns(self, interaction: discord.Interaction, member: discord.Member):
        """Erhalte eine Liste mit allen Warns eines Users."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT reason, warnID FROM warns WHERE guildID = (%s) AND userID = (%s)",
                                     (interaction.guild.id, member.id))
                result = await cursor.fetchall()
                if result == ():
                    embed2 = discord.Embed(title=f"Verwarnungen für {member.name}, {member.id}",
                                           description=f"Der User {member.name} hat keine Verwarnungen.\nUm jemanden zu warnen nutze `/warn`.",
                                           color=discord.Color.blue())
                    await interaction.response.send_message(embed=embed2)

                else:
                    embed = discord.Embed(title=f"Verwarnungen für {member.name}, {member.id}",
                                          description=f"Um jemanden zu warnen nutze `/warn`.\nUm jemanden eine Verwarnung zu entfernen nutze `/unwarn`.",
                                          color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                    embed.set_author(name=interaction.user, icon_url=interaction.user.avatar)
                    for eintrag in result:
                        reason = eintrag[0]
                        warnID = eintrag[1]

                        embed.add_field(name=f"WarnID: {warnID}", value=f"Grund: {reason}",
                                        inline=True)

                    await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Warn(bot))
    bot.tree.add_command(Automod(bot))
