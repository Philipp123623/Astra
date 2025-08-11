# cogs/uno.py
from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Literal

import aiomysql
import discord
from discord import app_commands
from discord.ext import commands, tasks

ASTRA_COLOR = discord.Color.from_rgb(70, 130, 180)

# ------------------- Karten/Regeln -------------------

COLORS = ["R", "Y", "G", "B"]  # rot/gelb/grün/blau
NUMS = [str(i) for i in range(10)]
ACTIONS = ["skip", "reverse", "+2"]       # farbgebunden
WILDS = ["wild", "+4"]                    # farblos

EMOJI_COLOR = {"R": "🔴", "Y": "🟡", "G": "🟢", "B": "🔵", "ANY": "🎨"}
EMOJI_VAL = {**{n: n for n in NUMS}, "skip": "⏭️", "reverse": "🔁", "+2": "+2", "wild": "🃏", "+4": "+4"}

TURN_TIMEOUT_SEC = 45         # Zeit pro Zug
UNO_FORGET_PENALTY = 2        # Strafe, wenn UNO nicht gedrückt wird
MAX_PLAYERS = 6
MIN_PLAYERS = 2

def mk_deck() -> List[Dict]:
    deck: List[Dict] = []
    for c in COLORS:
        deck.append({"color": c, "value": "0"})
        for _ in range(2):
            for n in NUMS[1:]:
                deck.append({"color": c, "value": n})
            for a in ACTIONS:
                deck.append({"color": c, "value": a})
    for _ in range(4):
        deck.append({"color": "ANY", "value": "wild"})
        deck.append({"color": "ANY", "value": "+4"})
    random.shuffle(deck)
    return deck

def label(card: Dict) -> str:
    return f"{EMOJI_COLOR.get(card['color'],'🎨')} {EMOJI_VAL.get(card['value'], card['value'])}"

def playable(card: Dict, top: Dict, forced: Optional[str]) -> bool:
    if card["color"] == "ANY":
        return True
    if forced:
        return card["color"] == forced or card["value"] == top["value"]
    return (card["color"] == top["color"]) or (card["value"] == top["value"]) or (top["color"] == "ANY")


# ------------------- State -------------------

@dataclass
class UnoState:
    game_id: int
    guild_id: int
    channel_id: int
    host_id: int

    status: Literal["lobby", "active", "ended", "cancelled"] = "lobby"
    lobby_open: bool = True
    players: List[int] = field(default_factory=list)
    hands: Dict[int, List[Dict]] = field(default_factory=dict)

    draw_pile: List[Dict] = field(default_factory=mk_deck)
    discard_pile: List[Dict] = field(default_factory=list)
    top_card: Dict = field(default_factory=lambda: {"color": "ANY", "value": "wild"})
    forced_color: Optional[str] = None

    direction: int = 1
    turn_index: int = 0
    draw_stack: int = 0

    last_turn_at: float = 0.0  # unix ts
    uno_called: Dict[int, bool] = field(default_factory=dict)

    lobby_message_id: Optional[int] = None
    table_message_id: Optional[int] = None

    def to_json(self) -> Tuple[str, str]:
        game = {
            "status": self.status,
            "lobby_open": self.lobby_open,
            "players": self.players,
            "draw_pile": self.draw_pile,
            "discard_pile": self.discard_pile,
            "top_card": self.top_card,
            "forced_color": self.forced_color,
            "direction": self.direction,
            "turn_index": self.turn_index,
            "draw_stack": self.draw_stack,
            "last_turn_at": self.last_turn_at,
        }
        players = {
            str(uid): {"hand": self.hands.get(uid, []), "uno": self.uno_called.get(uid, False)}
            for uid in self.players
        }
        return json.dumps(game, separators=(",", ":")), json.dumps(players, separators=(",", ":"))

    @classmethod
    def from_row(cls, row: dict) -> "UnoState":
        game = json.loads(row["game_json"])
        players = json.loads(row["players_json"])
        s = cls(
            game_id=row["game_id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            host_id=row["host_id"],
        )
        s.status = game["status"]
        s.lobby_open = game.get("lobby_open", True)
        s.players = list(map(int, game["players"]))
        s.draw_pile = game["draw_pile"]
        s.discard_pile = game["discard_pile"]
        s.top_card = game["top_card"]
        s.forced_color = game["forced_color"]
        s.direction = int(game["direction"])
        s.turn_index = int(game["turn_index"])
        s.draw_stack = int(game["draw_stack"])
        s.last_turn_at = float(game.get("last_turn_at", 0))
        s.hands = {int(uid): data["hand"] for uid, data in players.items()}
        s.uno_called = {int(uid): bool(data.get("uno", False)) for uid, data in players.items()}
        s.lobby_message_id = row["lobby_message_id"]
        s.table_message_id = row["table_message_id"]
        return s

    # ---- helpers ----
    def current_uid(self) -> int:
        return self.players[self.turn_index % len(self.players)]

    def seat(self, uid: int) -> int:
        return self.players.index(uid)

    def ensure_draw(self):
        if not self.draw_pile:
            keep = self.discard_pile[-1]
            pool = self.discard_pile[:-1]
            random.shuffle(pool)
            self.draw_pile = pool
            self.discard_pile = [keep]

    def draw(self, uid: int, n: int) -> List[Dict]:
        out: List[Dict] = []
        for _ in range(n):
            self.ensure_draw()
            out.append(self.draw_pile.pop())
        self.hands[uid].extend(out)
        return out

    def valid_moves(self, uid: int) -> List[Tuple[int, Dict]]:
        return [(i, c) for i, c in enumerate(self.hands[uid]) if playable(c, self.top_card, self.forced_color)]

    def next_turn(self, steps: int = 1):
        self.turn_index = (self.turn_index + steps * self.direction) % len(self.players)
        self.last_turn_at = datetime.now(timezone.utc).timestamp()

    def deal(self):
        for uid in self.players:
            self.hands[uid] = [self.draw_pile.pop() for _ in range(7)]
            self.uno_called[uid] = False
        # Startkarte (keine Wild/+4)
        while True:
            c = self.draw_pile.pop()
            if c["color"] != "ANY" and c["value"] not in ("wild", "+4"):
                self.top_card = c
                self.discard_pile.append(c)
                break
            self.draw_pile.insert(0, c)
        self.forced_color = None
        self.last_turn_at = datetime.now(timezone.utc).timestamp()

    def play(self, uid: int, idx: int, chosen_color: Optional[str]) -> str:
        card = self.hands[uid].pop(idx)
        self.discard_pile.append(card)
        self.top_card = card

        # UNO zurücksetzen sobald man >1 Karte hat
        if len(self.hands[uid]) > 1:
            self.uno_called[uid] = False

        if card["color"] == "ANY":
            self.forced_color = chosen_color or random.choice(COLORS)
            if card["value"] == "wild":
                return "wild"
            else:
                self.draw_stack += 4
                return "+4"
        else:
            self.forced_color = None
            v = card["value"]
            if v == "skip":
                return "skip"
            if v == "reverse":
                self.direction *= -1
                return "reverse"
            if v == "+2":
                self.draw_stack += 2
                return "+2"
            return "normal"


# ------------------- Views -------------------

class LobbyView(discord.ui.View):
    def __init__(self, cog: "UnoCog", game_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_id = game_id

    @discord.ui.button(label="Beitreten", style=discord.ButtonStyle.success, custom_id="uno:lobby:join")
    async def join(self, it: discord.Interaction, _): await self.cog.ui_lobby_join(it, self.game_id)

    @discord.ui.button(label="Verlassen", style=discord.ButtonStyle.secondary, custom_id="uno:lobby:leave")
    async def leave(self, it: discord.Interaction, _): await self.cog.ui_lobby_leave(it, self.game_id)

    @discord.ui.button(label="Lobby öffnen/schließen", style=discord.ButtonStyle.blurple, custom_id="uno:lobby:toggle")
    async def toggle(self, it: discord.Interaction, _): await self.cog.ui_lobby_toggle(it, self.game_id)

    @discord.ui.button(label="Starten (Host)", style=discord.ButtonStyle.primary, custom_id="uno:lobby:start")
    async def start(self, it: discord.Interaction, _): await self.cog.ui_lobby_start(it, self.game_id)

    @discord.ui.button(label="Abbrechen (Host)", style=discord.ButtonStyle.danger, custom_id="uno:lobby:cancel")
    async def cancel(self, it: discord.Interaction, _): await self.cog.ui_lobby_cancel(it, self.game_id)


class TableView(discord.ui.View):
    def __init__(self, cog: "UnoCog", game_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_id = game_id

    @discord.ui.button(label="Hand öffnen (Zug)", style=discord.ButtonStyle.primary, custom_id="uno:table:hand")
    async def hand(self, it: discord.Interaction, _): await self.cog.ui_open_hand(it, self.game_id)

    @discord.ui.button(label="Ziehen", style=discord.ButtonStyle.secondary, custom_id="uno:table:draw")
    async def draw(self, it: discord.Interaction, _): await self.cog.ui_draw(it, self.game_id)

    @discord.ui.button(label="UNO!", style=discord.ButtonStyle.success, custom_id="uno:table:uno")
    async def uno(self, it: discord.Interaction, _): await self.cog.ui_uno(it, self.game_id)


class HandView(discord.ui.View):
    def __init__(self, cog: "UnoCog", state: UnoState, uid: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.state = state
        self.uid = uid
        # Buttons für spielbare Karten
        for idx, c in self.state.valid_moves(uid):
            txt = label(c)
            self.add_item(PlayButton(idx, txt))
        self.add_item(ColorPickSelect())

class PlayButton(discord.ui.Button):
    def __init__(self, hand_index: int, text: str):
        super().__init__(style=discord.ButtonStyle.primary, label=text, custom_id=f"uno:play:{hand_index}")
        self.hand_index = hand_index
    async def callback(self, it: discord.Interaction):
        await self.view.cog.ui_play_card(it, self.hand_index)  # type: ignore

class ColorPickSelect(discord.ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label=f"{EMOJI_COLOR[c]} {c}", value=c) for c in COLORS]
        super().__init__(placeholder="(Optional) Farbe für WILD/+4 wählen", min_values=0, max_values=1, options=opts)

# ------------------- Slash-Group -------------------

@app_commands.guild_only()
class Uno(app_commands.Group):
    def __init__(self, cog: "UnoCog"):
        super().__init__(name="uno", description="UNO Light – PvP mit Lobby & Tisch")
        self.cog = cog

    @app_commands.command(name="start", description="UNO-Lobby in diesem Kanal erstellen.")
    @app_commands.describe(privat="Lobby geschlossen (nur Einladungen) oder offen?")
    async def start(self, it: discord.Interaction, privat: Optional[bool] = False):
        await self.cog.cmd_start_lobby(it, privat=bool(privat))

    @app_commands.command(name="einladen", description="Lade einen Nutzer in die Lobby ein.")
    async def invite(self, it: discord.Interaction, user: discord.User):
        await self.cog.cmd_invite(it, user)

    @app_commands.command(name="beitreten", description="Der letzten Lobby in diesem Kanal beitreten (falls offen/ eingeladen).")
    async def join(self, it: discord.Interaction):
        await self.cog.cmd_join(it)

    @app_commands.command(name="verlassen", description="Lobby verlassen.")
    async def leave(self, it: discord.Interaction):
        await self.cog.cmd_leave(it)

    @app_commands.command(name="status", description="Status der Runde/Lobby anzeigen.")
    async def status(self, it: discord.Interaction):
        await self.cog.cmd_status(it)


# ------------------- Cog -------------------

class UnoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        if not hasattr(bot, "pool") or not isinstance(bot.pool, aiomysql.Pool):  # type: ignore
            raise RuntimeError("Dieses Cog erwartet aiomysql-Pool in bot.pool")
        self.bot = bot
        self.pool: aiomysql.Pool = bot.pool

    async def cog_load(self):
        await self.ensure_tables()
        # Recovery: aktive/lobby Spiele re-attachen
        await self._recover_views()
        # Background Task starten
        self.maintain_games.start()
        # Slash group registrieren
        try:
            self.bot.tree.add_command(Uno(self))
        except Exception:
            pass

    async def cog_unload(self):
        self.maintain_games.cancel()

    # ---------- DB ----------

    async def ensure_tables(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS uno_games (
              game_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              guild_id BIGINT NOT NULL,
              channel_id BIGINT NOT NULL,
              host_id BIGINT NOT NULL,
              status ENUM('lobby','active','ended','cancelled') NOT NULL DEFAULT 'lobby',
              lobby_open TINYINT(1) NOT NULL DEFAULT 1,
              lobby_message_id BIGINT NULL,
              table_message_id BIGINT NULL,
              game_json JSON NOT NULL,
              players_json JSON NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
            await conn.commit()

    async def _insert_game(self, st: UnoState) -> int:
        gj, pj = st.to_json()
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("""
            INSERT INTO uno_games (guild_id, channel_id, host_id, status, lobby_open, game_json, players_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (st.guild_id, st.channel_id, st.host_id, st.status, 1 if st.lobby_open else 0, gj, pj))
            game_id = cur.lastrowid
            await conn.commit()
        return int(game_id)

    async def _fetch_row(self, game_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM uno_games WHERE game_id=%s", (game_id,))
            return await cur.fetchone()

    async def _fetch_open_lobby(self, guild_id: int, channel_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM uno_games
                 WHERE guild_id=%s AND channel_id=%s AND status='lobby'
                 ORDER BY created_at DESC LIMIT 1
            """, (guild_id, channel_id))
            return await cur.fetchone()

    async def _save_state(self, st: UnoState):
        gj, pj = st.to_json()
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("""
                UPDATE uno_games
                   SET status=%s,
                       lobby_open=%s,
                       lobby_message_id=%s,
                       table_message_id=%s,
                       game_json=%s,
                       players_json=%s
                 WHERE game_id=%s
            """, (st.status, 1 if st.lobby_open else 0, st.lobby_message_id, st.table_message_id, gj, pj, st.game_id))
            await conn.commit()

    async def _recover_views(self):
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM uno_games WHERE status IN ('lobby','active')")
            rows = await cur.fetchall()
        for r in rows or []:
            st = UnoState.from_row(r)
            # Lobby View re-attach
            if st.status == "lobby" and st.lobby_message_id:
                ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
                try:
                    msg = await ch.fetch_message(st.lobby_message_id)
                    await msg.edit(view=LobbyView(self, st.game_id))
                except Exception:
                    pass
            # Table View re-attach
            if st.status == "active" and st.table_message_id:
                ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
                try:
                    msg = await ch.fetch_message(st.table_message_id)
                    await msg.edit(view=TableView(self, st.game_id))
                except Exception:
                    pass

    # ---------- Embeds ----------

    def emb_lobby(self, st: UnoState) -> discord.Embed:
        e = discord.Embed(
            title=f"UNO Lobby #{st.game_id}",
            description=("Lobby ist **offen** – jeder kann beitreten."
                         if st.lobby_open else "Lobby ist **geschlossen** – nur auf Einladung."),
            color=ASTRA_COLOR
        )
        e.add_field(name="Host", value=f"<@{st.host_id}>", inline=True)
        e.add_field(name="Spieler (2–6)", value="\n".join(f"<@{u}>" for u in st.players) or "—", inline=True)
        e.set_footer(text="Host: Lobby öffnen/schließen • Starten • Abbrechen")
        return e

    def emb_table(self, st: UnoState) -> discord.Embed:
        direction = "➡️" if st.direction == 1 else "⬅️"
        counts = " | ".join(f"<@{u}>: **{len(st.hands.get(u, []))}**" for u in st.players)
        top = label(st.top_card) + (f" → {EMOJI_COLOR[st.forced_color]}" if st.forced_color else "")
        e = discord.Embed(
            title=f"UNO – Spiel #{st.game_id}",
            description=(f"**Am Zug:** <@{st.current_uid()}>  |  **Richtung:** {direction}\n"
                         f"**Oberste Karte:** {top}\n"
                         f"**Karten:** {counts}"),
            color=ASTRA_COLOR
        )
        if st.draw_stack:
            e.add_field(name="Zieh-Stapel", value=f"{st.draw_stack} Karten fällig", inline=False)
        e.set_footer(text="„Hand öffnen“ wenn du dran bist • „Ziehen“ wenn keine Karte passt • „UNO!“ bei 1 Karte")
        return e

    # ---------- Commands ----------

    async def cmd_start_lobby(self, it: discord.Interaction, privat: bool):
        if await self._fetch_open_lobby(it.guild_id, it.channel_id):  # type: ignore
            return await it.response.send_message("❌ Hier läuft bereits eine Lobby.", ephemeral=True)

        st = UnoState(
            game_id=0,
            guild_id=it.guild_id,         # type: ignore
            channel_id=it.channel_id,     # type: ignore
            host_id=it.user.id,
            lobby_open=not privat,
            status="lobby",
        )
        st.players = [it.user.id]
        st.game_id = await self._insert_game(st)

        embed = self.emb_lobby(st)
        await it.response.send_message(embed=embed, view=LobbyView(self, st.game_id))
        st.lobby_message_id = (await it.original_response()).id
        await self._save_state(st)

    async def cmd_invite(self, it: discord.Interaction, user: discord.User):
        row = await self._fetch_open_lobby(it.guild_id, it.channel_id)  # type: ignore
        if not row: return await it.response.send_message("❌ Keine Lobby gefunden.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id != st.host_id:
            return await it.response.send_message("❌ Nur der Host kann einladen.", ephemeral=True)
        try:
            e = discord.Embed(
                title=f"UNO-Einladung #{st.game_id}",
                description=f"<@{st.host_id}> lädt dich in eine UNO-Lobby ein.\nKanal: <#{st.channel_id}>",
                color=ASTRA_COLOR
            )
            join_cmd = f"</uno beitreten:{self.bot.tree.get_command('uno').id}>" if self.bot.tree.get_command('uno') else "`/uno beitreten`"  # type: ignore
            e.add_field(name="Beitreten", value=join_cmd)
            await user.send(embed=e)
            await it.response.send_message("✅ Einladung verschickt.", ephemeral=True)
        except Exception:
            await it.response.send_message("⚠️ Einladung konnte nicht per DM gesendet werden.", ephemeral=True)

    async def cmd_join(self, it: discord.Interaction):
        row = await self._fetch_open_lobby(it.guild_id, it.channel_id)  # type: ignore
        if not row: return await it.response.send_message("❌ Keine offene Lobby hier.", ephemeral=True)
        await self.ui_lobby_join(it, row["game_id"])

    async def cmd_leave(self, it: discord.Interaction):
        row = await self._fetch_open_lobby(it.guild_id, it.channel_id)  # type: ignore
        if not row: return await it.response.send_message("❌ Keine offene Lobby hier.", ephemeral=True)
        await self.ui_lobby_leave(it, row["game_id"])

    async def cmd_status(self, it: discord.Interaction):
        # zeige Lobby/Spiel falls vorhanden
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM uno_games
                 WHERE guild_id=%s AND channel_id=%s
                   AND status IN ('lobby','active')
                 ORDER BY updated_at DESC LIMIT 1
            """, (it.guild_id, it.channel_id))  # type: ignore
            row = await cur.fetchone()
        if not row:
            return await it.response.send_message("ℹ️ Kein aktives UNO-Spiel hier.", ephemeral=True)
        st = UnoState.from_row(row)
        emb = self.emb_lobby(st) if st.status == "lobby" else self.emb_table(st)
        view = LobbyView(self, st.game_id) if st.status == "lobby" else TableView(self, st.game_id)
        await it.response.send_message(embed=emb, view=view, ephemeral=True)

    # ---------- UI Actions (Lobby) ----------

    async def ui_lobby_join(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "lobby":
            return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if not st.lobby_open and it.user.id != st.host_id:
            return await it.response.send_message("❌ Lobby ist geschlossen. Nur Einladung erlaubt.", ephemeral=True)
        if it.user.id in st.players:
            return await it.response.send_message("Du bist bereits in der Lobby.", ephemeral=True)
        if len(st.players) >= MAX_PLAYERS:
            return await it.response.send_message("❌ Lobby ist voll.", ephemeral=True)
        st.players.append(it.user.id)
        await self._save_state(st)
        # UI aktualisieren
        await self._edit_lobby_message(st)
        await it.response.send_message("✅ Beigetreten.", ephemeral=True)

    async def ui_lobby_leave(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "lobby":
            return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id not in st.players:
            return await it.response.send_message("Du bist nicht in der Lobby.", ephemeral=True)
        st.players.remove(it.user.id)
        if not st.players:
            st.status = "cancelled"
        else:
            if it.user.id == st.host_id:
                st.host_id = st.players[0]  # Host wechseln
        await self._save_state(st)
        await self._edit_lobby_message(st)
        await it.response.send_message("✅ Verlassen.", ephemeral=True)

    async def ui_lobby_toggle(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "lobby":
            return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id != st.host_id:
            return await it.response.send_message("❌ Nur der Host kann die Lobby öffnen/schließen.", ephemeral=True)
        st.lobby_open = not st.lobby_open
        await self._save_state(st)
        await self._edit_lobby_message(st)
        await it.response.send_message(f"✅ Lobby ist jetzt {'offen' if st.lobby_open else 'geschlossen'}.", ephemeral=True)

    async def ui_lobby_start(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "lobby":
            return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id != st.host_id:
            return await it.response.send_message("❌ Nur der Host kann starten.", ephemeral=True)
        if len(st.players) < MIN_PLAYERS:
            return await it.response.send_message(f"❌ Mindestens {MIN_PLAYERS} Spieler nötig.", ephemeral=True)

        st.status = "active"
        st.deal()
        # Lobby-Message einfrieren
        await self._save_state(st)
        await self._edit_lobby_message(st, disable=True)

        # Table posten
        ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
        msg = await ch.send(embed=self.emb_table(st), view=TableView(self, st.game_id))
        st.table_message_id = msg.id
        await self._save_state(st)
        await it.response.send_message("🎮 Spiel gestartet!", ephemeral=True)

    async def ui_lobby_cancel(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "lobby":
            return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id != st.host_id:
            return await it.response.send_message("❌ Nur der Host kann abbrechen.", ephemeral=True)
        st.status = "cancelled"
        await self._save_state(st)
        await self._edit_lobby_message(st, disable=True)
        await it.response.send_message("❎ Lobby abgebrochen.", ephemeral=True)

    async def _edit_lobby_message(self, st: UnoState, disable: bool = False):
        if not st.lobby_message_id:
            return
        ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
        try:
            view = None if disable else LobbyView(self, st.game_id)
            await (await ch.fetch_message(st.lobby_message_id)).edit(embed=self.emb_lobby(st), view=view)
        except Exception:
            pass

    # ---------- UI Actions (Table) ----------

    async def ui_open_hand(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "active":
            return await it.response.send_message("❌ Spiel existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id != st.current_uid():
            return await it.response.send_message("⏳ Du bist nicht am Zug.", ephemeral=True)

        # nur spielbare Karten + Farbauswahl
        hv = HandView(self, st, it.user.id)
        # Zeige Hand als Liste
        lines = [f"{i+1}. {label(c)}" for i, c in enumerate(st.hands[it.user.id])]
        desc = "Deine Hand:\n" + ("\n".join(lines) if lines else "—")
        await it.response.send_message(desc, view=hv, ephemeral=True)

    async def ui_draw(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "active":
            return await it.response.send_message("❌ Spiel existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id != st.current_uid():
            return await it.response.send_message("⏳ Du bist nicht am Zug.", ephemeral=True)

        n = st.draw_stack if st.draw_stack else 1
        st.draw(it.user.id, n)
        st.draw_stack = 0
        st.next_turn(1)
        await self._save_state(st)
        await self._refresh_table(st)
        await it.response.send_message(f"🃏 Du hast {n} Karte(n) gezogen.", ephemeral=True)

    async def ui_uno(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "active":
            return await it.response.send_message("❌ Spiel existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)
        if len(st.hands.get(it.user.id, [])) == 1:
            st.uno_called[it.user.id] = True
            await self._save_state(st)
            return await it.response.send_message("✅ UNO gerufen!", ephemeral=True)
        return await it.response.send_message("ℹ️ Du hast aktuell nicht genau 1 Karte.", ephemeral=True)

    async def ui_play_card(self, it: discord.Interaction, hand_index: int):
        # game_id steckt nicht direkt im custom_id, daher holen wir es über Ephemeral-Context:
        # Wir speichern die letzte geöffnete Hand nicht; stattdessen prüfen wir aktive Spiele in dem Kanal.
        # (Alternativ: custom_id mit game_id codieren und hier parsen.)
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM uno_games
                 WHERE guild_id=%s AND channel_id=%s AND status='active'
                 ORDER BY updated_at DESC LIMIT 1
            """, (it.guild_id, it.channel_id))  # type: ignore
            row = await cur.fetchone()
        if not row:
            return await it.response.send_message("❌ Spiel nicht gefunden.", ephemeral=True)

        st = UnoState.from_row(row)
        uid = it.user.id
        if uid != st.current_uid():
            return await it.response.send_message("⏳ Du bist nicht am Zug.", ephemeral=True)
        if hand_index < 0 or hand_index >= len(st.hands[uid]):
            return await it.response.send_message("❌ Ungültige Karte.", ephemeral=True)

        card = st.hands[uid][hand_index]
        if not playable(card, st.top_card, st.forced_color):
            return await it.response.send_message("❌ Diese Karte kann nicht gelegt werden.", ephemeral=True)

        # ggf. Farbe aus Select übernehmen
        chosen_color = None
        if card["color"] == "ANY":
            view: HandView = it.message.components and it.message._state._views.get(it.message.id)  # type: ignore
            # robust: aus dem Select-Wert holen, wenn vorhanden
            try:
                # Discord gibt die Selektion über the interaction.data aus:
                comp = it.data.get("components") if hasattr(it, "data") else None  # type: ignore
                # wir setzen chosen_color unten sicherheitshalber mit None->random
            except Exception:
                pass
            # einfacher: lese die aktuelle View, falls vorhanden
            for child in (getattr(it.message, "components", []) or []):
                pass
            # wir versuchen stattdessen den Select-Wert aus dem payload:
            values = []
            try:
                values = it.data.get("values", [])  # type: ignore
            except Exception:
                values = []
            if values:
                chosen_color = values[0] if values[0] in COLORS else None

        effect = st.play(uid, hand_index, chosen_color)
        # UNO-Strafe checken (wenn Spieler nach dem Legen 1 Karte hat)
        if len(st.hands[uid]) == 1 and not st.uno_called.get(uid, False):
            st.draw(uid, UNO_FORGET_PENALTY)
            note = f"⚠️ UNO nicht gerufen! +{UNO_FORGET_PENALTY} gezogen."
        else:
            note = None
        # Sieg?
        if len(st.hands[uid]) == 0:
            st.status = "ended"
            await self._save_state(st)
            await self._announce_end(st, winner_id=uid)
            return await it.response.send_message("🎉 Karte gespielt – du hast GEWONNEN!", ephemeral=True)

        # Effekt ausführen
        step = 1
        if effect == "skip":
            step = 2
        elif effect == "reverse":
            step = 1  # Richtung gewechselt, Zug geht normal weiter
        elif effect in ("+2", "+4"):
            step = 1  # Ziehen passiert beim NÄCHSTEN Spieler auf Draw-Button oder Timeout

        st.next_turn(step)
        st.uno_called[uid] = False  # reset
        await self._save_state(st)
        await self._refresh_table(st)

        txt = f"✅ {label(card)} gelegt."
        if st.forced_color and card["color"] == "ANY":
            txt += f" Farbe gesetzt auf {EMOJI_COLOR[st.forced_color]}"
        if note:
            txt += f"\n{note}"
        await it.response.send_message(txt, ephemeral=True)

    async def _refresh_table(self, st: UnoState):
        if not st.table_message_id:
            return
        ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
        try:
            msg = await ch.fetch_message(st.table_message_id)
            await msg.edit(embed=self.emb_table(st), view=TableView(self, st.game_id))
        except Exception:
            pass

    async def _announce_end(self, st: UnoState, winner_id: int):
        if not st.table_message_id:
            return
        ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
        try:
            msg = await ch.fetch_message(st.table_message_id)
            e = discord.Embed(
                title=f"UNO – Spiel #{st.game_id} beendet",
                description=f"🏆 **Gewinner:** <@{winner_id}>",
                color=discord.Color.gold()
            )
            await msg.edit(embed=e, view=None)
        except Exception:
            pass

    # ---------- Background Maintenance ----------

    @tasks.loop(seconds=10)
    async def maintain_games(self):
        # Timeouts / Auto-Draw / Aufräumen
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM uno_games WHERE status='active'")
            rows = await cur.fetchall()

        now = datetime.now(timezone.utc).timestamp()
        for r in rows or []:
            st = UnoState.from_row(r)
            # Timeout?
            if now - st.last_turn_at > TURN_TIMEOUT_SEC:
                uid = st.current_uid()
                n = st.draw_stack if st.draw_stack else 1
                st.draw(uid, n)
                st.draw_stack = 0
                st.next_turn(1)
                await self._save_state(st)
                await self._refresh_table(st)

        # Aufräumen alter Lobbys (leer oder alt)
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                UPDATE uno_games SET status='cancelled'
                 WHERE status='lobby'
                   AND TIMESTAMPDIFF(MINUTE, updated_at, CURRENT_TIMESTAMP) > 120
            """)
            await conn.commit()

    @maintain_games.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(UnoCog(bot))
