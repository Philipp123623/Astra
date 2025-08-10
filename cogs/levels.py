import os
import json
from io import BytesIO
from typing import Literal
import random
import discord
from discord import app_commands, File
from discord.ext import commands
from PIL import Image, ImageDraw, ImageChops, ImageFont

# ──────────────────────────────────────────────────────────────────────────────
# Assets & Styles
# ──────────────────────────────────────────────────────────────────────────────
ASSETS_DIR = "cogs/assets/Levelcards"
DEFAULT_STYLE = "standard"  # entspricht standard.png

def list_styles():
    if not os.path.isdir(ASSETS_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(ASSETS_DIR)
        if f.lower().endswith(".png")
    )

def style_to_path(style_name: str) -> str:
    if not os.path.isdir(ASSETS_DIR):
        return os.path.join(ASSETS_DIR, f"{DEFAULT_STYLE}.png")
    for f in os.listdir(ASSETS_DIR):
        if f.lower().endswith(".png") and os.path.splitext(f)[0].lower() == style_name.lower():
            return os.path.join(ASSETS_DIR, f)
    return os.path.join(ASSETS_DIR, f"{DEFAULT_STYLE}.png")

# ──────────────────────────────────────────────────────────────────────────────
# Layout-Gruppen + Skalierung
# ──────────────────────────────────────────────────────────────────────────────
def _layout_key_for_style(style: str) -> str:
    s = (style or "").lower()
    if s in ("levelcard_astra", "standard"):   # blaue Standardkarte
        return "standard"
    return "new"                               # alle anderen = neue Karten

BASE_BY_GROUP = {
    "new": (1075, 340),       # neue Karten (türkis)
    "standard": (1064, 339),  # Standardkarte (blau)
}

def _deepcopy(obj):
    import json as _json
    return _json.loads(_json.dumps(obj))

def _merge_overrides(base: dict, ovr: dict | None) -> dict:
    res = _deepcopy(base)
    for k, v in (ovr or {}).items():
        if isinstance(v, dict) and isinstance(res.get(k), dict):
            res[k].update(v)
        else:
            res[k] = v
    return res

def _scale_layout(layout: dict, dst_w: int, dst_h: int, base_w: int, base_h: int) -> dict:
    sx = dst_w / float(base_w)
    sy = dst_h / float(base_h)
    sfont = (sx + sy) / 2.0
    def sc(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if isinstance(v, dict):
                out[k] = sc(v)
            elif k in ("x","w","size","border","pad_x","r","max_w","ring_width","inset"):
                out[k] = int(round(v * sx))
            elif k in ("y","h","pad_y"):
                out[k] = int(round(v * sy))
            elif k in ("font","min_font"):
                out[k] = max(8, int(round(v * sfont)))
            else:
                out[k] = v
        return out
    return sc(layout)

def _resolved_layout(style: str, img_w: int, img_h: int) -> dict:
    key = _layout_key_for_style(style)
    base = LAYOUTS[key]
    merged = _merge_overrides(base, STYLE_OVERRIDES.get(key))
    bw, bh = BASE_BY_GROUP[key]
    return _scale_layout(merged, img_w, img_h, bw, bh)

# ──────────────────────────────────────────────────────────────────────────────
# Progressbar-Farben
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_HEX = "#61BFC4"
BAR_COLORS = {
    "türkis_stripes":              "#C980E8",
    "Halloween_stripes":           "#61BFC4",
    "Christmas_stripes":           "#61BFC4",
    "Easter_stripes":              "#61BFC4",
    "standard_stripes_left_star":  "#61BFC4",
    "standard_stripes_right_star": "#61BFC4",
    "standard":                    "#61BFC4",
}
def bar_color_for(style: str) -> str:
    return BAR_COLORS.get(style, DEFAULT_HEX)

# ──────────────────────────────────────────────────────────────────────────────
# Pixelgenaue Layouts (Avatar/Text; Progressbar-Position nicht nötig für Füllung)
# ──────────────────────────────────────────────────────────────────────────────
LAYOUTS = {
    "new": {
        "avatar": {"x": 57, "y": 93, "size": 155, "inset": 8, "draw_ring": False, "ring_width": 0},
        "username": {"x": 246, "y": 95, "max_w": 600, "font": 34},
        "rank": {"x": 393, "y": 157, "font": 53},
        "level_center": {"x": 931, "y": 95, "font": 38, "min_font": 22, "max_w": 170},
        "xp_center": {"x": 931, "y": 223, "font": 30, "min_font": 18, "max_w": 230},
    },
    "standard": {
        "avatar": {"x": 64, "y": 98, "size": 142, "inset": 0, "draw_ring": True, "ring_width": 12},
        "username": {"x": 246, "y": 95, "max_w": 600, "font": 34},
        "rank": {"x": 393, "y": 157, "font": 53},
        "level_center": {"x": 931, "y": 95, "font": 38, "min_font": 22, "max_w": 170},
        "xp_center": {"x": 931, "y": 223, "font": 30, "min_font": 18, "max_w": 230},
    }
}

STYLE_OVERRIDES = {}
FONT_PATH = "cogs/fonts/Poppins-SemiBold.ttf"

# -------------------------------------------
# Pretty names -> interne Dateinamen (ohne .png)
# -------------------------------------------
PRETTY_TO_FILENAME = {
    "Standard": "standard",
    "Türkis Stripes": "türkis_stripes",
    "Halloween Stripes": "Halloween_stripes",
    "Christmas Stripes": "Christmas_stripes",
    "Easter Stripes": "Easter_stripes",
    "Standard Stripes Left Star": "standard_stripes_left_star",
    "Standard Stripes Right Star": "standard_stripes_right_star",
}
PRETTY_CHOICES = tuple(PRETTY_TO_FILENAME.keys())

# ──────────────────────────────────────────────────────────────────────────────
# Diskrete Progressbar-Geometrie (exakt nach deinen Koordinaten)
# ──────────────────────────────────────────────────────────────────────────────
PB_GEOM = {
    "standard": {  # 1064 x 339
        "left_cap": {
            214:(275,312), 213:(276,311), 212:(276,311), 211:(276,310),
            210:(278,309), 209:(279,308), 208:(281,306),
        },
        "right_cap": {
            881:(275,312), 882:(276,311), 883:(276,311), 884:(277,310),
            885:(278,309), 886:(279,308), 887:(281,306),
        },
        "y_full": (275, 312),     # inklusiv
        "x_span": (208, 887),     # inklusiv
    },
    "new": {       # 1075 x 340
        "left_cap": {
            220:(276,313), 219:(277,312), 218:(277,312), 217:(278,311),
            216:(279,310), 215:(280,309), 214:(282,307),
        },
        "right_cap": {
            887:(276,313), 888:(277,312), 889:(277,312), 890:(278,311),
            891:(279,310), 892:(280,309), 893:(282,307),
        },
        "y_full": (276, 313),
        "x_span": (214, 893),
    }
}

# Cache für Slot-Masken
_SLOT_MASK_CACHE: dict[tuple[str, tuple[int,int]], Image.Image] = {}

def _geom_key(img_w: int, img_h: int, style: str) -> str:
    # Entscheide robust: Stil oder Bildgröße
    if (img_w, img_h) == (1064, 339) or (style or "").lower() in ("standard", "levelcard_astra"):
        return "standard"
    return "new"

def _slot_mask_from_coords(img_w: int, img_h: int, layout_key: str) -> Image.Image:
    """
    Baut eine binäre L-Maske (255 innen, 0 außen) für die innere Progressbar
    EXAKT nach den Koordinatenlisten. Keine AA-Pixel.
    """
    cache_key = (layout_key, (img_w, img_h))
    if cache_key in _SLOT_MASK_CACHE:
        return _SLOT_MASK_CACHE[cache_key]

    geom = PB_GEOM[layout_key]
    x0, x1 = geom["x_span"]
    y0, y1 = geom["y_full"]           # inklusiv
    left_cap  = geom["left_cap"]
    right_cap = geom["right_cap"]

    mask = Image.new("L", (img_w, img_h), 0)
    d = ImageDraw.Draw(mask)

    # Mittelteil: volle Höhe zwischen Kappen
    mid_x0 = max(x0, max(left_cap.keys()) + 1)
    mid_x1 = min(x1, min(right_cap.keys()) - 1)
    if mid_x1 >= mid_x0:
        d.rectangle((mid_x0, y0, mid_x1, y1), fill=255)

    # Linke Kappe: spaltenweise
    for x, (yt, yb) in left_cap.items():
        d.line((x, yt, x, yb), fill=255)

    # Rechte Kappe: spaltenweise
    for x, (yt, yb) in right_cap.items():
        d.line((x, yt, x, yb), fill=255)

    _SLOT_MASK_CACHE[cache_key] = mask
    return mask

# ──────────────────────────────────────────────────────────────────────────────
# Render-Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _mk_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size=max(8, int(size)))

def _center_text(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                 text: str, font: ImageFont.FreeTypeFont, fill: str):
    w = draw.textlength(text, font=font)
    bbox = font.getbbox(text)
    h = bbox[3] - bbox[1]
    draw.text((cx - w/2, cy - h/2), text, font=font, fill=fill)

def _truncate_to_width(draw, text: str, font, max_px: int) -> str:
    if draw.textlength(text, font=font) <= max_px:
        return text
    ell = "…"
    while text and draw.textlength(text + ell, font=font) > max_px:
        text = text[:-1]
    return text + ell

def _draw_progressbar(background: Image.Image, lay: dict,
                      xp_start: int | float, xp_end: int | float,
                      style_key: str):
    """
    Pixelgenau:
    - Slot-Maske wird exakt aus deinen Koordinaten aufgebaut (keine Rundungen/AA).
    - Füllmaske = Slot ∩ (x0..x_fill_end, y0..y1).
    """
    perc = 0.0 if xp_end <= 0 else max(0.0, min(1.0, float(xp_start) / float(xp_end)))
    if perc <= 0.0:
        return

    img_w, img_h = background.size
    geom_key = _geom_key(img_w, img_h, style_key)
    geom = PB_GEOM[geom_key]

    x0, x1 = geom["x_span"]
    y0, y1 = geom["y_full"]

    total_w = x1 - x0 + 1
    fill_w  = max(1, min(int(round(total_w * perc)), total_w))
    x_fill_end = x0 + fill_w - 1

    # 1) Slot (komplette Schiene)
    slot_mask = _slot_mask_from_coords(img_w, img_h, geom_key)

    # 2) Füllmaske = Slot ∩ Begrenzungsrect
    fill_mask = Image.new("L", (img_w, img_h), 0)
    d = ImageDraw.Draw(fill_mask)
    d.rectangle((x0, y0, x_fill_end, y1), fill=255)
    fill_mask = ImageChops.multiply(slot_mask, fill_mask)

    # 3) Einfärben
    fill_img = Image.new("RGBA", (img_w, img_h), bar_color_for(style_key))
    background.paste(fill_img, (0, 0), fill_mask)

# ──────────────────────────────────────────────────────────────────────────────
# Slash-Gruppe nur für Levelkarten
# ──────────────────────────────────────────────────────────────────────────────
class Level(app_commands.Group):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(name="levelsystem", description="Alles rund ums Levelsystem.")

    # Autocomplete (optional nutzbar)
    async def _style_autocomplete(self, interaction: discord.Interaction, current: str):
        names = list_styles()
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    # /rank
    @app_commands.command(name="rank", description="Sendet deine Levelcard.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.guild_only()
    async def rank(self, interaction: discord.Interaction, user: discord.User | None = None):
        user = user or interaction.user

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT enabled FROM levelsystem WHERE guild_id=%s", (interaction.guild.id,))
                enabled = await cur.fetchone()
                if not enabled or enabled[0] == 0:
                    return await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server deaktiviert.**",
                        ephemeral=True
                    )

                await cur.execute(
                    "SELECT user_xp, user_level FROM levelsystem WHERE client_id=%s AND guild_id=%s",
                    (user.id, interaction.guild.id)
                )
                row = await cur.fetchone()
                if not row:
                    return await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Keine Einträge für diesen User gefunden.**",
                        ephemeral=True
                    )
                xp_start, lvl_start = row
                xp_end = 5.5 * (lvl_start ** 2) + 30 * lvl_start

                await cur.execute(
                    "SELECT style FROM levelstyle WHERE guild_id=%s AND client_id=%s",
                    (interaction.guild.id, user.id)
                )
                srow = await cur.fetchone()
                style_name = srow[0] if srow else DEFAULT_STYLE
                bg_path = style_to_path(style_name)

                await cur.execute(
                    "SELECT client_id FROM levelsystem WHERE guild_id=%s ORDER BY user_level DESC, user_xp DESC",
                    (interaction.guild.id,)
                )
                rows = await cur.fetchall()
                rank_pos = 0
                if rows:
                    for i, r in enumerate(rows, start=1):
                        if int(r[0]) == user.id:
                            rank_pos = i
                            break

        await interaction.response.defer(thinking=True)

        # Render
        background = Image.open(bg_path).convert("RGBA")
        draw = ImageDraw.Draw(background)
        img_w, img_h = background.size
        lay = _resolved_layout(style_name, img_w, img_h)

        # -------- Avatar --------
        av = lay["avatar"]
        av_size = av["size"]
        av_x, av_y = av["x"], av["y"]

        avatar_asset = user.display_avatar.replace(size=256)
        avatar_bytes = await avatar_asset.read()
        avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((av_size, av_size))

        inset = av.get("inset", 0)
        if av.get("draw_ring", False):
            ring_w = av.get("ring_width", 10)
            draw.ellipse((av_x, av_y, av_x + av_size, av_y + av_size), outline="white", width=ring_w)
            inset = max(inset, ring_w)

        inner_d = (av_size - 2 * inset, av_size - 2 * inset)
        mask = Image.new("L", inner_d, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, inner_d[0], inner_d[1]), fill=255)
        avatar_cropped = avatar_img.resize(inner_d)
        background.paste(avatar_cropped, (av_x + inset, av_y + inset), mask)

        # -------- Username & Rang --------
        font_username = _mk_font(lay["username"]["font"])
        font_rank = _mk_font(lay["rank"]["font"])

        ux, uy = lay["username"]["x"], lay["username"]["y"]
        uname = _truncate_to_width(draw, str(user), font_username, lay["username"]["max_w"])
        draw.text((ux, uy), uname, font=font_username, fill="white")

        rx, ry = lay["rank"]["x"], lay["rank"]["y"]
        draw.text((rx, ry), f"#{rank_pos}", font=font_rank, fill="white")

        # -------- Level & XP (mittig + Auto-Fit) --------
        def _fit_center_text(draw, cx, cy, text, base_size, min_size, max_w):
            size = base_size
            font = _mk_font(size)
            while draw.textlength(text, font=font) > max_w and size > min_size:
                size -= 1
                font = _mk_font(size)
            _center_text(draw, cx, cy, text, font, "white")

        lev_cfg = lay["level_center"]
        xp_cfg = lay["xp_center"]
        _fit_center_text(draw, lev_cfg["x"], lev_cfg["y"], f"{lvl_start}",
                         lev_cfg["font"], lev_cfg.get("min_font", 16), lev_cfg.get("max_w", 170))
        _fit_center_text(draw, xp_cfg["x"], xp_cfg["y"], f"{xp_start}/{round(xp_end)}",
                         xp_cfg["font"], xp_cfg.get("min_font", 16), xp_cfg.get("max_w", 230))

        # -------- Progressbar (pixelgenau) --------
        _draw_progressbar(background, lay, xp_start, xp_end, style_name)

        buf = BytesIO()
        background.save(buf, "PNG")
        buf.seek(0)
        await interaction.followup.send(file=File(buf, filename=f"rank_{style_name}.png"))

    # /setstyle
    @app_commands.command(name="setstyle", description="Wähle deine Rank-Card.")
    @app_commands.describe(style="Style-Name")
    @app_commands.guild_only()
    async def setstyle(
            self,
            interaction: discord.Interaction,
            style: Literal[PRETTY_CHOICES],  # zeigt hübsche Namen ohne Unterstriche
    ):
        internal_style = PRETTY_TO_FILENAME[style]  # map auf Dateiname

        available = set(list_styles())
        if internal_style not in available:
            return await interaction.response.send_message(
                f"❌ Der Style **{style}** ist (noch) nicht verfügbar.", ephemeral=True
            )

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS levelstyle
                    (
                        guild_id  BIGINT      NOT NULL,
                        client_id BIGINT      NOT NULL,
                        style     VARCHAR(64) NOT NULL,
                        PRIMARY KEY (guild_id, client_id)
                    )
                    """
                )
                await cur.execute(
                    """
                    INSERT INTO levelstyle (guild_id, client_id, style)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE style = VALUES(style)
                    """,
                    (interaction.guild.id, interaction.user.id, internal_style)
                )

        await interaction.response.send_message(f"✅ Style auf **{style}** gesetzt.", ephemeral=True)

    # /previewstyle
    @app_commands.command(name="previewstyle", description="Preview deiner Rank-Card (ohne zu speichern).")
    @app_commands.describe(style="Style-Name")
    @app_commands.guild_only()
    async def previewstyle(
            self,
            interaction: discord.Interaction,
            style: Literal[PRETTY_CHOICES],
    ):
        internal_style = PRETTY_TO_FILENAME[style]

        if internal_style not in set(list_styles()):
            return await interaction.response.send_message(
                f"❌ Der Style **{style}** ist (noch) nicht verfügbar.", ephemeral=True
            )

        await interaction.response.defer(thinking=True, ephemeral=True)
        bg_path = style_to_path(internal_style)

        # Daten für echte Vorschau
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT user_xp, user_level FROM levelsystem WHERE client_id=%s AND guild_id=%s",
                    (interaction.user.id, interaction.guild.id)
                )
                row = await cur.fetchone()
                xp_start, lvl_start = row if row else (0, 0)
                xp_end = 5.5 * (lvl_start ** 2) + 30 * lvl_start

                await cur.execute(
                    "SELECT client_id FROM levelsystem WHERE guild_id=%s ORDER BY user_level DESC, user_xp DESC",
                    (interaction.guild.id,)
                )
                rows = await cur.fetchall()
                rank_pos = 0
                if rows:
                    for i, r in enumerate(rows, start=1):
                        if int(r[0]) == interaction.user.id:
                            rank_pos = i
                            break

        # Render
        background = Image.open(bg_path).convert("RGBA")
        draw = ImageDraw.Draw(background)
        img_w, img_h = background.size
        lay = _resolved_layout(internal_style, img_w, img_h)

        # Avatar
        av = lay["avatar"]
        av_size = av["size"]
        av_x, av_y = av["x"], av["y"]

        avatar_asset = interaction.user.display_avatar.replace(size=256)
        avatar_bytes = await avatar_asset.read()
        avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((av_size, av_size))

        inset = av.get("inset", 0)
        if av.get("draw_ring", False):
            ring_w = av.get("ring_width", 10)
            draw.ellipse((av_x, av_y, av_x + av_size, av_y + av_size), outline="white", width=ring_w)
            inset = max(inset, ring_w)

        inner_d = (av_size - 2 * inset, av_size - 2 * inset)
        mask = Image.new("L", inner_d, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, inner_d[0], inner_d[1]), fill=255)
        avatar_cropped = avatar_img.resize(inner_d)
        background.paste(avatar_cropped, (av_x + inset, av_y + inset), mask)

        # Username & Rang
        font_username = _mk_font(lay["username"]["font"])
        font_rank = _mk_font(lay["rank"]["font"])

        ux, uy = lay["username"]["x"], lay["username"]["y"]
        uname = _truncate_to_width(draw, str(interaction.user), font_username, lay["username"]["max_w"])
        draw.text((ux, uy), uname, font=font_username, fill="white")

        rx, ry = lay["rank"]["x"], lay["rank"]["y"]
        draw.text((rx, ry), f"#{rank_pos or '—'}", font=font_rank, fill="white")

        # Level & XP
        def _fit_center_text(draw, cx, cy, text, base_size, min_size, max_w):
            size = base_size
            font = _mk_font(size)
            while draw.textlength(text, font=font) > max_w and size > min_size:
                size -= 1
                font = _mk_font(size)
            _center_text(draw, cx, cy, text, font, "white")

        lev_cfg = lay["level_center"]
        xp_cfg = lay["xp_center"]
        _fit_center_text(draw, lev_cfg["x"], lev_cfg["y"], f"{lvl_start}",
                         lev_cfg["font"], lev_cfg.get("min_font", 16), lev_cfg.get("max_w", 170))
        _fit_center_text(draw, xp_cfg["x"], xp_cfg["y"], f"{xp_start}/{round(xp_end)}",
                         xp_cfg["font"], xp_cfg.get("min_font", 16), xp_cfg.get("max_w", 230))

        # Progressbar (exakt)
        _draw_progressbar(background, lay, xp_start, xp_end, internal_style)

        buf = BytesIO()
        background.save(buf, "PNG")
        buf.seek(0)
        await interaction.followup.send(
            content=f"**Preview:** `{style}`",
            file=File(buf, filename=f"preview_{internal_style}.png"),
            ephemeral=True
        )



    @app_commands.command(name="status")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction, arg: Literal['Einschalten', 'Ausschalten']):
        """Lege einen Kanal fest, in den die Level Up Nachrichten gesendet werden."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if arg == "Ausschalten":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                        return
                    if enabled[0] == 1:
                        await cur.execute(f"UPDATE levelsystem SET enabled = 0 WHERE guild_id = (%s)",
                                          (interaction.guild.id))
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> **Das Levelsystem ist jetzt auf diesem Server deaktiviert.**")
                        return
                if arg == "Einschalten":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await cur.execute(f"UPDATE levelsystem SET enabled = 1 WHERE guild_id = (%s)",
                                          (interaction.guild.id))
                        await interaction.response.send_message(
                            "<:Astra_accept:1141303821176422460> **Das Levelsystem ist jetzt auf diesem Server aktiviert.**")
                        return
                    if enabled[0] == 1:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                        return

    @app_commands.command(name="leaderboard", description="Zeigt das Top 10 Level und XP Leaderboard an.")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT client_id, user_level, user_xp FROM levelsystem WHERE guild_id = %s ORDER BY user_level DESC, user_xp DESC LIMIT 10",
                    (interaction.guild.id,)
                )
                top10 = await cur.fetchall()

        if not top10:
            return await interaction.response.send_message(
                "<:Astra_x:1141303954555289600> Es wurden keine Daten für dieses Server-Leaderboard gefunden.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"Top 10 Level Leaderboard für {interaction.guild.name}",
            color=discord.Color.blue()
        )

        description = ""
        place = 1
        for user_id, level, xp in top10:
            user = interaction.guild.get_member(user_id)
            name = user.display_name if user else f"User ID: {user_id}"
            description += f"**#{place}**: {name} — Level {level} ({xp} XP)\n"
            place += 1

        embed.description = description
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="levelupkanal")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def levelsystem_setchannel(self, interaction: discord.Interaction, arg: Literal[
        'Kanal des Levelups', 'Bestimmter Kanal(Kanalangabe benötigt)', 'Private Nachricht', 'Deaktivieren'],
                                     channel: discord.TextChannel = None):
        """Set a channel for your levelmessages."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                await cur.execute("SELECT type FROM levelchannel WHERE guildID = (%s)", (interaction.guild.id))
                result = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                        ephemeral=True)
                    return
                if enabled[0] == 1:
                    if arg == "Kanal des Levelups":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Last Channel"))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Last Channel", interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                    if arg == "Bestimmter Kanal(Kanalangabe benötigt)":
                        if not result:
                            try:
                                await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                                  (interaction.guild.id, channel.id))
                                await interaction.response.send_message(
                                    "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                            except:
                                await interaction.response.send_message(
                                    f"<:Astra_x:1141303954555289600> **Du musst einen Kanel angeben.**", ephemeral=True)
                                return
                        if result:
                            try:
                                await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                                  (channel.id, interaction.guild.id))
                                await interaction.response.send_message(
                                    "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                            except:
                                await interaction.response.send_message(
                                    f"<:Astra_x:1141303954555289600> **Du musst einen Kanal angeben.**", ephemeral=True)
                                return
                    if arg == "Private Nachricht":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Private Message"))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Private Message", interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich geändert.**")
                    if arg == "Deaktivieren":
                        if not result:
                            await cur.execute("INSERT INTO levelchannel(guildID, type) VALUES(%s, %s)",
                                              (interaction.guild.id, "Deactivated"))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Level-Up-Kanal wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelchannel SET type = (%s) WHERE guildID = (%s)",
                                              ("Deactivated", interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der Levelupkanal wurde erfolgreich zurückgesetzt.**")

    @app_commands.command(name="levelupnachricht")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def levelsystem_setmessage(self, interaction: discord.Interaction,
                                     arg: Literal['Custom Nachricht', 'Deaktivieren'], message: str = None):
        """Custom levelmessage: Use %level for the level and %member as member mention."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                        ephemeral=True)
                    return
                if enabled[0] == 1:
                    if arg == "Custom Nachricht":
                        await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await cur.execute("INSERT INTO levelmsg(message, guildID) VALUES(%s, %s)",
                                              (message, interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich geändert.**")
                        if result:
                            await cur.execute("UPDATE levelmsg SET message = (%s) WHERE guildID = (%s)",
                                              (message, interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich geändert.**")

                    if arg == "Deaktivieren":
                        await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich zurückgesetzt.**")
                            return
                        if result:
                            await cur.execute("DELETE FROM levelmsg WHERE guildID = (%s)", (interaction.guild.id))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Die Level-UP-Nachricht wurde erfolgreich zurückgesetzt.**")

    @app_commands.command(name="role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def levelsystem_role_add(self, interaction: discord.Interaction,
                                   modus: Literal['Hinzufügen', 'Entfernen', 'Anzeigen'], level: int,
                                   role: discord.Role):
        """Füge/Entferne Rollen die man ab dem jeweiligem Level bekommt."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if modus == "Hinzufügen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            "SELECT guildID FROM levelroles WHERE levelreq = (%s) and roleID = (%s) and guildID = (%s)",
                            (level, role.id, interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await cur.execute("INSERT INTO levelroles(guildID, roleID, levelreq) VALUES(%s, %s, %s)",
                                              (interaction.guild.id, role.id, level))
                            await interaction.response.send_message(
                                f"<:Astra_accept:1141303821176422460> **User bekommen nun die Rolle {role.mention} wenn sie Level `{level}` erreichen**")
                        if result:
                            roleid = result[0]
                            roleobj = interaction.guild.get_role(roleid)

                            await interaction.response.send_message(
                                f"<:Astra_x:1141303954555289600> **Die Rolle {roleobj.mention} ist bereits für dieses Level aktiv**.",
                                ephemeral=True)

                if modus == "Entfernen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        if enabled[0] == 0:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                                ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            "SELECT guildID FROM levelroles WHERE roleID = (%s) and levelreq = (%s) and guildID = (%s)",
                            (role.id, level, interaction.guild.id))
                        result = await cur.fetchone()
                        if not result:
                            await interaction.response.send_message(
                                f"<:Astra_x:1141303954555289600> **Es sind keine Rollen für das Level `{level}` aktiv.**",
                                ephemeral=True)
                        if result:
                            await cur.execute(
                                "DELETE FROM levelroles WHERE levelreq = (%s) and roleID = (%s) and guildID = (%s)",
                                (level, role.id, interaction.guild.id))

                            await interaction.response.send_message(
                                f"<:Astra_accept:1141303821176422460> **Rolle `{role.name}` von Level `{level}` entfernt.**")

                if modus == "Anzeigen":
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute("SELECT roleID, levelreq FROM levelroles WHERE guildID = (%s)",
                                          (interaction.guild.id))
                        result = await cur.fetchall()
                        if result == ():
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Es sind Keine Level-UP-Rollen aktiv.**",
                                ephemeral=True)
                        if result:
                            embed = discord.Embed(title="Aktive Level-UP-Rollen",
                                                  description=f"Um Rollen zu entfernen nutze `/levelsystem role`",
                                                  color=discord.Color.blue())
                            for x in result:
                                roleid = x[0]
                                level = x[1]
                                try:
                                    role = interaction.guild.get_role(int(roleid))
                                except:
                                    await interaction.response.send_message(
                                        "<:Astra_x:1141303954555289600> **Es sind Keine Level-UP-Rollen aktiv.**",
                                        ephemeral=True)

                                embed.add_field(name=f"Level: {level}", value=f"Rolle: {role.mention}", inline=True)
                            await interaction.response.send_message(embed=embed)


class levelsystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cd_mapping = commands.CooldownMapping.from_cooldown(1, 3, commands.BucketType.guild)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return
        if msg.author.bot:
            return
        else:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    bucket = self.cd_mapping.get_bucket(msg)
                    retry_after = bucket.update_rate_limit()
                    if retry_after:
                        return
                    else:
                        await cur.execute(
                            f"SELECT user_xp, user_level FROM levelsystem WHERE client_id = (%s) AND guild_id = (%s)",
                            (msg.author.id, msg.guild.id))
                        result = await cur.fetchall()

                        await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (msg.guild.id))
                        enabled = await cur.fetchone()
                        if len(result) == 0:
                            await cur.execute(
                                f"INSERT INTO levelsystem (client_id, user_xp, user_level, guild_id, enabled) VALUES (%s, %s, %s, %s, %s)",
                                (msg.author.id, 2, 0, msg.guild.id, 0))
                        else:
                            if enabled[0] == 0:
                                return
                            if enabled[0] == 1:
                                xp_start = int(result[0][0])
                                lvl_start = int(result[0][1])
                                xp_end = 5.5 * (lvl_start ** 2) + 30 * lvl_start
                                await cur.execute("SELECT xp FROM levelxp WHERE guildID = (%s)", (msg.guild.id))
                                xpres = await cur.fetchone()
                                if not xpres:
                                    newxp = random.randint(1, 5)
                                if xpres:
                                    newxp = random.randint(1, 5) * 2

                                await cur.execute(
                                    "UPDATE levelsystem SET user_xp = (%s) WHERE client_id = (%s) AND guild_id = (%s)",
                                    (result[0][0] + newxp, msg.author.id, msg.guild.id))
                                if xp_end >= 58000.0 and lvl_start >= 100 and xp_start >= 58000.0:
                                    return
                                if xp_end <= 58000.0 and lvl_start <= 100 and xp_start <= 58000.0:
                                    if xp_end < (xp_start + newxp):
                                        await cur.execute(
                                            "UPDATE levelsystem SET user_level = (%s) WHERE client_id = (%s) AND guild_id = (%s)",
                                            (int(lvl_start) + 1, msg.author.id, msg.guild.id))
                                        await cur.execute(
                                            "UPDATE levelsystem SET user_xp = (%s) WHERE client_id = (%s) AND guild_id = (%s)",
                                            (0 + 1, msg.author.id, msg.guild.id))

                                        # --- CommunityGoal: Levelup-Progress inkrementieren ---
                                        cog = self.bot.get_cog("CommunityGoalsCog")
                                        if cog:
                                            await cog.count_levelup(msg.guild.id)

                                        await cur.execute("SELECT type FROM levelchannel WHERE guildID = (%s)",
                                                          (msg.guild.id,))
                                        result6 = await cur.fetchone()
                                        if not result6:
                                            await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                              (msg.guild.id))
                                            messageres = await cur.fetchone()
                                            if messageres is None:
                                                await cur.execute(
                                                    "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                    (msg.guild.id, int(lvl_start) + 1))
                                                result8 = await cur.fetchone()
                                                if result8:
                                                    roleid = result8[0]
                                                    role = msg.guild.get_role(roleid)
                                                    member = msg.author
                                                    if role in member.roles:
                                                        pass
                                                    else:
                                                        await member.add_roles(role)
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1}",
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                                if not result8:
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                            if messageres is not None:
                                                await cur.execute(
                                                    "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                    (msg.guild.id, int(lvl_start) + 1))
                                                result5 = await cur.fetchone()
                                                lvl = int(lvl_start + 1)
                                                finalmsg = messageres[0].replace("%member",
                                                                                 str(msg.author.mention)).replace(
                                                    "%level", (str(lvl)))
                                                if result5:
                                                    roleid = result5[0]
                                                    role = msg.guild.get_role(roleid)
                                                    member = msg.author
                                                    if role in member.roles:
                                                        pass
                                                    else:
                                                        await member.add_roles(role)
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=finalmsg,
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                                if not result5:
                                                    embed = discord.Embed(title="Level-UP",
                                                                          description=finalmsg,
                                                                          color=discord.Color.green())
                                                    await msg.channel.send(msg.author.mention, embed=embed)
                                        if result6:
                                            if result6[0] == str("Private Message"):
                                                await cur.execute(
                                                    "SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                    (msg.guild.id))
                                                messageres = await cur.fetchone()
                                                if messageres is None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result11 = await cur.fetchone()
                                                    if result11:
                                                        roleid = result11[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                                    if not result11:
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                                if messageres is not None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result10 = await cur.fetchone()
                                                    lvl = int(lvl_start + 1)
                                                    finalmsg = messageres[0].replace("%member",
                                                                                     str(msg.author.mention)).replace(
                                                        "%level", (str(lvl)))
                                                    if result10:
                                                        roleid = result10[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                                    if not result10:
                                                        lvl = int(lvl_start + 1)
                                                        finalmsg = messageres[0].replace("%member",
                                                                                         str(msg.author.mention)).replace(
                                                            "%level", (str(lvl)))
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.author.send(msg.author.mention, embed=embed)
                                            if result6[0] == str("Deactivated"):
                                                await cur.execute(
                                                    "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                    (msg.guild.id, int(lvl_start) + 1))
                                                result12 = await cur.fetchone()
                                                if result12:
                                                    roleid = result12[0]
                                                    role = msg.guild.get_role(roleid)
                                                    member = msg.author
                                                    if role in member.roles:
                                                        pass
                                                    else:
                                                        await member.add_roles(role)
                                                if not result12:
                                                    pass
                                            if result6[0] == str("Last Channel"):
                                                await cur.execute(
                                                    "SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                    (msg.guild.id))
                                                messageres = await cur.fetchone()
                                                if messageres is None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result15 = await cur.fetchone()
                                                    if result15:
                                                        roleid = result15[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                                    if not result15:
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                                if messageres is not None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result14 = await cur.fetchone()
                                                    lvl = int(lvl_start + 1)
                                                    finalmsg = messageres[0].replace("%member",
                                                                                     str(msg.author.mention)).replace(
                                                        "%level", (str(lvl)))
                                                    if result14 is not None:
                                                        roleid = result14[0]
                                                        role = msg.guild.get_role(roleid)
                                                        lvl = int(lvl_start + 1)
                                                        finalmsg = messageres[0].replace("%member",
                                                                                         str(msg.author.mention)).replace(
                                                            "%level", (str(lvl)))
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                                    if result14 is None:
                                                        embed = discord.Embed(title="Level-UP", description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await msg.channel.send(msg.author.mention, embed=embed)
                                            if result6[0].isnumeric():
                                                await cur.execute("SELECT message FROM levelmsg WHERE guildID = (%s)",
                                                                  (msg.guild.id))
                                                messageres = await cur.fetchone()

                                                if messageres is None:
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result9 = await cur.fetchone()
                                                    if result9:
                                                        roleid = result9[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await channel.send(msg.author.mention, embed=embed)
                                                    if not result9:
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        embed = discord.Embed(title="Level-UP",
                                                                          description=f"Weiter so {msg.author.mention}! Du hast Level {int(lvl_start) + 1} erreicht",
                                                                          color=discord.Color.green())
                                                        await channel.send(msg.author.mention, embed=embed)
                                                if messageres is not None:
                                                    lvl = int(lvl_start + 1)
                                                    finalmsg = messageres[0].replace("%member",
                                                                                     str(msg.author.mention)).replace(
                                                        "%level", (str(lvl)))
                                                    await cur.execute(
                                                        "SELECT roleID FROM levelroles WHERE guildID = (%s) and levelreq = (%s)",
                                                        (msg.guild.id, int(lvl_start) + 1))
                                                    result5 = await cur.fetchone()
                                                    if result5:
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        roleid = result5[0]
                                                        role = msg.guild.get_role(roleid)
                                                        member = msg.author
                                                        if role in member.roles:
                                                            pass
                                                        else:
                                                            await member.add_roles(role)
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())

                                                        await channel.send(msg.author.mention, embed=embed)
                                                    if not result5:
                                                        channel = self.bot.get_channel(int(result6[0]))
                                                        embed = discord.Embed(title="Level-UP",
                                                                              description=finalmsg,
                                                                              color=discord.Color.green())
                                                        await channel.send(msg.author.mention, embed=embed)

    @app_commands.command(name="xpboost")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def levelsystem_xpboost(self, interaction: discord.Interaction,
                                  status: Literal['Aktivieren(x2)', 'Deaktivieren(x1)']):
        """Aktiviere den XP-Boost für deinen Server."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)", (interaction.guild.id))
                enabled = await cur.fetchone()
                if enabled[0] == 0:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                        ephemeral=True)
                if enabled[0] == 1:
                    await cur.execute("SELECT xp FROM levelxp WHERE guildID = (%s)", (interaction.guild.id))
                    result = await cur.fetchone()
                    if status == "Aktivieren(x2)":
                        if not result:
                            await cur.execute("INSERT INTO levelxp(guildID, xp) VALUES(%s, %s)",
                                              (interaction.guild.id, 2))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der XP-Boost ist jetzt für diesen Server aktiviert. User bekommen nun 2x XP.**")
                        if result:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Der XP-Boost ist für diesen Server bereits aktiviert.**",
                                ephemeral=True)
                    if status == "Deaktivieren(x1)":
                        if not result:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Der XP-Boost ist für diesen Server bereits deaktiviert.**.",
                                ephemeral=True)
                        if result:
                            await cur.execute("DELETE FROM levelxp WHERE guildID = (%s) and xp = (%s)",
                                              (interaction.guild.id, 2))
                            await interaction.response.send_message(
                                "<:Astra_accept:1141303821176422460> **Der XP-Boost ist jetzt für diesen Server deaktiviert. User bekommen nun nichtmehr 2x XP**")

    @app_commands.command(name="setlevel")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def levelsystem_setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int):
        """Set the level from a user on your server."""
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if level > 100:
                    await interaction.response.send_message(
                        "<:Astra_x:1141303954555289600> **Das Level kann icht höher als 100 sein.**",
                        ephemeral=True)
                if level <= 100:
                    await cur.execute(f"SELECT enabled FROM levelsystem WHERE guild_id = (%s)",
                                      (interaction.guild.id))
                    enabled = await cur.fetchone()
                    if enabled[0] == 0:
                        await interaction.response.send_message(
                            "<:Astra_x:1141303954555289600> **Das Levelsystem ist auf diesem Server bereits deaktiviert.**",
                            ephemeral=True)
                    if enabled[0] == 1:
                        await cur.execute(
                            f"SELECT user_xp, user_level FROM levelsystem WHERE client_id = (%s) AND guild_id = (%s)",
                            (member.id, interaction.guild.id))
                        result = await cur.fetchall()
                        if not result:
                            await interaction.response.send_message(
                                "<:Astra_x:1141303954555289600> **Keine Einträge für diesen User gefunden.**",
                                ephemeral=True)
                        if result:
                            await cur.execute(
                                "UPDATE levelsystem SET user_level = (%s) WHERE guild_id = (%s) and client_id = (%s)",
                                (level, interaction.guild.id, member.id))
                            await cur.execute(
                                "UPDATE levelsystem SET user_xp = (%s) WHERE guild_id = (%s) and client_id = (%s) and user_level = (%s)",
                                (0 + 1, interaction.guild.id, member.id, level))
                            await interaction.response.send_message(
                                f"<:Astra_accept:1141303821176422460> **Der User {member.mention} wurde auf Level `{level}` gesetzt.**")

async def setup(bot):
    await bot.add_cog(levelsystem(bot))
    bot.tree.add_command(Level(bot))
