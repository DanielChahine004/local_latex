"""A BibTeX file, read for the one thing `notesmap check` needs: key <-> DOI.

The notes and the thesis keep separate bibliographies -- a `\\doi{}` in a note
and an entry in `references.bib` are written at different times and nothing
connects them, so the same paper can end up noted under one DOI and cited under
another, or noted and never cited at all. This reads the `.bib` well enough to
cross-check the two, and no further: a brace-counting scan for entry keys and
their `doi` fields, with `url = {https://doi.org/...}` as a fallback for the
entries a publisher exported without a `doi` field.

Not a BibTeX parser. It does not resolve @string, crossref or concatenation,
because none of those can hold a DOI in a file biber already accepts.
"""
from __future__ import annotations

import re
from pathlib import Path

# @article{Key2026, ... -- the key runs to the first comma
_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s}]+)\s*,", re.M)
# doi = {10.x/y} | doi = "10.x/y" | doi = 10.x/y   (biber is case-insensitive)
_DOI = re.compile(r"""^\s*doi\s*=\s*(?:\{(?P<b>[^{}]*)\}|"(?P<q>[^"]*)"|(?P<r>[^,\n]+))""",
                  re.M | re.I)
_URL_DOI = re.compile(r"""^\s*url\s*=\s*[{"]?\s*https?://(?:dx\.)?doi\.org/(?P<u>[^}"\s,]+)""",
                      re.M | re.I)


def normalise(doi: str) -> str:
    """A DOI as it compares: no resolver prefix, no trailing punctuation, lower case.

    DOIs are case-insensitive by specification, and publishers are not
    consistent about it, so a case-sensitive comparison invents mismatches.
    """
    d = doi.strip().strip(".,;")
    d = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    return d.strip().rstrip("/").lower()


def _bodies(text: str):
    """(kind, key, body) per entry, body delimited by brace counting.

    A regex cannot delimit an entry: `title = {A {Nested} Brace}` and a stray
    `@` inside a field both defeat it.
    """
    for m in _ENTRY.finditer(text):
        i, depth = text.index("{", m.start()), 0
        for j in range(i, len(text)):
            c = text[j]
            if c == "{" and text[j - 1] != "\\":
                depth += 1
            elif c == "}" and text[j - 1] != "\\":
                depth -= 1
                if depth == 0:
                    yield m.group(1).lower(), m.group(2), text[i + 1:j]
                    break


class Bibliography:
    """Entry keys and their DOIs, and the lookups a cross-check needs."""

    def __init__(self, path: Path):
        self.path = path
        self.keys: dict[str, str | None] = {}            # key -> DOI or None
        self.by_doi: dict[str, list[str]] = {}           # DOI -> keys carrying it
        self.kinds: dict[str, str] = {}                  # key -> @article, @book, ...
        text = path.read_text(encoding="utf-8")
        for kind, key, body in _bodies(text):
            m = _DOI.search(body)
            doi = next((g for g in (m.group("b"), m.group("q"), m.group("r")) if g), "") if m else ""
            if not doi:
                m = _URL_DOI.search(body)
                doi = m.group("u") if m else ""
            doi = normalise(doi) if doi else None
            self.keys[key] = doi
            self.kinds[key] = kind
            if doi:
                self.by_doi.setdefault(doi, []).append(key)

    def __len__(self) -> int:
        return len(self.keys)

    @property
    def duplicate_dois(self) -> dict[str, list[str]]:
        """DOIs cited under more than one key -- two entries for one paper."""
        return {d: ks for d, ks in self.by_doi.items() if len(ks) > 1}

    @property
    def without_doi(self) -> list[str]:
        """Keys carrying no DOI. Expected for @book and @misc, not for @article."""
        return [k for k, d in self.keys.items() if not d]
