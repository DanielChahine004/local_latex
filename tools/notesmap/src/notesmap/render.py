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
import math
import os
import re
import tempfile
import threading
import time
from pathlib import Path

from .config import Config
from .latex import Converter
from .layout import PANEL_W, Rect, auto_place, centre, estimate_height, panel_w, project, push_out, tangles
from .parse import Entry, Notes
from .redact import redact
from . import tables
from .source import Source
from .web import HELPERS_JSX, DETRADAR_CSS, DETRADAR_SRC, MAP_CSS, PIN_JSX, REACT_CSS, REACT_SRC, SEARCH_CSS, SEARCH_SRC, RADAR_CSS, RADAR_SRC, TABLE_CSS, TABLE_SRC, edit_jsx

PITCH, ROW_GAP = PANEL_W + 40, 100
PIN_D = 38                   # the marker's size, and the room a panel leaves it



def _row_id(r: dict, first: str) -> str:
    """A table row's identity across panels: its set, first column and detector."""
    return f"{r.get('Set', '')}|{r.get(first) or ''}|{r.get('Detector') or ''}"


def _sel_initial(data: list[dict], spec: dict, first: str) -> list[str]:
    """What a star chart starts with: the named builds (first match, outside the
    reference set) and every reference row."""
    ref, out = spec.get("reference"), []
    for name in spec.get("initial", []):
        r = next((r for r in data if r.get(first) == name and r["Set"] != ref), None)
        if r:
            out.append(_row_id(r, first))
    return out + [_row_id(r, first) for r in data if r["Set"] == ref]

class Board:
    def __init__(self, canvas, cfg: Config, source: Source, conv: Converter, map_mode: bool) -> None:
        self.canvas, self.cfg, self.src, self.conv, self.map_mode = canvas, cfg, source, conv, map_mode
        self.lock = threading.RLock()
        self.panels: dict[str, object] = {}       # group key -> panel
        self.table_panels: dict[str, tuple] = {}  # [tables] key -> (table panel, its rows)
        self.owner: dict[str, str] = {}           # any entry key -> its group key
        self.props: dict[str, dict] = {}
        self.pins: dict[str, object] = {}
        self.where: dict[str, tuple] = {}         # group key -> (location tuple, x, y)
        self.arrows: dict[str, tuple] = {}        # arrow name -> (start, end, kwargs)
        self.show_layout = os.environ.get("NOTESMAP_LAYOUT", "") not in ("", "0")
        self.why: dict[str, str] = {}             # arrow name -> the sentence behind it
        self.shown: dict[str, str] = {}           # arrow name -> the caption on it now
        self.arrow_objs: dict[str, object] = {}
        self.rows: list[list[str]] = []
        self.notes: Notes | None = None           # the last notes applied, for redrawing arrows
        self.crossed: list[tuple[str, str]] = []  # leader pairs last reported as crossing
        self.images: dict[tuple[str, str], str] = {}
        self._tick = 0
        self.query = ""                           # the search box's words
        self.hits: set[str] = set()               # entry keys matching them
        self.search_panel = None
        self.search_scale = 1.0
        self.links = False                        # the grey arrows between programmes; off until asked for
        self.texts: dict[str, str] = {}           # entry key -> what search reads
        self.map_w = cfg.map_width
        if map_mode:
            self._draw_map()
        self._edit_link()
        self._search_box()
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

    def _search_box(self) -> None:
        """A standing box that colours every note matching what is typed in it."""
        if self.map_mode:
            scale = self.map_w / 4500
            w, x, y = round(900 * scale), round(self.map_w * 0.34), -round(90 * scale)
        else:
            scale, w, x, y = 1.0, 520, 40, -120
        self.search_scale = scale
        self.search_panel = self.canvas.react(HELPERS_JSX + SEARCH_SRC, css=SEARCH_CSS, name="find", w=w, x=x, y=y,
                                              frame=False, props={"q": "", "hits": [], "scale": scale,
                                                                  "links": self.links})
        self.search_panel.on("search")(lambda msg: self.search(msg.get("q", "")))
        self.search_panel.on("links")(lambda msg: self.show_links(bool(msg.get("on"))))

    def show_links(self, on: bool) -> None:
        """Show or hide the grey arrows between programmes. danvas cannot scope an
        arrow to one viewer, so this is the board's state, seen by everyone."""
        with self.lock:
            if on == self.links:
                return
            self.links = on
            if self.notes is not None:
                self._arrows(self.notes)
            self._match()                         # the button learns the new state
            self.settle()

    def search(self, q: str) -> None:
        with self.lock:
            self.query = " ".join(w for w in str(q).lower().split() if w)
            self._match()

    def _match(self) -> None:
        """Entries holding all the typed words, then their programmes, then a repaint.

        A programme counts as a match when one of its papers does, so a word found
        only inside a card still lights the panel it is in."""
        words = self.query.split()
        self.hits = {k for k, text in self.texts.items()
                     if words and all(w in text for w in words)}
        for group, members in self._members().items():
            if self.hits & members:
                self.hits.add(group)
        hits = [{"key": k, "title": self.conv.labels.get(k, k)}
                for k in self.texts if k in self.hits]
        if self.search_panel is not None:
            self.search_panel.update(q=self.query, hits=hits, scale=self.search_scale, links=self.links)
        self._repaint()

    def _members(self) -> dict[str, set[str]]:
        """Group key -> the keys of the entries shown in its panel."""
        out: dict[str, set[str]] = {}
        for key, group in self.owner.items():
            out.setdefault(group, set()).add(key)
        return out

    def _repaint(self) -> None:
        """Push the current props again: panels read query and hits from them."""
        for key, panel in self.panels.items():
            props = dict(self.props[key], query=self.query, filtered=bool(self.query),
                         hits=sorted(self.hits))
            if props != self.props[key]:
                self.props[key] = props
                panel.update(**props)

    # --- public -------------------------------------------------------------------

    def apply(self, notes: Notes) -> dict:
        # \ref{..:key} reads as the entry's short name, its title up to " -- ",
        # taken before redaction so a reference to a hidden entry still reads well
        labels = {e.key: self.conv.to_text(e.title).split(" – ")[0].strip() for e in notes.all_entries()}
        notes = redact(notes, self.cfg.hide_sections, self.cfg.hide_gaps, self.cfg.show_loose,
                       self.cfg.hide_programmes)
        with self.lock:
            self.conv.labels = labels
            groups = self._groups(notes)
            added = [k for k in groups if k not in self.panels]
            removed = [k for k in self.panels if k not in groups]
            for key in removed:
                self._remove(key)
            self.texts = {e.key: f"{e.title} {e.tex} {getattr(e.location, 'place', '') or ''}".lower()
                          for e in notes.all_entries()}
            self.hits = {k for k in self.hits if k in self.texts}
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
            self._tables(groups)
            self.notes = notes
            self._arrows(notes)
            self._match()                         # the box learns the new notes
            self.settle()
            return {"added": added, "removed": removed, "panels": len(groups),
                    "arrows": len([a for a in self.arrows if not a.endswith("_leader")])}

    def focus(self, key: str | None) -> None:
        """Caption the arrows touching one panel, and clear the rest.

        The map draws no captions standing: six sentences laid over the oceans
        were unreadable, and danvas reports no geometry for a caption, so they
        could not be kept clear of anything. Pointing at a programme is the ask
        for them, and only for its own -- so a relationship says what it is,
        one node at a time."""
        if not self.map_mode:
            return
        with self.lock:
            for name, obj in self.arrow_objs.items():
                if name.endswith("_leader"):
                    continue
                a, _, b = name.partition("->")
                # an unfolded card's own arrows (open_arrows) keep their captions
                pinned = a in self.cfg.open_arrows
                want = self.why.get(name, "") if pinned or key in (a, b) else ""
                if self.shown.get(name, "") != want:
                    self.shown[name] = want
                    try:
                        obj.update(text=want or None)
                    except (KeyError, ValueError):     # disconnected mid-hover
                        self.shown.pop(name, None)

    def set_open(self, key: str, note: str | None) -> None:
        """Unfold note (or fold it if it is already open) in the panel for key."""
        with self.lock:
            pr = self.props.get(key)
            if pr is None:
                return
            pr["open"] = None if pr["open"] == note else note
            self.panels[key].update(**pr)
            self.panels[key].to_front()
            if key in self.cfg.open_arrows and self.notes is not None:
                self._arrows(self.notes)          # this panel's arrows follow its open card
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
        groups = {p.key: (self.conv.to_text(p.title), p, p.papers) for p in notes.programmes}
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

    def _width(self, key: str, node: Entry | None) -> float:
        """A panel's width: a [map] fixed entry may give its own, else the kind's."""
        spec = self.cfg.map_fixed.get(key)
        if spec and len(spec) > 2:
            return spec[2]
        return panel_w(node.kind if node else "programme")

    def _html(self, md: str) -> str:
        def inline(s: str) -> str:
            s = html.escape(s, quote=False)
            for tag in ("sup", "sub"):
                s = s.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
            s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
            s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
            return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        out, items, rows = [], [], []

        def flush():
            if items:
                out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
                items.clear()
            if rows:
                head, *body = rows
                out.append('<table class="lb"><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head)
                           + "</tr></thead><tbody>"
                           + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                           + "</tbody></table>")
                rows.clear()
        for line in md.split("\n"):
            s = line.strip()
            if s.startswith("|") and s.endswith("|"):
                if items:
                    out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
                    items.clear()
                rows.append([c.strip() for c in s[1:-1].split("|")])
                continue
            if rows:
                flush()
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

    @staticmethod
    def _dates(node: Entry | None) -> dict | None:
        """The panel's dates: text for the eye, epochs for the countdown in the browser."""
        d = node.dates if node else None
        if d is None:
            return None
        def stamp(when):
            return int(when.timestamp() * 1000) if when else None
        def span(a, b):
            if not a:
                return ""
            if not b or a.date() == b.date():
                return a.strftime("%-d %b %Y")
            same = (a.year, a.month) == (b.year, b.month)
            return f"{a.strftime('%-d')}–{b.strftime('%-d %b %Y')}" if same else \
                   f"{a.strftime('%-d %b')} – {b.strftime('%-d %b %Y')}"
        return {"text": span(d.start, d.end), "start": stamp(d.start), "end": stamp(d.end),
                "deadline": stamp(d.deadline), "deadlineLabel": d.deadline_label}

    def _props(self, key: str, title: str, node: Entry | None, papers: list[Entry]) -> dict:
        thumb = self._image(node.thumb) if node else None
        loc = node.location if node else None
        # cards in date order; undated ones keep note order at the end
        dated = sorted(papers, key=lambda p: p.year if p.year is not None else 9999)
        pdfs = self.cfg.pdf_keys()
        props = {
            "key": key, "title": title,
            "query": self.query, "filtered": bool(self.query),
            "hits": sorted(self.hits),
            "kind": node.kind if node else "programme",
            "dates": self._dates(node),
            "open": self.props[key].get("open") if key in self.props
                    else (key if key in self.cfg.open_default else None),
            "place": self.conv.to_md(loc.place) if loc else "",
            "figures": [{"src": thumb, "caption": ""}] if thumb else [],
            "html": self._html(self._own_text(key, node)) if node else "",
            "lead": self._snippet(node) if node else "",
            "link": node.link if node else None,
            "papers": [{"key": p.key, "title": self.conv.to_text(p.title), "year": str(p.year) if p.year else "",
                        "snippet": self._snippet(p), "thumb": self._image(p.thumb), "link": p.link,
                        "pdf": self.cfg.pdf_url.format(key=p.key) if p.key in pdfs else None,
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
        panel = self.canvas.react(REACT_SRC, css=css, name=key, props=props,
                                  w=self._width(key, node),
                                  frame=False, x=x, y=y)
        panel.on_error(lambda msg, key=key: print(f"[notesmap] panel {key}: {msg}", flush=True))
        panel.on("toggle")(lambda msg, key=key: self.set_open(key, msg.get("key")))
        panel.on("resize")(lambda msg, key=key: self.resize(key, msg.get("w")))
        panel.on("focus")(lambda msg, key=key: self.focus(key if msg.get("on") else None))
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

    def _own_text(self, key: str, node: Entry) -> str:
        md = node.full(self.conv)
        if key not in self.cfg.tables:
            return md
        keep = self.cfg.tables[key].get("panel")
        return tables.strip(tables.only(md, keep) if keep else md)

    def _tables(self, groups) -> None:
        """A table panel for each [tables] programme, at its fixed spot, refreshed in place.

        Each row carries its paper's DOI and PDF links, found from the note its
        first column names, so the table links straight to the sources."""
        entries = {e.key: e for g in groups.values() for e in ([g[1]] if g[1] else []) + g[2]}
        pdfs = self.cfg.pdf_keys()
        for key, spec in self.cfg.tables.items():
            prog = key.split("/")[0]          # "Prog/Name": a second panel from one programme
            node = groups[prog][1] if prog in groups else None
            data = tables.rows(node.full(self.conv), spec) if node else []
            have = self.table_panels.get(key)
            if not data:
                if have is not None:
                    self.canvas.remove(self.table_panels.pop(key)[0])
                continue
            if spec.get("view") == "radar":
                self._radar(key, spec, data, have)
                continue
            if spec.get("view") == "detectors":
                self._detector_radar(key, spec, data, have)
                continue
            first = next(iter(data[0]))
            first = next(c for c in data[0] if c != "Set") if first == "Set" else first
            for r in data:
                k = tables.keyof(r.get(first) or "", set(entries), spec.get("keys", {}))
                link = entries[k].link if k else None
                r["_doi"] = link
                r["_pdf"] = self.cfg.pdf_url.format(key=k) if k and k in pdfs else None
            scale = self.map_w / 4500 if self.map_mode else 1.0
            props = {"columns": tables.columns(data), "rows": data, "flags": spec.get("flags", {}),
                     "plain": spec.get("plain", "measured"), "scale": scale}
            chart = next(((k, s) for k, s in self.cfg.tables.items() if s.get("selector") == key), None)
            if chart:                         # this table picks what a star chart draws
                ck, cs = chart
                for r in data:
                    r["_id"] = _row_id(r, first)
                props["select"] = {"bus": ck, "initial": _sel_initial(data, cs, first),
                                   "refs": [r["_id"] for r in data if r["Set"] == cs.get("reference")],
                                   "axes": [{"key": c, "max": cs["max"][c]} for c in cs["axes"]]}
            if have is None:
                x, y, w, _ = spec["at"]
                panel = self.canvas.react(HELPERS_JSX + TABLE_SRC, css=TABLE_CSS, name=re.sub(r"\W+", "_", key) + "_table", props=props,
                                          w=w, x=x, y=y, frame=False)
                self.table_panels[key] = (panel, props)
            elif have[1] != props:
                have[0].update(**props)
                self.table_panels[key] = (have[0], props)

    def _radar(self, key: str, spec: dict, data: list[dict], have) -> None:
        """Two row sets on shared numeric axes, drawn as demand against supply."""
        label = lambda r: next(v for c, v in r.items() if c != "Set")   # each set names its own first column
        axes = [c for c in data[0] if c != "Set" and not c.endswith(" basis")
                and not c.startswith("_") and isinstance(data[0][c], float)]
        pick = lambda s: [{"name": label(r), "values": [r.get(c) or 0 for c in axes]} for r in data if r["Set"] == s]
        props = {"axes": axes, "demand": pick(spec["demand"]), "supply": pick(spec["supply"]),
                 "scale": self.map_w / 4500 if self.map_mode else 1.0}
        if have is None:
            x, y, w, _ = spec["at"]
            panel = self.canvas.react(HELPERS_JSX + RADAR_SRC, css=RADAR_CSS, name=re.sub(r"\W+", "_", key) + "_radar",
                                      props=props, w=w, x=x, y=y, frame=False)
            self.table_panels[key] = (panel, props)
        elif have[1] != props:
            have[0].update(**props)
            self.table_panels[key] = (have[0], props)

    def _detector_radar(self, key: str, spec: dict, data: list[dict], have) -> None:
        """Rows of a table panel on a radar of chosen "lower is better" columns."""
        name = next(c for c in data[0] if c != "Set")
        axes = [{"key": c, "label": l, "max": spec["max"][c]} for c, l in spec["axes"].items()]
        for a in axes:                              # an axis may switch to another column
            if a["key"] in spec.get("alternates", {}):
                a["alt"] = dict(spec["alternates"][a["key"]])
        keys = [a["key"] for a in axes] + [a["alt"]["key"] for a in axes if "alt" in a]
        rows = [{"id": _row_id(r, name), "name": r[name], "detector": r.get("Detector") or "", "set": r["Set"],
                 "v": {k: r.get(k) for k in keys},
                 "f": {k: r.get(f"_{spec.get('flag_from', {}).get(k, k)} flag", "") for k in keys}} for r in data]
        reference = [r for r in rows if r["set"] == spec.get("reference")]
        rows = [r for r in rows if r["set"] != spec.get("reference")]
        props = {"axes": axes, "rows": rows, "reference": reference, "flags": spec.get("flags", {}),
                 "bus": key, "selInitial": _sel_initial(data, spec, name),
                 "simSet": spec.get("simulated", ""), "scale": self.map_w / 4500 if self.map_mode else 1.0}
        if have is None:
            x, y, w, _ = spec["at"]
            panel = self.canvas.react(HELPERS_JSX + DETRADAR_SRC, css=DETRADAR_CSS, name=re.sub(r"\W+", "_", key) + "_radar",
                                      props=props, w=w, x=x, y=y, frame=False)
            self.table_panels[key] = (panel, props)
        elif have[1] != props:
            have[0].update(**props)
            self.table_panels[key] = (have[0], props)

    def layout_report(self) -> dict:
        """The board as the browsers measured it: every panel's box, each map
        leader's pin and panel, and which leaders cross or run under a panel."""
        from .layout import Rect, centre, crosses, through
        geo = {e["name"]: e for e in self.canvas.describe() if isinstance(e.get("h"), (int, float))}
        box = lambda e: Rect(e["x"], e["y"], e.get("w") or 0, e["h"])
        panels = {n: box(e) for n, e in geo.items() if n != "world" and not n.endswith("_pin")}
        pins = {n[:-4]: centre(box(e)) for n, e in geo.items() if n.endswith("_pin")}
        seg = {k: (pins[k], centre(panels[k])) for k in pins if k in panels}
        ks = sorted(seg)
        return {"panels": {k: [b.x, b.y, b.w, b.h] for k, b in panels.items()},
                "pins": pins,
                "crossing": [[a, b] for i, a in enumerate(ks) for b in ks[i + 1:] if crosses(seg[a], seg[b])],
                "under": [[k, o] for k in ks for o, r in panels.items() if o != k and through(seg[k], r)]}

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

    def _size(self, key: str, node: Entry | None, papers: list[Entry], geo: dict) -> tuple[float, float]:
        """A panel's width and height: what the browser measured, else the estimate."""
        w = self._width(key, node)
        g = geo.get(key)
        if g and isinstance(g.get("h"), (int, float)):
            return g.get("w", w), g["h"]
        return w, estimate_height(bool(node and node.thumb), len(papers), w)

    def _place_on_map(self, groups) -> None:
        geo = {e["name"]: e for e in self.canvas.describe()} if self.panels else {}
        # the pins are obstacles too: a panel over its own pin leaves the leader
        # nowhere to land, and over a neighbour's it reads as that programme
        # having no pin at all. They are known before anything is placed.
        taken = [Rect(px - PIN_D / 2, py - PIN_D / 2, PIN_D, PIN_D)
                 for (_, n, _) in groups.values() if n and n.location
                 for px, py in [project(n.location.lat, n.location.lon, self.map_w)]]
        shelf_x, shelf_y = self.cfg.unplaced
        fixed = self.cfg.map_fixed
        unplaced = [k for k, (_, n, _) in groups.items() if not (n and n.location) and k not in fixed]
        # the size is part of the signature, not just the location: the first pass
        # has only estimated heights, and a panel that measures taller than its
        # estimate would otherwise keep a position chosen for a shorter one, and
        # grow down over a pin or a neighbour. Only the panels that are staying
        # put are obstacles -- one about to move must not avoid where it was.
        size = {k: self._size(k, n, ps, geo) for k, (_, n, ps) in groups.items()}
        sigs = {k: ((n.location.lat, n.location.lon, n.location.offset)
                    if n and n.location else None, round(size[k][0]), round(size[k][1]))
                for k, (_, n, _) in groups.items()}
        staying = {k for k in groups if k in self.where and self.where[k][0] == sigs[k]}
        boxes = {k: Rect(self.where[k][1], self.where[k][2], *size[k]) for k in staying}
        taken += list(boxes.values())
        pins = {k: project(n.location.lat, n.location.lon, self.map_w)
                for k, (_, n, _) in groups.items() if n and n.location and k not in fixed}
        # hand offsets first: they are decisions, so the automatic panels are the
        # ones that give way, steering their leaders clear of these
        order = sorted(groups, key=lambda k: not (k in fixed or (groups[k][1] and groups[k][1].location
                                                                  and groups[k][1].location.offset)))
        for key in order:
            title, node, papers = groups[key]
            if key in staying:
                continue
            loc = node.location if node else None
            w, h = size[key]
            sig = sigs[key]
            if key in fixed:
                # a fixed spot off the map, set in notesmap.toml, and no pin
                x, y = fixed[key][0], fixed[key][1]
                self._drop_pin(key)
            elif loc is None:
                # no \location: a shelf of its own, in note order
                x, y = shelf_x + unplaced.index(key) * PITCH, shelf_y
                self._drop_pin(key)
            else:
                px, py = project(loc.lat, loc.lon, self.map_w)
                if loc.offset:
                    # an offset is a request, not a licence to cover a neighbour:
                    # two programmes in one city (a lab and its spin-off) otherwise
                    # land on top of each other
                    x, y = px + loc.offset[0], py + loc.offset[1]
                    if any(Rect(x, y, w, h).overlaps(t) for t in taken):
                        nx, ny = push_out(Rect(x, y, w, h), taken, loc.offset)
                        if (nx, ny) != (0.0, 0.0):
                            print(f"[notesmap] {key}: \\location offset overlapped a panel; "
                                  f"slid it out by {nx - x:+.0f},{ny - y:+.0f}", flush=True)
                            x, y = nx, ny
                else:
                    leaders = [(pins[k], centre(b)) for k, b in boxes.items() if k in pins]
                    x, y = auto_place((px, py), w, h, taken, leaders, list(boxes.values()),
                                      Rect(0, 0, self.map_w, self.map_w / 2))
                self._set_pin(key, px, py)
            taken.append(Rect(x, y, w, h))
            boxes[key] = Rect(x, y, w, h)
            if key in self.panels:
                self.panels[key].set_layout(x=x, y=y)
            else:
                self._create(key, x, y, groups)
            self.where[key] = (sig, x, y)
            if loc is not None and self.show_layout:
                # NOTESMAP_LAYOUT=1 prints where everything actually ended up, in
                # the form the notes take, so a layout you like can be written
                # back into main.tex instead of being recomputed every restart
                print(f"[notesmap] layout  {key}: "
                      f"\\location[{round(x - px)},{round(y - py)}]"
                      f"{{{loc.lat}}}{{{loc.lon}}}{{{loc.place}}}", flush=True)
            if loc is not None:
                self._connect(f"{key}_leader", f"{key}_pin", key,
                              color="red", size="m", arrowhead_end="none")
        # what is left crossing is between hand-placed panels: say so once, with
        # the pair, so a \location offset can be changed by hand
        crossed = tangles({k: (pins[k], boxes[k]) for k in pins if k in boxes})
        if crossed != self.crossed:
            self.crossed = crossed
            for a, b in crossed:
                print(f"[notesmap] leaders cross: {a} and {b}", flush=True)

    def _set_pin(self, key: str, px: float, py: float) -> None:
        if key in self.pins:
            self.pins[key].set_layout(x=px - PIN_D / 2, y=py - PIN_D / 2)
        else:
            # a tiny panel, not a managed shape: shapes draw beneath panels and the
            # map is a panel. decorative = no chrome, not draggable, click-through
            self.pins[key] = self.canvas.react(jsx=PIN_JSX, name=f"{key}_pin", w=PIN_D, h=PIN_D,
                                               x=px - PIN_D / 2, y=py - PIN_D / 2, decorative=True)

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
        self.why.pop(name, None)
        self.shown.pop(name, None)
        obj = self.arrow_objs.pop(name, None)
        if obj is not None:
            try:
                self.canvas.disconnect(obj)
            except (KeyError, ValueError):
                pass

    @staticmethod
    def _caption(why: str, limit: int = 80) -> str:
        """The sentence that makes a reference, cut to a label (board only).

        danvas draws the caption at the curve's midpoint and reports no geometry
        for it, so the renderer cannot know where it lands or whether it covers
        something. On the board the rows are regular enough for that to be safe;
        length is the one lever, and the full sentence is in the panel either
        way. The map draws no caption at all."""
        why = " ".join(why.split())
        if len(why) <= limit:
            return why
        cut = why[:limit].rsplit(" ", 1)[0]
        return cut.rstrip(" ,;:--") + "\u2026"

    def _arrows(self, notes: Notes) -> None:
        # every \ref between two panels is an edge, captioned by the sentence that
        # makes it; a pair referring to each other becomes one double-headed arrow
        prefixes = self.cfg.ref_prefixes
        gated = set(self.cfg.open_arrows)
        edges: dict[tuple[str, str], str] = {}
        for e in notes.all_entries():
            src = self.owner.get(e.key)
            if src is None:
                continue
            # a gated programme draws a card's arrows only while that card is unfolded
            if src in gated and self.props.get(src, {}).get("open") != e.key:
                continue
            reasons = e.ref_reasons(self.conv, prefixes)
            for r in e.refs(prefixes):
                dst = self.owner.get(r)
                if dst is not None and dst != src and (src, dst) not in edges:
                    edges[(src, dst)] = reasons.get(r, "")
        for a, b in self.cfg.prune:
            edges.pop((a, b), None)
        if not self.links:
            edges = {}                            # hidden: every arrow below is disconnected
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
            # no caption on the map: danvas draws it at the curve's midpoint and
            # reports no geometry for it, so the renderer cannot keep it clear of
            # a panel or of the next caption, and at the zoom where the whole
            # world fits it reads as prose floating in the sea. The sentence is
            # in the panel it was written in. The board has room, so it keeps it.
            # the map shows these one node at a time, on hover, so they can run
            # longer than a board label that has to sit among all the others
            self.why[name] = self._caption(why, 140 if self.map_mode else 80)
            # an open_arrows programme draws one card's few arrows at a time, so on
            # the map those keep their captions standing instead of only on hover
            standing = not self.map_mode or a in gated
            text = (self.why[name] or None) if standing else None
            if standing:
                self.shown[name] = self.why[name]
            self._connect(name, a, b, text=text, color="grey", dash="dashed", size="s",
                          bend=bend, arrowhead_start="arrow" if both else "none")
        for name in [n for n in self.arrows if not n.endswith("_leader") and n not in wanted]:
            self._disconnect(name)
