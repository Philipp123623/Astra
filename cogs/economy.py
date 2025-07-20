import discord
from discord import app_commands
from discord.app_commands import Group
from discord.ui import Button, View
from discord.ext import commands
import aiomysql
import asyncio
from typing import Literal
import random
from datetime import datetime, timedelta

JOBS = [{"name": "Küchenhilfe", "req": 0,
         "desc": "\nVerdiene zwischen 20 und 30 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **0** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [20, 30]},
        {"name": "Kassierer", "req": 5,
         "desc": "\nVerdiene zwischen 30 und 40 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **5** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [30, 40]},
        {"name": "Kebap-Mann", "req": 10,
         "desc": "\nVerdiene zwischen 40 und 50 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **10** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [40, 50]},
        {"name": "Elektroniker", "req": 15,
         "desc": "\nVerdiene zwischen 50 und 60 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **15** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [50, 60]},
        {"name": "Betreuer", "req": 20,
         "desc": "\nVerdiene zwischen 60 und 70 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **20** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [60, 70]},
        {"name": "Bäcker", "req": 25,
         "desc": "\nVerdiene zwischen 70 und 80 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **25** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [70, 80]},
        {"name": "Bauarbeiter", "req": 30,
         "desc": "\nVerdiene zwischen 80 und 90 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **30** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [80, 90]},
        {"name": "Gärtner", "req": 35,
         "desc": "\nVerdiene zwischen 90 und 100 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **35** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [90, 100]},
        {"name": "Lehrer", "req": 40,
         "desc": "\nVerdiene zwischen 100 und 110 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **40** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [100, 110]},
        {"name": "Koch", "req": 45,
         "desc": "\nVerdiene zwischen 110 und 120 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **45** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [110, 120]},
        {"name": "Sanitäter", "req": 50,
         "desc": "\nVerdiene zwischen 120 und 130 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **50** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [120, 130]},
        {"name": "TV-Moderator", "req": 60,
         "desc": "\nVerdiene zwischen 130 und 140 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **60** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [130, 140]},
        {"name": "Schauspieler", "req": 70,
         "desc": "\nVerdiene zwischen 140 und 150 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **70** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [140, 150]},
        {"name": "Ingenieur", "req": 80,
         "desc": "\nVerdiene zwischen 140 und 150 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **80** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [150, 160]},
        {"name": "Streamer", "req": 90,
         "desc": "\nVerdiene zwischen 160 und 170 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **90** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [160, 170]},
        {"name": "Athlet", "req": 100,
         "desc": "\nVerdiene zwischen 170 und 180 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **100** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [170, 180]},
        {"name": "Polizist", "req": 120,
         "desc": "\nVerdiene zwischen 180 und 190 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **120** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [180, 190]},
        {"name": "Programmierer", "req": 140,
         "desc": "\nVerdiene zwischen 190 und 200 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **140** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [190, 200]},
        {"name": "Chirurg", "req": 160,
         "desc": "\nVerdiene zwischen 170 und 180 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **160** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [220, 240]},
        {"name": "Chefarzt", "req": 180,
         "desc": "\nVerdiene zwischen 240 und 250 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **180** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [240, 250]},
        {"name": "Rechtsanwalt", "req": 200,
         "desc": "\nVerdiene zwischen 250 und 260 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **200** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [250, 260]},
        {"name": "Unternehmensleiter", "req": 250,
         "desc": "\nVerdiene zwischen 260 und 270 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **250** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [260, 270]},
        {"name": "Richter", "req": 300,
         "desc": "\nVerdiene zwischen 270 und 280 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **300** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [270, 300]},
        {"name": "Astronaut", "req": 350,
         "desc": "\nVerdiene zwischen 300 und 310 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **400** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [300, 330]},
        {"name": "Pilot", "req": 400,
         "desc": "\nVerdiene zwischen 300 und 310 <:Coin:1359178077011181811>  pro Stunde.\nDu musst mindestens **400** Stunden gearbeitet haben, um diesen Job freizuschalten.",
         "amt": [330, 400]}
]

JOBS += [
    {"name": "Wissenschaftler", "req": 450,
     "desc": "\nVerdiene zwischen 410 und 430 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **450** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [410, 430]},

    {"name": "Professor", "req": 500,
     "desc": "\nVerdiene zwischen 440 und 460 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **500** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [440, 460]},

    {"name": "Pharmaforscher", "req": 550,
     "desc": "\nVerdiene zwischen 470 und 490 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **550** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [470, 490]},

    {"name": "Bankmanager", "req": 600,
     "desc": "\nVerdiene zwischen 500 und 530 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **600** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [500, 530]},

    {"name": "Politiker", "req": 650,
     "desc": "\nVerdiene zwischen 530 und 560 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **650** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [530, 560]},

    {"name": "Unternehmensberater", "req": 700,
     "desc": "\nVerdiene zwischen 560 und 590 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **700** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [560, 590]},

    {"name": "Chefredakteur", "req": 750,
     "desc": "\nVerdiene zwischen 590 und 620 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **750** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [590, 620]},

    {"name": "Finanzanalyst", "req": 800,
     "desc": "\nVerdiene zwischen 620 und 650 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **800** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [620, 650]},

    {"name": "Medienproduzent", "req": 850,
     "desc": "\nVerdiene zwischen 650 und 680 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **850** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [650, 680]},

    {"name": "Entwicklungsleiter", "req": 900,
     "desc": "\nVerdiene zwischen 680 und 710 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **900** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [680, 710]},

    {"name": "Regierungsberater", "req": 1000,
     "desc": "\nVerdiene zwischen 710 und 750 <:Coin:1359178077011181811> pro Stunde.\nDu musst mindestens **1000** Stunden gearbeitet haben, um diesen Job freizuschalten.",
     "amt": [710, 750]}
]


# Kartenwert berechnung
CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
    '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10, 'A': 11
}

def calculate_hand_value(hand):
    value = 0
    aces = 0
    for card in hand:
        rank = card[:-1] if card[:-1] != '' else card[0]  # handle '10♠'
        card_value = CARD_VALUES.get(rank, 0)
        value += card_value
        if rank == 'A':
            aces += 1
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

class BlackjackView(discord.ui.View):
    def __init__(self, bot, interaction, bet, economy):
        super().__init__(timeout=180)
        self.bot = bot
        self.interaction = interaction
        self.bet = bet
        self.economy = economy
        self.user_id = interaction.user.id

        self.player_hand = []
        self.dealer_hand = []
        self.deck = self.create_deck()
        self.message = None
        self.stand_called = False
        self.result_shown = False

        self.deal_initial_cards()

    def create_deck(self):
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [f'{rank}{suit}' for suit in suits for rank in ranks]
        random.shuffle(deck)
        return deck

    def deal_initial_cards(self):
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    async def update_message(self):
        player_value = calculate_hand_value(self.player_hand)
        dealer_value = calculate_hand_value(self.dealer_hand)

        player_cards = " ".join(self.player_hand)
        dealer_cards_display = self.dealer_hand[0] + " ❓" if not self.stand_called else " ".join(self.dealer_hand)
        dealer_value_display = "?" if not self.stand_called else str(dealer_value)

        embed = discord.Embed(title="Blackjack", color=discord.Color.blue())

        embed.add_field(name="<:Astra_user:1141303940365959241> Deine Karten:", value=f"```{player_cards}```Wert: **{player_value}**", inline=False)
        embed.add_field(name="<:Astra_dev:1141303833407017001> Karten des Dealers:", value=f"```{dealer_cards_display}```Wert: **{dealer_value_display}**", inline=False)

        game_over = False
        result_text = ""

        if player_value > 21:
            game_over = True
            result_text = "<:Astra_x:1141303954555289600> Du hast den Wert von 21 überschritten. Du hast verloren."
        elif dealer_value > 21:
            game_over = True
            result_text = "<:Astra_gw1:1141303852889550928> Der Dealer hat überzogen. Du hast gewonnen!"
        elif self.stand_called and dealer_value >= 17:
            game_over = True
            if player_value > dealer_value:
                result_text = "<:Astra_gw1:1141303852889550928> Du hast gewonnen!"
            elif player_value < dealer_value:
                result_text = "<:Astra_x:1141303954555289600> Der Dealer hat gewonnen."
            else:
                result_text = "<:Astra_x:1141303954555289600> Unentschieden."

        if game_over:
            embed.add_field(name="<:Astra_wichtig:1141303951862534224> Ergebnis", value=result_text, inline=False)
            for child in self.children:
                child.disabled = True
            if not self.result_shown:
                self.result_shown = True
                if player_value <= 21 and (player_value > dealer_value or dealer_value > 21):
                    await self.economy.update_balance(self.user_id, wallet_change=self.bet * 2)
                elif player_value == dealer_value:
                    await self.economy.update_balance(self.user_id, wallet_change=self.bet)

        if self.message is None:
            self.message = await self.interaction.original_response()
            await self.message.edit(embed=embed, view=self)
        else:
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if calculate_hand_value(self.player_hand) >= 21:
            return

        self.player_hand.append(self.deck.pop())
        await self.update_message()

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stand_called = True

        await self.animate_dealer_cards()
        await self.update_message()

    async def animate_dealer_cards(self):
        await asyncio.sleep(1)
        while calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
            await self.update_message()
            await asyncio.sleep(1.2)



class JobListView(discord.ui.View):
    def __init__(self, jobs, user_hours):
        super().__init__()
        self.jobs = jobs
        self.user_hours = user_hours
        self.page = 0
        self.items_per_page = 5

    def generate_job_embed(self):
        embed = discord.Embed(
            title="<:Astra_file1:1141303837181886494> Jobliste",
            color=discord.Color.blue()
        )
        start_idx = self.page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        jobs_to_display = self.jobs[start_idx:end_idx]

        for job in jobs_to_display:
            locked = self.user_hours < job["req"]
            status = "<:Astra_locked:1141824745243942912> Gesperrt" if locked else "<:Astra_unlock:1141824750851731486> Verfügbar"
            embed.add_field(
                name=f"{job['name']} ({status})",
                value=f"{job['desc']}\nBenötigte Stunden: **{job['req']}**",
                inline=False
            )

        total_pages = (len(self.jobs) + self.items_per_page - 1) // self.items_per_page
        embed.set_footer(text=f"Seite {self.page + 1} von {total_pages}")
        return embed

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.primary, emoji="<:Astra_arrow_backwards:1392540551546671348>", row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            embed = self.generate_job_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Weiter", style=discord.ButtonStyle.primary, emoji="<:Astra_arrow:1141303823600717885>", row=0)
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (self.page + 1) * self.items_per_page < len(self.jobs):
            self.page += 1
            embed = self.generate_job_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏠", style=discord.ButtonStyle.secondary, row=0)
    async def go_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page != 0:
            self.page = 0
            embed = self.generate_job_embed()
            await interaction.response.edit_message(embed=embed, view=self)

@app_commands.guild_only()
class Eco(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="eco",
            description="Alles rund um Economy."
        )

    async def get_user(self, user_id: int):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM economy_users WHERE user_id = %s", (user_id,))
                data = await cur.fetchone()
                if not data:
                    await cur.execute("INSERT INTO economy_users (user_id) VALUES (%s)", (user_id,))
                    return user_id, 0, 0, None, 0, None
                return data

    async def update_balance(self, user_id: int, wallet_change=0, bank_change=0):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE economy_users SET wallet = wallet + %s, bank = bank + %s WHERE user_id = %s",
                    (wallet_change, bank_change, user_id)
                )

    async def get_balance(self, user_id: int):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT wallet, bank FROM economy_users WHERE user_id = %s", (user_id,))
                return await cur.fetchone()

    @app_commands.command(name="balance", description="Zeigt deinen aktuellen Kontostand an.")
    @app_commands.guild_only()
    async def balance(self, interaction: discord.Interaction):
        """Zeigt deinen aktuellen Kontostand an."""
        user_id = interaction.user.id
        user_data = await self.get_user(user_id)
        wallet, bank = user_data[1], user_data[2]
        job_name = user_data[3]
        hours = user_data[4]

        embed = discord.Embed(title=f"{interaction.user}'s Kontostand", description="> Erhalte Hier Infos über deinen Kontostand und über deinen aktuellen Beruf.", color=discord.Color.blue())
        embed.add_field(name="Barvermögen", value=f"{wallet} <:Coin:1359178077011181811>", inline=True)
        embed.add_field(name="Bank", value=f"{bank} <:Coin:1359178077011181811>", inline=True)
        embed.add_field(name="Beruf", value=f"{job_name}, <:Astra_time:1141303932061233202> {hours} Stunden", inline=True)
        embed.set_thumbnail(url=interaction.user.avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="deposit", description="Zahle Geld auf dein Bankkonto ein.")
    @app_commands.guild_only()
    @app_commands.describe(betrag="Der Betrag, den du einzahlen möchtest.")
    async def deposit(self, interaction: discord.Interaction, betrag: int):
        """Zahle Geld auf dein Bankkonto ein."""
        if betrag <= 0:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte gib einen gültigen Betrag ein.", ephemeral=True)
            return

        user_data = await self.get_user(interaction.user.id)
        if user_data[1] < betrag:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Du hast nicht genug Geld in deinem Wallet.", ephemeral=True)
            return

        await self.update_balance(interaction.user.id, -betrag, betrag)
        await interaction.response.send_message(f"Du hast {betrag} <:Coin:1359178077011181811> auf dein Bankkonto eingezahlt.", ephemeral=True)

    @app_commands.command(name="withdraw", description="Hebe Geld von deinem Bankkonto ab.")
    @app_commands.guild_only()
    @app_commands.describe(betrag="Der Betrag, den du abheben möchtest.")
    async def withdraw(self, interaction: discord.Interaction, betrag: int):
        """Hebe Geld von deinem Bankkonto ab."""
        if betrag <= 0:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte gib einen gültigen Betrag ein.", ephemeral=True)
            return

        user_data = await self.get_user(interaction.user.id)
        if user_data[2] < betrag:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Du hast nicht genug Geld auf deinem Bankkonto.", ephemeral=True)
            return

        await self.update_balance(interaction.user.id, betrag, -betrag)
        await interaction.response.send_message(f"Du hast {betrag} <:Coin:1359178077011181811> von deinem Bankkonto abgehoben.")



    @app_commands.command(name="beg", description="Bitte um ein kleines Trinkgeld.")
    @app_commands.guild_only()
    async def beg(self, interaction: discord.Interaction):
        """Bitte um ein kleines Trinkgeld."""
        user_id = interaction.user.id
        user_data = await self.get_user(user_id)
        last_work = user_data[5]  # Wir verwenden last_work auch als letzte beg Zeit für Demo
        now = datetime.utcnow()

        if last_work and now < last_work + timedelta(hours=3):
            remaining = (last_work + timedelta(hours=3)) - now
            mins = divmod(remaining.seconds, 60)[0]
            await interaction.response.send_message(f"<:Astra_time:1141303932061233202> Du kannst in {mins} Minuten wieder betteln.", ephemeral=True)
            return

        amount = random.randint(5, 25)
        await self.update_balance(user_id, wallet_change=amount)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE economy_users SET last_work = %s WHERE user_id = %s", (now, user_id))

        await interaction.response.send_message(f"<:Astra_accept:1141303821176422460> Du hast {amount} <:Coin:1359178077011181811> von einem freundlichen Fremden erhalten!")

    @app_commands.command(name="slot", description="Spiele ein Slot-Spiel um Coins zu gewinnen oder zu verlieren.")
    @app_commands.guild_only()
    @app_commands.describe(einsatz="Wie viele Coins willst du setzen?")
    async def slot(self, interaction: discord.Interaction, einsatz: int):
        """Spiele ein Slot-Spiel um Coins zu gewinnen oder zu verlieren."""
        user_id = interaction.user.id
        user_data = await self.get_user(user_id)  # Holen der Benutzerdaten aus der Datenbank

        # Überprüfen ob der Einsatz gültig ist
        if einsatz <= 0 or einsatz > user_data[1]:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Ungültiger Einsatz.", ephemeral=True)
            return

        # Die möglichen Obst-Emojis für den Slot
        emojis = ["🍇", "🍋", "🍒", "🍓", "🍊"]

        # Das animierte Spin-Emoji, das während der Drehung angezeigt wird
        spin_emoji = "<a:spin:1141384584437702717>"

        # Resultat der Slot-Maschine
        result = [random.choice(emojis) for _ in range(3)]  # Zufällige Auswahl der Symbole für das Slot-Spiel
        win = False
        gewinn = 0

        # Wenn alle 3 Symbole gleich sind, gibt es einen großen Gewinn
        if result.count(result[0]) == 3:
            win = True
            gewinn = einsatz * 5  # Für 3 gleiche Symbole gibt es 5x den Einsatz als Gewinn
        # Wenn 2 Symbole gleich sind, bekommt der Benutzer seinen Einsatz zurück (oder keinen Verlust)
        elif result.count(result[0]) == 2 or result.count(result[1]) == 2:
            gewinn = 0  # Keine Änderung, der Einsatz wird nicht verloren
        else:
            gewinn = -einsatz  # Bei keinem Gewinn verliert der Benutzer seinen Einsatz

        # Benutzer-Balance aktualisieren
        await self.update_balance(user_id, wallet_change=gewinn)

        # Erstellen von Embeds für die Animation
        embed1 = discord.Embed(colour=discord.Colour.blurple(), description="<:Astra_ticket:1141833836204937347> Slots - Der Einsatz wird getätigt")
        embed1.add_field(name="Slots:", value=f"[{spin_emoji} {spin_emoji} {spin_emoji}]", inline=False)
        embed1.add_field(name="Einsatz", value=f"{einsatz} <:Coin:1359178077011181811> ", inline=False)
        embed1.set_author(name=interaction.user, icon_url=interaction.user.avatar)

        # Embed für den ersten Spin
        embed2 = discord.Embed(colour=discord.Colour.blurple(), description="<:Astra_ticket:1141833836204937347> Slots - Der erste Spin")
        embed2.add_field(name="Slots:", value=f"[{result[0]} {spin_emoji} {spin_emoji}]", inline=False)
        embed2.add_field(name="Einsatz", value=f"{einsatz} <:Coin:1359178077011181811> ", inline=False)
        embed2.set_author(name=interaction.user, icon_url=interaction.user.avatar)

        # Embed für den zweiten Spin
        embed3 = discord.Embed(colour=discord.Colour.blurple(), description="<:Astra_ticket:1141833836204937347> Slots - Der zweite Spin")
        embed3.add_field(name="Slots:", value=f"[{result[0]} {result[1]} {spin_emoji}]", inline=False)
        embed3.add_field(name="Einsatz", value=f"{einsatz} <:Coin:1359178077011181811> ", inline=False)
        embed3.set_author(name=interaction.user, icon_url=interaction.user.avatar)

        # Finales Embed mit den Ergebnissen
        embed4 = discord.Embed(colour=discord.Colour.blurple(), description="<:Astra_gw1:1141303852889550928> Slots - Endergebnis")
        embed4.add_field(name="Slots:", value=f"[{result[0]} {result[1]} {result[2]}]", inline=False)
        embed4.add_field(name="Ergebnis", value=f"{'Gewonnen' if win else 'Verloren'} {gewinn} <:Coin:1359178077011181811> !", inline=False)
        embed4.set_author(name=interaction.user, icon_url=interaction.user.avatar)

        # Senden der Embeds mit Animation
        await interaction.response.send_message(embed=embed1)
        message = await interaction.original_response()
        await asyncio.sleep(1.5)
        await message.edit(embed=embed2)
        await asyncio.sleep(1.5)
        await message.edit(embed=embed3)
        await asyncio.sleep(1.5)
        await message.edit(embed=embed4)

    @app_commands.command(name="rps", description="Spiele Schere, Stein, Papier gegen den Bot.")
    @app_commands.guild_only()
    @app_commands.describe(choice="Wähle 'Schere', 'Stein' oder 'Papier'.")
    async def rps(self, interaction: discord.Interaction, choice: Literal['Stein', 'Schere', 'Papier']):
        """Spiele Schere, Stein, Papier gegen den Bot."""
        choice = choice.lower()
        if choice not in ["schere", "stein", "papier"]:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte wähle entweder 'Schere', 'Stein' oder 'Papier'.",
                                                    ephemeral=True)
            return

        bot_choice = random.choice(["schere", "stein", "papier"])
        result = ""

        if choice == bot_choice:
            result = "Unentschieden!"
        elif (choice == "schere" and bot_choice == "papier") or \
                (choice == "stein" and bot_choice == "schere") or \
                (choice == "papier" and bot_choice == "stein"):
            result = "<:Astra_gw1:1141303852889550928> Du hast gewonnen!"
        else:
            result = "<:Astra_x:1141303954555289600> Du hast verloren!"

        embed = discord.Embed(title="Schere, Stein, Papier", color=discord.Color.blue())
        embed.add_field(name="Deine Wahl", value=f"**{choice.capitalize()}**", inline=False)
        embed.add_field(name="Bot's Wahl", value=f"**{bot_choice.capitalize()}**", inline=False)
        embed.add_field(name="Ergebnis", value=result, inline=False)

        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="coinflip",
                          description="Lass die Münze entscheiden! Wähle 'Kopf' oder 'Zahl' und setze einen Einsatz.")
    @app_commands.guild_only()
    @app_commands.describe(wahl="Deine Wahl: 'Kopf' oder 'Zahl'", betrag="Der Betrag, den du setzen möchtest.")
    async def coinflip(self, interaction: discord.Interaction, wahl: str, betrag: int):
        """Lass die Münze entscheiden! Wähle 'Kopf' oder 'Zahl' und setze einen Einsatz."""
        # Überprüfen, ob die Eingabe gültig ist
        guess = wahl.lower()
        if guess not in ["kopf", "zahl"]:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte wähle entweder 'Kopf' oder 'Zahl'.", ephemeral=True)
            return

        if betrag <= 0:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte gib einen gültigen Betrag ein, der größer als 0 ist.",
                                                    ephemeral=True)
            return

        user_data = await self.get_user(interaction.user.id)
        wallet = user_data[1]

        if wallet < betrag:
            await interaction.response.send_message(
                f"<:Astra_x:1141303954555289600> Du hast nicht genug Münzen. Dein aktueller Kontostand ist {wallet} <:Coin:1359178077011181811>.", ephemeral=True)
            return

        # Münzwurf
        result = random.choice(["Kopf", "Zahl"])

        # Embed erstellen
        embed = discord.Embed(title="Münzwurf", color=discord.Color.blue())
        embed.add_field(name="Deine Wahl", value=f"**{guess.capitalize()}**", inline=False)
        embed.add_field(name="Ergebnis", value=f"**{result}**", inline=False)

        # Das Ergebnis vergleichen und eine Nachricht ausgeben
        if guess == result.lower():
            # Nutzer hat gewonnen, Coins zurückgeben + Gewinn
            gewonnen = betrag * 2  # Einfaches Beispiel, doppelter Einsatz bei Gewinn
            await self.update_balance(interaction.user.id, gewonnen, 0)
            embed.add_field(name="<:Astra_gw1:1141303852889550928> Glückwunsch!", value=f"Du hast gewonnen! Du erhältst {gewonnen} <:Coin:1359178077011181811>.", inline=False)
        else:
            # Nutzer hat verloren, Coins abziehen
            await self.update_balance(interaction.user.id, -betrag, 0)
            embed.add_field(name="<:Astra_x:1141303954555289600>  Leider verloren", value=f"Du hast verloren und {betrag} <:Coin:1359178077011181811> verloren.", inline=False)

        # Nachricht senden
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rob", description="Versuche, einen anderen Nutzer auszurauben!")
    @app_commands.guild_only()
    @app_commands.describe(ziel="Wen willst du ausrauben?")
    async def rob(self, interaction: discord.Interaction, ziel: discord.User):
        """Versuche, einen anderen Nutzer auszurauben."""
        user_id = interaction.user.id
        target_id = ziel.id

        if user_id == target_id:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Du kannst dich nicht selbst ausrauben.", ephemeral=True)
            return

        user_data = await self.get_user(user_id)
        target_data = await self.get_user(target_id)
        now = datetime.utcnow()

        if user_data[5] and now < user_data[5] + timedelta(hours=8):
            remaining = (user_data[5] + timedelta(hours=8)) - now
            await interaction.response.send_message(f"<:Astra_time:1141303932061233202> Du kannst in {remaining.seconds // 60} Minuten wieder rauben.",
                                                    ephemeral=True)
            return

        if target_data[1] < 50:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Ziel hat zu wenig Geld zum Ausrauben.", ephemeral=True)
            return

        erfolg = random.random() < 0.5
        if erfolg:
            betrag = random.randint(20, min(200, target_data[1]))
            await self.update_balance(user_id, wallet_change=betrag)
            await self.update_balance(target_id, wallet_change=-betrag)
            msg = f"<:Astra_accept:1141303821176422460> Du hast erfolgreich {betrag} <:Coin:1359178077011181811>  von {ziel.mention} gestohlen!"
        else:
            strafe = random.randint(10, 30)
            await self.update_balance(user_id, wallet_change=-strafe)
            msg = f"<:Astra_x:1141303954555289600> Du wurdest erwischt! Du zahlst eine Strafe von {strafe} <:Coin:1359178077011181811> ."

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE economy_users SET last_work = %s WHERE user_id = %s", (now, user_id))

        await interaction.response.send_message(msg)


    @app_commands.command(name="leaderboard", description="Zeige die reichsten Spieler.")
    @app_commands.guild_only()
    @app_commands.describe(scope="Wähle, ob die globale oder serverbezogene Rangliste angezeigt wird.")
    async def leaderboard(
            self,
            interaction: discord.Interaction,
            scope: Literal["global", "server"]
    ):
        """Zeige die reichsten Spieler, entweder global oder serverbezogen."""
        try:
            # Datenbankverbindung aufbauen
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if scope == "global":
                        await cur.execute("""
                            SELECT user_id, wallet + bank AS gesamt 
                            FROM economy_users 
                            ORDER BY gesamt DESC 
                            LIMIT 10
                        """)
                    elif scope == "server":
                        await cur.execute("""
                            SELECT user_id, wallet + bank AS gesamt 
                            FROM economy_users 
                            WHERE guild_id = %s 
                            ORDER BY gesamt DESC 
                            LIMIT 10
                        """, (interaction.guild.id,))

                    top_users = await cur.fetchall()

            if not top_users:
                await interaction.response.send_message(
                    "Es wurden keine Benutzer gefunden oder die Rangliste ist leer.")
                return

            # Embed erstellen
            embed = discord.Embed(
                title="<:Astra_users:1141303946602872872> Rangliste (Global)" if scope == "global" else f"<:Astra_users:1141303946602872872> Rangliste ({interaction.guild.name})",
                color=discord.Color.blue()
            )

            for i, (user_id, gesamt) in enumerate(top_users, start=1):
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                name = user.name if user else f"Unbekannt ({user_id})"
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"{gesamt} <:Coin:1359178077011181811>",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"<:Astra_x:1141303954555289600> Es gab einen Fehler beim Abrufen der Rangliste: {e}", ephemeral=True)
            print(f"Fehler beim Abrufen der Rangliste: {e}")


@app_commands.guild_only()
class Job(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="job",
            description="Alles rund um deinen Job"
        )

    @app_commands.command(name="work", description="Arbeite in deinem aktuellen Job.")
    @app_commands.guild_only()
    async def work(self, interaction: discord.Interaction):
        """Arbeite in deinem aktuellen Job."""
        user_id = interaction.user.id
        user_data = await self.get_user(user_id)
        job_name = user_data[3]
        hours = user_data[4]
        last_work = user_data[5]

        if not job_name:
            await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> Du hast keinen Job. Nutze `/job apply`, um einen Job zu wählen.",
                ephemeral=True)
            return

        if last_work:
            now = datetime.utcnow()
            if now < last_work + timedelta(hours=8):
                verbleibend = (last_work + timedelta(hours=8)) - now
                stunden, minuten = divmod(verbleibend.seconds, 3600)[0], divmod(verbleibend.seconds % 3600, 60)[0]
                await interaction.response.send_message(
                    f"<:Astra_time:1141303932061233202> Du musst noch {stunden}h {minuten}min warten, bevor du wieder arbeiten kannst.",
                    ephemeral=True)
                return

        job = next((j for j in JOBS if j["name"] == job_name), None)
        if not job:
            await interaction.response.send_message("Fehler: Dein Job wurde nicht gefunden.", ephemeral=True)
            return

        coins_per_hour = random.randint(*job["amt"])
        earned = coins_per_hour

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE economy_users SET wallet = wallet + %s, hours_worked = hours_worked + 1, last_work = %s WHERE user_id = %s",
                    (earned, datetime.utcnow(), user_id))

        await interaction.response.send_message(
            f"<:Astra_time:1141303932061233202> Du hast 1 Stunde als **{job_name}** gearbeitet und {earned} <:Coin:1359178077011181811> verdient!")

    @app_commands.command(name="list", description="Zeigt die Jobliste.")
    @app_commands.guild_only()
    async def job_list(self, interaction: discord.Interaction):
        """Erhalte eine Liste mit allen Jobs"""
        user_data = await self.get_user(interaction.user.id)
        user_hours = user_data[4]  # Stunden, die der User gearbeitet hat

        view = JobListView(JOBS, user_hours)
        embed = view.generate_job_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="apply", description="Bewirb dich auf einen verfügbaren Job.")
    @app_commands.guild_only()
    @app_commands.describe(name="Name des Jobs, den du annehmen möchtest.")
    async def job_apply(self, interaction: discord.Interaction, name: str):
        """Bewirb dich auf einen verfügbaren Job."""
        user_data = await self.get_user(interaction.user.id)
        user_hours = user_data[4]
        job = next((j for j in JOBS if j["name"].lower() == name.lower()), None)

        if not job:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Dieser Job existiert nicht.",
                                                    ephemeral=True)
            return

        if user_hours < job["req"]:
            await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> Du hast noch nicht genug Stunden gearbeitet, um diesen Job zu bekommen.",
                ephemeral=True)
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE economy_users SET job = %s WHERE user_id = %s",
                                  (job["name"], interaction.user.id))

        await interaction.response.send_message(
            f"<:Astra_accept:1141303821176422460> Du arbeitest jetzt als **{job['name']}**!")

    @app_commands.command(name="quit", description="Kündige deinen aktuellen Job.")
    @app_commands.guild_only()
    async def job_quit(self, interaction: discord.Interaction):
        """Kündige deinen aktuellen Job."""
        user_data = await self.get_user(interaction.user.id)
        if not user_data[3]:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Du hast momentan keinen Job.",
                                                    ephemeral=True)
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE economy_users SET job = NULL WHERE user_id = %s", (interaction.user.id,))

        await interaction.response.send_message(
            "<:Astra_accept:1141303821176422460> Du hast deinen Job erfolgreich gekündigt.")


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None


    async def get_user(self, user_id: int):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM economy_users WHERE user_id = %s", (user_id,))
                data = await cur.fetchone()
                if not data:
                    await cur.execute("INSERT INTO economy_users (user_id) VALUES (%s)", (user_id,))
                    return user_id, 0, 0, None, 0, None
                return data

    async def update_balance(self, user_id: int, wallet_change=0, bank_change=0):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE economy_users SET wallet = wallet + %s, bank = bank + %s WHERE user_id = %s",
                    (wallet_change, bank_change, user_id)
                )

    async def get_balance(self, user_id: int):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT wallet, bank FROM economy_users WHERE user_id = %s", (user_id,))
                return await cur.fetchone()


    @app_commands.command(name="blackjack", description="Spiele eine Runde Blackjack.")
    @app_commands.guild_only()
    @app_commands.describe(einsatz="Der Betrag, den du setzen möchtest.")
    async def blackjack(self, interaction: discord.Interaction, einsatz: int):
        """Spiele eine Runde Blackjack."""
        user_data = await self.get_user(interaction.user.id)
        wallet = user_data[1]

        if einsatz <= 0:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> Bitte gib einen gültigen Einsatz an.", ephemeral=True)
            return

        if wallet < einsatz:
            await interaction.response.send_message("<:Astra_x:1141303954555289600> hast nicht genug Münzen.", ephemeral=True)
            return

        # Abziehen des Einsatzes
        await self.update_balance(interaction.user.id, wallet_change=-einsatz)

        # Blackjack-View mit dem Economy-System
        view = BlackjackView(self.bot, interaction, einsatz, self)  # Übergabe des Economy-Cogs

        embed = discord.Embed(
            title="Blackjack wird gestartet!",
            description="Ziehe Karten mit `Hit` oder beende mit `Stand`. Ziel: So nah wie möglich an 21!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Einsatz", value=f"{einsatz} <:Coin:1359178077011181811>", inline=False)

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()  # Damit `update_message` funktioniert
        await view.update_message()

    @commands.command(name="addcoins",
                      description="Füge einem Nutzer <:Coin:1359178077011181811> hinzu (Nur für Botbesitzer).")
    @commands.is_owner()
    async def addcoins(self, ctx, user: discord.User, betrag: int, balance_type: str = "wallet"):
        """Fügt einem Nutzer Coins hinzu. Kann Bar- oder Bank-Balance verwenden."""
        if betrag <= 0:
            await ctx.channel.send("<:Astra_x:1141303954555289600> Ungültiger Betrag.")
            return

        # Überprüfen, ob balance_type korrekt ist (wallet oder bank)
        if balance_type not in ["wallet", "bank"]:
            await ctx.channel.send("<:Astra_x:1141303954555289600> Ungültiger Balance-Typ. Verwende `wallet` oder `bank`.")
            return

        # User Balance abrufen
        user_data = await self.get_balance(user.id)
        current_balance = user_data[0] if balance_type == "wallet" else user_data[1]

        # Balance aktualisieren
        await self.update_balance(user.id, wallet_change=betrag if balance_type == "wallet" else 0,
                                  bank_change=betrag if balance_type == "bank" else 0)
        await ctx.channel.send(
            f"<:Astra_accept:1141303821176422460> {betrag} <:Coin:1359178077011181811> wurden {user.mention} zu {balance_type} hinzugefügt.")

    @commands.command(name="removecoins",
                      description="Entferne einem Nutzer <:Coin:1359178077011181811> (Nur für Botbesitzer).")
    @commands.is_owner()
    async def removecoins(self, ctx, user: discord.User, betrag: int, balance_type: str = "wallet"):
        """Entfernt einem Nutzer Coins. Kann Bar- oder Bank-Balance verwenden."""
        if betrag <= 0:
            await ctx.channel.send("<:Astra_x:1141303954555289600> Ungültiger Betrag.")
            return

        # Überprüfen, ob balance_type korrekt ist (wallet oder bank)
        if balance_type not in ["wallet", "bank"]:
            await ctx.channel.send("<:Astra_x:1141303954555289600> Ungültiger Balance-Typ. Verwende `wallet` oder `bank`.")
            return

        # User Balance abrufen
        user_data = await self.get_balance(user.id)
        current_balance = user_data[0] if balance_type == "wallet" else user_data[1]

        # Überprüfen, ob der Betrag entfernt werden kann
        if current_balance < betrag:
            await ctx.channel.send(f"<:Astra_x:1141303954555289600> {user.mention} hat nicht genug {balance_type} um {betrag} zu entfernen.")
            return

        # Balance aktualisieren
        await self.update_balance(user.id, wallet_change=-betrag if balance_type == "wallet" else 0,
                                  bank_change=-betrag if balance_type == "bank" else 0)
        await ctx.channel.send(
            f"<:Astra_accept:1141303821176422460> {betrag} <:Coin:1359178077011181811> wurden {user.mention} von {balance_type} entfernt.")


async def setup(bot):
    await bot.add_cog(Economy(bot))
    bot.tree.add_command(Eco())
    bot.tree.add_command(Job())
