"""Where panels go.

Map: equirectangular, so x is linear in longitude and y in latitude. A
programme with \\location[dx,dy] hangs its panel at that offset from the pin;
one without an offset is placed automatically on the nearest free spot of
widening rings around its pin, so a new programme never needs a hand-picked
position and never covers one already placed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# The panel's content is laid out at DESIGN_W (web.py's own constant, kept in
# step) and zoomed to whatever width it is given, so a narrower PANEL_W is a
# smaller copy of the same panel -- shorter as well as narrower.
DESIGN_W = 880
PANEL_W = 560         # small enough that a crowded region (the Low Countries) still
                      # reads as separate panels; zoom in for the text
CONF_W = 380          # a conference says less than a programme: dates, not papers


def panel_w(kind: str) -> int:
    return CONF_W if kind == "conference" else PANEL_W


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def overlaps(self, o: "Rect", pad: float = 40) -> bool:
        return not (self.x + self.w + pad <= o.x or o.x + o.w + pad <= self.x
                    or self.y + self.h + pad <= o.y or o.y + o.h + pad <= self.y)


def project(lat: float, lon: float, width: int) -> tuple[float, float]:
    return (lon + 180) * width / 360, (90 - lat) * (width / 2) / 180


def estimate_height(has_figure: bool, n_papers: int, w: float = PANEL_W) -> float:
    """Before the browser reports it: title and lead, figure, rows of cards.

    The figure sits beside the heading, so it adds only what it outgrows it by."""
    design = 110 + (80 if has_figure else 0) + 215 * math.ceil(n_papers / 5)
    return design * w / DESIGN_W             # the content is zoomed to the panel's width


def auto_place(pin: tuple[float, float], w: float, h: float,
               taken: list[Rect]) -> tuple[float, float]:
    """The first free spot on rings around the pin, starting up and to the right."""
    px, py = pin
    for radius in range(300, 6000, 250):
        steps = max(12, int(2 * math.pi * radius / 400))
        for i in range(steps):
            a = -math.pi / 4 + 2 * math.pi * i / steps
            cx, cy = px + radius * math.cos(a), py + radius * math.sin(a)
            r = Rect(cx - w / 2, cy - h / 2, w, h)
            if not any(r.overlaps(t) for t in taken):
                return r.x, r.y
    return px + 100, py + 100


def push_out(r: Rect, taken: list[Rect], away: tuple[float, float]) -> tuple[float, float]:
    """r slid away from the pin until it covers nothing, keeping the direction a
    hand-written \\location[dx,dy] asked for. (0, 0) if it never comes free."""
    dx, dy = away
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    for step in range(0, 4000, 40):
        moved = Rect(r.x + ux * step, r.y + uy * step, r.w, r.h)
        if not any(moved.overlaps(t) for t in taken):
            return moved.x, moved.y
    return 0.0, 0.0
