"""An example parser: one Markdown file per programme, in programmes/.

    # Group -- what they build            the programme; the file name is its key
    location: 51.05, 3.72, Ghent          optional, one line each, right after a heading
    image: img/group.png
    link: https://...
    refs: OtherKey, Author2023            cross-references, drawn as arrows

    Free Markdown: the programme note. Its first paragraph is the lead line.

    ## Author et al. 2023 -- Title        a paper
    key: Author2023
    ...

Wired up with `parser = "mdnotes:parse"` in notesmap.toml. It reads through
`source`, so edits to any programme file, and files added to or removed from
programmes/, reach the map on their own.
"""
import re

from notesmap.parse import Entry, Location, Notes

FIELD = re.compile(r"^(location|image|link|refs|key):\s*(.+)$")


def _entry(kind, title, key, lines, file, line):
    given, body = {}, []
    for text in lines:
        m = FIELD.match(text.strip())
        if m and not body:                       # fields sit before the text
            name, value = m.groups()
            if name == "location":
                lat, lon, place = (v.strip() for v in value.split(",", 2))
                given["location"] = Location(float(lat), float(lon), place)
            elif name == "image":
                given["thumb"] = value.strip()
            elif name == "link":
                given["link"] = value.strip()
            elif name == "refs":
                given["refs"] = [k.strip() for k in value.split(",") if k.strip()]
            elif name == "key":
                key = value.strip()
        elif text.strip() or body:
            body.append(text)
    text = "\n".join(body).strip()
    given["full"] = text
    given["lead"] = text.split("\n\n", 1)[0]
    if "refs" in given:
        # an arrow's caption: the first sentence naming the target, else the lead
        given["reasons"] = {k: next((s for s in re.split(r"(?<=[.!?])\s+", text) if k in s), "")
                            for k in given["refs"]}
    return Entry(kind, title.strip(), key, file, line, given=given)


def parse(source, cfg):
    programmes = []
    for rel in source.listdir("programmes"):
        if not rel.endswith(".md"):
            continue
        key = rel.rsplit("/", 1)[-1][:-3]
        lines = source.read_text(rel).splitlines()
        # split at headings: "# " opens the programme, "## " each paper
        parts, cur = [], None
        for n, text in enumerate(lines, 1):
            if text.startswith("# ") or text.startswith("## "):
                cur = ["programme" if text.startswith("# ") else "paper", text.lstrip("# "), n, []]
                parts.append(cur)
            elif cur is not None:
                cur[3].append(text)
        if not parts or parts[0][0] != "programme":
            raise ValueError(f"{rel}: the first heading must be '# Programme title'")
        kind, title, n, body = parts[0]
        prog = _entry("programme", title, key, body, rel, n)
        for kind, title, n, body in parts[1:]:
            paper_key = re.sub(r"\W+", "", title.split(" -- ")[0]) or f"{key}{n}"
            prog.papers.append(_entry("paper", title, paper_key, body, rel, n))
        programmes.append(prog)
    return Notes(programmes)
