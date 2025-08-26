import discord
from discord.ext import commands
from discord import app_commands
import traceback
from typing import Literal
from datetime import datetime, timezone

# -----------------------------
# Tabellen (wie in deiner DB)
# tempchannels(guild_id BIGINT, channel_id BIGINT)
# usertempchannels(guildID BIGINT, userID BIGINT, channelID BIGINT)
# -----------------------------

# Zwischenspeicher für laufende Tempchannels (wird beim Neustart nicht befüllt – ist nur eine Optimierung)
tempchannels: list[int] = []


def isTempChannel(channel: discord.abc.GuildChannel) -> bool:
    return channel.id in tempchannels


async def isJoinHub(bot: commands.Bot, channel: discord.VoiceChannel) -> bool:
    """Prüft, ob der gejointe Voice der konfigurierte JoinHub ist."""
    async with bot.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute(
                    "SELECT channel_id FROM tempchannels WHERE guild_id = %s",
                    (channel.guild.id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return False
                return int(channel.id) == int(row[0])
            except Exception:
                return False


def build_threshold_overwrites(guild: discord.Guild, base_role: discord.Role, *, allow_connect: bool = True):
    """Overwrites: nur base_role und höher sehen/verbinden"""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True)
    }
    for r in guild.roles:
        if r.position >= base_role.position:
            overwrites[r] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True if allow_connect else None,
                speak=True if allow_connect else None
            )
    return overwrites


class RenameModal(discord.ui.Modal, title="Umbenennen"):
    name = discord.ui.TextInput(
        label="Name",
        style=discord.TextStyle.short,
        placeholder="Tippe den gewünschten Namen ein.",
        required=True,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )
        try:
            await vc.edit(name=str(self.name.value))
            await interaction.followup.send("✅ Kanal umbenannt.", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Konnte den Kanal nicht umbenennen.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        try:
            await interaction.response.send_message("Oops! Etwas ist schiefgelaufen", ephemeral=True)
        except Exception:
            pass
        traceback.print_tb(error.__traceback__)


class LimitModal(discord.ui.Modal, title="Limit"):
    limit = discord.ui.TextInput(
        label="Limit (0–99)",
        style=discord.TextStyle.short,
        placeholder="Tippe das gewünschte Kanal-Limit (0 für Standard).",
        required=True,
        max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )
        try:
            lim = int(str(self.limit.value).strip())
            if lim < 0 or lim > 99:
                return await interaction.followup.send(
                    "<:Astra_x:1141303954555289600> Das Limit **muss** zwischen **0–99** liegen.",
                    ephemeral=True,
                )
            await vc.edit(user_limit=lim)
            await interaction.followup.send("✅ Limit gesetzt.", ephemeral=True)
        except ValueError:
            await interaction.followup.send("❌ Bitte eine Zahl zwischen 0–99 eingeben.", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Konnte das Limit nicht setzen.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        try:
            await interaction.response.send_message("Oops! Etwas ist schiefgelaufen", ephemeral=True)
        except Exception:
            pass
        traceback.print_tb(error.__traceback__)


class TempChannelView(discord.ui.View):
    """Persistente Steuerelemente für den persönlichen Tempchannel."""
    def __init__(self):
        super().__init__(timeout=None)

    def _is_owner(self, owner_id: int, user_id: int) -> bool:
        return int(owner_id) == int(user_id)

    async def _get_owner_mapping(self, interaction: discord.Interaction):
        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT channelID, userID FROM usertempchannels WHERE guildID = %s AND channelID = %s",
                    (interaction.guild.id, getattr(interaction.user.voice.channel, "id", 0)),
                )
                return await cur.fetchone()

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_view:lock",
        emoji="<:Schloss_2:1141384576019730474>",
    )
    async def lock(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer(ephemeral=True)
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        row = await self._get_owner_mapping(interaction)
        if not row:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        channelID, ownerID = row
        if vc.id != int(channelID) or not self._is_owner(ownerID, interaction.user.id):
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Nur der Kanalbesitzer kann das.**", ephemeral=True
            )

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True),
            interaction.user: discord.PermissionOverwrite(connect=True, speak=True, view_channel=True),
            interaction.guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True),
        }
        try:
            await vc.edit(overwrites=overwrites)
            await interaction.followup.send("🔒 Kanal gesperrt (niemand sonst kann verbinden).", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Konnte den Kanal nicht sperren.", ephemeral=True)

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_view:unlock",
        emoji="<:Schloss:1141384573171802132>",
    )
    async def unlock(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer(ephemeral=True)
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        row = await self._get_owner_mapping(interaction)
        if not row:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        channelID, ownerID = row
        if vc.id != int(channelID) or not self._is_owner(ownerID, interaction.user.id):
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Nur der Kanalbesitzer kann das.**", ephemeral=True
            )

        # Entsperren = @everyone darf wieder connecten
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
            interaction.user: discord.PermissionOverwrite(connect=True, speak=True, view_channel=True),
            interaction.guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True),
        }
        try:
            await vc.edit(overwrites=overwrites)
            await interaction.followup.send("🔓 Kanal entsperrt (alle können verbinden).", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Konnte den Kanal nicht entsperren.", ephemeral=True)

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_view:hide",
        emoji="<:Verstecken:1141384593438683278>",
    )
    async def hide(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer(ephemeral=True)
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        row = await self._get_owner_mapping(interaction)
        if not row:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        channelID, ownerID = row
        if vc.id != int(channelID) or not self._is_owner(ownerID, interaction.user.id):
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Nur der Kanalbesitzer kann das.**", ephemeral=True
            )

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(connect=True, speak=True, view_channel=True),
            interaction.guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True),
        }
        try:
            await vc.edit(overwrites=overwrites)
            await interaction.followup.send("🙈 Kanal versteckt (nur du siehst ihn).", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Konnte den Kanal nicht verstecken.", ephemeral=True)

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_view:visible",
        emoji="<:Zeigen:1141384600384438324>",
    )
    async def visible(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer(ephemeral=True)
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        row = await self._get_owner_mapping(interaction)
        if not row:
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        channelID, ownerID = row
        if vc.id != int(channelID) or not self._is_owner(ownerID, interaction.user.id):
            return await interaction.followup.send(
                "<:Astra_x:1141303954555289600> **Nur der Kanalbesitzer kann das.**", ephemeral=True
            )

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
            interaction.user: discord.PermissionOverwrite(connect=True, speak=True, view_channel=True),
            interaction.guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True),
        }
        try:
            await vc.edit(overwrites=overwrites)
            await interaction.followup.send("👀 Kanal sichtbar für alle.", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ Konnte den Kanal nicht sichtbar machen.", ephemeral=True)

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_view:rename",
        emoji="<:Umbenennen:1141384590494290033>",
    )
    async def rename(self, interaction: discord.Interaction, button: discord.Button):
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        row = await self._get_owner_mapping(interaction)
        if not row:
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )
        channelID, ownerID = row
        if vc.id != int(channelID) or not self._is_owner(ownerID, interaction.user.id):
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> **Nur der Kanalbesitzer kann das.**", ephemeral=True
            )

        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_view:limit",
        emoji="<:Limit:1141319054674636870>",
    )
    async def limit(self, interaction: discord.Interaction, button: discord.Button):
        vc = getattr(interaction.user.voice, "channel", None)
        if not vc:
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )

        row = await self._get_owner_mapping(interaction)
        if not row:
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> **Du bist nicht in einem Tempchannel.**", ephemeral=True
            )
        channelID, ownerID = row
        if vc.id != int(channelID) or not self._is_owner(ownerID, interaction.user.id):
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> **Nur der Kanalbesitzer kann das.**", ephemeral=True
            )

        await interaction.response.send_modal(LimitModal())


class TempChannelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Persistente View registrieren
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TempChannelView())

    # ---------- Slash Commands ----------

    @app_commands.command(
        name="voicesetup",
        description="Erstellt, aktualisiert oder entfernt das Voice-Autoerstellungs-Setup."
    )
    @app_commands.describe(
        aktion="Was soll passieren?",
        sichtbarkeit="Wer darf JoinHub + Interface sehen? (nur bei 'erstellen')",
        rolle="Nur nötig, wenn sichtbarkeit='rolle'"
    )
    @app_commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def voicesetup(
            self,
            interaction: discord.Interaction,
            aktion: Literal["erstellen", "entfernen"],
            sichtbarkeit: Literal["jeder", "rolle", "privat"] = None,
            rolle: discord.Role | None = None
    ):
        await interaction.response.defer(ephemeral=True)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:

                # ---------------- Entfernen ----------------
                if aktion == "entfernen":
                    await cur.execute("SELECT channel_id FROM tempchannels WHERE guild_id = %s",
                                      (interaction.guild.id,))
                    row = await cur.fetchone()
                    if not row:
                        return await interaction.followup.send("❌ Kein Setup gefunden.", ephemeral=True)

                    joinhub = interaction.guild.get_channel(int(row[0]))
                    category = joinhub.category if joinhub else None

                    if joinhub:
                        try:
                            await joinhub.delete(reason="Voicesetup entfernt")
                        except Exception:
                            pass
                    if category:
                        try:
                            for ch in category.channels:
                                try:
                                    await ch.delete(reason="Voicesetup entfernt")
                                except Exception:
                                    pass
                            await category.delete(reason="Voicesetup entfernt")
                        except Exception:
                            pass

                    await cur.execute("DELETE FROM tempchannels WHERE guild_id = %s", (interaction.guild.id,))
                    await cur.execute("DELETE FROM usertempchannels WHERE guildID = %s", (interaction.guild.id,))
                    await conn.commit()
                    return await interaction.followup.send("✅ Voicesetup entfernt.", ephemeral=True)

                # ---------------- Erstellen/Aktualisieren ----------------
                if sichtbarkeit is None:
                    return await interaction.followup.send(
                        "❌ Bitte `sichtbarkeit` angeben, wenn du erstellen willst.", ephemeral=True
                    )

                # Overwrites wählen
                if sichtbarkeit == "jeder":
                    ovw = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True,
                                                                          manage_channels=True),
                    }
                elif sichtbarkeit == "privat":
                    ovw = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True,
                                                                          manage_channels=True),
                    }
                elif sichtbarkeit == "rolle":
                    if rolle is None:
                        return await interaction.followup.send("❌ Du musst eine Rolle angeben, wenn du `rolle` wählst.",
                                                               ephemeral=True)
                    ovw = build_threshold_overwrites(interaction.guild, rolle, allow_connect=True)

                # DB abfragen
                await cur.execute("SELECT channel_id FROM tempchannels WHERE guild_id = %s", (interaction.guild.id,))
                row = await cur.fetchone()

                if row is None:
                    # neu erstellen
                    category = await interaction.guild.create_category(
                        "Private Sprachkanäle", overwrites=ovw, reason="Voicesetup"
                    )
                    joinhub = await interaction.guild.create_voice_channel(
                        "Join to create", category=category, overwrites=ovw, reason="Voicesetup"
                    )
                    interface = await interaction.guild.create_text_channel(
                        "interface", category=category, overwrites=ovw, reason="Voicesetup"
                    )
                    embed = discord.Embed(
                        title="Interface",
                        description="> Stelle deinen Tempchannel mit den Buttons unten ein.",
                        colour=discord.Colour.blue()
                    )
                    await interface.send(embed=embed, view=TempChannelView())

                    await cur.execute(
                        "INSERT INTO tempchannels (guild_id, channel_id) VALUES (%s, %s)",
                        (interaction.guild.id, joinhub.id)
                    )
                    await conn.commit()

                    return await interaction.followup.send(
                        f"✅ Voicesetup erstellt (Sichtbarkeit: **{sichtbarkeit}**"
                        + (f" ab {rolle.mention}" if sichtbarkeit == "rolle" else "") + ")",
                        ephemeral=True
                    )
                else:
                    # aktualisieren
                    joinhub_id = int(row[0])
                    joinhub = interaction.guild.get_channel(joinhub_id)
                    category = joinhub.category if joinhub else None

                    if category:
                        await category.edit(overwrites=ovw, reason="Voicesetup aktualisiert")
                        interface = discord.utils.get(category.text_channels, name="interface")
                        if interface:
                            await interface.edit(overwrites=ovw, reason="Voicesetup aktualisiert")
                    if joinhub:
                        await joinhub.edit(overwrites=ovw, reason="Voicesetup aktualisiert")

                    return await interaction.followup.send(
                        f"🔁 Voicesetup aktualisiert (Sichtbarkeit: **{sichtbarkeit}**"
                        + (f" ab {rolle.mention}" if sichtbarkeit == "rolle" else "") + ")",
                        ephemeral=True
                    )

    # ---------- Voice Event ----------

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Wenn ein Tempchannel leer wird -> löschen
                if before and before.channel:
                    if isTempChannel(before.channel):
                        bchan = before.channel
                        if len(bchan.members) == 0:
                            try:
                                await bchan.delete(reason="Keine User im Sprachkanal.")
                            except Exception:
                                pass
                            try:
                                await cur.execute(
                                    "DELETE FROM usertempchannels WHERE guildID = %s AND channelID = %s",
                                    (before.channel.guild.id, before.channel.id)
                                )
                            except Exception:
                                pass
                            # Local Cache aufräumen
                            try:
                                tempchannels.remove(before.channel.id)
                            except ValueError:
                                pass

                # JoinHub gejoint -> persönlichen Kanal klonen und umziehen
                if after and after.channel:
                    try:
                        if await isJoinHub(self.bot, after.channel):
                            name = f"{member.name}"
                            output = await after.channel.clone(name=name, reason="JoinHub gejoined.")
                            if output:
                                tempchannels.append(output.id)
                                try:
                                    await member.move_to(output, reason="Tempchannel erstellt.")
                                except Exception:
                                    pass
                                try:
                                    await cur.execute(
                                        "INSERT INTO usertempchannels (guildID, userID, channelID) VALUES (%s, %s, %s)",
                                        (after.channel.guild.id, member.id, output.id)
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        # Fehler beim Prüfen des JoinHubs ignorieren
                        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TempChannelCog(bot))
