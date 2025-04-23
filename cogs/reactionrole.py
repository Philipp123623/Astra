import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction
from typing import List, Literal
import aiomysql
import re

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

def is_valid_emoji(emoji: str):
    custom_emoji_pattern = re.compile(r'<a?:[a-zA-Z0-9_~]+:[0-9]+>')
    standard_emoji_pattern = re.compile(r'^[#-9©® -㌀ἀ0-ᾟF]+$')
    return custom_emoji_pattern.match(emoji) or standard_emoji_pattern.match(emoji)

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
    def __init__(self, interaction: discord.Interaction, roles: List[discord.Role], style: str):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.roles = roles
        self.selected = []
        self.role_data = []
        self.embed_message = None
        self.embed = discord.Embed(title="Reaktionsrollen Setup", description="Füge Rollen über das Select-Menü hinzu oder entferne sie durch erneute Auswahl.", color=discord.Color.blue())
        self.embed.set_footer(text="Reaction Roles Setup")
        self.style = style
        self.embed_data = None
        self.select = RoleSelect(roles, self)
        self.add_item(self.select)
        self.add_item(SaveButton())
        self.add_item(CancelButton())

class RoleSelect(ui.Select):
    def __init__(self, roles: List[discord.Role], parent: RoleSelectView):
        self.parent_view = parent
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in roles if not role.managed and role.name != "@everyone"
        ][:25]
        super().__init__(placeholder="Wähle eine Rolle aus", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)

        existing = next((r for r in self.parent_view.role_data if r["role_id"] == role_id), None)
        if existing:
            self.parent_view.role_data.remove(existing)
            self.parent_view.selected.remove(role_id)
        else:
            modal = RoleConfigModal(role)
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.parent_view.role_data.append(modal.result)
            self.parent_view.selected.append(role_id)

        self.parent_view.embed.clear_fields()
        for r in self.parent_view.role_data:
            self.parent_view.embed.add_field(name=r["label"], value=f"<@&{r['role_id']}>", inline=False)

        if self.parent_view.embed_message is None:
            self.parent_view.embed_message = await interaction.followup.send(embed=self.parent_view.embed, view=self.parent_view, ephemeral=True)
        else:
            await self.parent_view.embed_message.edit(embed=self.parent_view.embed, view=self.parent_view)

class SaveButton(ui.Button):
    def __init__(self):
        super().__init__(label="Fertig", style=discord.ButtonStyle.green, emoji="<:Astra_accept:1141303821176422460>", custom_id="save_button")

    async def callback(self, interaction: Interaction):
        final_modal = FinalEmbedModal()
        await interaction.response.send_modal(final_modal)
        await final_modal.wait()
        self.view.embed_data = final_modal.embed_data
        await interaction.followup.send("<:Astra_accept:1141303821176422460> Embed-Konfiguration abgeschlossen.", ephemeral=True)
        self.view.stop()

class CancelButton(ui.Button):
    def __init__(self):
        super().__init__(label="Abbrechen", style=discord.ButtonStyle.danger, emoji="<:Astra_x:1141303954555289600>", custom_id="cancel_button")

    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("<:Astra_x:1141303954555289600> Reaktionsrollen-Setup abgebrochen.", ephemeral=True)
        self.view.stop()

class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def setup_persistent_view(self, role_data, style) -> ui.View:
        view = ui.View(timeout=None)

        def make_button_callback(rid):
            async def callback(i: Interaction):
                role = i.guild.get_role(rid)
                if role in i.user.roles:
                    await i.user.remove_roles(role)
                    await i.response.send_message(f"<:Astra_accept:1141303821176422460> Rolle **{role.name}** entfernt.", ephemeral=True)
                else:
                    await i.user.add_roles(role)
                    await i.response.send_message(f"<:Astra_accept:1141303821176422460> Rolle **{role.name}** vergeben.", ephemeral=True)
            return callback

        if style.lower() in ["buttons", "button"]:
            for r in role_data:
                btn = ui.Button(label=r['label'], emoji=r['emoji'], style=discord.ButtonStyle.secondary, custom_id=f"role_button_{r['role_id']}")
                btn.callback = make_button_callback(r['role_id'])
                view.add_item(btn)
        else:
            options = []
            for r in role_data:
                emoji = r['emoji'] if r['emoji'] and is_valid_emoji(r['emoji']) else None
                options.append(discord.SelectOption(label=r['label'], value=str(r['role_id']), emoji=emoji))

            select = ui.Select(placeholder="Wähle deine Rolle aus...", options=options, custom_id="reactionrole_select", min_values=0, max_values=len(options))

            async def select_callback(i: Interaction):
                selected = [int(v) for v in select.values]
                added, removed = [], []
                for option in options:
                    rid = int(option.value)
                    role = i.guild.get_role(rid)
                    if role in i.user.roles and rid not in selected:
                        await i.user.remove_roles(role)
                        removed.append(role.name)
                    elif role not in i.user.roles and rid in selected:
                        await i.user.add_roles(role)
                        added.append(role.name)
                msg = []
                if added:
                    msg.append(f"<:Astra_accept:1141303821176422460> Rollen vergeben: {', '.join(added)}")
                if removed:
                    msg.append(f"<:Astra_x:1141303954555289600> Rollen entfernt: {', '.join(removed)}")
                await i.response.send_message('\n'.join(msg), ephemeral=True)

            select.callback = select_callback
            view.add_item(select)

        return view

    @app_commands.command(name="reactionrole", description="Erstellt eine Reaction Role Nachricht")
    async def reactionrole(self, interaction: Interaction, style: Literal["buttons", "select"]):
        roles = [role for role in interaction.guild.roles if role.name != "@everyone"]
        view = RoleSelectView(interaction, roles, style)
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
        view_final = await self.setup_persistent_view(role_data, style)
        msg = await interaction.channel.send(embed=embed, view=view_final)
        self.bot.add_view(view_final, message_id=msg.id)

        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO reactionrole_messages 
                    (message_id, guild_id, channel_id, style, embed_title, embed_description, embed_color, embed_image, embed_thumbnail)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    msg.id,
                    interaction.guild.id,
                    interaction.channel.id,
                    style,
                    embed_data['title'],
                    embed_data['description'],
                    f"{embed_data['color']:06x}",
                    embed_data['image'],
                    embed_data['thumbnail']
                ))

                for r in role_data:
                    await cursor.execute("""
                        INSERT INTO reactionrole_entries (message_id, role_id, label, emoji)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        msg.id,
                        r['role_id'],
                        r['label'],
                        r['emoji']
                    ))

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT message_id, style FROM reactionrole_messages")
                for msg_id, style in await cursor.fetchall():
                    await cursor.execute("SELECT role_id, label, emoji FROM reactionrole_entries WHERE message_id = %s", (msg_id,))
                    role_data = [
                        {"role_id": rid, "label": label, "emoji": emoji}
                        for rid, label, emoji in await cursor.fetchall()
                    ]
                    view = await self.setup_persistent_view(role_data, style)
                    self.bot.add_view(view, message_id=msg_id)

async def setup(bot):
    await bot.add_cog(ReactionRole(bot))