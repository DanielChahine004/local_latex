"""List bibliography entries that are never cited.

Second-brain aid: park a \\bibitem in references.bib now, cite it whenever, and
run this to see what is still uncited. The reverse (citing a key with no entry)
biber already errors on, so it is not repeated here.

    python tools/uncited.py

Prints a numbered list of uncited keys, each with its annotation field (the
private "why I kept this" note) if present. Nothing if every entry is cited.
Read-only.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# One @type{key, ...body...} block, up to the next @entry or end of file.
ENTRY_RE = re.compile(r"@[a-zA-Z]+\{([^,]+),(.*?)(?=\n@|\Z)", re.DOTALL)
# \cite{a,b} \parencite[p.~5]{c} \nocite{*} ... -> the brace group after 'cite'.
# Matches any *cite command; \needcite's prose argument is harmless (it never
# equals a real key). \nocite{*} counts '*' as cited, which is the point of it.
CITE_RE = re.compile(r"cite[^{}]*\{([^}]*)\}")


def field(body, name):
    """Value of a `name = {...}` field, whitespace collapsed, or "" if absent.
    ponytail: [^}]* stops at the first }, so a value containing a literal } is
    truncated. Titles and notes here don't; widen to brace-matching if one does.
    """
    m = re.search(rf"\b{name}\s*=\s*\{{([^}}]*)\}}", body, re.DOTALL | re.IGNORECASE)
    return " ".join(m.group(1).split()) if m else ""


def entries_defined(bib):
    """{key: (title, annotation)} for every @entry in the .bib."""
    return {
        m.group(1).strip(): (field(m.group(2), "title"), field(m.group(2), "annotation"))
        for m in ENTRY_RE.finditer(bib)
    }


def keys_cited(texts):
    cited = set()
    for text in texts:
        for m in CITE_RE.finditer(text):
            cited.update(k.strip() for k in m.group(1).split(","))
    return cited


def main():
    bib = (SRC / "references.bib").read_text(encoding="utf-8")
    texts = [p.read_text(encoding="utf-8") for p in SRC.rglob("*.tex")]
    cited = keys_cited(texts)

    entries = entries_defined(bib)
    uncited = sorted(k for k in entries if k not in cited and "*" not in cited)
    for i, key in enumerate(uncited, 1):
        title, note = entries[key]
        print(f"{i}. {key}" + (f" -- {title}" if title else ""))
        if note:
            print(f"     {note}")
    if not uncited:
        print("uncited: none -- every entry is cited", file=sys.stderr)


def selftest():
    bib = ("@article{Used2020,\n title={x}}\n"
           "@book{Parked1999,\n title={Long\n  Title},\n annotation = {kept for\n  chapter 3}}")
    tex = r"Text \cite{Used2020} and \parencite[p.~5]{Used2020}, \needcite{a note}."
    entries = entries_defined(bib)
    assert set(entries) == {"Used2020", "Parked1999"}
    assert entries["Parked1999"] == ("Long Title", "kept for chapter 3")  # collapsed
    assert entries["Used2020"] == ("x", "")  # title, no annotation
    assert "Used2020" in keys_cited([tex])
    assert "Parked1999" not in keys_cited([tex])
    # multi-key and star
    assert keys_cited([r"\cite{A, B}"]) == {"A", "B"}
    assert "*" in keys_cited([r"\nocite{*}"])
    print("uncited selftest: ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
