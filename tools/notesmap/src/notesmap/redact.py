"""What the board shows: the notes minus your own working.

The PDF keeps everything; the board is often public and should carry only what
the papers and programmes say. Three things are left off it:

    sections  whole \\paragraph blocks whose heading starts with one of
              [publish] hide_sections (case-insensitive), with everything up to
              the next \\paragraph
    asides    \\aside{...}: a sentence of your own inside a factual paragraph;
              typeset as normal text in the PDF
    gaps      \\gap{...}, when [publish] hide_gaps is on
    entries   programmes listed in [publish] hide_programmes, and the loose
              papers when [publish] show_loose is off

Cross-references inside any of these disappear with them, so an arrow survives
only if some shown sentence makes the reference.
"""
from __future__ import annotations

import re
from dataclasses import replace

from .latex import expand
from .parse import Entry, Notes


def _strip(tex: str, hide_sections: list[str], hide_gaps: bool) -> str:
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    tex = expand(tex, "aside", 1, lambda a: "")
    if hide_gaps:
        tex = expand(tex, "gap", 1, lambda a: "")
    if hide_sections:
        wanted = [h.lower() for h in hide_sections]
        parts = re.split(r"^(\\paragraph\{.*\})[ \t]*$", tex, flags=re.M)
        keep = [parts[0]]
        for i in range(1, len(parts), 2):
            heading = re.match(r"\\paragraph\{(.*)\}", parts[i]).group(1).lower()
            if not any(heading.startswith(w) for w in wanted):
                keep += [parts[i], parts[i + 1]]
        tex = "".join(keep)
    return tex


def _entry(e: Entry, hide_sections: list[str], hide_gaps: bool) -> Entry:
    body = _strip(e.tex, hide_sections, hide_gaps).split("\n")
    return replace(e, body=body, papers=[_entry(p, hide_sections, hide_gaps) for p in e.papers])


def redact(notes: Notes, hide_sections: list[str], hide_gaps: bool, show_loose: bool,
           hide_programmes: list[str] = ()) -> Notes:
    return Notes(
        programmes=[_entry(p, hide_sections, hide_gaps) for p in notes.programmes
                    if p.key not in hide_programmes],
        loose=[_entry(p, hide_sections, hide_gaps) for p in notes.loose] if show_loose else [],
        files=notes.files,
        warnings=notes.warnings,
    )
