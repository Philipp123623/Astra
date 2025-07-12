import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from datetime import datetime

class CategorySelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Moderation', value="Mod", emoji='<:Astra_moderation:1141303878541918250>'),
            discord.SelectOption(label="Levelsystem", value="Level", emoji="<:Astra_level:1141825043278598154>"),
            discord.SelectOption(label="Giveaways", value="GW", emoji="<:Astra_gw1:1141303852889550928>"),
            discord.SelectOption(label='Settings & Setup', value="Settings", emoji='<:Astra_settings:1061390649200476170>'),
            discord.SelectOption(label='Tickets', value="Ticket", emoji='<:Astra_ticket:1141833836204937347>'),
            discord.SelectOption(label='Automod', value="Automod", emoji="<:Astra_time:1141303932061233202>"),
            discord.SelectOption(label='Information', value="Info", emoji='<:Astra_support:1141303923752325210>'),
            discord.SelectOption(label='Fun', value="Fun", emoji='<:Astra_fun:1141303841665601667>'),
            discord.SelectOption(label='Economy', value="Eco", emoji='<:Astra_cookie:1141303831293079633>'),
            discord.SelectOption(label='Nachrichten', value="Messages", emoji='<:Astra_messages:1141303867850641488>'),
            discord.SelectOption(label='Minispiele', value="Minigames", emoji='<:Astra_minigames:1141303876528648232>'),
        ]
        super().__init__(placeholder="Wähle eine Kategorie", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await HelpView.show_embed(interaction, self.values[0])

class HomeButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, emoji="🏠", label="Home")

    async def callback(self, interaction: discord.Interaction):
        await HelpView.show_embed(interaction, "Home")

class HelpView(View):
    def __init__(self, bot: commands.Bot, uptime: datetime):
        super().__init__(timeout=None)
        self.bot = bot
        self.uptime = uptime
        self.add_item(HomeButton())
        self.add_item(CategorySelect())

    @staticmethod
    async def show_embed(interaction: discord.Interaction, category: str):
        bot = interaction.client
        cog = bot.get_cog("help")
        if category == "Home":
            delta_uptime = datetime.utcnow() - cog.uptime
            uptime_str = f"{delta_uptime.days}d {(delta_uptime.seconds // 3600) % 24}h {(delta_uptime.seconds // 60) % 60}m {delta_uptime.seconds % 60}s"
            embed = discord.Embed(
                title="Help Menü",
                description=(
                    "<:Astra_info:1141303860556738620> **__Wichtige Informationen:__**\n"
                    "Hier findest du alle Commands.\n"
                    "Falls du Hilfe brauchst, komm auf unseren [**Support Server ➚**](https://discord.gg/NH9DdSUJrE).\n\n"
                    f"**Uptime:** {uptime_str}\n"
                    f"**Ping**: {bot.latency * 1000:.0f} ms"
                ),
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Letzte Updates",
                value=(
                    "> <:Coin:1359178077011181811> Neues Economy: </job:1362756274130915433>, </economy:1362756274130915432>\n"
                    "> <:Astra_minigames:1141303876528648232> Neue Minigames: </hangman:1362756274130915431>, </snake:1362756275544522825>\n"
                    "> <:Astra_gw1:1141303852889550928> Giveaway: </gewinnspiel:1197746882164834335>\n"
                    "> <:Astra_level:1141825043278598154> Levelsystem: </levelsystem status:1362756275133222930>"
                )
            )
            embed.add_field(
                name="Links",
                value=(
                    "**[Einladen](https://discord.com/oauth2/authorize?client_id=1113403511045107773&permissions=1899359446&scope=bot%20applications.commands) | "
                    "[Support](https://discord.gg/NH9DdSUJrE) | [Voten](https://top.gg/bot/1113403511045107773/vote)**"
                ),
                inline=False
            )
            embed.set_image(url="https://cdn.discordapp.com/attachments/842039866740178944/987332928767938630/Astra-premium3.gif")
            embed.set_footer(text="Astra Development ©2025", icon_url=interaction.guild.icon)
        else:
            pages = cog.pages
            description = pages.get(category, "Seite nicht gefunden!")
            embed = discord.Embed(title=f"Command Menü | {category}", description=description, color=discord.Color.blue())
            embed.set_author(name=f"{bot.user.name} Hilfe", icon_url=bot.user.avatar)
            embed.set_footer(text="Astra Development ©2025", icon_url=interaction.guild.icon)

        await interaction.response.edit_message(embed=embed, view=HelpView(bot, cog.uptime))

class help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.uptime = datetime.utcnow()
        self.pages = {
            "Mod": "> **👥 × User Befehle:**\n> Keine User Befehle.\n\n> **👮‍♂ × Team Befehle:**\n> </kick:1362756274130915437> - Kicke einen User.\n> </ban:1362756274130915438> - Banne einen User",
            "Level": "> Level-System-Befehle kommen hier rein...",
            "GW": "> Giveaway-Befehle hier...",
            "Settings": "> Setup und Settings hier...",
            "Ticket": "> Ticket-Commands hier...",
            "Automod": "> Automod-Commands hier...",
            "Info": "> Info-Commands hier...",
            "Fun": "> Fun-Commands hier...",
            "Eco": "> Economy-Commands hier...",
            "Messages": "> Nachrichten-Commands hier...",
            "Minigames": "> Minispiele-Befehle hier...",
        }

    @commands.command()
    async def hilfe(self, ctx):
        view = HelpView(self.bot, self.uptime)
        await ctx.send(embed=await self.get_home_embed(ctx.guild), view=view)

    async def get_home_embed(self, guild):
        delta_uptime = datetime.utcnow() - self.uptime
        uptime_str = f"{delta_uptime.days}d {(delta_uptime.seconds // 3600) % 24}h {(delta_uptime.seconds // 60) % 60}m {delta_uptime.seconds % 60}s"
        embed = discord.Embed(
            title="Help Menü",
            description=(
                "<:Astra_info:1141303860556738620> **__Wichtige Informationen:__**\n"
                "Hier findest du alle Commands.\n"
                "Falls du Hilfe brauchst, komm auf unseren [**Support Server ➚**](https://discord.gg/NH9DdSUJrE).\n\n"
                f"**Uptime:** {uptime_str}"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Astra Development ©2025", icon_url=guild.icon)
        return embed

async def setup(bot):
    await bot.add_cog(help(bot))
