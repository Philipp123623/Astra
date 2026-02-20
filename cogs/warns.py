import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import timedelta
from typing import Literal
import asyncio


# =========================================================
# ================= AUTOMOD SETUP VIEW ====================
# =========================================================

class AutomodSetupView(ui.LayoutView):

    TOTAL_STEPS = 4

    def __init__(self, bot: commands.Bot, invoker: discord.User):
        super().__init__(timeout=300)
        self.bot = bot
        self.invoker = invoker
        self.page = 0

        self.warn_threshold = None
        self.warn_action = None
        self.timeout_duration = 30

        self.caps_enabled = False
        self.caps_percent = 50

        self.blacklist_words = []

        self._build()

    def _progress(self):
        filled = int(self.page / self.TOTAL_STEPS * 14)
        return "█" * filled + "░" * (14 - filled)

    def _build(self):
        self.clear_items()

        container = ui.Container(
            accent_color=discord.Colour.orange().value
        )

        container.add_item(ui.TextDisplay(
            "# 🤖 Automod Setup\n"
            f"Schritt {self.page}/{self.TOTAL_STEPS}\n"
            f"`{self._progress()}`"
        ))

        container.add_item(ui.Separator())

        # ================= PAGE 0 =================

        if self.page == 0:
            container.add_item(ui.TextDisplay(
                "Willkommen im Automod Setup.\n\n"
                "Hier richtest du Warn-System, Caps-Filter\n"
                "und Blacklist zentral ein."
            ))

        # ================= PAGE 1 – WARN =================

        elif self.page == 1:

            container.add_item(ui.TextDisplay(
                f"Warn Grenze: {self.warn_threshold or 'Nicht gesetzt'}\n"
                f"Aktion: {self.warn_action or 'Nicht gesetzt'}"
            ))

            warn_select = ui.Select(
                placeholder="Warn Grenze",
                options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 11)]
            )

            async def warn_cb(interaction):
                self.warn_threshold = int(warn_select.values[0])
                self._build()
                await interaction.response.edit_message(view=self)

            warn_select.callback = warn_cb
            container.add_item(ui.ActionRow(warn_select))

            action_select = ui.Select(
                placeholder="Aktion",
                options=[
                    discord.SelectOption(label="Kick", value="Kick"),
                    discord.SelectOption(label="Ban", value="Ban"),
                    discord.SelectOption(label="Timeout", value="Timeout"),
                ]
            )

            async def action_cb(interaction):
                self.warn_action = action_select.values[0]
                self._build()
                await interaction.response.edit_message(view=self)

            action_select.callback = action_cb
            container.add_item(ui.ActionRow(action_select))

        # ================= PAGE 2 – CAPS =================

        elif self.page == 2:

            status = "Aktiv" if self.caps_enabled else "Deaktiviert"

            container.add_item(ui.TextDisplay(
                f"Caps Filter: {status}\nLimit: {self.caps_percent}%"
            ))

            toggle = ui.Button(label="Toggle", style=discord.ButtonStyle.secondary)

            async def toggle_cb(interaction):
                self.caps_enabled = not self.caps_enabled
                self._build()
                await interaction.response.edit_message(view=self)

            toggle.callback = toggle_cb
            container.add_item(ui.ActionRow(toggle))

            percent_select = ui.Select(
                placeholder="Prozent",
                options=[discord.SelectOption(label=f"{i}%", value=str(i)) for i in range(10, 101, 10)]
            )

            async def percent_cb(interaction):
                self.caps_percent = int(percent_select.values[0])
                self._build()
                await interaction.response.edit_message(view=self)

            percent_select.callback = percent_cb
            container.add_item(ui.ActionRow(percent_select))

        # ================= PAGE 3 – BLACKLIST =================

        elif self.page == 3:

            words = ", ".join(self.blacklist_words) or "Keine"

            container.add_item(ui.TextDisplay(
                f"Aktuelle Wörter:\n`{words}`"
            ))

            add_btn = ui.Button(label="Wort hinzufügen")

            async def add_cb(interaction):

                class WordModal(ui.Modal, title="Blacklist Wort"):
                    word = ui.TextInput(label="Wort")

                    async def on_submit(self, inter):
                        self.view.blacklist_words.append(self.word.value.lower())
                        self.view._build()
                        await inter.response.edit_message(view=self.view)

                await interaction.response.send_modal(WordModal())

            add_btn.callback = add_cb
            container.add_item(ui.ActionRow(add_btn))

        # ================= PAGE 4 – SAVE =================

        elif self.page == 4:

            container.add_item(ui.TextDisplay("Bestätige die Einrichtung."))

            save = ui.Button(label="Speichern", style=discord.ButtonStyle.success)

            async def save_cb(interaction):

                if interaction.user.id != self.invoker.id:
                    return await interaction.response.send_message(
                        "Nur der Ersteller darf speichern.",
                        ephemeral=True
                    )

                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cursor:

                        await cursor.execute("DELETE FROM automod WHERE guildID=%s", (interaction.guild.id,))
                        await cursor.execute("DELETE FROM capslock WHERE guildID=%s", (interaction.guild.id,))
                        await cursor.execute("DELETE FROM blacklist WHERE serverID=%s", (interaction.guild.id,))

                        if self.warn_threshold and self.warn_action:
                            await cursor.execute(
                                "INSERT INTO automod (guildID, warns, action) VALUES (%s,%s,%s)",
                                (interaction.guild.id, self.warn_threshold, self.warn_action)
                            )

                        if self.caps_enabled:
                            await cursor.execute(
                                "INSERT INTO capslock (guildID, percent) VALUES (%s,%s)",
                                (interaction.guild.id, self.caps_percent)
                            )

                        for word in self.blacklist_words:
                            await cursor.execute(
                                "INSERT INTO blacklist(word, serverID) VALUES (%s,%s)",
                                (word, interaction.guild.id)
                            )

                await interaction.response.edit_message(content="✅ Automod eingerichtet.", view=None)

            save.callback = save_cb
            container.add_item(ui.ActionRow(save))

        # ================= NAVIGATION =================

        nav = []

        if self.page > 0:
            back = ui.Button(label="Zurück")
            async def back_cb(interaction):
                self.page -= 1
                self._build()
                await interaction.response.edit_message(view=self)
            back.callback = back_cb
            nav.append(back)

        if self.page < self.TOTAL_STEPS:
            nxt = ui.Button(label="Weiter")
            async def next_cb(interaction):
                self.page += 1
                self._build()
                await interaction.response.edit_message(view=self)
            nxt.callback = next_cb
            nav.append(nxt)

        container.add_item(ui.ActionRow(*nav))
        self.add_item(container)


class AutomodConfigView(ui.LayoutView):

    def __init__(self, bot: commands.Bot, invoker: discord.User, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.invoker = invoker
        self.guild = guild

        self.warn_rules = []
        self.caps = None
        self.words = []

    async def start(self, interaction: discord.Interaction):
        await self._load_data()
        self._build()
        await interaction.response.send_message(view=self, ephemeral=True)

    async def _load_data(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute(
                    "SELECT warns, action FROM automod WHERE guildID=%s",
                    (self.guild.id,)
                )
                self.warn_rules = await cursor.fetchall()

                await cursor.execute(
                    "SELECT percent FROM capslock WHERE guildID=%s",
                    (self.guild.id,)
                )
                self.caps = await cursor.fetchone()

                await cursor.execute(
                    "SELECT word FROM blacklist WHERE serverID=%s",
                    (self.guild.id,)
                )
                self.words = await cursor.fetchall()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Nur der Command-Ersteller darf dieses Panel bedienen.",
                ephemeral=True
            )
            return False
        return True

    def _build(self):
        self.clear_items()

        container = ui.Container(
            accent_color=discord.Colour.blurple().value
        )

        container.add_item(ui.TextDisplay(
            "# ⚙️ Automod Konfiguration"
        ))

        container.add_item(ui.Separator())

        # ================= WARN RULES =================

        warn_text = (
            "Keine Regeln gesetzt."
            if not self.warn_rules
            else "\n".join([f"{w} → {a}" for w, a in self.warn_rules])
        )

        container.add_item(ui.TextDisplay(
            f"## Warn-Regeln\n{warn_text}"
        ))

        add_rule = ui.Button(label="Regel hinzufügen", style=discord.ButtonStyle.success)
        remove_rule = ui.Button(label="Regel entfernen", style=discord.ButtonStyle.danger)

        async def add_rule_cb(interaction):

            class RuleModal(ui.Modal, title="Neue Warn-Regel"):
                warns = ui.TextInput(label="Warn Grenze (1-10)")
                action = ui.TextInput(label="Aktion (Kick/Ban/Timeout)")

                async def on_submit(self, inter):
                    async with self.view.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "INSERT INTO automod (guildID, warns, action) VALUES (%s,%s,%s)",
                                (self.view.guild.id, self.warns.value, self.action.value)
                            )
                    await self.view._refresh(inter)

            await interaction.response.send_modal(RuleModal())

        async def remove_rule_cb(interaction):

            class RemoveModal(ui.Modal, title="Warn-Regel entfernen"):
                warns = ui.TextInput(label="Warn Grenze")

                async def on_submit(self, inter):
                    async with self.view.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "DELETE FROM automod WHERE guildID=%s AND warns=%s",
                                (self.view.guild.id, self.warns.value)
                            )
                    await self.view._refresh(inter)

            await interaction.response.send_modal(RemoveModal())

        add_rule.callback = add_rule_cb
        remove_rule.callback = remove_rule_cb

        container.add_item(ui.ActionRow(add_rule, remove_rule))

        container.add_item(ui.Separator())

        # ================= CAPS =================

        caps_status = (
            f"Aktiv ({self.caps[0]}%)"
            if self.caps
            else "Deaktiviert"
        )

        container.add_item(ui.TextDisplay(
            f"## Caps Filter\n{caps_status}"
        ))

        toggle_caps = ui.Button(label="Ein/Aus")
        set_percent = ui.Button(label="Prozent ändern")

        async def toggle_cb(interaction):
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    if self.caps:
                        await cursor.execute(
                            "DELETE FROM capslock WHERE guildID=%s",
                            (self.guild.id,)
                        )
                    else:
                        await cursor.execute(
                            "INSERT INTO capslock (guildID, percent) VALUES (%s,%s)",
                            (self.guild.id, 50)
                        )

            await self._refresh(interaction)

        async def percent_cb(interaction):

            class PercentModal(ui.Modal, title="Caps Prozent ändern"):
                percent = ui.TextInput(label="Neuer Prozentwert")

                async def on_submit(self, inter):
                    async with self.view.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "UPDATE capslock SET percent=%s WHERE guildID=%s",
                                (self.percent.value, self.view.guild.id)
                            )
                    await self.view._refresh(inter)

            await interaction.response.send_modal(PercentModal())

        toggle_caps.callback = toggle_cb
        set_percent.callback = percent_cb

        container.add_item(ui.ActionRow(toggle_caps, set_percent))

        container.add_item(ui.Separator())

        # ================= BLACKLIST =================

        words_text = (
            ", ".join([w[0] for w in self.words])
            if self.words
            else "Keine Wörter gesetzt."
        )

        container.add_item(ui.TextDisplay(
            f"## Blacklist\n{words_text}"
        ))

        add_word = ui.Button(label="Wort hinzufügen")
        remove_word = ui.Button(label="Wort entfernen")

        async def add_word_cb(interaction):

            class AddWord(ui.Modal, title="Blacklist Wort hinzufügen"):
                word = ui.TextInput(label="Wort")

                async def on_submit(self, inter):
                    async with self.view.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "INSERT INTO blacklist(word, serverID) VALUES (%s,%s)",
                                (self.word.value.lower(), self.view.guild.id)
                            )
                    await self.view._refresh(inter)

            await interaction.response.send_modal(AddWord())

        async def remove_word_cb(interaction):

            class RemoveWord(ui.Modal, title="Blacklist Wort entfernen"):
                word = ui.TextInput(label="Wort")

                async def on_submit(self, inter):
                    async with self.view.bot.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "DELETE FROM blacklist WHERE serverID=%s AND word=%s",
                                (self.view.guild.id, self.word.value.lower())
                            )
                    await self.view._refresh(inter)

            await interaction.response.send_modal(RemoveWord())

        add_word.callback = add_word_cb
        remove_word.callback = remove_word_cb

        container.add_item(ui.ActionRow(add_word, remove_word))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction):
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
