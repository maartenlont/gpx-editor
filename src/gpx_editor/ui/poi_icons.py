"""Shared POI/cue icon definitions used by the map widget and the POI table."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

# ---------------------------------------------------------------------------
# Icon definition tables
# ---------------------------------------------------------------------------

# cue_type (lower-case) → (Bootstrap Glyphicon name, folium color)
CUE_ICON: dict[str, tuple[str, str]] = {
    "left":         ("arrow-left",  "red"),
    "turn left":    ("arrow-left",  "red"),
    "sharp left":   ("arrow-left",  "darkred"),
    "slight left":  ("arrow-left",  "orange"),
    "bear left":    ("arrow-left",  "orange"),
    "fork left":    ("arrow-left",  "orange"),
    "right":        ("arrow-right", "red"),
    "turn right":   ("arrow-right", "red"),
    "sharp right":  ("arrow-right", "darkred"),
    "slight right": ("arrow-right", "orange"),
    "bear right":   ("arrow-right", "orange"),
    "fork right":   ("arrow-right", "orange"),
    "straight":     ("arrow-up",    "blue"),
    "continue":     ("arrow-up",    "blue"),
    "u-turn":       ("repeat",      "darkred"),
    "uturn":        ("repeat",      "darkred"),
    "roundabout":   ("refresh",     "purple"),
}
DEFAULT_CUE_ICON: tuple[str, str] = ("map-marker", "red")

# POI name (lower-case) → (Bootstrap Glyphicon name, folium color)
POI_NAME_ICON: dict[str, tuple[str, str]] = {
    # Navigation
    "start":          ("flag",        "green"),
    "right":          ("arrow-right", "red"),
    "left":           ("arrow-left",  "red"),
    "sharp right":    ("arrow-right", "darkred"),
    "sharp left":     ("arrow-left",  "darkred"),
    "slight right":   ("arrow-right", "orange"),
    "slight left":    ("arrow-left",  "orange"),
    # Climb categories
    "4th category":   ("chevron-up",  "cadetblue"),
    "3rd category":   ("chevron-up",  "blue"),
    "2nd category":   ("chevron-up",  "orange"),
    "1st category":   ("chevron-up",  "red"),
    # Fuel
    "bp":             ("flash",       "darkgreen"),
    "omv":            ("flash",       "red"),
    # Points of interest
    "coffee":         ("coffee",      "beige"),
    "food":           ("cutlery",     "beige"),
    "restaurant":     ("cutlery",     "beige"),
    "water":          ("tint",        "blue"),
    "water fountain": ("tint",        "blue"),
    "parking":        ("car",         "gray"),
    "hospital":       ("plus-sign",   "red"),
    "bike":           ("wrench",      "darkblue"),
    "photo":          ("camera",      "purple"),
    "summit":         ("flag",        "darkred"),
    "waypoint":       ("map-marker",  "green"),
    "generic":        ("info-sign",   "green"),
}
DEFAULT_POI_ICON: tuple[str, str] = ("info-sign", "green")

# ---------------------------------------------------------------------------
# Qt rendering helpers
# ---------------------------------------------------------------------------

_FOLIUM_HEX: dict[str, str] = {
    "red":       "#D63E2A",
    "blue":      "#4A90D9",
    "green":     "#72AF26",
    "orange":    "#F69730",
    "darkred":   "#A23336",
    "darkblue":  "#00649F",
    "darkgreen": "#728224",
    "cadetblue": "#436978",
    "purple":    "#D252B9",
    "beige":     "#FFCB92",
    "gray":      "#7B7B7B",
    "black":     "#303030",
    "lightred":  "#FF8E7F",
    "lightblue": "#A8D3E6",
    "lightgreen":"#BBF26B",
    "lightgray": "#A3A3A3",
}

# Glyphicon → single Unicode character that fits in a small circle.
_GLYPH_CHAR: dict[str, str] = {
    "flag":        "⚑",
    "arrow-left":  "←",
    "arrow-right": "→",
    "arrow-up":    "↑",
    "chevron-up":  "^",
    "flash":       "⚡",
    "tint":        "~",
    "car":         "P",
    "plus-sign":   "+",
    "wrench":      "⚙",
    "camera":      "◉",
    "coffee":      "C",
    "cutlery":     "F",
    "info-sign":   "i",
    "map-marker":  "●",
    "repeat":      "U",
    "refresh":     "↺",
}

# Colors whose background is light enough that black text is more readable.
_LIGHT_COLORS = {"beige", "lightgreen", "lightblue", "lightgray"}


def make_icon(glyphicon: str, folium_color: str, size: int = 18) -> QIcon:
    """Return a *size*×*size* QIcon: filled circle in *folium_color* with a glyph."""
    hex_color = _FOLIUM_HEX.get(folium_color, "#999999")
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    p.setBrush(QColor(hex_color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)

    char = _GLYPH_CHAR.get(glyphicon, "●")
    p.setPen(Qt.black if folium_color in _LIGHT_COLORS else Qt.white)
    font = QFont()
    font.setPixelSize(size - 6)
    font.setBold(True)
    p.setFont(font)
    p.drawText(px.rect(), Qt.AlignCenter, char)
    p.end()

    return QIcon(px)


def poi_icon_for_row(row: dict) -> QIcon:
    """Return the QIcon for a POI row (uses the *name* field for lookup)."""
    name = (row.get("name") or "").lower()
    glyph, color = POI_NAME_ICON.get(name, DEFAULT_POI_ICON)
    return make_icon(glyph, color)
