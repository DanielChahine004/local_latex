"""Where panels go.

Map: equirectangular, so x is linear in longitude and y in latitude. A
programme with \\location[dx,dy] hangs its panel at that offset from the pin;
one without an offset is placed automatically on the nearest free spot of
widening rings around its pin, so a new programme never needs a hand-picked
position and never covers one already placed.

Leaders (pin to panel centre, where danvas binds them) should not cross. A
hand offset is a decision and is kept, so those panels are placed first; the
automatic ones then pay for every crossing and every panel their leader would
run under, and take a spot a few rings out rather than tangle. Crossings that
remain are between hand-placed panels, and are reported, not undone.
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


Point = tuple[float, float]
Segment = tuple[Point, Point]

# What a free spot costs, in canvas units of extra leader length: a panel will
# sit up to eight rings further out to keep its leader from crossing another,
# or four to keep it from running under another panel.
CROSS_COST = 2000
THROUGH_COST = 1000
WIDEN = 1500          # how far past the first free ring the search keeps looking


def centre(r: Rect) -> Point:
    return r.x + r.w / 2, r.y + r.h / 2


def _side(p: Point, q: Point, r: Point) -> float:
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def crosses(s: Segment, t: Segment) -> bool:
    """Whether two leaders cross. One sharing a pin with another (two programmes
    in one city) meets it there, which is not a crossing."""
    (a, b), (c, d) = s, t
    if a == c or a == d or b == c or b == d:
        return False
    return (_side(a, b, c) * _side(a, b, d) < 0) and (_side(c, d, a) * _side(c, d, b) < 0)


def through(s: Segment, r: Rect) -> bool:
    """Whether a leader runs under a panel: crosses one of its edges, or ends inside it."""
    x0, y0, x1, y1 = r.x, r.y, r.x + r.w, r.y + r.h
    if any(x0 < p[0] < x1 and y0 < p[1] < y1 for p in s):
        return True
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return any(crosses(s, e) for e in edges)


def leader_cost(pin: Point, r: Rect, leaders: list[Segment], panels: list[Rect]) -> float:
    """What a panel at r costs in leaders: each crossing, and each panel its leader runs under."""
    s = (pin, centre(r))
    return (CROSS_COST * sum(crosses(s, t) for t in leaders)
            + THROUGH_COST * sum(through(s, p) for p in panels))


def auto_place(pin: Point, w: float, h: float, taken: list[Rect],
               leaders: list[Segment] = (), panels: list[Rect] = (),
               bounds: Rect | None = None) -> tuple[float, float]:
    """The cheapest free spot on rings around the pin: nearest first, but one whose
    leader would cross another programme's, or run under a panel, gives way to
    one a few rings further out. Ties go to the first found, up and to the right.
    With bounds (the map), a spot that hangs off its edge is not free."""
    px, py = pin
    best, best_cost, limit = None, math.inf, 6000
    for radius in range(300, 6000, 250):
        if radius > limit:
            break
        steps = max(12, int(2 * math.pi * radius / 400))
        for i in range(steps):
            a = -math.pi / 4 + 2 * math.pi * i / steps
            cx, cy = px + radius * math.cos(a), py + radius * math.sin(a)
            r = Rect(cx - w / 2, cy - h / 2, w, h)
            if any(r.overlaps(t) for t in taken):
                continue
            if bounds and not (bounds.x <= r.x and bounds.y <= r.y and r.x + r.w <= bounds.x + bounds.w
                               and r.y + r.h <= bounds.y + bounds.h):
                continue
            if best is None:
                limit = radius + WIDEN
            cost = radius + leader_cost(pin, r, leaders, panels)
            if cost < best_cost:
                best, best_cost = r, cost
    return (best.x, best.y) if best else (px + 100, py + 100)


def tangles(placed: dict[str, tuple[Point, Rect]]) -> list[tuple[str, str]]:
    """Every pair of programmes whose leaders cross."""
    keys = sorted(placed)
    segs = {k: (placed[k][0], centre(placed[k][1])) for k in keys}
    return [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if crosses(segs[a], segs[b])]


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
