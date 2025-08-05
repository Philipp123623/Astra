import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import json
import random


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user(self, user_id: int):
        """Holt den Benutzer aus der Datenbank."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM economy_users WHERE user_id = %s", (user_id,))
                data = await cur.fetchone()
                if not data:
                    await cur.execute("INSERT INTO economy_users (user_id) VALUES (%s)", (user_id,))
                    return user_id, 0, 0, None, 0, None  # Falls der Benutzer nicht existiert, wird er erstellt
                return data

    async def update_balance(self, user_id: int, wallet_change=0, bank_change=0):
        """Aktualisiert das Wallet und/oder Bankguthaben des Benutzers."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE economy_users SET wallet = wallet + %s, bank = bank + %s WHERE user_id = %s",
                    (wallet_change, bank_change, user_id)
                )

    async def get_balance(self, user_id: int):
        """Holt das Wallet- und Bankguthaben des Benutzers."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT wallet, bank FROM economy_users WHERE user_id = %s", (user_id,))
                return await cur.fetchone()


class buttons_emj(discord.ui.View):
    def __init__(self, bot, economy):
        super().__init__(timeout=None)
        self.bot = bot
        self.economy = economy

    @discord.ui.button(label='Skip', style=discord.ButtonStyle.grey, custom_id='persistent_view:skip', emoji="⏩")
    async def skip(self, interaction: discord.Interaction, button: discord.Button):
        try:
            if interaction.response.is_done():
                return

            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT channelID, messageID FROM emojiquiz WHERE guildID = (%s)", (interaction.guild.id,))
                    already_on = await cur.fetchone()
                    if not already_on:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> Das Emojiquizz ist deaktiviert.")
                        return

                    user_balance = await self.economy.get_balance(interaction.user.id)
                    wallet, bank = user_balance
                    if wallet < 20:
                        await interaction.response.send_message(
                            "Du hast nicht genug Geld, um das Quiz zu überspringen. Du benötigst mindestens 20 <:Astra_cookie:1141303831293079633>.",
                            ephemeral=True)
                        return

                    # Wenn der Benutzer genug Geld hat
                    await self.economy.update_balance(interaction.user.id, wallet_change=-20)
                    await interaction.channel.send(
                        f"{interaction.user.mention} hat das Wort übersprungen. (-20 <:Astra_cookie:1141303831293079633>)")

                    # Lösche alte Quiz-Nachricht!
                    channel_id, old_message_id = already_on
                    try:
                        quiz_channel = self.bot.get_channel(channel_id)
                        if quiz_channel and old_message_id:
                            msg = await quiz_channel.fetch_message(old_message_id)
                            await msg.delete()
                    except Exception:
                        pass  # Fehler beim Löschen? Ignorieren

                    # Fortfahren mit dem Quiz
                    await cur.execute("DELETE FROM emojiquiz_lsg WHERE guildID = (%s)", (interaction.guild.id,))
                    query = "SELECT question, answer, hint FROM emojiquiz_quizzez ORDER BY RAND() LIMIT 1;"
                    await cur.execute(query)
                    quiz_data = await cur.fetchone()
                    if quiz_data:
                        question, answer, hint = quiz_data

                        emojiquiz_embed = discord.Embed(
                            title="Emojiquiz",
                            description="Solltest du Probleme beim Lösen haben, kannst du die Buttons dieser Nachricht benutzen.",
                            colour=discord.Colour.blue())
                        emojiquiz_embed.add_field(name="❓ Gesuchter Begriff", value=question, inline=True)
                        emojiquiz_embed.add_field(name="❗️ Tipp", value=f"||{hint}||", inline=True)
                        emojiquiz_embed.set_footer(
                            text=f"The last Quiz was skipped by {interaction.user.name}",
                            icon_url=interaction.user.avatar)

                        sent = await interaction.channel.send(embed=emojiquiz_embed, view=buttons_emj(bot=self.bot, economy=self.economy))
                        await cur.execute("UPDATE emojiquiz SET messageID = %s WHERE guildID = %s", (sent.id, interaction.guild.id))
                        await cur.execute("INSERT INTO emojiquiz_lsg(guildID, lösung) VALUES (%s, %s)", (interaction.guild.id, answer))

                        # Nur dem Nutzer Feedback geben (Button Response)
                        await interaction.response.send_message(
                            "Das Quiz wurde übersprungen und eine neue Frage gepostet!", ephemeral=True)
        except discord.errors.NotFound:
            print(f"Die Interaktion von {interaction.user} ist abgelaufen oder bereits beantwortet.")

    @discord.ui.button(label='Initial letter', style=discord.ButtonStyle.grey, custom_id='persistent_view:tip', emoji="💡")
    async def tip(self, interaction: discord.Interaction, button: discord.Button):
        async with interaction.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT channelID FROM emojiquiz WHERE guildID = (%s)", (interaction.guild.id,))
                already_on = await cur.fetchone()
                if not already_on:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> Das Emojiquizz ist deaktiviert.")
                    return
                await cur.execute("SELECT lösung FROM emojiquiz_lsg WHERE guildID = (%s)", (interaction.guild.id,))
                lsg = await cur.fetchone()
                loesung = lsg[0]
                words = loesung.split()

                user_balance = await self.economy.get_balance(interaction.user.id)
                wallet, bank = user_balance
                if wallet < 20:
                    await interaction.response.send_message(
                        "Du hast nicht genug Geld, um den Tipp zu erhalten. Du benötigst mindestens 20 <:Astra_cookie:1141303831293079633>.",
                        ephemeral=True)
                    return

                first_letter = words[0][0]
                await self.economy.update_balance(interaction.user.id, wallet_change=-20)
                await interaction.response.send_message(
                    f"💡 Der erste Buchstabe für das Wort was du suchst ist: {first_letter}. Aber mehr Tipps kann ich dir nicht geben.",
                    ephemeral=True)



class emojiquiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = Economy(bot)  # Füge die Economy-Instanz hinzu

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:  # Ignoriere private Nachrichten
            return
        if msg.author.bot:  # Ignoriere Nachrichten von Bots
            return

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM emojiquiz_lsg WHERE guildID = %s", (msg.guild.id,))
                # Prüfe, ob das Emoji-Quiz aktiv ist
                await cur.execute("SELECT channelID, messageID FROM emojiquiz WHERE guildID = %s", (msg.guild.id,))
                already_on = await cur.fetchone()
                if not already_on:
                    return  # Emoji-Quiz ist nicht aktiviert

                channelID = already_on[0]
                quiz_message_id = already_on[1]
                if int(channelID) == int(msg.channel.id):
                    # Hole die Lösung für das Quiz
                    await cur.execute("SELECT lösung FROM emojiquiz_lsg WHERE guildID = %s", (msg.guild.id,))
                    result2 = await cur.fetchone()
                    if result2:
                        loesung = result2[0]
                        if msg.content.strip().lower() == loesung.strip().lower():  # Überprüfe die Antwort (whitespace + case-insensitive)
                            # ✅ Reaktion für richtige Antwort
                            right_message = await msg.channel.fetch_message(msg.id)
                            await right_message.add_reaction('✅')
                            await cur.execute("DELETE FROM emojiquiz_lsg WHERE guildID = %s", (msg.guild.id,))

                            # Frage für neues Quiz holen
                            query = "SELECT question, answer, hint FROM emojiquiz_quizzez ORDER BY RAND() LIMIT 1;"
                            await cur.execute(query)
                            quiz_data = await cur.fetchone()
                            if quiz_data:
                                question = quiz_data[0]
                                answer = quiz_data[1]
                                hint = quiz_data[2]

                                # Guthaben erhöhen
                                await self.economy.update_balance(msg.author.id, wallet_change=20)

                                # --- Alte Quiznachricht löschen ---
                                if quiz_message_id:
                                    try:
                                        old_msg = await msg.channel.fetch_message(int(quiz_message_id))
                                        await old_msg.delete()
                                    except Exception:
                                        pass  # Nachricht existiert evtl. nicht mehr

                                # Neue Quiz-Nachricht senden
                                emojiquiz_embed = discord.Embed(
                                    title="Emojiquiz",
                                    description="Solltest du Probleme beim Lösen haben, kannst du die Buttons dieser Nachricht benutzen.",
                                    colour=discord.Colour.blue())
                                emojiquiz_embed.add_field(name="❓ Gesuchter Begriff", value=question, inline=True)
                                emojiquiz_embed.add_field(name="❗️ Tipp", value=f"||{hint}||", inline=True)
                                emojiquiz_embed.set_footer(
                                    text=f"Das letzte Quiz wurde von {msg.author.name} erraten!",
                                    icon_url=msg.author.avatar.url
                                )
                                sent = await msg.channel.send(embed=emojiquiz_embed,
                                                              view=buttons_emj(bot=self.bot, economy=self.economy))

                                # Neue Quiz-Message-ID speichern
                                await cur.execute("UPDATE emojiquiz SET messageID = %s WHERE guildID = %s",
                                                  (sent.id, msg.guild.id))

                                # Lösung für neues Quiz abspeichern
                                await cur.execute("INSERT INTO emojiquiz_lsg(guildID, lösung) VALUES (%s, %s)",
                                                  (msg.guild.id, answer))

                        elif msg.content.lower() != loesung.lower():  # Falsche Antwort
                            message = await msg.channel.fetch_message(msg.id)
                            await message.add_reaction('❌')  # Falsche Antwort - ❌ Reaktion hinzufügen

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(buttons_emj(bot=self.bot, economy=self.economy))

    @app_commands.command(name="emojiquiz")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def emojiquiz(self, interaction: discord.Interaction, status: Literal['An', 'Aus'],
                        channel: discord.TextChannel):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if status == "An":
                    await cur.execute("SELECT channelID, messageID FROM emojiquiz WHERE guildID = (%s)",
                                      (interaction.guild.id,))
                    already_on = await cur.fetchone()
                    if already_on:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> Das Emojiquizz ist bereits aktiviert.")
                    else:
                        query = "SELECT question, answer, hint FROM emojiquiz_quizzez ORDER BY RAND() LIMIT 1;"
                        await cur.execute(query)
                        quiz_data = await cur.fetchone()
                        if quiz_data:
                            question, answer, hint = quiz_data

                            emojiquiz_embed = discord.Embed(
                                title="Emojiquiz",
                                description="Solltest du Probleme beim Lösen haben, kannst du die Buttons dieser Nachricht benutzen.",
                                colour=discord.Colour.blue())
                            emojiquiz_embed.add_field(name="❓ Gesuchter Begriff", value=question, inline=True)
                            emojiquiz_embed.add_field(name="❗️ Tipp", value=f"||{hint}||", inline=True)
                            emojiquiz_embed.set_footer(
                                text=f"Das letzte Quiz wurde von {interaction.user.name} erraten!",
                                icon_url=interaction.user.avatar)

                            sent = await channel.send(embed=emojiquiz_embed,
                                                      view=buttons_emj(bot=self.bot, economy=self.economy))
                            await cur.execute(
                                "INSERT INTO emojiquiz(guildID, channelID, messageID) VALUES (%s, %s, %s)",
                                (interaction.guild.id, channel.id, sent.id))
                            await cur.execute(
                                "INSERT INTO emojiquiz_lsg(guildID, lösung) VALUES (%s, %s)",
                                (interaction.guild.id, answer))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> Das Emojiquiz ist nun aktiviert!")

                if status == "Aus":
                    await cur.execute("SELECT channelID, messageID FROM emojiquiz WHERE guildID = (%s)",
                                      (interaction.guild.id,))
                    already_off = await cur.fetchone()
                    if not already_off:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> Das Emojiquizz ist bereits deaktiviert.")
                    else:
                        channel_id, msg_id = already_off
                        # Versuche, die Quiznachricht zu löschen
                        try:
                            quiz_channel = self.bot.get_channel(channel_id)
                            quiz_msg = await quiz_channel.fetch_message(msg_id)
                            await quiz_msg.delete()
                        except Exception:
                            pass  # Ignoriere Fehler beim Löschen

                        await cur.execute(
                            "DELETE FROM emojiquiz WHERE guildID = (%s) AND channelID = (%s)",
                            (interaction.guild.id, channel.id))
                        await cur.execute(
                            "DELETE FROM emojiquiz_lsg WHERE guildID = %s",
                            (interaction.guild.id,))
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> Das Emojiquiz ist nun deaktiviert!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(emojiquiz(bot))
