import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
import random

hangman_game = {
    "current_word": "",
    "guesses": [],
    "attempts_left": 9,
    "game": False,
    "player": None,
    "view_page": 1,
}

HANGMAN_PICS = [
    """```\n|‾‾‾‾‾‾|\n|\n|\n|\n|\n|\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|\n|\n|\n|\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|      😟\n|\n|\n|\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|      😟\n|      👕\n|\n|\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|      😟\n|    🫲👕\n|\n|\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|      😟\n|    🫲👕🫱\n|\n|\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|      😟\n|    🫲👕🫱\n|      🩳\n|\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|      😟\n|    🫲👕🫱\n|      🩳\n|     👞\n|\n|__________\n```""",
    """```\n|‾‾‾‾‾‾|\n|      🎩\n|      😟\n|    🫲👕🫱\n|      🩳\n|     👞👞\n|\n|__________\n```""",
]

class HangmanRestartView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

        restart_button = Button(label="🔁 Neustarten", style=discord.ButtonStyle.success)
        restart_button.callback = self.restart_game
        self.add_item(restart_button)

    async def restart_game(self, interaction: discord.Interaction):
        # Debug-Ausgabe: Überprüfe den aktuellen Status des Spiels
        print(f"Spielstatus beim Neustart: {hangman_game['game']}")

        if hangman_game["game"]:  # Wenn ein Spiel läuft
            print("Beende das laufende Spiel...")  # Debug-Ausgabe
            hangman_game["game"] = False  # Beende das laufende Spiel
            await interaction.response.send_message("Das Spiel wurde beendet! Starte ein neues Spiel...", ephemeral=True)

            # Starte dann ein neues Spiel
            await self.start_new_game(interaction)
        else:
            print("Kein Spiel läuft derzeit!")  # Debug-Ausgabe
            await interaction.response.send_message("Kein Spiel läuft derzeit. Starte zuerst ein Spiel!", ephemeral=True)

    async def start_new_game(self, interaction: discord.Interaction):
        # Debug-Ausgabe: Wenn ein neues Spiel gestartet wird
        print("Starte neues Hangman-Spiel...")

        word = random.choice([  # Liste von Wörtern
            "WASSER", "MOND", "HIMMEL", "HAUS", "AUTO", "TISCH", "VOGEL", "BÄUME", "NACHT", "FREUND", "BILD", "FISCH"
        ])

        # Sicherstellen, dass das Spiel als aktiv markiert wird
        hangman_game.update({
            "game": True,
            "current_word": word,
            "guesses": [],
            "attempts_left": 9,
            "player": interaction.user,
            "view_page": 1,
        })

        print("Spielstatus nach dem Start:", hangman_game["game"])  # Debug-Ausgabe

        display = "⬜ " * len(word)
        ascii_art = HANGMAN_PICS[0]
        embed = discord.Embed(title="Hangman", description=f"{display.strip()}\n{ascii_art}\n`{' '.join(['_' for _ in word])}`", color=discord.Color.blue())
        embed.add_field(name="Versuche übrig", value="9", inline=True)
        embed.add_field(name="Geratene Buchstaben", value="Noch keine", inline=False)

        view = HangmanGameView(interaction.user, self.bot, 1)
        await interaction.response.send_message(embed=embed, view=view)



class HangmanGameView(View):
    def __init__(self, player, bot, page=1):
        super().__init__(timeout=None)
        self.bot = bot
        self.page = page
        self.player = player

        # Bestimme die Buchstaben, die auf dieser Seite angezeigt werden
        letters = "ABCDEFGHIJKLM" if page == 1 else "NOPQRSTUVWXYZ"
        
        # Erstelle Buttons für die Buchstaben und deaktiviere sie, wenn sie bereits geraten wurden
        for letter in letters:
            button = Button(label=letter, style=discord.ButtonStyle.primary)
            # Deaktiviere den Button, wenn der Buchstabe bereits geraten wurde
            if letter in hangman_game['guesses']:
                button.disabled = True
            button.callback = self.make_guess_callback(letter, button)
            self.add_item(button)

        # Erstelle den Navigationsbutton
        nav_button = Button(label="▶️" if page == 1 else "◀️", style=discord.ButtonStyle.secondary)
        nav_button.callback = self.switch_page
        self.add_item(nav_button)

        # Erstelle den Stopp-Button
        stop_button = Button(label="🛑 Stopp", style=discord.ButtonStyle.danger)
        stop_button.callback = self.quit_game
        self.add_item(stop_button)

    def make_guess_callback(self, letter, button):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.player:
                await interaction.response.send_message("Nicht dein Spiel!", ephemeral=True)
                return

            if letter in hangman_game['guesses']:
                await interaction.response.send_message("Bereits geraten!", ephemeral=True)
                return

            hangman_game['guesses'].append(letter)
            button.disabled = True  # Deaktiviere den Button

            if letter not in hangman_game["current_word"]:
                hangman_game["attempts_left"] -= 1

            await self.update_game(interaction)

        return callback

    async def update_game(self, interaction: discord.Interaction):
        # Defer sofort, um Discord zu sagen, dass du noch antworten wirst
        await interaction.response.defer()

        word = hangman_game["current_word"]
        guessed = hangman_game["guesses"]
        attempts_left = hangman_game["attempts_left"]
        display = " ".join([l if l in guessed else "_" for l in word])
        guessed_display = " ".join([l if l in guessed else "⬜" for l in word])
        ascii_art = HANGMAN_PICS[9 - attempts_left]

        embed = discord.Embed(title="Hangman", description=f"{guessed_display}\n{ascii_art}\n`{display}`", color=discord.Color.blue())
        embed.add_field(name="Versuche übrig", value=str(attempts_left), inline=True)
        embed.add_field(name="Geratene Buchstaben", value=" ".join(guessed) if guessed else "Noch keine", inline=False)

        if "_" not in display:
            embed.title = "🎉 Gewonnen!"
            await interaction.message.edit(embed=embed, view=HangmanRestartView(self.bot))
            hangman_game["game"] = False
            return

        if attempts_left <= 0:
            embed.title = "💀 Verloren!"
            embed.description = f"{HANGMAN_PICS[-1]}\nDas Wort war: `{word}`"
            await interaction.message.edit(embed=embed, view=HangmanRestartView(self.bot))
            hangman_game["game"] = False
            return

        await interaction.message.edit(embed=embed, view=self)

    async def switch_page(self, interaction: discord.Interaction):
        # Defer die Antwort, bevor du Änderungen vornimmst
        await interaction.response.defer()

        new_page = 2 if self.page == 1 else 1
        hangman_game["view_page"] = new_page
        await interaction.message.edit(view=HangmanGameView(self.player, self.bot, new_page))

    async def quit_game(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message("Nicht dein Spiel!", ephemeral=True)
            return

        embed = discord.Embed(title="Spiel abgebrochen", description="Das Spiel wurde vom Spieler beendet.", color=discord.Color.orange())
        await interaction.message.edit(embed=embed, view=None)
        hangman_game["game"] = False
        await interaction.response.defer()


class hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="hangman", description="Starte ein Hangman-Spiel")
    async def hangman(self, interaction: discord.Interaction):
        """Spiele Hangman."""
        if hangman_game["game"]:
            await interaction.response.send_message("Ein Spiel läuft bereits!", ephemeral=True)
            return

        # Spiel initialisieren
        word = random.choice([  # Liste von Wörtern
            "WASSER", "MOND", "HIMMEL", "HAUS", "AUTO", "TISCH", "VOGEL", "BÄUME", "NACHT", "FREUND", "BILD", "FISCH"
        ])

        hangman_game.update({
            "game": True,
            "current_word": word,
            "guesses": [],
            "attempts_left": 9,
            "player": interaction.user,
            "view_page": 1,
        })

        display = "⬜ " * len(word)
        ascii_art = HANGMAN_PICS[0]
        embed = discord.Embed(title="Hangman", description=f"{display.strip()}\n{ascii_art}\n`{' '.join(['_' for _ in word])}`", color=discord.Color.blurple())
        embed.add_field(name="Versuche übrig", value="9", inline=True)
        embed.add_field(name="Geratene Buchstaben", value="Noch keine", inline=False)

        view = HangmanGameView(interaction.user, self.bot, 1)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(hangman(bot))
