import discord
from discord.ext import commands
import subprocess
import textwrap
import traceback
import sys
import psutil
import inspect
import io
import asyncio
import time

class DevTools(commands.Cog):
    def __init__(self, bot, owner_id):
        self.bot = bot
        self.owner_id = owner_id
        self.start_time = time.time()
        self.commands_run = 0

    def cog_check(self, ctx):
        return ctx.author.id == self.owner_id

    def format_output(self, output):
        if len(output) > 1900:
            return output[:1900] + "\n... (Ausgabe gekürzt)"
        return output

    @commands.command(name="eval")
    async def eval_code(self, ctx, *, code: str):
        """Führt Python-Code aus."""
        self.commands_run += 1
        code = code.strip("` ")
        fn_code = f"async def _eval_fn():\n{textwrap.indent(code, '    ')}"
        env = {
            'bot': self.bot,
            'discord': discord,
            'commands': commands,
            'ctx': ctx,
            'asyncio': asyncio,
            '__import__': __import__
        }
        try:
            exec(fn_code, env)
            result = await env["_eval_fn"]()
            output = repr(result)
        except Exception:
            output = traceback.format_exc()
        await ctx.send(f"```py\n{self.format_output(output)}```")

    @commands.command(name="shell")
    async def shell_command(self, ctx, *, command: str):
        """Führt Shell-Befehl aus."""
        self.commands_run += 1
        try:
            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True, timeout=15)
            output = self.format_output(output)
            await ctx.send(f"```bash\n{output}```")
        except subprocess.CalledProcessError as e:
            output = self.format_output(e.output)
            await ctx.send(f"```bash\nFehler:\n{output}```")
        except Exception as e:
            await ctx.send(f"Exception: {e}")

    @commands.command(name="load")
    async def load_cog(self, ctx, cog: str):
        self.commands_run += 1
        try:
            self.bot.load_extension(cog)
            await ctx.send(f"Cog `{cog}` geladen.")
        except Exception as e:
            await ctx.send(f"Fehler beim Laden:\n```py\n{e}```")

    @commands.command(name="unload")
    async def unload_cog(self, ctx, cog: str):
        self.commands_run += 1
        try:
            self.bot.unload_extension(cog)
            await ctx.send(f"Cog `{cog}` entladen.")
        except Exception as e:
            await ctx.send(f"Fehler beim Entladen:\n```py\n{e}```")

    @commands.command(name="reload")
    async def reload_cog(self, ctx, cog: str):
        self.commands_run += 1
        try:
            self.bot.reload_extension(cog)
            await ctx.send(f"Cog `{cog}` neu geladen.")
        except Exception as e:
            await ctx.send(f"Fehler beim Neuladen:\n```py\n{e}```")

    @commands.command(name="source")
    async def source(self, ctx, *, command_name: str = None):
        """Zeigt den Quellcode eines Slash-Commands oder des gesamten Cogs."""
        self.commands_run += 1

        if command_name is None:
            # Quellcode des gesamten Cogs anzeigen
            try:
                source = inspect.getsource(self.__class__)
                await ctx.send(f"```py\n{source}```")
            except Exception as e:
                await ctx.send(f"Fehler: {e}")
            return

        # Slash-Command suchen im bot.tree
        cmd = None
        for command in self.bot.tree.get_commands():
            if command.name == command_name:
                cmd = command
                break

        if not cmd:
            await ctx.send(f"Slash Command `{command_name}` nicht gefunden.")
            return

        try:
            source = inspect.getsource(cmd.callback)
            if len(source) > 1900:
                source = source[:1900] + "\n# ... (gekürzt)"
            await ctx.send(f"```py\n{source}```")
        except Exception as e:
            await ctx.send(f"Fehler beim Abrufen des Quellcodes: {e}")

    @commands.command(name="memory")
    async def memory(self, ctx):
        """Zeigt Speicherverbrauch des Bots."""
        self.commands_run += 1
        try:
            process = psutil.Process()
            mem = process.memory_info().rss / (1024 ** 2)  # MB
            await ctx.send(f"Speicherverbrauch: {mem:.2f} MB")
        except Exception as e:
            await ctx.send(f"Fehler: {e}")

    @commands.command(name="stats")
    async def stats(self, ctx):
        """Zeigt ein paar Bot-Statistiken."""
        self.commands_run += 1
        uptime = time.time() - self.start_time
        embed = discord.Embed(title="Bot Statistiken", color=discord.Color.blurple())
        embed.add_field(name="Uptime", value=f"{uptime/60:.2f} Minuten")
        embed.add_field(name="Server (Guilds)", value=str(len(self.bot.guilds)))
        embed.add_field(name="Benutzer", value=str(len(self.bot.users)))
        embed.add_field(name="Commands ausgeführt", value=str(self.commands_run))
        embed.set_footer(text=f"Deine ID: {self.owner_id}")
        await ctx.send(embed=embed)

    @commands.command(name="ping")
    async def ping(self, ctx):
        """Zeigt die Latenz."""
        self.commands_run += 1
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! Latenz: {latency}ms")

    @commands.command(name="restart")
    async def restart(self, ctx):
        """Startet den Bot-Service neu via systemctl."""
        await ctx.send("🔁 Starte Bot-Service neu...")
        # Starte den Service neu über den absoluten Pfad
        subprocess.Popen(["/usr/bin/systemctl", "restart", "astrabot.service"])
        await self.bot.close()

    @commands.command(name="logs")
    async def logs(self, ctx, lines: int = 20):
        """Zeigt die letzten X Zeilen des systemd-Service-Logs."""
        proc = subprocess.run(
            ["journalctl", "-u", "astrabot.service", f"-n{lines}", "--no-pager"],
            capture_output=True, text=True
        )
        output = proc.stdout
        if len(output) > 1900:
            output = output[-1900:]  # letzte 1900 Zeichen
        await ctx.send(f"```bash\n{output}```")

    @commands.command(name="update")
    @commands.is_owner()
    async def update(self, ctx):
        """Führt git pull im /root/Astra Verzeichnis aus."""
        await ctx.send("🔄 Ziehe Updates vom Git-Repo in /root/Astra...")

        proc = subprocess.run(
            "cd /root/Astra && /usr/bin/git pull",  # <-- absoluter Pfad zu git
            shell=True,
            capture_output=True,
            text=True
        )

        output = proc.stdout + proc.stderr
        if len(output) > 1900:
            output = output[:1900] + "\n... (gekürzt)"
        await ctx.send(f"```bash\n{output}```")

    @commands.command(name="sysinfo")
    async def sysinfo(self, ctx):
        """Zeigt CPU- und RAM-Auslastung des Servers."""
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        await ctx.send(
            f"**System Info:**\n"
            f"CPU-Auslastung: {cpu}%\n"
            f"RAM-Auslastung: {mem.percent}% ({mem.used // 1024 ** 2}MB / {mem.total // 1024 ** 2}MB)"
        )


async def setup(bot: commands.Bot) -> None:
    # Ersetze hier deine User-ID!
    owner_id = 789555434201677824
    await bot.add_cog(DevTools(bot, owner_id))