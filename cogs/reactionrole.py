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
    title = ui.TextInput(label="Embed Titel", max_length=256, required=True)
    description = ui.TextInput(label="Embed Beschreibung", style=discord.TextStyle.paragraph, required=True)
    color = ui.TextInput(label="Farbe (Hex, optional)", required=False)
    thumbnail = ui.TextInput(label="Thumbnail URL (optional)", required=False)
    image = ui.TextInput(label="Image URL (optional)", required=False)

    async def on_submit(self, interaction: Interaction):
        self.embed_data = {
            "title": self.title.value,
            "description": self.description.value,
            "color": int(self.color.value.lstrip('#'), 16) if self.color.value else 0x2F3136,
            "thumbnail": self.thumbnail.value,
            "image": self.image.value
        }
        await interaction.response.defer()
        self.stop()

class RoleSelectView(ui.View):
    def __init__(self, ctx: discord.Interaction, roles: List[discord.Role]):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.roles = roles
        self.selected = []
        self.role_data = []
        self.add_item(RoleSelect(roles))

class RoleSelect(ui.Select):
    def __init__(self, roles: List[discord.Role]):
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles if not role.managed and role.name != "@everyone"]
        super().__init__(placeholder="Wähle eine Rolle aus", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        modal = RoleConfigModal(role)
        await interaction.response.send_modal(modal)
        await modal.wait()

        self.view.role_data.append(modal.result)
        self.view.selected.append(role_id)

        content = "**Aktuelle Rollen:**\n" + "\n".join([f"{r['emoji'] or ''} {r['label']} (<@&{r['role_id']}>)" for r in self.view.role_data])
        await interaction.edit_original_response(content=content, view=self.view)

class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reactionrole", description="Erstellt eine Reaction Role Nachricht")
    @app_commands.choices(style=[
        app_commands.Choice(name="Buttons", value="buttons"),
        app_commands.Choice(name="Select Menü", value="select")
    ])
    async def reactionrole(self, interaction: Interaction, style: app_commands.Choice[str]):
        roles = [role for role in interaction.guild.roles if role.name != "@everyone"]
        view = RoleSelectView(interaction, roles)
        await interaction.response.send_message(content="Wähle Rollen für deine Reaktionsrollen aus.", view=view, ephemeral=True)
        await view.wait()

        final_modal = FinalEmbedModal()
        await interaction.followup.send_modal(final_modal)
        await final_modal.wait()

        embed_data = final_modal.embed_data
        embed = discord.Embed(title=embed_data['title'], description=embed_data['description'], color=embed_data['color'])
        if embed_data['thumbnail']:
            embed.set_thumbnail(url=embed_data['thumbnail'])
        if embed_data['image']:
            embed.set_image(url=embed_data['image'])

        role_data = view.role_data
        if style.value == "buttons":
            view_final = ui.View(timeout=None)
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
            view_final = ui.View(timeout=None)
            view_final.add_item(select)

        final_message = await interaction.channel.send(embed=embed, view=view_final)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                INSERT INTO reactionrole_messages (message_id, guild_id, channel_id, style, embed_title, embed_description, embed_color, embed_image, embed_thumbnail)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    final_message.id,
                    interaction.guild.id,
                    interaction.channel.id,
                    style.value,
                    embed.title,
                    embed.description,
                    hex(embed.color.value)[2:],
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
