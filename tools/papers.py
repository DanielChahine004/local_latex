"""The paper PDFs: a clone of the private thesis-papers repo in papers/.

    pixi run papers-pull     clone it on first use, then pull, and copy its
                             references.bib into src/thesis/
    pixi run papers-push     commit what changed in papers/ and push it
    pixi run papers-fetch    download the open-access copy of each missing PDF
    pixi run papers ...      the paperstore CLI on papers/: add, check, search,
                             text, annotate, notes (pixi run papers --help)

One file per paper, named by its key in src/thesis/references.bib:
papers/pdfs/Freire2026.pdf. The key is the index, so a \\cite or a note's key finds
its PDF with no lookup. The repo is private because most of these are under
publisher copyright; papers/ is git-ignored here so none of it reaches the
public thesis repo or Overleaf. Collaborators are added on GitHub
(Settings -> Collaborators) and can also drop PDFs in through the web page.

fetch asks OpenAlex for each DOI's open-access locations and keeps only a
response that is actually a PDF; publishers often answer a script with an HTML
page instead. What it cannot get stays listed as missing.

papers/ is a paperstore store (github.com/DanielChahine004/paperstore): its
references.bib is the bibliography, checked against each DOI's record, and
annotations/ holds notes anchored to quotes in the PDFs. pull keeps
src/thesis/references.bib a copy of that bib, merged both ways (merge_bib), so
an entry added on Overleaf reaches thesis-papers instead of being overwritten.
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPERS = REPO / "papers"
PDFS = PAPERS / "pdfs"                    # thesis-papers keeps its PDFs here (paperstore.toml pdfs)
BIB = REPO / "src" / "thesis" / "references.bib"
EXPORT = PAPERS / "references.bib"
HEADER = ("% Copied from thesis-papers/references.bib by pixi run papers-pull (and sync). An entry added or"
          " edited here goes back to thesis-papers on the next sync.\n\n")
REMOTE = "https://github.com/DanielChahine004/thesis-papers.git"
UA = "Mozilla/5.0 (thesis-papers fetch)"


def git(*args):
    subprocess.run(["git", "-C", str(PAPERS), *args], check=True)


def pull():
    if not (PAPERS / ".git").exists():
        subprocess.run(["git", "clone", REMOTE, str(PAPERS)], check=True)
    else:
        git("pull", "--rebase", "--autostash", "--quiet")
    print(f"{len(pdfs())} PDFs in papers/")
    if EXPORT.exists():
        merge_bib()


# --- the bibliography copy ---------------------------------------------------
# BIB is a copy of papers/references.bib, headed by the thesis-papers commit it
# came from. An entry changed only in the copy (added or edited on Overleaf, say)
# goes back to thesis-papers; one changed only there comes here; one changed in
# both stops the sync with both versions shown, so neither is lost.

HEAD_RE = re.compile(r"\A% Copied from thesis-papers/references\.bib(?:@([0-9a-f]{7,40}))?[^\n]*\n(?:\n)?")


def norm(text):
    return text.replace("\r\n", "\n")


def entries(text):
    """{key: entry text} for every @type{key, ...} in a .bib, braces matched."""
    out = {}
    pos = 0
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s{}]+)\s*,", text):
        if m.start() < pos or m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        depth, i = 0, text.index("{", m.start())
        for i in range(i, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                break
        pos = i + 1
        out[m.group(2)] = text[m.start():pos].strip()
    return out


def merge_bib():
    copy = norm(BIB.read_text(encoding="utf-8")) if BIB.exists() else ""
    head = HEAD_RE.match(copy)
    base_sha = head.group(1) if head else None
    mine = entries(copy)
    raw = EXPORT.read_text(encoding="utf-8")
    store_text = norm(raw)
    store = entries(store_text)
    if base_sha:
        shown = subprocess.run(["git", "-C", str(PAPERS), "show", f"{base_sha}:references.bib"],
                               capture_output=True, text=True, encoding="utf-8")
        base = entries(norm(shown.stdout)) if shown.returncode == 0 else dict(mine)
    else:
        base = dict(mine)   # no record of where the copy came from: thesis-papers wins

    back, conflicts, dropped = {}, [], []
    for key in sorted(set(mine) | set(store) | set(base)):
        b, s, m = base.get(key), store.get(key), mine.get(key)
        if m == s or m == b:
            continue                       # same, or changed only in thesis-papers
        if s == b:
            if m is None:
                dropped.append(key)        # deleted here only: thesis-papers keeps it
            else:
                back[key] = m              # added or edited here only
        else:
            conflicts.append((key, s, m))

    if conflicts:
        here = BIB.relative_to(REPO).as_posix()
        for key, s, m in conflicts:
            print(f"\n{key} differs in thesis-papers and in {here}:")
            print("--- thesis-papers\n" + (s or "(deleted)") + f"\n--- {here}\n" + (m or "(deleted)"))
        sys.exit(f"\n{len(conflicts)} conflicting entr{'y' if len(conflicts) == 1 else 'ies'}, nothing changed: "
                 f"make the two versions agree (if you edit papers/references.bib, `pixi run papers-push` it), "
                 f"then sync again")

    if back:
        for key, text in back.items():
            if key in store:
                store_text = store_text.replace(store[key], text, 1)
            else:
                store_text = store_text.rstrip("\n") + "\n\n" + text + "\n"
        EXPORT.write_text(store_text, encoding="utf-8", newline="\r\n" if "\r\n" in raw else "\n")
        git("commit", "--quiet", "-m", "references.bib: " + ", ".join(back) + " from the thesis", "--", "references.bib")
        git("push", "--quiet")
        print("sent to thesis-papers:", ", ".join(back))
        new_keys = [k for k in back if k not in store and k not in pdfs()]
        if new_keys:
            print("  no PDF yet for", ", ".join(new_keys), "- add one with: pixi run papers add <doi> --pdf <file>,"
                  " or mark it nopdf = {why}")
    if dropped:
        print("deleted only in the copy, so kept in thesis-papers:", ", ".join(dropped))

    sha = subprocess.run(["git", "-C", str(PAPERS), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    new = HEADER.replace("references.bib", f"references.bib@{sha[:12]}", 1) + store_text
    if copy != new:
        BIB.write_text(new, encoding="utf-8", newline="\r\n")
        print(f"{BIB.relative_to(REPO).as_posix()} updated from papers/")


def push():
    git("add", "-A")
    staged = subprocess.run(
        ["git", "-C", str(PAPERS), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True).stdout.split()
    if staged:
        git("commit", "--quiet", "-m", "Add " + ", ".join(Path(f).stem for f in staged))
    git("pull", "--rebase", "--quiet")
    git("push", "--quiet")
    print(f"pushed {len(staged)} file(s)" if staged else "nothing new to push")


def bib_entries(books=False):
    """{key: doi or None} for every entry in references.bib. Books, and entries
    marked `nopdf = {reason}`, are left out unless asked for: a complete reference
    cites them reliably without a PDF."""
    text = BIB.read_text(encoding="utf-8")
    entries = {}
    for m in re.finditer(r"@(\w+)\{([^,\s]+),(.*?)\n\}", text, re.S):
        kind, key, body = m.group(1).lower(), m.group(2), m.group(3)
        # a book, or an entry marked nopdf = {why}, is cited without a PDF
        if (kind == "book" or re.search(r"\bnopdf\s*=", body, re.I)) and not books:
            continue
        doi = re.search(r"\bDOI\s*=\s*\{([^}]+)\}", body, re.I)
        entries[key] = doi.group(1).strip() if doi else None
    return entries


def pdfs():
    return {p.stem for p in PDFS.glob("*.pdf")} if PDFS.exists() else set()



def get(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def candidates(doi):
    """Open-access PDF URLs for a DOI, best first."""
    try:
        work = json.loads(get("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi)))
    except (urllib.error.URLError, ValueError):
        return []
    urls = []
    for loc in [work.get("best_oa_location")] + work.get("locations", []):
        if loc and loc.get("pdf_url") and loc["pdf_url"] not in urls:
            urls.append(loc["pdf_url"])
    pmcid = (work.get("ids") or {}).get("pmcid")
    if pmcid:
        pmcid = pmcid.rsplit("/", 1)[-1]
    else:
        # OpenAlex misses many PubMed Central author manuscripts; ask Europe PMC
        try:
            hits = json.loads(get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&query="
                + urllib.parse.quote(f'DOI:"{doi}"')))["resultList"]["result"]
            pmcid = hits[0].get("pmcid") if hits else None
        except (urllib.error.URLError, ValueError, KeyError):
            pmcid = None
    if pmcid:
        urls.append(f"https://europepmc.org/articles/{pmcid}?pdf=render")
    return urls


def fetch():
    PDFS.mkdir(parents=True, exist_ok=True)
    entries, have = bib_entries(), pdfs()
    got = 0
    for key, doi in entries.items():
        if key in have or not doi:
            continue
        for url in candidates(doi):
            try:
                data = get(url, "application/pdf")
            except (urllib.error.URLError, TimeoutError, ValueError):
                continue
            if data.startswith(b"%PDF"):
                (PDFS / f"{key}.pdf").write_bytes(data)
                print(f"  fetched  {key}")
                got += 1
                break
        else:
            print(f"  no open copy  {key}")
    print(f"fetched {got}; run papers-push to share them")


if __name__ == "__main__":
    commands = {"pull": pull, "push": push, "fetch": fetch}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit("usage: papers.py " + "|".join(commands))
    commands[sys.argv[1]]()
