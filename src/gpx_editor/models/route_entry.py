from __future__ import annotations

from dataclasses import dataclass

from gpx_editor.models.route import RouteData

PALETTE: list[tuple[str, str]] = [
    ("#1565C0", "Blue"),
    ("#B71C1C", "Red"),
    ("#2E7D32", "Green"),
    ("#E65100", "Orange"),
    ("#6A1B9A", "Purple"),
    ("#00695C", "Teal"),
    ("#F9A825", "Amber"),
    ("#4E342E", "Brown"),
    ("#00BCD4", "Cyan"),
    ("#EC407A", "Pink"),
    ("#546E7A", "Slate"),
    ("#000000", "Black"),
]


def next_color(used: list[str]) -> str:
    for hex_color, _ in PALETTE:
        if hex_color not in used:
            return hex_color
    return PALETTE[len(used) % len(PALETTE)][0]


@dataclass
class RouteEntry:
    route: RouteData
    color: str
    label: str
    visible: bool = True
