# /// script
# requires-python = ">=3.11"
# dependencies = ["danvas>=0.6.8", "pillow"]
# ///
"""Paper-notes as a zoomable board, one React panel per programme.

Reads src/paper-notes/main.tex. Each programme shows its title, a lead line, its
\\thumb{file} image, and a row of cards for its papers, each fronted by its own
\\thumb. \\includegraphics{file} anywhere in a note is an inline figure when the
note is unfolded; paths resolve from the paper-notes folder, as for the PDF.
Clicking a title or card unfolds the full note in place; arrows follow the notes'
\\ref cross-references. Run: pixi run notes-canvas (uv fetches danvas on first
run); edits to main.tex reload the board in place; --map pins the panels to a
world map; add --snapshot out.png to also write a PNG and layout dump once a
browser connects.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import danvas

SRC = Path(__file__).resolve().parent.parent / "src" / "paper-notes" / "main.tex"
IMG_ROOT = SRC.parent   # image paths in the notes (\thumb, \includegraphics) resolve from here

# --map: NASA Blue Marble (public domain), equirectangular, so x is linear in
# longitude and y in latitude. Scaled up so panels have room; 1 degree = 25 px.
MAP = Path(__file__).resolve().parent / "assets" / "world-blue-marble.jpg"
import os
MAP_W = int(os.environ.get("MAP_W", 9000))   # override to capture the whole map in a snapshot
MAP_H = MAP_W // 2
# programme key -> (lat, lon, panel dx, panel dy): where the pin goes, and where
# the panel hangs relative to it, chosen by hand so the European cluster fans out
PLACES = {
    "AnnPET":   (39.63,  -79.95,   100, -520),   # Morgantown WV
    "Penn":     (39.95,  -75.19,   100,  300),   # Philadelphia
    "cMiCE":    (47.65, -122.31,   100, -320),   # Seattle
    "Delft":    (52.00,    4.37,  -960, -700),
    "Ghent":    (51.05,    3.72,  -960,  200),
    "Aachen":   (50.78,    6.08,   150, -820),
    "MODE":     (50.67,    4.61,  -960, 1100),   # Louvain-la-Neuve, one of the collaboration's homes
    "OpenGATE": (45.76,    4.84,   150, 1100),   # CREATIS, Lyon
    "UTOFPET":  (43.72,   10.40,   150, 2000),   # Pisa
    "J-PET":    (50.06,   19.94,   420, -300),   # Krakow
    "i3M":      (39.48,   -0.34, -1000, 1500),   # Valencia
    "UTS":      (-33.88, 151.20,  -900, -600),   # Sydney
    "HUST":     (30.51,  114.41,  -960, -700),   # Wuhan
}
UNPLACED = (400, 3500)   # the machinery panel: no institution, so the Southern Ocean

# cross-references that are not relationships between programmes (a shared
# citation, a co-authored review) and only clutter the board; (source, target)
PRUNED_LINKS = {("i3M", "machinery"), ("Delft", "machinery")}

# --- LaTeX -> Markdown ---------------------------------------------------------

UNITS = {
    r"\milli\metre": "mm", r"\centi\metre": "cm", r"\metre": "m", r"\micro\metre": "µm",
    r"\nano\second": "ns", r"\pico\second": "ps", r"\volt": "V", r"\percent": "%",
    r"\degreeCelsius": "°C", r"\kilo\electronvolt": "keV", r"\mega\hertz": "MHz",
    r"cps\per\kilo\becquerel": "cps/kBq",
}
SHORT = {"mm": "mm", "cm": "cm", "um": "µm", "ps": "ps", "ns": "ns", "keV": "keV", "MeV": "MeV"}


def unit(s: str) -> str:
    s = s.strip()
    return UNITS.get(s, s.lstrip("\\"))


def take_args(text: str, i: int, n: int) -> tuple[list[str], int]:
    """Read n brace-delimited arguments starting at text[i]; returns (args, end)."""
    args = []
    for _ in range(n):
        while i < len(text) and text[i] in " \t":
            i += 1
        if i >= len(text) or text[i] != "{":
            break
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        args.append(text[i + 1:j])
        i = j + 1
    return args, i


def expand(text: str, macro: str, n: int, fn) -> str:
    out, i, key = [], 0, "\\" + macro
    while True:
        k = text.find(key, i)
        # must not be a longer macro name (e.g. \mm vs \mmx)
        while k != -1 and k + len(key) < len(text) and text[k + len(key)].isalpha():
            k = text.find(key, k + 1)
        if k == -1:
            out.append(text[i:])
            break
        out.append(text[i:k])
        args, end = take_args(text, k + len(key), n)
        out.append(fn(*args) if len(args) == n else text[k:end])
        i = end
    return "".join(out)


def to_md(tex: str) -> str:
    t = "\n".join(l for l in tex.splitlines() if not l.lstrip().startswith("%"))
    t = expand(t, "gap", 1, lambda a: f"**[gap: {to_md(a)}]**")
    t = expand(t, "qtyproduct", 2, lambda v, u: f"{v.replace(' x ', '×')} {unit(u)}")
    t = expand(t, "qtyrange", 3, lambda a, b, u: f"{a}–{b} {unit(u)}")
    t = expand(t, "qty", 2, lambda v, u: f"{v} {unit(u)}")
    for m, u in SHORT.items():
        t = expand(t, m, 1, lambda v, u=u: f"{v} {u}")
    t = expand(t, "emph", 1, lambda a: f"*{a}*")
    t = expand(t, "textbf", 1, lambda a: f"**{a}**")
    t = expand(t, "textsuperscript", 1, lambda a: f"<sup>{a}</sup>")
    t = expand(t, "textcolor", 2, lambda c, a: a)
    t = expand(t, "ref", 1, lambda a: a.split(":", 1)[-1])
    t = expand(t, "cite", 1, lambda a: f"[{a}]")
    t = expand(t, "label", 1, lambda a: "")
    t = expand(t, "thumb", 1, lambda a: "")          # the card image, read separately by Node.thumb
    t = expand(t, "doi", 1, lambda a: f"doi:{a}")
    t = expand(t, "href", 2, lambda u, a: a)
    t = expand(t, "url", 1, lambda a: a)
    t = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", r"\n\n![](\1)\n\n", t)   # inline figure
    t = expand(t, "paragraph", 1, lambda a: f"\n\n**{a}**\n\n")
    t = re.sub(r"\\begin\{itemize\}|\\end\{itemize\}", "\n", t)
    t = re.sub(r"\\begin\{quote\}(.*?)\\end\{quote\}", lambda m: "\n> " + " ".join(m.group(1).split()) + "\n", t, flags=re.S)
    t = re.sub(r"^\s*\\item\s*", "- ", t, flags=re.M)
    t = re.sub(r"\$([^$]+)\$", r"`\1`", t)
    for acc, plain, accented in (("'", "aeiou", "áéíóú"), ("`", "aeiou", "àèìòù"), ('"', "aeiou", "äëïöü"),
                                 ("~", "aon", "ãõñ"), ("^", "aeiou", "âêîôû")):
        for p, a in zip(plain, accented):
            t = t.replace(f"\\{acc}{p}", a).replace(f"\\{acc}{{{p}}}", a)
    t = t.replace("\\\\", " ").replace("\\ ", " ").replace("~", " ")
    t = t.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
    t = t.replace("\\%", "%").replace("\\&", "&").replace("\\$", "$").replace("\\_", "_")
    t = t.replace("\\S", "§").replace("\\textdegree", "°").replace("{,}", ",")
    t = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", t)   # any leftover \cmd{arg}
    t = re.sub(r"\\[A-Za-z]+", "", t)
    t = t.replace("{", "").replace("}", "")
    # join hard-wrapped lines inside a paragraph, keep list items and blank lines
    lines, out = t.splitlines(), []
    for l in lines:
        s = l.strip()
        if not s:
            out.append("")
        elif out and out[-1] and not s.startswith(("- ", "#", ">", "![")) and not out[-1].startswith(("#", "![")):
            out[-1] += " " + s
        else:
            out.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# --- parse the notes -------------------------------------------------------------

@dataclass
class Node:
    kind: str            # "programme" | "paper"
    title: str
    key: str
    body: list[str] = field(default_factory=list)
    papers: list["Node"] = field(default_factory=list)

    @property
    def tex(self) -> str:
        return "\n".join(self.body)

    @property
    def thumb(self) -> str | None:
        """The image fronting this entry: the first \\thumb{...} in its note."""
        m = re.search(r"\\thumb\{([^}]*)\}", self.tex)
        return m.group(1).strip() if m else None

    @property
    def link(self) -> str | None:
        """Where the paper lives online: the first \\doi{...}, \\href{url}{...} or \\url{...}."""
        m = re.search(r"\\doi\{([^}]*)\}", self.tex)
        if m:
            return "https://doi.org/" + m.group(1).strip()
        m = re.search(r"\\(?:href|url)\{([^}]*)\}", self.tex)
        return m.group(1).strip() if m else None

    @property
    def refs(self) -> list[str]:
        return [k for k in re.findall(r"\\ref\{(?:prog|note):([^}]+)\}", self.tex) if k != self.key]

    def ref_reasons(self) -> dict[str, str]:
        """Target key -> the sentence that makes the reference, as the arrow's caption."""
        out: dict[str, str] = {}
        for para in re.split(r"\n\s*\n", self.tex):
            for key in dict.fromkeys(re.findall(r"\\ref\{(?:prog|note):([^}]+)\}", para)):
                if key == self.key or key in out:
                    continue
                text = to_md(re.sub(r"^\\paragraph\{[^}]*\}", "", para.strip()))
                text = re.sub(r"\*\*\[gap:.*?\]\*\*", "", text, flags=re.S)
                text = re.sub(r"[*`>]|^- ", "", text, flags=re.M)
                # keep "et al." and initials such as "A. J." from ending a sentence
                text = re.sub(r"\b(al|vs|et|cf|e\.g|i\.e)\.", r"\1․", " ".join(text.split()))
                text = re.sub(r"\b([A-Z])\.", r"\1․", text)
                for sent in re.split(r"(?<=[.!?])\s+", text):
                    if key in sent:
                        sent = sent.replace("․", ".")
                        out[key] = sent
                        break
        return out

    def sections(self) -> list[tuple[str, str]]:
        parts = re.split(r"^\\paragraph\{([^}]*)\}", self.tex, flags=re.M)
        secs = [("", parts[0])] + [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
        return [(h, b) for h, b in secs if b.strip()]

    def overview(self) -> str:
        want = ("what it is", "summary", "why it matters", "capsule")
        for w in want:
            for h, b in self.sections():
                if h.lower().startswith(w):
                    return to_md(f"\\paragraph{{{h}}}\n{b}")
        h, b = self.sections()[0] if self.sections() else ("", "*(empty)*")
        return to_md(f"\\paragraph{{{h}}}\n{b}" if h else b)

    def full(self) -> str:
        return to_md(self.tex) or "*(empty)*"


def parse(path: Path) -> list[Node]:
    src = path.read_text(encoding="utf-8").split("\\begin{document}", 1)[1]
    begin = re.compile(r"\\begin\{(programnote|papernote)\}\{([^}]*)\}\{([^}]*)\}")
    nodes: list[Node] = []
    prog: Node | None = None
    paper: Node | None = None
    for line in src.splitlines():
        m = begin.match(line.strip())
        if m:
            kind = "programme" if m.group(1) == "programnote" else "paper"
            n = Node(kind, m.group(2), m.group(3))
            if kind == "programme":
                prog = n
                nodes.append(n)
            else:
                paper = n
                (prog.papers if prog else nodes).append(n)
            continue
        if line.strip() == "\\end{papernote}":
            paper = None
            continue
        if line.strip() == "\\end{programnote}":
            prog = None
            continue
        if paper is not None:
            paper.body.append(line)
        elif prog is not None:
            prog.body.append(line)
    return nodes


# --- the canvas ------------------------------------------------------------------

def clean_title(t: str) -> str:
    return to_md(t)


def md_to_html(md: str) -> str:
    """The small Markdown subset to_md emits: paragraphs, lists, quotes, inline marks."""
    import html
    def inline(s: str) -> str:
        s = html.escape(s, quote=False).replace("&lt;sup&gt;", "<sup>").replace("&lt;/sup&gt;", "</sup>")
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
            src = image_url(s[4:-1])
            if src:
                out.append(f'<img class="inl" src="{src}" alt="">')
        elif s.startswith("- "):
            items.append(s[2:])
        elif s.startswith("> "):
            flush(); out.append(f"<blockquote>{inline(s[2:])}</blockquote>")
        elif s:
            flush(); out.append(f"<p>{inline(s)}</p>")
        else:
            flush()
    flush()
    return "".join(out)


def data_url(path: Path) -> str:
    import base64, mimetypes
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def image_url(ref: str) -> str | None:
    """A path written in the notes -> data URL, or None (with a warning) if the file is missing."""
    p = (IMG_ROOT / ref).resolve()
    if not p.is_file():
        print(f"[notes] image not found: {ref}", flush=True)
        return None
    return data_url(p)


def year_of(title: str) -> str:
    m = re.search(r"\b(?:19|20)\d{2}\b(?:\s*onwards)?", title)
    return m.group(0) if m else ""


def snippet(node: Node) -> str:
    text = re.sub(r"\*\*[^*]+\*\*\n\n", "", node.overview(), count=1)   # drop the heading
    text = re.sub(r"!\[\]\([^)]*\)", "", text)
    plain = re.sub(r"\*\*\[gap:.*?\]\*\*", "", text, flags=re.S).strip()
    if not plain:   # an unread paper: the gap is all there is, so show it
        plain = re.sub(r"\*\*\[gap:\s*(.*?)\]\*\*", r"\1", text, flags=re.S).strip()
    first = re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0]
    return re.sub(r"[*`]", "", first)[:220]


def paper_props(canvas, p: Node) -> dict:
    return {"key": p.key, "title": clean_title(p.title), "year": year_of(p.title), "snippet": snippet(p),
            "thumb": image_url(p.thumb) if p.thumb else None, "link": p.link,   # no image: an initial
            "html": md_to_html(p.full())}


REACT_SRC = r"""
function Component({ canvas, props }) {
  const p = props;
  const open = p.open || null;
  const toggle = (k) => canvas.send({ event: "toggle", key: k });
  const openNode = open === p.key ? p : (p.papers || []).find(x => x.key === open);
  return (
    <div className="prog">
      <div className="head">
        <h1>{p.title}</h1>
        {p.link && <a className="chip" href={p.link} target="_blank" rel="noreferrer" title={p.link}>site ↗</a>}
        <button className={"chip" + (open === p.key ? " on" : "")} onClick={() => toggle(p.key)}>
          {open === p.key ? "hide programme note" : "programme note"}
        </button>
      </div>
      {p.lead && <p className="lead">{p.lead}</p>}
      {p.figures.length > 0 && (
        <div className="figs">
          {p.figures.map((f, i) => (
            <figure key={i}>
              <img src={f.src} alt={f.caption} />
              <figcaption>{f.caption}</figcaption>
            </figure>
          ))}
        </div>
      )}
      {p.papers.length > 0 && (
        <div className="cards">
          {p.papers.map(c => (
            <div key={c.key} className={"card" + (open === c.key ? " on" : "")} onClick={() => toggle(c.key)}
                 title="Click to unfold the note">
              {c.thumb ? <img src={c.thumb} alt="" /> : <div className="thumb">{c.title.slice(0, 1)}</div>}
              <div className="t">{c.title}</div>
              <div className="s">{c.snippet}</div>
              <div className="y">
                <span>{c.year}</span>
                <span className="hint">{open === c.key ? "hide note" : "note ▾"}</span>
                {c.link && <a href={c.link} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
                              title={c.link}>{c.link.includes("doi.org") ? "DOI ↗" : "link ↗"}</a>}
              </div>
            </div>
          ))}
        </div>
      )}
      {openNode && (
        <div className="note">
          <div className="nh">{openNode.title}<span onClick={() => toggle(open)}>close</span></div>
          <div dangerouslySetInnerHTML={{ __html: openNode.html }} />
        </div>
      )}
    </div>
  );
}
"""

REACT_CSS = """
.prog { font: 14px/1.45 system-ui, sans-serif; color: var(--pc-text, #ddd); padding: 12px 14px 14px;
        border: 1px solid rgba(127,127,127,.45); border-radius: 10px; background: rgba(127,127,127,.07); }
.head { display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
.prog h1 { font-size: 26px; font-weight: 500; margin: 0; }
.chip { font: 12px system-ui, sans-serif; padding: 3px 10px; border-radius: 999px; cursor: pointer;
        border: 1px solid var(--pc-accent, #3b82f6); color: var(--pc-accent, #3b82f6); background: transparent; }
.chip:hover, .chip.on { background: var(--pc-accent, #3b82f6); color: #fff; }
a.chip { text-decoration: none; }
.prog .lead { text-align: center; opacity: .8; margin: 0 auto 14px; max-width: 700px; }
.figs { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 14px; }
.figs figure { margin: 0; max-width: 100%; }
.figs img { max-height: 180px; max-width: 100%; border-radius: 4px; display: block; }
.note img.inl { display: block; max-width: 100%; max-height: 240px; margin: 8px auto; border-radius: 4px; }
.figs figcaption { font-size: 11px; opacity: .75; text-align: center; margin-top: 4px; max-width: 520px; }
.cards { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; }
.card { width: 150px; cursor: pointer; border-radius: 6px; padding: 6px; background: rgba(127,127,127,.12);
        border: 1px solid rgba(127,127,127,.3); transition: border-color .1s, background .1s; }
.card:hover { border-color: var(--pc-accent, #3b82f6); background: rgba(127,127,127,.2); }
.card.on { border-color: var(--pc-accent, #3b82f6); box-shadow: 0 0 0 1px var(--pc-accent, #3b82f6); }
.card img, .card .thumb { width: 100%; height: 96px; object-fit: cover; border-radius: 4px; display: block; }
.card .thumb { display: grid; place-items: center; font-size: 40px; background: rgba(127,127,127,.25); }
.card .t { font-weight: 600; font-size: 12px; margin: 6px 0 2px; display: -webkit-box; -webkit-line-clamp: 3;
           -webkit-box-orient: vertical; overflow: hidden; }
.card .s { font-size: 10.5px; opacity: .8; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical;
           overflow: hidden; }
.card .y { font-size: 11px; opacity: .8; margin-top: 6px; display: flex; gap: 8px; align-items: center; }
.card .y .hint { margin-left: auto; color: var(--pc-accent, #3b82f6); }
.card .y a { color: var(--pc-accent, #3b82f6); text-decoration: none; font-weight: 600; }
.note { margin-top: 14px; padding: 10px 12px; border-top: 1px solid rgba(127,127,127,.4); }
.note .nh { font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 6px; }
.note .nh span { cursor: pointer; opacity: .6; font-weight: 400; }
.note p, .note li { margin: 0 0 8px; }
.note blockquote { margin: 0 0 8px 12px; opacity: .85; }
.note code { font-size: 12px; }
"""


def main() -> None:
    nodes = parse(SRC)
    canvas = danvas.Canvas()
    panels: dict[str, object] = {}
    props_of: dict[str, dict] = {}
    W, PITCH, ROW_GAP = 880, 920, 100

    progs = [n for n in nodes if n.kind == "programme"]
    loose = [n for n in nodes if n.kind == "paper"]
    groups = {p.key: (clean_title(p.title), p, p.papers) for p in progs}
    if loose:
        groups["machinery"] = ("Machinery (no programme)", None, loose)

    # rows by relationship, ordered so that linked panels sit side by side and
    # most cross-reference arrows stay short; anything new lands in a final row
    ROWS = [
        ["i3M", "AnnPET", "HUST", "Delft", "machinery"],    # the annulus cluster and what it cites
        ["cMiCE", "Ghent", "UTOFPET", "Aachen", "J-PET"],   # neural localisation and its precursors
        ["MODE", "OpenGATE", "UTS", "Penn"],                # tooling stubs and history
    ]
    placed = {k for row in ROWS for k in row}
    rows = [[k for k in row if k in groups] for row in ROWS] + [[k for k in groups if k not in placed]]
    rows = [r for r in rows if r]

    map_mode = "--map" in sys.argv
    if map_mode:
        # the world map is a click-through backdrop; each programme gets a pin at
        # its institution and its panel hangs off the pin by a leader line, offset
        # so the European cluster fans out instead of piling up. The image panel
        # shows a picture at its own pixel size, so the 2048 px source is
        # upscaled in memory to the canvas size it must cover.
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.open(MAP).resize((MAP_W, MAP_H), Image.BICUBIC).save(buf, "JPEG", quality=80)
        canvas.image(buf.getvalue(), name="world", w=MAP_W, h=MAP_H, x=0, y=0, decorative=True)

    # since danvas 0.6.8 arrows share the panels' z-order, so an open note brought
    # to the front sits above every arrow while the arrows stay above the map
    arrows = []

    def link(start, end, **kw):
        arrows.append(a := canvas.connect(start, end, **kw))
        return a

    def make_panel(key, x, y):
        title, node, papers = groups[key]
        props_of[key] = {
            "key": key, "title": title, "open": None,
            "figures": [{"src": u, "caption": ""}] if node and node.thumb and (u := image_url(node.thumb)) else [],
            "html": md_to_html(node.full()) if node else "",
            "lead": snippet(node) if node else "",
            "link": node.link if node else None,
            # cards in date order, from the year in each title; undated ones keep file order at the end
            "papers": [paper_props(canvas, p) for p in
                       sorted(papers, key=lambda p: int(year_of(p.title)[:4]) if year_of(p.title) else 9999)],
        }
        css = REACT_CSS + (".prog { background: #12151c; }" if map_mode else "")   # opaque over terrain
        panels[key] = canvas.react(REACT_SRC, css=css, name=key, props=props_of[key], w=W,
                                   frame=False, x=x, y=y)
        panels[key].on_error(lambda msg, key=key: print(f"[react:{key}] {msg}", flush=True))
        for p in papers:
            panels[p.key] = panels[key]

    if map_mode:
        for key in groups:
            lat, lon, dx, dy = PLACES.get(key, (None, None, 0, 0))
            if lat is None:
                make_panel(key, *UNPLACED)
                continue
            px, py = (lon + 180) * MAP_W / 360, (90 - lat) * MAP_H / 180
            # a tiny panel, not a managed shape: shapes draw beneath panels, so
            # the map image would cover them. decorative = no chrome, not
            # selectable or draggable, click-through; the leader arrow still binds
            pin = canvas.react(jsx='<div style="width:30px;height:30px;border-radius:50%;background:#e5322d;'
                                   'border:4px solid #fff;box-shadow:0 0 8px #000"></div>',
                               name=f"{key}_pin", w=38, h=38, x=px - 19, y=py - 19, decorative=True)
            make_panel(key, px + dx, py + dy)
            link(pin, panels[key], color="red", size="m", arrowhead_end="none", name=f"{key}_leader")
        rows = []   # nothing to re-stack: on the map every panel stands alone
    else:
        # placed by coordinate and re-stacked by repack(): relative anchors (below=)
        # resolve once against a default height and never move when a React panel's
        # auto-height settles or a note unfolds, so the rows are packed from the
        # heights the browser reports instead
        for ri, row in enumerate(rows):
            for ci, key in enumerate(row):
                make_panel(key, 40 + ci * PITCH, 40 + ri * 500)

    def repack():
        """Rows take their height from the tallest rendered panel, read back from
        the browser, so an unfolded note pushes the rows below it down."""
        if not rows:
            return
        hs = {e["name"]: e["h"] for e in canvas.describe() if isinstance(e.get("h"), (int, float))}
        y = 40
        for row in rows:
            for key in row:
                panels[key].set_layout(y=y)
            y += max(hs.get(k, 300) for k in row) + ROW_GAP

    def repack_later(*delays: float):
        import threading, time
        for d in delays:
            threading.Thread(target=lambda d=d: (time.sleep(d), repack()), daemon=True).start()

    @canvas.on_connect
    def _(viewer):
        repack_later(3.0, 8.0)   # long panels settle their height later than short ones

    # the browser reports a panel's fitted height through the same layout
    # message as a user drag, so every height change re-stacks the rows
    # (debounced: a growing note reports several times)
    tick = [0]

    def on_layout(comp):
        tick[0] += 1
        mine = tick[0]
        import threading, time

        def go():
            time.sleep(0.4)
            if tick[0] == mine:
                repack()
        threading.Thread(target=go, daemon=True).start()

    for key in list(groups):
        panels[key].on_layout(on_layout)

    def set_open(key: str, note: str | None):
        """Python owns which note is unfolded, so it can also drive it (tests, links)."""
        pr = props_of[key]

        pr["open"] = None if pr["open"] == note else note
        panels[key].update(**pr)
        panels[key].to_front()   # above its neighbours and, since 0.6.8, above the arrows too
        repack_later(1.0, 3.0)

    for key in list(groups):
        @panels[key].on("toggle")
        def _(msg, key=key):
            set_open(key, msg.get("key"))

    # every \ref between two panels is an edge, captioned by the sentence that
    # makes it; a pair referring to each other becomes one double-headed arrow
    edges: dict[tuple[str, str], str] = {}
    for n in nodes + [p for pr in progs for p in pr.papers]:
        reasons = n.ref_reasons()
        for r in n.refs:
            a, b = panels.get(n.key), panels.get(r)
            if a is not None and b is not None and a is not b and (a.name, b.name) not in edges:
                edges[(a.name, b.name)] = reasons.get(r, "")
    for src, dst in PRUNED_LINKS:
        edges.pop((src, dst), None)
    col_of = {k: (ri, ci) for ri, row in enumerate(rows) for ci, k in enumerate(row)}
    drawn = set()
    for (sa, sb), why in edges.items():
        if (sb, sa) in drawn:
            continue
        both = (sb, sa) in edges
        a, b = panels[sa], panels[sb]
        # neighbours get a straight arrow; anything longer arcs clear of the panels between
        if map_mode:
            bend = 120
        else:
            (ra, ca), (rb, cb) = col_of[sa], col_of[sb]
            bend = 0 if ra == rb and abs(ca - cb) == 1 else 140
        link(a, b, text=why or None, color="grey", dash="dashed", size="s", bend=bend,
             arrowhead_start="arrow" if both else "none", name=f"{sa}->{sb}")
        drawn.add((sa, sb))

    def raise_panels():
        """Stack: map, then the arrows, then pins and panels. Panel moves persist
        across reload while an arrow's to_back is live-only (danvas 0.6.8), so
        the arrows stay where they were drawn and everything except the map is
        raised above them. Repeated after a viewer connects: a panel's late
        height report can put it back beneath the arrows."""
        if not map_mode:
            return
        for a in arrows:
            a.to_back()
        canvas["world"].to_back()

    raise_panels()

    @canvas.on_connect
    def _(viewer):
        import threading, time
        for d in (3.0, 9.0):
            threading.Thread(target=lambda d=d: (time.sleep(d), raise_panels()), daemon=True).start()

    snapshot = sys.argv[sys.argv.index("--snapshot") + 1] if "--snapshot" in sys.argv else None
    # open on the map's centre with the whole world in view; the board view frames its panels
    view = {"grid": False, "zoom": 0.2, "x": MAP_W / 2, "y": MAP_H / 2} if map_mode else {"grid": True, "zoom": 0.5}
    # hot_reload re-runs this script when main.tex or an image it pulls in
    # changes, so an edit reaches the open tab without a relaunch; the watch
    # globs resolve from this file's folder, not the cwd. It needs block=True,
    # so --snapshot, which serves in the background, goes without.
    live = snapshot is None
    canvas.serve(port=8000, view=view, block=live, hot_reload=live,
                 watch=["../src/paper-notes/*.tex", "../src/paper-notes/img/**/*"])
    if snapshot:
        # wait for a browser tab (the only thing that can render), write a PNG and
        # the resolved layout, then unfold one note and write both again so the
        # anchored panels' shift can be checked; keep serving afterwards
        import json, threading, time
        for _ in range(120):
            if canvas.viewers:
                break
            time.sleep(0.5)
        time.sleep(12)
        out = Path(snapshot)
        # the full map is 9000 x 4500 and its render times out, so frame a few panels there
        import os
        keys = os.environ.get("SNAP_KEYS", "i3M,AnnPET,Penn").split(",")   # which panels to frame on the map
        frame = None if not map_mode or keys == ["all"] else [panels[k] for k in keys if k in panels]
        canvas.screenshot(frame, path=snapshot)
        out.with_suffix(".json").write_text(json.dumps(canvas.describe(), indent=1, default=str))
        set_open("AnnPET", "AnnPET")
        time.sleep(10)
        out.with_name(out.stem + "_open.json").write_text(json.dumps(canvas.describe(), indent=1, default=str))
        try:
            canvas.screenshot(frame, path=str(out.with_name(out.stem + "_open.png")))
        except TimeoutError as e:   # a render that takes too long must not take the server down
            print(f"[snapshot] second screenshot skipped: {e}", flush=True)
        set_open("AnnPET", "AnnPET")   # close it again: the arrows must come back
        time.sleep(4)
        out.with_name(out.stem + "_closed.json").write_text(json.dumps(canvas.describe(), indent=1, default=str))
        print(f"[snapshot] wrote {snapshot}", flush=True)
        threading.Event().wait()


if __name__ == "__main__":
    main()
