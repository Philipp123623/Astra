import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction
from typing import List, Literal, Optional


class EmbedModal(ui.Modal, title="Embed Konfiguration"):
    title_input = ui.TextInput(label="Titel", required=True, max_length=256)
    description_input = ui.TextInput(label="Beschreibung", style=discord.TextStyle.paragraph, required=True)
    color_input = ui.TextInput(label="Farbe (Hex, z.B. #ff0000)", required=False)

    def __init__(self):
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.embed_data = {
            "title": self.title_input.value,
            "description": self.description_input.value,
            "color": self.color_input.value.lstrip("#") if self.color_input.value else "2F3136"
        }
        self.stop()


class RoleSelect(ui.Select):
    def __init__(self, roles: List[discord.Role]):
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles if not role.managed][:8]
        super().__init__(placeholder="Wähle Rollen für die Reaction Role aus...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: Interaction):
        self.view.selected_roles = [int(value) for value in self.values]
        await interaction.response.defer()
        self.view.stop()


class RoleSelectView(ui.View):
    def __init__(self, roles: List[discord.Role]):
        super().__init__(timeout=60)
        self.selected_roles = []
        self.add_item(RoleSelect(roles))


class ReactionViewButton(ui.View):
    def __init__(self, bot: commands.Bot, role_data: List[tuple]):
        super().__init__(timeout=None)
        self.bot = bot
        for role_id, label, emoji in role_data:
            self.add_item(ReactionButton(role_id, label, emoji))


class ReactionButton(ui.Button):
    def __init__(self, role_id: int, label: str, emoji: Optional[str]):
        super().__init__(label=label, emoji=emoji or None, style=discord.ButtonStyle.secondary, custom_id=f"reactionrole:{role_id}")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Rolle {role.name} entfernt.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Rolle {role.name} vergeben.", ephemeral=True)


class ReactionViewSelect(ui.View):
    def __init__(self, bot: commands.Bot, role_data: List[tuple]):
        super().__init__(timeout=None)
        self.bot = bot
        options = [discord.SelectOption(label=label, value=str(role_id), emoji=emoji or None) for role_id, label, emoji in role_data]
        self.add_item(ui.Select(placeholder="Wähle deine Rolle aus...", options=options, custom_id="reactionrole_select"))

    @ui.select(custom_id="reactionrole_select")
    async def select_callback(self, select: ui.Select, interaction: discord.Interaction):
        selected_id = int(select.values[0])
        role = interaction.guild.get_role(selected_id)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Rolle {role.name} entfernt.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Rolle {role.name} vergeben.", ephemeral=True)


class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reactionrole")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole(
        self,
        interaction: discord.Interaction,
        style: Literal["Button", "Select"]
    ):
        """Erstellt eine Reaction Role Nachricht."""
        await interaction.response.send_modal(EmbedModal())
        modal: EmbedModal = await interaction.client.wait_for("modal_submit", check=lambda i: i.user == interaction.user and i.custom_id == "Embed Konfiguration")

        embed_data = modal.embed_data
        color = int(embed_data["color"], 16)
        embed = discord.Embed(title=embed_data["title"], description=embed_data["description"], color=color)

        # Rollen Auswahl
        role_view = RoleSelectView(interaction.guild.roles)
        await interaction.followup.send("Wähle bis zu 8 Rollen für die Reaction Role:", view=role_view, ephemeral=True)
        await role_view.wait()

        if not role_view.selected_roles:
            return await interaction.followup.send("Keine Rollen ausgewählt.", ephemeral=True)

        # Emoji Abfrage
        role_data = []
        for role_id in role_view.selected_roles:
            role = interaction.guild.get_role(role_id)
            await interaction.followup.send(f"Gib ein Emoji für **{role.name}** ein (oder `skip`):", ephemeral=True)
            msg = await self.bot.wait_for("message", check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
            emoji = None if msg.content.lower() == "skip" else msg.content
            role_data.append((role.id, role.name, emoji))

        # Nachricht senden
        view = ReactionViewButton(self.bot, role_data) if style == "Button" else ReactionViewSelect(self.bot, role_data)
        message = await interaction.channel.send(embed=embed, view=view)

        # In DB speichern
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO reactionrole_messages (message_id, guild_id, channel_id, style, embed_title, embed_description, embed_color) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (message.id, interaction.guild.id, interaction.channel.id, style, embed.title, embed.description, embed.color.value)
                )
                for role_id, label, emoji in role_data:
                    await cursor.execute(
                        "INSERT INTO reactionrole_entries (message_id, role_id, label, emoji) VALUES (%s, %s, %s, %s)",
                        (message.id, role_id, label, emoji)
                    )

    # Persistent Views beim Bot-Start laden
    @commands.Cog.listener()
    async def on_ready(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT message_id, style FROM reactionrole_messages")
                messages = await cursor.fetchall()
                for msg_id, style in messages:
                    await cursor.execute("SELECT role_id, label, emoji FROM reactionrole_entries WHERE message_id = %s", (msg_id,))
                    role_data = await cursor.fetchall()
                    view = ReactionViewButton(self.bot, role_data) if style == "Button" else ReactionViewSelect(self.bot, role_data)
                    self.bot.add_view(view, message_id=msg_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))
