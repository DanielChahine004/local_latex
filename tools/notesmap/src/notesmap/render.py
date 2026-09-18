"""Notes -> a danvas board, kept in step with the notes as they change.

Board.apply(notes) is the only entry point that changes content. It diffs the
new notes against what is on screen: panels are updated in place (an unfolded
note stays unfolded), added, or removed; pins move with their \\location;
arrows are reconnected only when their endpoints or caption change. It can be
called any number of times, from any thread.
"""
from __future__ import annotations

import html
import io
import re
import tempfile
import threading
import time
from pathlib import Path

from .config import Config
from .latex import Converter
from .layout import PANEL_W, Rect, auto_place, estimate_height, project
from .parse import Entry, Notes
from .redact import redact
from .source import Source
from .web import MAP_CSS, PIN_JSX, REACT_CSS, REACT_SRC, edit_jsx

PITCH, ROW_GAP = PANEL_W + 40, 100


class Board:
    def __init__(self, canvas, cfg: Config, source: Source, conv: Converter, map_mode: bool) -> None:
        self.canvas, self.cfg, self.src, self.conv, self.map_mode = canvas, cfg, source, conv, map_mode
        self.lock = threading.RLock()
        self.panels: dict[str, object] = {}       # group key -> panel
        self.owner: dict[str, str] = {}           # any entry key -> its group key
        self.props: dict[str, dict] = {}
        self.pins: dict[str, object] = {}
        self.where: dict[str, tuple] = {}         # group key -> (location tuple, x, y)
        self.arrows: dict[str, tuple] = {}        # arrow name -> (start, end, kwargs)
        self.arrow_objs: dict[str, object] = {}
        self.rows: list[list[str]] = []
        self.images: dict[tuple[str, str], str] = {}
        self._tick = 0
        self.map_w = cfg.map_width
        if map_mode:
            self._draw_map()
        self._edit_link()
        canvas.on_connect(lambda viewer: self.later(self.settle, 3.0, 9.0))

    def _edit_link(self) -> None:
        """A standing panel linking to the companion editor, if one is configured."""
        self.edit_panel = None
        if not self.cfg.edit_url:
            return
        if self.map_mode:
            # a footer, centred just below the map rather than on it: danvas's own
            # toolbar floats over the middle of the viewport's bottom edge, and a
            # signpost placed under it cannot be clicked
            scale = self.map_w / 4500          # legible without dominating the map
            w = round(300 * scale)
            # left of centre, because danvas's toolbar floats over the middle of
            # the viewport's bottom edge and would take the click
            x, y = round(self.map_w * 0.24), self.map_w // 2 + round(24 * scale)
        else:
            scale, w = 1.0, 380
            x, y = 0, -220
        self.edit_panel = self.canvas.react(
            jsx=edit_jsx(self.cfg.edit_url, self.cfg.edit_label, scale),
            name="edit_link", w=w, x=x, y=y)

    # --- public -------------------------------------------------------------------

    def apply(self, notes: Notes) -> dict:
        # \ref{..:key} reads as the entry's short name, its title up to " -- ",
        # taken before redaction so a reference to a hidden entry still reads well
        labels = {e.key: self.conv.to_md(e.title).split(" – ")[0].strip() for e in notes.all_entries()}
        notes = redact(notes, self.cfg.hide_sections, self.cfg.hide_gaps, self.cfg.show_loose,
                       self.cfg.hide_programmes)
        with self.lock:
            self.conv.labels = labels
            groups = self._groups(notes)
            added = [k for k in groups if k not in self.panels]
            removed = [k for k in self.panels if k not in groups]
            for key in removed:
                self._remove(key)
            self.owner = {e.key: g for g, (_, node, papers) in groups.items()
                          for e in ([node] if node else []) + papers}
            if self.map_mode:
                self._place_on_map(groups)
            else:
                self._place_in_rows(groups)
            for key, (title, node, papers) in groups.items():
                props = self._props(key, title, node, papers)
                if key in self.panels:
                    if props != self.props[key]:
                        self.props[key] = props
                        self.panels[key].update(**props)
            self._arrows(notes)
            self.settle()
            return {"added": added, "removed": removed, "panels": len(groups),
                    "arrows": len([a for a in self.arrows if not a.endswith("_leader")])}

    def set_open(self, key: str, note: str | None) -> None:
        """Unfold note (or fold it if it is already open) in the panel for key."""
        with self.lock:
            pr = self.props.get(key)
            if pr is None:
                return
            pr["open"] = None if pr["open"] == note else note
            self.panels[key].update(**pr)
            self.panels[key].to_front()
            self.later(self.settle, 1.0, 3.0)

    def resize(self, key: str, w) -> None:
        """Set a panel's width from its corner grip; the content scales to fit."""
        try:
            w = int(float(w))
        except (TypeError, ValueError):
            return
        w = max(PANEL_W // 4, min(PANEL_W * 3, w))
        with self.lock:
            panel = self.panels.get(key)
            if panel is not None:
                panel.set_layout(w=w)
        self.later(self.settle, 0.8)

    def settle(self) -> None:
        """Re-stack after heights change: rows repack, and on the map the arrows
        and then the map go to the back (an arrow's to_back does not persist)."""
        with self.lock:
            if self.rows:
                geo = {e["name"]: e for e in self.canvas.describe() if isinstance(e.get("h"), (int, float))}
                y = 40
                for row in self.rows:
                    x = 40
                    for key in row:
                        # columns follow each panel's own width, so a resized panel
                        # pushes its neighbours along instead of covering them
                        self.panels[key].set_layout(x=x, y=y)
                        x += geo.get(key, {}).get("w", PANEL_W) + (PITCH - PANEL_W)
                    y += max(geo.get(k, {}).get("h", 300) for k in row) + ROW_GAP
            if self.map_mode:
                for arrow in self.arrow_objs.values():
                    arrow.to_back()
                self.canvas["world"].to_back()
            # the arrow layer takes the pointer wherever it crosses the link, so
            # the link has to sit above it or it cannot be clicked
            if self.edit_panel is not None:
                self.edit_panel.to_front()

    @staticmethod
    def later(fn, *delays: float) -> None:
        for d in delays:
            threading.Thread(target=lambda d=d: (time.sleep(d), fn()), daemon=True).start()

    # --- content ------------------------------------------------------------------

    def _groups(self, notes: Notes) -> dict[str, tuple[str, Entry | None, list[Entry]]]:
        groups = {p.key: (self.conv.to_md(p.title), p, p.papers) for p in notes.programmes}
        if notes.loose:
            groups[self.cfg.loose_key] = (self.cfg.loose_title, None, notes.loose)
        return groups

    def _image(self, rel: str | None) -> str | None:
        if not rel:
            return None
        stamp = self.src.stamp(rel)
        if stamp is None:
            return None
        key = (rel, stamp)
        if key not in self.images:
            url = self.src.data_url(rel)
            if url is None:
                return None
            self.images[key] = url
        return self.images[key]

    def _html(self, md: str) -> str:
        def inline(s: str) -> str:
            s = html.escape(s, quote=False)
            for tag in ("sup", "sub"):
                s = s.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
            s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
            s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
            return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        out, items = [], []

        def flush():
            if items:
                out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
                items.clear()
        for line in md.split("\n"):
            s = line.strip()
            if s.startswith("![](") and s.endswith(")"):
                flush()
                url = self._image(s[4:-1])
                if url:
                    out.append(f'<img class="inl" src="{url}" alt="">')
            elif s.startswith("- "):
                items.append(s[2:])
            elif s.startswith("> "):
                flush()
                out.append(f"<blockquote>{inline(s[2:])}</blockquote>")
            elif s:
                flush()
                out.append(f"<p>{inline(s)}</p>")
            else:
                flush()
        flush()
        return "".join(out)

    def _snippet(self, e: Entry) -> str:
        text = re.sub(r"\*\*[^*]+\*\*\n\n", "", e.overview(self.conv, self.cfg.overview_sections), count=1)
        text = re.sub(r"!\[\]\([^)]*\)", "", text)
        plain = re.sub(r"\*\*\[gap:.*?\]\*\*", "", text, flags=re.S).strip()
        if not plain:   # an unread paper: the gap is all there is, so show it
            plain = re.sub(r"\*\*\[gap:\s*(.*?)\]\*\*", r"\1", text, flags=re.S).strip()
        # "et al." and initials such as "A. J." do not end the first sentence
        guarded = re.sub(r"\b(al|vs|et|cf|e\.g|i\.e)\.", r"\1․", plain)
        guarded = re.sub(r"\b([A-Z])\.", r"\1․", guarded)
        first = re.split(r"(?<=[.!?])\s", guarded, maxsplit=1)[0].replace("․", ".")
        return re.sub(r"[*`]", "", first)[:220]

    def _props(self, key: str, title: str, node: Entry | None, papers: list[Entry]) -> dict:
        thumb = self._image(node.thumb) if node else None
        loc = node.location if node else None
        # cards in date order; undated ones keep note order at the end
        dated = sorted(papers, key=lambda p: p.year if p.year is not None else 9999)
        props = {
            "key": key, "title": title,
            "open": self.props.get(key, {}).get("open"),
            "place": self.conv.to_md(loc.place) if loc else "",
            "figures": [{"src": thumb, "caption": ""}] if thumb else [],
            "html": self._html(node.full(self.conv)) if node else "",
            "lead": self._snippet(node) if node else "",
            "link": node.link if node else None,
            "papers": [{"key": p.key, "title": self.conv.to_md(p.title), "year": str(p.year) if p.year else "",
                        "snippet": self._snippet(p), "thumb": self._image(p.thumb), "link": p.link,
                        "html": self._html(p.full(self.conv)) or "<p><i>(empty)</i></p>"}
                       for p in dated],
        }
        keys = {key} | {p["key"] for p in props["papers"]}
        if props["open"] not in keys:            # the open note was deleted
            props["open"] = None
        return props

    def _create(self, key: str, x: float, y: float, groups) -> None:
        title, node, papers = groups[key]
        props = self._props(key, title, node, papers)
        css = REACT_CSS + (MAP_CSS if self.map_mode else "")
        panel = self.canvas.react(REACT_SRC, css=css, name=key, props=props, w=PANEL_W,
                                  frame=False, x=x, y=y)
        panel.on_error(lambda msg, key=key: print(f"[notesmap] panel {key}: {msg}", flush=True))
        panel.on("toggle")(lambda msg, key=key: self.set_open(key, msg.get("key")))
        panel.on("resize")(lambda msg, key=key: self.resize(key, msg.get("w")))
        panel.on_layout(self._on_layout)
        self.panels[key], self.props[key] = panel, props

    def _on_layout(self, comp) -> None:
        # a corner drag pins the height; the content scales with the width and
        # sets its own height, so hand the height back to the content
        if getattr(comp, "_auto_h", True) is False:
            comp.h = "auto"
        # the browser reports a fitted height like a drag; debounce and repack
        self._tick += 1
        mine = self._tick

        def go():
            time.sleep(0.4)
            if self._tick == mine:
                self.settle()
        threading.Thread(target=go, daemon=True).start()

    def _remove(self, key: str) -> None:
        for name in [n for n, (a, b, _) in self.arrows.items() if key in (a, b)]:
            self._disconnect(name)
        for d in (self.panels, self.pins):
            comp = d.pop(key, None)
            if comp is not None:
                self.canvas.remove(comp)
        self.props.pop(key, None)
        self.where.pop(key, None)

    # --- placement ----------------------------------------------------------------

    def _draw_map(self) -> None:
        from PIL import Image
        src = self.cfg.resolve(self.cfg.map_image) if self.cfg.map_image else \
            Path(__file__).parent / "assets" / "world-blue-marble.jpg"
        w, h = self.map_w, self.map_w // 2
        cache = Path(tempfile.gettempdir()) / "notesmap" / f"{src.stem}-{src.stat().st_mtime_ns}-{w}.jpg"
        if not cache.exists():   # the image panel shows pixels 1:1, so scale once and keep it
            cache.parent.mkdir(parents=True, exist_ok=True)
            Image.open(src).convert("RGB").resize((w, h), Image.BICUBIC).save(cache, "JPEG", quality=80)
        self.canvas.image(cache.read_bytes(), name="world", w=w, h=h, x=0, y=0, decorative=True)

    def _place_on_map(self, groups) -> None:
        taken = [Rect(x, y, PANEL_W, estimate_height(bool(n and n.thumb), len(ps)))
                 for k, (_, x, y) in self.where.items() if k in groups
                 for (_, n, ps) in [groups[k]]]
        shelf_x, shelf_y = self.cfg.unplaced
        unplaced = [k for k, (_, n, _) in groups.items() if not (n and n.location)]
        for key, (title, node, papers) in groups.items():
            loc = node.location if node else None
            sig = (loc.lat, loc.lon, loc.offset) if loc else None
            if key in self.where and self.where[key][0] == sig:
                continue                              # unchanged: leave it where it is
            h = estimate_height(bool(node and node.thumb), len(papers))
            if loc is None:
                # no \location: a shelf of its own, in note order
                x, y = shelf_x + unplaced.index(key) * PITCH, shelf_y
                self._drop_pin(key)
            else:
                px, py = project(loc.lat, loc.lon, self.map_w)
                if loc.offset:
                    x, y = px + loc.offset[0], py + loc.offset[1]
                else:
                    x, y = auto_place((px, py), h, taken)
                self._set_pin(key, px, py)
            taken.append(Rect(x, y, PANEL_W, h))
            if key in self.panels:
                self.panels[key].set_layout(x=x, y=y)
            else:
                self._create(key, x, y, groups)
            self.where[key] = (sig, x, y)
            if loc is not None:
                self._connect(f"{key}_leader", f"{key}_pin", key,
                              color="red", size="m", arrowhead_end="none")

    def _set_pin(self, key: str, px: float, py: float) -> None:
        if key in self.pins:
            self.pins[key].set_layout(x=px - 19, y=py - 19)
        else:
            # a tiny panel, not a managed shape: shapes draw beneath panels and the
            # map is a panel. decorative = no chrome, not draggable, click-through
            self.pins[key] = self.canvas.react(jsx=PIN_JSX, name=f"{key}_pin", w=38, h=38,
                                               x=px - 19, y=py - 19, decorative=True)

    def _drop_pin(self, key: str) -> None:
        if key in self.pins:
            self._disconnect(f"{key}_leader")
            self.canvas.remove(self.pins.pop(key))

    def _place_in_rows(self, groups) -> None:
        placed = {k for row in self.cfg.rows for k in row}
        rows = [[k for k in row if k in groups] for row in self.cfg.rows]
        rows.append([k for k in groups if k not in placed])
        self.rows = [r for r in rows if r]
        for ri, row in enumerate(self.rows):
            for ci, key in enumerate(row):
                x, y = 40 + ci * PITCH, 40 + ri * 500
                if key in self.panels:
                    self.panels[key].set_layout(x=x)
                else:
                    self._create(key, x, y, groups)

    # --- arrows -------------------------------------------------------------------

    def _component(self, name: str):
        return self.pins[name[:-4]] if name.endswith("_pin") else self.panels[name]

    def _connect(self, name: str, a: str, b: str, **kw) -> None:
        spec = (a, b, kw)
        if self.arrows.get(name) == spec:
            return
        self.arrow_objs[name] = self.canvas.connect(self._component(a), self._component(b), name=name, **kw)
        self.arrows[name] = spec

    def _disconnect(self, name: str) -> None:
        self.arrows.pop(name, None)
        obj = self.arrow_objs.pop(name, None)
        if obj is not None:
            try:
                self.canvas.disconnect(obj)
            except (KeyError, ValueError):
                pass

    def _arrows(self, notes: Notes) -> None:
        # every \ref between two panels is an edge, captioned by the sentence that
        # makes it; a pair referring to each other becomes one double-headed arrow
        prefixes = self.cfg.ref_prefixes
        edges: dict[tuple[str, str], str] = {}
        for e in notes.all_entries():
            src = self.owner.get(e.key)
            if src is None:
                continue
            reasons = e.ref_reasons(self.conv, prefixes)
            for r in e.refs(prefixes):
                dst = self.owner.get(r)
                if dst is not None and dst != src and (src, dst) not in edges:
                    edges[(src, dst)] = reasons.get(r, "")
        for a, b in self.cfg.prune:
            edges.pop((a, b), None)
        col = {k: (ri, ci) for ri, row in enumerate(self.rows) for ci, k in enumerate(row)}
        wanted: set[str] = set()
        for (a, b), why in edges.items():
            if (b, a) in edges and f"{b}->{a}" in wanted:
                continue
            both = (b, a) in edges
            if self.map_mode or a not in col or b not in col:
                bend = 120
            else:
                (ra, ca), (rb, cb) = col[a], col[b]
                bend = 0 if ra == rb and abs(ca - cb) == 1 else 140
            name = f"{a}->{b}"
            wanted.add(name)
            self._connect(name, a, b, text=why or None, color="grey", dash="dashed", size="s",
                          bend=bend, arrowhead_start="arrow" if both else "none")
        for name in [n for n in self.arrows if not n.endswith("_leader") and n not in wanted]:
            self._disconnect(name)
