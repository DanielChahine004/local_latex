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

PANEL_W = 880


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


def estimate_height(has_figure: bool, n_papers: int) -> float:
    """Before the browser reports it: title and lead, figure, rows of cards."""
    return 110 + (200 if has_figure else 0) + 215 * math.ceil(n_papers / 5)


def auto_place(pin: tuple[float, float], h: float, taken: list[Rect]) -> tuple[float, float]:
    """The first free spot on rings around the pin, starting up and to the right."""
    px, py = pin
    for radius in range(300, 6000, 250):
        steps = max(12, int(2 * math.pi * radius / 400))
        for i in range(steps):
            a = -math.pi / 4 + 2 * math.pi * i / steps
            cx, cy = px + radius * math.cos(a), py + radius * math.sin(a)
            r = Rect(cx - PANEL_W / 2, cy - h / 2, PANEL_W, h)
            if not any(r.overlaps(t) for t in taken):
                return r.x, r.y
    return px + 100, py + 100
