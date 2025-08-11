# cogs/uno.py
from __future__ import annotations
import asyncio, json, random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Literal

import aiomysql
import discord
from discord import app_commands
from discord.ext import commands, tasks

ASTRA = discord.Color.from_rgb(70, 130, 180)
UNO_GOLD = discord.Color.gold()

COLORS = ["R", "Y", "G", "B"]
NUMS = [str(i) for i in range(10)]
ACTIONS = ["skip", "reverse", "+2"]
WILDS = ["wild", "+4"]

EMO_COLOR = {"R": "🔴", "Y": "🟡", "G": "🟢", "B": "🔵", "ANY": "🎨"}
EMO_VAL = {**{n: n for n in NUMS}, "skip": "⏭️", "reverse": "🔁", "+2": "+2", "wild": "🃏", "+4": "+4"}
EMO_DIR = {1: "➡️", -1: "⬅️"}
EMO_SEP = "│"

TURN_TIMEOUT = 45
UNO_PENALTY = 2
MAX_PLAYERS = 6
MIN_PLAYERS = 2

ASTRA_COLOR = discord.Colour.blue()

def mk_deck() -> List[Dict]:
    d = []
    for c in COLORS:
        d.append({"color": c, "value": "0"})
        for _ in range(2):
            for n in NUMS[1:]:
                d.append({"color": c, "value": n})
            for a in ACTIONS:
                d.append({"color": c, "value": a})
    for _ in range(4):
        d.append({"color": "ANY", "value": "wild"})
        d.append({"color": "ANY", "value": "+4"})
    random.shuffle(d)
    return d

def lab(card: Dict) -> str:
    t = f"{EMO_COLOR.get(card['color'],'🎨')} {EMO_VAL.get(card['value'], card['value'])}"
    return t

def is_playable(card: Dict, top: Dict, forced: Optional[str]) -> bool:
    if card["color"] == "ANY":
        return True
    if forced:
        return card["color"] == forced or card["value"] == top["value"]
    return card["color"] == top["color"] or card["value"] == top["value"] or top["color"] == "ANY"

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
    last_turn_at: float = 0.0
    uno_called: Dict[int, bool] = field(default_factory=dict)
    invited: List[int] = field(default_factory=list)  # <— NEU
    lobby_message_id: Optional[int] = None
    table_message_id: Optional[int] = None

    def to_json(self) -> Tuple[str, str]:
        g = {
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
            "lobby_message_id": self.lobby_message_id,
            "table_message_id": self.table_message_id,
            "host_id": self.host_id,
            "invited": self.invited,
        }
        p = {str(uid): {"hand": self.hands.get(uid, []), "uno": self.uno_called.get(uid, False)} for uid in self.players}
        return json.dumps(g, separators=(",", ":")), json.dumps(p, separators=(",", ":"))

    @classmethod
    def from_row(cls, row: dict) -> "UnoState":
        game = json.loads(row["game_json"])
        g = json.loads(row["game_json"])
        p = json.loads(row["players_json"])
        s = cls(
            game_id=row["game_id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            host_id=row["host_id"],
        )
        s.invited = list(map(int, game.get("invited", [])))  # <— NEU
        s.status = g["status"]
        s.lobby_open = bool(g.get("lobby_open", True))
        s.players = list(map(int, g["players"]))
        s.draw_pile = g["draw_pile"]
        s.discard_pile = g["discard_pile"]
        s.top_card = g["top_card"]
        s.forced_color = g["forced_color"]
        s.direction = int(g["direction"])
        s.turn_index = int(g["turn_index"])
        s.draw_stack = int(g["draw_stack"])
        s.last_turn_at = float(g.get("last_turn_at", 0))
        s.lobby_message_id = g.get("lobby_message_id")
        s.table_message_id = g.get("table_message_id")
        s.host_id = g.get("host_id", row["host_id"])
        s.hands = {int(uid): data["hand"] for uid, data in p.items()}
        s.uno_called = {int(uid): bool(data.get("uno", False)) for uid, data in p.items()}
        return s

    def current_uid(self) -> int:
        return self.players[self.turn_index % len(self.players)]

    def ensure_draw(self):
        if not self.draw_pile:
            keep = self.discard_pile[-1] if self.discard_pile else {"color": "ANY", "value": "wild"}
            pool = self.discard_pile[:-1]
            random.shuffle(pool)
            self.draw_pile = pool
            self.discard_pile = [keep]

    def draw(self, uid: int, n: int) -> List[Dict]:
        out = []
        for _ in range(n):
            self.ensure_draw()
            out.append(self.draw_pile.pop())
        self.hands.setdefault(uid, []).extend(out)
        return out

    def valid_moves(self, uid: int) -> List[Tuple[int, Dict]]:
        return [(i, c) for i, c in enumerate(self.hands.get(uid, [])) if is_playable(c, self.top_card, self.forced_color)]

    def next_turn(self, steps: int = 1):
        self.turn_index = (self.turn_index + steps * self.direction) % len(self.players)
        self.last_turn_at = datetime.now(timezone.utc).timestamp()

    def deal(self):
        for uid in self.players:
            self.hands[uid] = [self.draw_pile.pop() for _ in range(7)]
            self.uno_called[uid] = False
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
        if len(self.hands[uid]) > 1:
            self.uno_called[uid] = False
        if card["color"] == "ANY":
            self.forced_color = chosen_color or random.choice(COLORS)
            if card["value"] == "wild":
                return "wild"
            else:
                self.draw_stack += 4
                return "+4"
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

class LobbyView(discord.ui.View):
    def __init__(self, cog: "UnoCog", gid: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.gid = gid

    @discord.ui.button(label="Beitreten", style=discord.ButtonStyle.success, custom_id="uno:lobby:join")
    async def join(self, it: discord.Interaction, _): await self.cog.ui_lobby_join(it, self.gid)

    @discord.ui.button(label="Verlassen", style=discord.ButtonStyle.secondary, custom_id="uno:lobby:leave")
    async def leave(self, it: discord.Interaction, _): await self.cog.ui_lobby_leave(it, self.gid)

    @discord.ui.button(label="Öffnen/Schließen", style=discord.ButtonStyle.blurple, custom_id="uno:lobby:toggle")
    async def toggle(self, it: discord.Interaction, _): await self.cog.ui_lobby_toggle(it, self.gid)

    @discord.ui.button(label="Start (Host)", style=discord.ButtonStyle.primary, custom_id="uno:lobby:start")
    async def start(self, it: discord.Interaction, _): await self.cog.ui_lobby_start(it, self.gid)

    @discord.ui.button(label="Abbrechen (Host)", style=discord.ButtonStyle.danger, custom_id="uno:lobby:cancel")
    async def cancel(self, it: discord.Interaction, _): await self.cog.ui_lobby_cancel(it, self.gid)

class TableView(discord.ui.View):
    def __init__(self, cog: "UnoCog", gid: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.gid = gid

    @discord.ui.button(label="Hand öffnen", style=discord.ButtonStyle.primary, custom_id="uno:table:hand")
    async def hand(self, it: discord.Interaction, _): await self.cog.ui_open_hand(it, self.gid)

    @discord.ui.button(label="Ziehen", style=discord.ButtonStyle.secondary, custom_id="uno:table:draw")
    async def draw(self, it: discord.Interaction, _): await self.cog.ui_draw(it, self.gid)

    @discord.ui.button(label="UNO!", style=discord.ButtonStyle.success, custom_id="uno:table:uno")
    async def uno(self, it: discord.Interaction, _): await self.cog.ui_uno(it, self.gid)

class PlayButton(discord.ui.Button):
    def __init__(self, gid: int, idx: int, label_txt: str, color_hint: str = "0"):
        cid = f"uno:play:{gid}:{idx}:{color_hint}"
        super().__init__(style=discord.ButtonStyle.primary, label=label_txt, custom_id=cid)
        self.gid = gid
        self.idx = idx
        self.color_hint = color_hint
    async def callback(self, it: discord.Interaction):
        await self.view.cog.ui_play_card(it, self.gid, self.idx, None if self.color_hint == "0" else self.color_hint)  # type: ignore

class HandView(discord.ui.View):
    def __init__(self, cog: "UnoCog", st: UnoState, uid: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.st = st
        self.uid = uid
        playable = st.valid_moves(uid)
        added = 0
        for idx, c in playable:
            if c["color"] == "ANY":
                for col in COLORS:
                    self.add_item(PlayButton(st.game_id, idx, f"{EMO_COLOR['ANY']} {EMO_VAL[c['value']]} → {EMO_COLOR[col]}", col))
                    added += 1
            else:
                self.add_item(PlayButton(st.game_id, idx, lab(c)))
                added += 1
            if added >= 20:
                break

@app_commands.guild_only()
class Uno(app_commands.Group):
    def __init__(self, cog: "UnoCog"):
        super().__init__(name="uno", description="UNO Light mit Lobby, Tisch und PvP")
        self.cog = cog

    @app_commands.command(name="start", description="Erstellt eine UNO-Lobby in diesem Kanal.")
    @app_commands.describe(privat="Wenn wahr, nur mit Einladung beitretbar.")
    async def start(self, it: discord.Interaction, privat: Optional[bool] = False):
        await self.cog.cmd_start_lobby(it, bool(privat))

    @app_commands.command(name="einladen", description="Lädt einen Nutzer in die Lobby ein.")
    async def invite(self, it: discord.Interaction, user: discord.User):
        await self.cog.cmd_invite(it, user)

    @app_commands.command(name="beitreten", description="Der letzten Lobby in diesem Kanal beitreten.")
    async def join(self, it: discord.Interaction):
        await self.cog.cmd_join(it)

    @app_commands.command(name="verlassen", description="Lobby verlassen.")
    async def leave(self, it: discord.Interaction):
        await self.cog.cmd_leave(it)

    @app_commands.command(name="status", description="Zeigt Status von Lobby oder Spiel.")
    async def status(self, it: discord.Interaction):
        await self.cog.cmd_status(it)

class UnoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        if not hasattr(bot, "pool") or not isinstance(bot.pool, aiomysql.Pool):
            raise RuntimeError("aiomysql-Pool fehlt in bot.pool")
        self.bot = bot
        self.pool: aiomysql.Pool = bot.pool
        self.locks: Dict[int, asyncio.Lock] = {}

    def lock_for(self, gid: int) -> asyncio.Lock:
        if gid not in self.locks:
            self.locks[gid] = asyncio.Lock()
        return self.locks[gid]

    async def cog_load(self):
        await self.ensure_tables()
        await self._recover_views()
        self.maintain_games.start()
        try:
            self.bot.tree.add_command(Uno(self))
        except Exception:
            pass

    async def cog_unload(self):
        self.maintain_games.cancel()

    async def ensure_tables(self):
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DROP TABLE uno_games;")
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS uno_games (
              game_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              guild_id BIGINT NOT NULL,
              channel_id BIGINT NOT NULL,
              host_id BIGINT NOT NULL,
              status ENUM('lobby','active','ended','cancelled') NOT NULL DEFAULT 'lobby',
              lobby_open TINYINT(1) NOT NULL DEFAULT 1,
              game_json JSON NOT NULL,
              players_json JSON NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              KEY idx_guild_channel (guild_id, channel_id),
              KEY idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
            await conn.commit()

    async def _insert_game(self, st: UnoState) -> int:
        gj, pj = st.to_json()
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("""
            INSERT INTO uno_games (guild_id, channel_id, host_id, status, lobby_open, game_json, players_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (st.guild_id, st.channel_id, st.host_id, st.status, 1 if st.lobby_open else 0, gj, pj))
            gid = cur.lastrowid
            await conn.commit()
        return int(gid)

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

    async def _fetch_active(self, guild_id: int, channel_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM uno_games
                 WHERE guild_id=%s AND channel_id=%s AND status='active'
                 ORDER BY updated_at DESC LIMIT 1
            """, (guild_id, channel_id))
            return await cur.fetchone()

    async def _save(self, st: UnoState):
        gj, pj = st.to_json()
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("""
                UPDATE uno_games
                   SET status=%s,
                       lobby_open=%s,
                       game_json=%s,
                       players_json=%s
                 WHERE game_id=%s
            """, (st.status, 1 if st.lobby_open else 0, gj, pj, st.game_id))
            await conn.commit()

    async def _recover_views(self):
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM uno_games WHERE status IN ('lobby','active')")
            rows = await cur.fetchall()
        for r in rows or []:
            st = UnoState.from_row(r)
            ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
            if st.status == "lobby":
                try:
                    msg = await ch.history(limit=50).find(lambda m: m.id == (st.lobby_message_id or 0))  # type: ignore
                except Exception:
                    msg = None
                if st.lobby_message_id:
                    try:
                        m = await ch.fetch_message(st.lobby_message_id)
                        await m.edit(view=LobbyView(self, st.game_id), embed=self.emb_lobby(st))
                    except Exception:
                        pass
            if st.status == "active":
                if st.table_message_id:
                    try:
                        m = await ch.fetch_message(st.table_message_id)
                        await m.edit(view=TableView(self, st.game_id), embed=self.emb_table(st))
                    except Exception:
                        pass

    def emb_lobby(self, st: UnoState) -> discord.Embed:
        e = discord.Embed(
            title=f"UNO Lobby #{st.game_id}",
            description=("🎨 Lobby ist **offen**" if st.lobby_open else "🎨 Lobby ist **geschlossen** (nur Einladung)"),
            color=ASTRA_COLOR,
        )
        e.add_field(name="Host", value=f"<@{st.host_id}>", inline=True)
        e.add_field(name="Spieler (2–6)", value="\n".join(f"<@{u}>" for u in st.players) or "—", inline=True)
        if st.invited:
            e.add_field(name="Eingeladen", value=", ".join(f"<@{u}>" for u in st.invited), inline=False)  # <— NEU
        e.set_footer(text="Host: Öffnen/Schließen • Start • Abbrechen")
        return e

    def emb_table(self, st: UnoState) -> discord.Embed:
        turn = st.current_uid()
        dir_txt = EMO_DIR[st.direction]
        top = lab(st.top_card)
        if st.forced_color:
            top += f" → {EMO_COLOR[st.forced_color]}"
        counts = []
        for u in st.players:
            mark = "🟢" if u == turn else "⚪"
            uno = " (UNO)" if len(st.hands.get(u, [])) == 1 else ""
            counts.append(f"{mark} <@{u}> ({len(st.hands.get(u, []))}){uno}")
        desc = "\n".join(counts)
        e = discord.Embed(title=f"UNO – Spiel #{st.game_id}", color=ASTRA, description=desc)
        e.add_field(name="Zug", value=f"<@{turn}> {dir_txt}", inline=True)
        e.add_field(name="Oberste Karte", value=top, inline=True)
        if st.draw_stack:
            e.add_field(name="Zieh-Stapel", value=f"+{st.draw_stack}", inline=True)
        e.set_footer(text="Hand öffnen, wenn du dran bist • Ziehen, falls nötig • UNO! bei 1 Karte")
        return e

    async def cmd_start_lobby(self, it: discord.Interaction, privat: bool):
        if await self._fetch_open_lobby(it.guild_id, it.channel_id):
            return await it.response.send_message("❌ Hier läuft bereits eine Lobby.", ephemeral=True)
        st = UnoState(game_id=0, guild_id=it.guild_id, channel_id=it.channel_id, host_id=it.user.id, lobby_open=not privat, status="lobby")
        st.players = [it.user.id]
        st.game_id = await self._insert_game(st)
        await it.response.send_message(embed=self.emb_lobby(st), view=LobbyView(self, st.game_id))
        msg = await it.original_response()
        st.lobby_message_id = msg.id
        await self._save(st)

    async def cmd_invite(self, it: discord.Interaction, user: discord.User):
        row = await self._fetch_open_lobby(it.guild_id, it.channel_id)
        if not row:
            return await it.response.send_message("❌ Keine Lobby gefunden.", ephemeral=True)
        st = UnoState.from_row(row)
        if it.user.id != st.host_id:
            return await it.response.send_message("❌ Nur der Host kann einladen.", ephemeral=True)

        # DM schicken (wie gehabt) ...
        try:
            e = discord.Embed(
                title=f"UNO-Einladung #{st.game_id}",
                description=f"<@{st.host_id}> lädt dich ein.\nKanal: <#{st.channel_id}>",
                color=ASTRA_COLOR,
            )
            e.add_field(name="Beitreten", value="Nutze `/uno beitreten` im Kanal der Lobby.")
            await user.send(embed=e)
        except Exception:
            pass  # DM kann fehlschlagen, Einladung gilt trotzdem

        if user.id not in st.invited:
            st.invited.append(user.id)  # <— Eintrag merken
            await self._save_state(st)

        await it.response.send_message("✅ Einladung hinterlegt.", ephemeral=True)
        return None

    async def cmd_join(self, it: discord.Interaction):
        row = await self._fetch_open_lobby(it.guild_id, it.channel_id)
        if not row:
            return await it.response.send_message("❌ Keine offene Lobby hier.", ephemeral=True)
        await self.ui_lobby_join(it, row["game_id"])

    async def cmd_leave(self, it: discord.Interaction):
        row = await self._fetch_open_lobby(it.guild_id, it.channel_id)
        if not row:
            return await it.response.send_message("❌ Keine offene Lobby hier.", ephemeral=True)
        await self.ui_lobby_leave(it, row["game_id"])

    async def cmd_status(self, it: discord.Interaction):
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM uno_games
                 WHERE guild_id=%s AND channel_id=%s
                   AND status IN ('lobby','active')
                 ORDER BY updated_at DESC LIMIT 1
            """, (it.guild_id, it.channel_id))
            row = await cur.fetchone()
        if not row:
            return await it.response.send_message("ℹ️ Kein aktives UNO hier.", ephemeral=True)
        st = UnoState.from_row(row)
        emb = self.emb_lobby(st) if st.status == "lobby" else self.emb_table(st)
        view = LobbyView(self, st.game_id) if st.status == "lobby" else TableView(self, st.game_id)
        await it.response.send_message(embed=emb, view=view, ephemeral=True)

    async def ui_lobby_join(self, it: discord.Interaction, game_id: int):
        row = await self._fetch_row(game_id)
        if not row or row["status"] != "lobby":
            return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
        st = UnoState.from_row(row)

        # <— HIER: Join-Regel anpassen
        invited_ok = it.user.id in st.invited
        if not st.lobby_open and it.user.id != st.host_id and not invited_ok:
            return await it.response.send_message("❌ Lobby ist geschlossen. Nur auf Einladung.", ephemeral=True)

        if it.user.id in st.players:
            return await it.response.send_message("Du bist bereits in der Lobby.", ephemeral=True)
        if len(st.players) >= MAX_PLAYERS:
            return await it.response.send_message("❌ Lobby ist voll.", ephemeral=True)

        st.players.append(it.user.id)
        if invited_ok:
            try:
                st.invited.remove(it.user.id)  # Einladung verbrauchen
            except ValueError:
                pass
        await self._save_state(st)
        await self._edit_lobby_message(st)
        await it.response.send_message("✅ Beigetreten.", ephemeral=True)

    async def ui_lobby_leave(self, it: discord.Interaction, game_id: int):
        async with self.lock_for(game_id):
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
                    st.host_id = st.players[0]
            await self._save(st)
            await self._edit_lobby(st)
            await it.response.send_message("✅ Verlassen.", ephemeral=True)

    async def ui_lobby_toggle(self, it: discord.Interaction, game_id: int):
        async with self.lock_for(game_id):
            row = await self._fetch_row(game_id)
            if not row or row["status"] != "lobby":
                return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
            st = UnoState.from_row(row)
            if it.user.id != st.host_id:
                return await it.response.send_message("❌ Nur der Host kann das.", ephemeral=True)
            st.lobby_open = not st.lobby_open
            await self._save(st)
            await self._edit_lobby(st)
            await it.response.send_message(f"✅ Lobby ist jetzt {'offen' if st.lobby_open else 'geschlossen'}.", ephemeral=True)

    async def ui_lobby_start(self, it: discord.Interaction, game_id: int):
        async with self.lock_for(game_id):
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
            await self._save(st)
            await self._edit_lobby(st, disable=True)
            ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
            msg = await ch.send(embed=self.emb_table(st), view=TableView(self, st.game_id))
            st.table_message_id = msg.id
            await self._save(st)
            await it.response.send_message("🎮 Spiel gestartet!", ephemeral=True)

    async def ui_lobby_cancel(self, it: discord.Interaction, game_id: int):
        async with self.lock_for(game_id):
            row = await self._fetch_row(game_id)
            if not row or row["status"] != "lobby":
                return await it.response.send_message("❌ Lobby existiert nicht mehr.", ephemeral=True)
            st = UnoState.from_row(row)
            if it.user.id != st.host_id:
                return await it.response.send_message("❌ Nur der Host kann abbrechen.", ephemeral=True)
            st.status = "cancelled"
            await self._save(st)
            await self._edit_lobby(st, disable=True)
            await it.response.send_message("❎ Lobby abgebrochen.", ephemeral=True)

    async def _edit_lobby(self, st: UnoState, disable: bool = False):
        if not st.lobby_message_id:
            return
        ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
        try:
            v = None if disable else LobbyView(self, st.game_id)
            m = await ch.fetch_message(st.lobby_message_id)
            await m.edit(embed=self.emb_lobby(st), view=v)
        except Exception:
            pass

    async def ui_open_hand(self, it: discord.Interaction, game_id: int):
        async with self.lock_for(game_id):
            row = await self._fetch_row(game_id)
            if not row or row["status"] != "active":
                return await it.response.send_message("❌ Spiel existiert nicht mehr.", ephemeral=True)
            st = UnoState.from_row(row)
            if it.user.id != st.current_uid():
                return await it.response.send_message("⏳ Du bist nicht am Zug.", ephemeral=True)
            hv = HandView(self, st, it.user.id)
            hand = st.hands.get(it.user.id, [])
            if not hand:
                return await it.response.send_message("Du hast keine Karten.", ephemeral=True)
            lines = [f"{i+1}. {lab(c)}" for i, c in enumerate(hand)]
            await it.response.send_message("Deine Hand:\n" + "\n".join(lines), view=hv, ephemeral=True)

    async def ui_draw(self, it: discord.Interaction, game_id: int):
        async with self.lock_for(game_id):
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
            await self._save(st)
            await self._refresh_table(st)
            await it.response.send_message(f"🃏 Du hast {n} Karte(n) gezogen.", ephemeral=True)

    async def ui_uno(self, it: discord.Interaction, game_id: int):
        async with self.lock_for(game_id):
            row = await self._fetch_row(game_id)
            if not row or row["status"] != "active":
                return await it.response.send_message("❌ Spiel existiert nicht mehr.", ephemeral=True)
            st = UnoState.from_row(row)
            if len(st.hands.get(it.user.id, [])) == 1:
                st.uno_called[it.user.id] = True
                await self._save(st)
                return await it.response.send_message("✅ UNO gerufen!", ephemeral=True)
            return await it.response.send_message("ℹ️ Du hast nicht genau 1 Karte.", ephemeral=True)

    async def ui_play_card(self, it: discord.Interaction, game_id: int, hand_index: int, chosen_color: Optional[str]):
        async with self.lock_for(game_id):
            row = await self._fetch_row(game_id)
            if not row or row["status"] != "active":
                return await it.response.send_message("❌ Spiel existiert nicht mehr.", ephemeral=True)
            st = UnoState.from_row(row)
            uid = it.user.id
            if uid != st.current_uid():
                return await it.response.send_message("⏳ Du bist nicht am Zug.", ephemeral=True)
            if hand_index < 0 or hand_index >= len(st.hands.get(uid, [])):
                return await it.response.send_message("❌ Ungültige Karte.", ephemeral=True)
            card = st.hands[uid][hand_index]
            if not is_playable(card, st.top_card, st.forced_color):
                return await it.response.send_message("❌ Diese Karte passt nicht.", ephemeral=True)
            if card["color"] == "ANY" and (chosen_color not in COLORS):
                return await it.response.send_message("❌ Wähle eine Zielfarbe.", ephemeral=True)
            effect = st.play(uid, hand_index, chosen_color)
            note = None
            if len(st.hands[uid]) == 1 and not st.uno_called.get(uid, False):
                st.draw(uid, UNO_PENALTY)
                note = f"⚠️ UNO nicht gerufen: +{UNO_PENALTY}"
            if len(st.hands[uid]) == 0:
                st.status = "ended"
                await self._save(st)
                await self._announce_end(st, uid)
                return await it.response.send_message("🎉 Karte gelegt – du hast gewonnen!", ephemeral=True)
            step = 1
            if effect == "reverse":
                if len(st.players) == 2:
                    step = 2
            if effect == "skip":
                step = 2
            st.next_turn(step)
            st.uno_called[uid] = False
            await self._save(st)
            await self._refresh_table(st)
            txt = f"✅ {lab(card)} gelegt."
            if st.forced_color and card["color"] == "ANY":
                txt += f" Farbe gesetzt auf {EMO_COLOR[st.forced_color]}"
            if note:
                txt += f"\n{note}"
            await it.response.send_message(txt, ephemeral=True)

    async def _refresh_table(self, st: UnoState):
        if not st.table_message_id:
            return
        ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
        try:
            m = await ch.fetch_message(st.table_message_id)
            await m.edit(embed=self.emb_table(st), view=TableView(self, st.game_id))
        except Exception:
            pass

    async def _announce_end(self, st: UnoState, winner_id: int):
        if not st.table_message_id:
            return
        ch = self.bot.get_channel(st.channel_id) or await self.bot.fetch_channel(st.channel_id)
        try:
            m = await ch.fetch_message(st.table_message_id)
            e = discord.Embed(title=f"UNO – Spiel #{st.game_id} beendet", description=f"🏆 Gewinner: <@{winner_id}>", color=UNO_GOLD)
            await m.edit(embed=e, view=None)
        except Exception:
            pass

    @tasks.loop(seconds=10)
    async def maintain_games(self):
        async with self.pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM uno_games WHERE status='active'")
            rows = await cur.fetchall()
        now = datetime.now(timezone.utc).timestamp()
        for r in rows or []:
            st = UnoState.from_row(r)
            if now - st.last_turn_at > TURN_TIMEOUT:
                async with self.lock_for(st.game_id):
                    row2 = await self._fetch_row(st.game_id)
                    if not row2 or row2["status"] != "active":
                        continue
                    st = UnoState.from_row(row2)
                    uid = st.current_uid()
                    n = st.draw_stack if st.draw_stack else 1
                    st.draw(uid, n)
                    st.draw_stack = 0
                    st.next_turn(1)
                    await self._save(st)
                    await self._refresh_table(st)

    @maintain_games.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(UnoCog(bot))
