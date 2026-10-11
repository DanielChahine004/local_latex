"""The paper PDFs: a clone of the private thesis-papers repo in papers/.

    pixi run papers-pull     clone it on first use, then pull
    pixi run papers-push     commit what was added to papers/ and push it
    pixi run papers-status   which bibliography keys have a PDF and which lack one
    pixi run papers-fetch    download the open-access copy of each missing one

One file per paper, named by its key in src/thesis/references.bib:
papers/Freire2026.pdf. The key is the index, so a \\cite or a note's key finds
its PDF with no lookup. The repo is private because most of these are under
publisher copyright; papers/ is git-ignored here so none of it reaches the
public thesis repo or Overleaf. Collaborators are added on GitHub
(Settings -> Collaborators) and can also drop PDFs in through the web page.

fetch asks OpenAlex for each DOI's open-access locations and keeps only a
response that is actually a PDF; publishers often answer a script with an HTML
page instead. What it cannot get stays listed as missing.
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
BIB = REPO / "src" / "thesis" / "references.bib"
REMOTE = "https://github.com/DanielChahine004/thesis-papers.git"
UA = "Mozilla/5.0 (thesis-papers fetch)"


def git(*args):
    subprocess.run(["git", "-C", str(PAPERS), *args], check=True)


def pull():
    if not (PAPERS / ".git").exists():
        subprocess.run(["git", "clone", REMOTE, str(PAPERS)], check=True)
    else:
        git("pull", "--rebase", "--quiet")
    print(f"{len(pdfs())} PDFs in papers/")


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


def bib_entries():
    """{key: doi or None} for every entry in references.bib."""
    text = BIB.read_text(encoding="utf-8")
    entries = {}
    for m in re.finditer(r"@\w+\{([^,\s]+),(.*?)\n\}", text, re.S):
        doi = re.search(r"\bDOI\s*=\s*\{([^}]+)\}", m.group(2), re.I)
        entries[m.group(1)] = doi.group(1).strip() if doi else None
    return entries


def pdfs():
    return {p.stem for p in PAPERS.glob("*.pdf")} if PAPERS.exists() else set()


def status():
    entries, have = bib_entries(), pdfs()
    missing = [k for k in entries if k not in have]
    stray = sorted(have - entries.keys())
    print(f"{len(entries) - len(missing)} of {len(entries)} bibliography entries have a PDF")
    for k in missing:
        print(f"  missing  {k}" + ("" if entries[k] else "  (no DOI)"))
    for k in stray:
        print(f"  no bib entry for papers/{k}.pdf")


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
        urls.append(f"https://europepmc.org/articles/{pmcid.rsplit('/', 1)[-1]}?pdf=render")
    return urls


def fetch():
    PAPERS.mkdir(exist_ok=True)
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
                (PAPERS / f"{key}.pdf").write_bytes(data)
                print(f"  fetched  {key}")
                got += 1
                break
        else:
            print(f"  no open copy  {key}")
    print(f"fetched {got}; run papers-push to share them")


if __name__ == "__main__":
    commands = {"pull": pull, "push": push, "status": status, "fetch": fetch}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit("usage: papers.py " + "|".join(commands))
    commands[sys.argv[1]]()
