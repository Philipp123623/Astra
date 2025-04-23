import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction
from typing import List, Optional, Literal
import aiomysql

class RoleConfigModal(ui.Modal, title="Rolle konfigurieren"):
    label_input = ui.TextInput(label="Anzeigename für die Rolle", required=True)
    emoji_input = ui.TextInput(label="Emoji (Standard oder benutzerdefiniert)", required=False)

    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role

    async def on_submit(self, interaction: Interaction):
        self.result = {
            "role_id": self.role.id,
            "label": self.label_input.value,
            "emoji": self.emoji_input.value or None
        }
        await interaction.response.defer()
        self.stop()

class FinalEmbedModal(ui.Modal, title="Erstelle das endgültige Embed"):
    title_input = ui.TextInput(label="Embed Titel", max_length=256, required=True)
    desc_input = ui.TextInput(label="Embed Beschreibung", style=discord.TextStyle.paragraph, required=True)
    color_input = ui.TextInput(label="Farbe (Hex, optional)", required=False)
    thumbnail_input = ui.TextInput(label="Thumbnail URL (optional)", required=False)
    image_input = ui.TextInput(label="Image URL (optional)", required=False)

    async def on_submit(self, interaction: Interaction):
        self.embed_data = {
            "title": self.title_input.value,
            "description": self.desc_input.value,
            "color": int(self.color_input.value.lstrip('#'), 16) if self.color_input.value else 0x2F3136,
            "thumbnail": self.thumbnail_input.value,
            "image": self.image_input.value
        }
        await interaction.response.defer()
        self.stop()

class RoleSelectView(ui.View):
    def __init__(self, interaction: discord.Interaction, roles: List[discord.Role]):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.roles = roles
        self.selected = []
        self.role_data = []
        self.embed_message = None
        self.embed = discord.Embed(title="Reaktionsrollen Setup", description="Hier kannst du mithilfe von Buttons, Reaktionsrollen dem Select Menü hinzufügen.", color=discord.Color.orange())
        self.embed.set_footer(text="Reaction Roles Setup")
        self.add_item(RoleSelect(roles))
        self.add_item(SaveButton())
        self.add_item(CancelButton())

class RoleSelect(ui.Select):
    def __init__(self, roles: List[discord.Role]):
        options = [
                      discord.SelectOption(label=role.name, value=str(role.id))
                      for role in roles if not role.managed and role.name != "@everyone"
                  ][:25]  # 🔧 HIER wird auf max. 25 Rollen begrenz
        super().__init__(placeholder="Wähle eine Rolle aus", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        modal = RoleConfigModal(role)
        await interaction.response.send_modal(modal)
        await modal.wait()

        self.view.role_data.append(modal.result)
        self.view.selected.append(role_id)

        roles_info = "\n".join([f"{r['emoji'] or ''} {r['label']} (<@&{r['role_id']}>)" for r in self.view.role_data])
        self.view.embed.clear_fields()
        self.view.embed.add_field(name="Ausgewählte Rollen", value=roles_info or "Keine", inline=False)

        if self.view.embed_message is None:
            self.view.embed_message = await interaction.followup.send(embed=self.view.embed, view=self.view, ephemeral=True)
        else:
            await self.view.embed_message.edit(embed=self.view.embed, view=self.view)

class SaveButton(ui.Button):
    def __init__(self):
        super().__init__(label="Fertig", style=discord.ButtonStyle.success)

    async def callback(self, interaction: Interaction):
        final_modal = FinalEmbedModal()
        await interaction.response.send_modal(final_modal)
        await final_modal.wait()
        self.view.embed_data = final_modal.embed_data
        self.view.stop()

class CancelButton(ui.Button):
    def __init__(self):
        super().__init__(label="Abbrechen", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("❌ Reaktionsrollen-Setup abgebrochen.", ephemeral=True)
        self.view.stop()

class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reactionrole", description="Erstellt eine Reaction Role Nachricht")
    async def reactionrole(self, interaction: Interaction, style: Literal["buttons", "select"]):
        roles = [role for role in interaction.guild.roles if role.name != "@everyone"]
        view = RoleSelectView(interaction, roles)
        await interaction.response.send_message("Wähle Rollen für deine Reaktionsrollen aus.", view=view, ephemeral=True)
        await view.wait()

        if not hasattr(view, 'embed_data'):
            return

        embed_data = view.embed_data
        embed = discord.Embed(title=embed_data['title'], description=embed_data['description'], color=embed_data['color'])
        if embed_data['thumbnail']:
            embed.set_thumbnail(url=embed_data['thumbnail'])
        if embed_data['image']:
            embed.set_image(url=embed_data['image'])

        role_data = view.role_data
        view_final = ui.View(timeout=None)

        if style == "buttons":
            for r in role_data:
                btn = ui.Button(label=r['label'], emoji=r['emoji'], style=discord.ButtonStyle.secondary, custom_id=f"reactionrole:{r['role_id']}")
                async def callback(i: Interaction, rid=r['role_id']):
                    role = i.guild.get_role(rid)
                    if role in i.user.roles:
                        await i.user.remove_roles(role)
                        await i.response.send_message(f"🔻 Rolle **{role.name}** entfernt.", ephemeral=True)
                    else:
                        await i.user.add_roles(role)
                        await i.response.send_message(f"✅ Rolle **{role.name}** vergeben.", ephemeral=True)
                btn.callback = callback
                view_final.add_item(btn)
        else:
            options = [discord.SelectOption(label=r['label'], emoji=r['emoji'], value=str(r['role_id'])) for r in role_data]
            select = ui.Select(placeholder="Wähle deine Rolle aus...", options=options, custom_id="reactionrole_select")
            async def select_callback(i: Interaction):
                rid = int(select.values[0])
                role = i.guild.get_role(rid)
                if role in i.user.roles:
                    await i.user.remove_roles(role)
                    await i.response.send_message(f"🔻 Rolle **{role.name}** entfernt.", ephemeral=True)
                else:
                    await i.user.add_roles(role)
                    await i.response.send_message(f"✅ Rolle **{role.name}** vergeben.", ephemeral=True)
            select.callback = select_callback
            view_final.add_item(select)

        final_message = await interaction.channel.send(embed=embed, view=view_final)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                embed_color = hex(embed.color.value)[2:] if isinstance(embed.color, discord.Colour) else "2F3136"
                await cursor.execute("""
                INSERT INTO reactionrole_messages (message_id, guild_id, channel_id, style, embed_title, embed_description, embed_color, embed_image, embed_thumbnail)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    final_message.id,
                    interaction.guild.id,
                    interaction.channel.id,
                    style,
                    embed.title,
                    embed.description,
                    embed_color,
                    embed_data['image'],
                    embed_data['thumbnail']
                ))
                for r in role_data:
                    await cursor.execute("""
                    INSERT INTO reactionrole_entries (message_id, role_id, label, emoji)
                    VALUES (%s, %s, %s, %s)
                    """, (final_message.id, r['role_id'], r['label'], r['emoji']))

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT message_id, style FROM reactionrole_messages")
                for msg_id, style in await cursor.fetchall():
                    await cursor.execute("SELECT role_id, label, emoji FROM reactionrole_entries WHERE message_id = %s", (msg_id,))
                    role_data = await cursor.fetchall()
                    view = ui.View(timeout=None)
                    if style == "buttons":
                        for rid, label, emoji in role_data:
                            btn = ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=f"reactionrole:{rid}")
                            async def callback(i: Interaction, rid=rid):
                                role = i.guild.get_role(rid)
                                if role in i.user.roles:
                                    await i.user.remove_roles(role)
                                    await i.response.send_message(f"🔻 Rolle **{role.name}** entfernt.", ephemeral=True)
                                else:
                                    await i.user.add_roles(role)
                                    await i.response.send_message(f"✅ Rolle **{role.name}** vergeben.", ephemeral=True)
                            btn.callback = callback
                            view.add_item(btn)
                    else:
                        options = [discord.SelectOption(label=label, emoji=emoji, value=str(rid)) for rid, label, emoji in role_data]
                        select = ui.Select(placeholder="Wähle deine Rolle aus...", options=options, custom_id="reactionrole_select")
                        async def select_callback(i: Interaction):
                            rid = int(select.values[0])
                            role = i.guild.get_role(rid)
                            if role in i.user.roles:
                                await i.user.remove_roles(role)
                                await i.response.send_message(f"🔻 Rolle **{role.name}** entfernt.", ephemeral=True)
                            else:
                                await i.user.add_roles(role)
                                await i.response.send_message(f"✅ Rolle **{role.name}** vergeben.", ephemeral=True)
                        select.callback = select_callback
                        view.add_item(select)
                    self.bot.add_view(view, message_id=msg_id)

async def setup(bot):
    await bot.add_cog(ReactionRole(bot))