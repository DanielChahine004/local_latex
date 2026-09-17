"""The notes -> Notes.

A programme is `\\begin{<programme_env>}{Title}{key}`; a paper is
`\\begin{<paper_env>}{Title}{key}`, nested inside its programme or standing
alone. Each environment opens on a line of its own. `\\input` and `\\include`
in the document body are followed, so a lab can keep one file per programme
and lock them separately.

Inside an entry the parser reads, and the converter hides from the text:

    \\thumb{img/x.png}                     the image fronting the entry
    \\location[dx,dy]{lat}{lon}{place}     where a programme sits on the map;
                                          [dx,dy] optionally fixes the panel's
                                          offset from its pin, in pixels
    \\doi{..}, \\href{url}{..}, \\url{..}    the entry's link, first one wins
    \\ref{prog:key}, \\ref{note:key}        a cross-reference, drawn as an arrow
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .latex import Converter
from .source import Source


class ParseError(Exception):
    pass


@dataclass
class Location:
    lat: float
    lon: float
    place: str
    offset: tuple[float, float] | None = None


@dataclass
class Entry:
    kind: str                                    # "programme" | "paper"
    title: str
    key: str
    file: str                                    # the file it was read from, for messages
    line: int
    body: list[str] = field(default_factory=list)
    papers: list["Entry"] = field(default_factory=list)

    @property
    def tex(self) -> str:
        return "\n".join(self.body)

    @property
    def code(self) -> str:
        """The body without LaTeX comments: what macros are read from."""
        return re.sub(r"(?<!\\)%.*", "", self.tex)

    @property
    def thumb(self) -> str | None:
        # images resolve from the main file's folder, as LaTeX does, even in an \input file
        m = re.search(r"\\thumb\{([^}]*)\}", self.code)
        return m.group(1).strip() if m else None

    @property
    def images(self) -> list[str]:
        refs = re.findall(r"\\(?:thumb|includegraphics(?:\[[^\]]*\])?)\{([^}]*)\}", self.code)
        return [r.strip() for r in refs]

    @property
    def link(self) -> str | None:
        m = re.search(r"\\doi\{([^}]*)\}", self.code)
        if m:
            return "https://doi.org/" + m.group(1).strip()
        m = re.search(r"\\(?:href|url)\{([^}]*)\}", self.code)
        return m.group(1).strip() if m else None

    @property
    def location(self) -> Location | None:
        m = re.search(r"\\location(?:\[([^\]]*)\])?\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}", self.code)
        if not m:
            return None
        try:
            lat, lon = float(m.group(2)), float(m.group(3))
        except ValueError:
            raise ParseError(f"{self.file}:{self.line}: \\location for {self.key} needs numeric lat and lon")
        offset = None
        if m.group(1):
            try:
                dx, dy = (float(v) for v in m.group(1).split(","))
                offset = (dx, dy)
            except ValueError:
                raise ParseError(f"{self.file}:{self.line}: \\location[dx,dy] for {self.key} needs two numbers")
        return Location(lat, lon, m.group(4).strip(), offset)

    def refs(self, prefixes: list[str]) -> list[str]:
        pat = r"\\ref\{(?:%s):([^}]+)\}" % "|".join(map(re.escape, prefixes))
        return [k for k in dict.fromkeys(re.findall(pat, self.code)) if k != self.key]

    def ref_reasons(self, conv: Converter, prefixes: list[str]) -> dict[str, str]:
        """Target key -> the sentence that makes the reference, as an arrow caption."""
        pat = r"\\ref\{(?:%s):([^}]+)\}" % "|".join(map(re.escape, prefixes))
        out: dict[str, str] = {}
        for para in re.split(r"\n\s*\n", self.code):
            for key in dict.fromkeys(re.findall(pat, para)):
                if key == self.key or key in out:
                    continue
                text = conv.to_md(re.sub(r"^\\paragraph\{[^}]*\}", "", para.strip()))
                text = re.sub(r"\*\*\[gap:.*?\]\*\*", "", text, flags=re.S)
                text = re.sub(r"[*`>]|^- ", "", text, flags=re.M)
                # keep "et al." and initials such as "A. J." from ending a sentence
                text = re.sub(r"\b(al|vs|et|cf|e\.g|i\.e)\.", r"\1․", " ".join(text.split()))
                text = re.sub(r"\b([A-Z])\.", r"\1․", text)
                for sent in re.split(r"(?<=[.!?])\s+", text):
                    if key in sent:
                        out[key] = sent.replace("․", ".")
                        break
        return out

    def sections(self) -> list[tuple[str, str]]:
        parts = re.split(r"^\\paragraph\{([^}]*)\}", self.tex, flags=re.M)
        secs = [("", parts[0])] + [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
        return [(h, b) for h, b in secs if b.strip()]

    def overview(self, conv: Converter, wanted: list[str]) -> str:
        secs = self.sections()
        for w in wanted:
            for h, b in secs:
                if h.lower().startswith(w.lower()):
                    return conv.to_md(f"\\paragraph{{{h}}}\n{b}")
        if not secs:
            return ""
        h, b = secs[0]
        return conv.to_md(f"\\paragraph{{{h}}}\n{b}" if h else b)

    def full(self, conv: Converter) -> str:
        return conv.to_md(self.tex)


@dataclass
class Notes:
    programmes: list[Entry]
    loose: list[Entry]                           # papers outside any programme
    files: list[str]                             # every .tex file read
    warnings: list[str] = field(default_factory=list)

    def all_entries(self):
        for p in self.programmes:
            yield p
            yield from p.papers
        yield from self.loose

    @property
    def images(self) -> set[str]:
        return {img for e in self.all_entries() for img in e.images}


INPUT = re.compile(r"^[ \t]*\\(?:input|include)\{([^}]+)\}", re.M)


def _read_expanded(src: Source, rel: str, files: list[str], depth: int = 0) -> list[tuple[str, int, str]]:
    """The file as (file, line number, text) triples, with \\input followed."""
    if depth > 16:
        raise ParseError(f"{rel}: \\input nested more than 16 deep")
    files.append(rel)
    text = src.read_text(rel)
    out: list[tuple[str, int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        m = INPUT.match(line)
        if m and not line.lstrip().startswith("%"):
            child = m.group(1).strip()
            if not child.endswith(".tex"):
                child += ".tex"
            child = src.join(src.main, child)       # LaTeX resolves \input from the main file
            if src.exists(child):
                out.extend(_read_expanded(src, child, files, depth + 1))
                continue
        out.append((rel, n, line))
    return out


def parse(src: Source, programme_env: str, paper_env: str) -> Notes:
    files: list[str] = []
    lines = _read_expanded(src, src.main, files)
    # the preamble is not notes: start after \begin{document} when there is one
    for i, (_, _, text) in enumerate(lines):
        if text.strip().startswith("\\begin{document}"):
            lines = lines[i + 1:]
            break
    envs = {programme_env: "programme", paper_env: "paper"}
    begin = re.compile(r"\\begin\{(%s|%s)\}\{(.*)\}\{([^{}]*)\}\s*$"
                       % (re.escape(programme_env), re.escape(paper_env)))
    progs: list[Entry] = []
    loose: list[Entry] = []
    warnings: list[str] = []
    seen: dict[str, str] = {}
    prog: Entry | None = None
    paper: Entry | None = None
    for f, n, text in lines:
        s = text.strip()
        m = begin.match(s)
        if m:
            kind = envs[m.group(1)]
            e = Entry(kind, m.group(2), m.group(3).strip(), f, n)
            if e.key in seen:
                warnings.append(f"{f}:{n}: key {e.key!r} already used at {seen[e.key]}")
            seen[e.key] = f"{f}:{n}"
            if kind == "programme":
                if prog is not None:
                    raise ParseError(f"{f}:{n}: {programme_env} {e.key!r} opens inside {prog.key!r}")
                prog = e
                progs.append(e)
            else:
                if paper is not None:
                    raise ParseError(f"{f}:{n}: {paper_env} {e.key!r} opens inside {paper.key!r}")
                paper = e
                (prog.papers if prog else loose).append(e)
            continue
        if s == f"\\end{{{paper_env}}}":
            if paper is None:
                raise ParseError(f"{f}:{n}: \\end{{{paper_env}}} without a matching begin")
            paper = None
            continue
        if s == f"\\end{{{programme_env}}}":
            if prog is None:
                raise ParseError(f"{f}:{n}: \\end{{{programme_env}}} without a matching begin")
            if paper is not None:
                raise ParseError(f"{f}:{n}: {programme_env} {prog.key!r} closes with {paper.key!r} still open")
            prog = None
            continue
        if s.startswith("\\end{document}"):
            break
        if paper is not None:
            paper.body.append(text)
        elif prog is not None:
            prog.body.append(text)
    # an entry still open at the end is how a half-written file looks
    if paper is not None:
        raise ParseError(f"{paper.file}:{paper.line}: {paper_env} {paper.key!r} never closes")
    if prog is not None:
        raise ParseError(f"{prog.file}:{prog.line}: {programme_env} {prog.key!r} never closes")
    notes = Notes(progs, loose, files, warnings)
    for e in notes.all_entries():
        e.location                                   # raises on a malformed \location
    return notes
