"""A programme's tabulars as one sortable table panel ([tables] in notesmap.toml).

The tabular stays the source: the PDF prints it, and the board reads the same
rows back out of the converted Markdown. A cell that is a number followed by a
letter ("1.4 p", "1200 r") splits into the number, which sorts, and the letter,
spelt out by `flags` into a "<column> basis" column, which filters. Unmarked
numbers take the basis `plain`. The paragraph a tabular sits under becomes the
`Set` column, so a measured and a simulated table stay apart after a sort.
`sets` limits a panel to the tables under the named headings, so one programme
can show differently shaped tables as separate panels (key "Prog/Name" in the
config). `derive` adds category columns from keywords in another column's text: the
first rule whose keyword appears wins, and a rule with no keywords is the
default.

Each row is tied to a note by its first column, read as "Surname Year" and
matched to the key Surname+Year, accents dropped; `keys` maps a first cell that
does not read that way ("cMiCE") to a key, or to "" for none. The board uses the
key for the row's DOI and PDF links.
"""
from __future__ import annotations

import re
import unicodedata

NUMBER = re.compile(r"^(-?\d+(?:\.\d+)?)\s*([A-Za-z]+)?\.?$")
HEADING = re.compile(r"^\*\*(.+?)\*\*$")
MISSING = {"", "–", "-", "--", "—"}


def rows(md: str, spec: dict) -> list[dict]:
    """The records of every pipe table in md, in order, typed and with derived columns."""
    flags: dict[str, str] = spec.get("flags", {})
    plain = spec.get("plain", "measured")
    section, header, raw = "", None, []
    for line in md.split("\n"):
        s = line.strip()
        m = HEADING.match(s)
        if m:
            section, header = m.group(1), None
        elif s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s[1:-1].split("|")]
            if header is None:
                header = cells
            else:
                raw.append((section, dict(zip(header, cells))))
        elif s:
            header = None
    numeric = {c for _, r in raw for c, v in r.items() if NUMBER.match(v)}
    # a column is numeric when every filled cell is a number; one stray word keeps it text
    numeric = {c for c in numeric if all(NUMBER.match(r[c]) or r[c] in MISSING for _, r in raw if c in r)}
    flagged = {c for _, r in raw for c, v in r.items() if c in numeric and (m := NUMBER.match(v)) and m.group(2)}
    sets = spec.get("sets")
    if sets:                      # a panel can take some headings' tables only
        raw = [(sec, r) for sec, r in raw if sec in sets]
        numeric = {c for c in numeric if any(c in r for _, r in raw)}
    out = []
    for section, r in raw:
        rec: dict = {"Set": section}
        for c, v in r.items():
            if c in numeric:
                m = NUMBER.match(v)
                rec[c] = float(m.group(1)) if m else None
                if c in flagged:
                    rec[f"{c} basis"] = (flags.get(m.group(2), m.group(2)) if m.group(2) else plain) if m else None
                    rec[f"_{c} flag"] = (m.group(2) or "") if m else ""
            else:
                rec[c] = None if v in MISSING else v
        derived = {}
        for name, rule in spec.get("derive", {}).items():
            text = (r.get(rule["from"]) or "").lower()
            derived.setdefault(rule["from"], {})[name] = next(
                (value for value, *words in rule["rules"] if not words or any(w.lower() in text for w in words)), None)
        # a derived column sits right after the one it is read from
        ordered = {}
        for c, v in rec.items():
            ordered[c] = v
            ordered.update(derived.get(c, {}))
        out.append(ordered)
    return out


def keyof(cell: str, known: set[str], keys: dict[str, str]) -> str | None:
    """The note a row belongs to: an explicit `keys` entry, else "Surname Year"."""
    if cell in keys:
        return keys[cell] or None
    m = re.match(r"^(\S+)\s+(\d{4})\b", cell or "")
    if not m:
        return None
    base = unicodedata.normalize("NFKD", m.group(1)).encode("ascii", "ignore").decode() + m.group(2)
    return base if base in known else None


def columns(records: list[dict]) -> list[dict]:
    """The table's columns: numeric or text, and for a number the basis column
    whose letter rides beside it rather than taking a column of its own."""
    names = [c for c in (records[0] if records else {}) if not c.startswith("_")]
    out = []
    for c in names:
        if c.endswith(" basis"):
            continue
        num = any(isinstance(r.get(c), float) for r in records)
        out.append({"name": c, "num": num, "basis": f"{c} basis" if f"{c} basis" in names else None})
    return out


def strip(md: str) -> str:
    """md without its pipe tables, for the panel that now sits beside a table panel."""
    return "\n".join(l for l in md.split("\n") if not (l.strip().startswith("|") and l.strip().endswith("|")))
