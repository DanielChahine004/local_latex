# CLAUDE.md

PhD thesis in LaTeX, built with Tectonic via pixi. `README.md` covers setup, build
and sync; this file is the conventions.

## Build

`pixi run build` → `build/thesis/main.pdf`. Nothing else compiles the thesis.
Three standalone documents, one folder each under `src/` (`thesis/`,
`paper-notes/`, `meetings/`), every root named `main.tex`; `pixi run build-notes`
and `pixi run build-meetings` build the other two.

`units.tex` and `references.bib` live in `src/thesis/` and are the only copies.
`build-notes` passes `-Z search-path=src/thesis` so paper-notes reads them in
place.

TikZ is externalised (`\tikzexternalize` in `main.tex`): each `tikzpicture`
becomes `build/thesis/main-figureN.pdf`, remade only when its source changes.
Tectonic has no `-jobname`, so `tools/tikz-external.bat` (Linux:
`tools/tikz-external`, kept in step with it) writes a same-named driver and
compiles that; Overleaf uses pgf's stock `pdflatex` call. The build
needs `-k` (the `.md5` stamps are intermediates) and `-Z shell-escape-cwd=` at
the outdir. A figure that reads `\ref` is remade on the next pass after its
labels settle; that is pgf, not a bug. Delete `build/thesis/main-figure*` to
force a redo.

## Overleaf

The thesis lives on a paid Overleaf plan linked to the GitHub repo via
Overleaf's GitHub Sync (Overleaf Menu → GitHub → pull/push). Everything flows
local ⇄ GitHub ⇄ Overleaf: run `pixi run sync` locally, then pull from within
Overleaf, and vice versa. Live TikZ compiles fine within the paid timeout.

Only `src/thesis/` is set up as the Overleaf project root. `paper-notes` needs
the search-path flag, so it builds locally, not on Overleaf.

## Source formatting

- **Hard tabs**, one per nesting level (editor tab size 4). Never align a
  continuation line with runs of spaces; give it one level more than its parent.
- **One sentence per line, no hard wrap.** A newline only after a sentence-ending
  full stop.
- **UTF-8 without a BOM, CRLF endings.** `.editorconfig` and `.gitattributes`
  both enforce it. A BOM on an `\input` file reaches the page as a character.
  One exception, in `.gitattributes`: `src/paper-notes/**.tex` is LF, because it
  is edited live in JupyterLab (`pixi run notes-edit`), which always writes LF
  and would otherwise mark the whole file changed on every save. Those files
  never go to Overleaf, so the rule buys nothing there.
- **`% !TeX root = <path>/main.tex` heads every file that is not a root**, so a
  build triggered from a chapter or a figure finds the right document.

None of this affects the PDF. All of it keeps diffs to the line that changed.

### Comments

Keep a file header near a dozen lines. Record the constraint and the trap, not
the derivation that found them, and never restate what a guard already enforces:
`\chainfit` and the `TLBOX` hook in `pet-timeline.tex` re-derive their numbers on
demand, and measurements copied into a comment go stale the moment a label moves.

## Writing

- **Units:** `\keV{511}`, `\mm{20}`, `\ps{200}` — not raw `\qty`. Add new
  shorthands in `units.tex` beside the existing ones. For a range use siunitx's
  `\qtyrange{4}{12}{\nano\second}` directly.
- **Acronyms:** plain text in the body, no markup. The printed list in
  `src/thesis/acronyms.tex` is hand-maintained.
- **Missing citation:** `\needcite{what would satisfy this}` — prints a visible
  scaffold badge rather than passing silently as sourced fact.
- **Unwritten section:** `\topics{...}` holds its plan.
- **Labels:** every `\section` and `\subsection` carries `\label{sec:<slug>}` on
  the line directly below it, whether or not anything points there yet. Prefixes
  are `ch:`, `sec:`, `fig:`, `eq:`. Retrofitting labels across a finished thesis
  costs far more than writing them as you go.
- **House style:** British spelling (-ise, -isation), `---` unspaced for an
  em-dash, ``` ``…'' ``` for quotes, and a `~` before every cross-reference
  (`Figure~\ref{...}`, `part~1`).
- **Bibliography keys are `AuthorYear`** — `Casey1986`, `Moskal2014`. The style
  is `numeric`, so keys never reach the page. `paperstore add` makes them from
  the DOI record, and `paperstore check` holds each key to its record's first
  author and year.

## Figures

- One directory per chapter, `src/thesis/figures/<NN-name>/`, `\input` from the chapter.
- Declare every colour with `\providecolor` at the top of the figure, and prefix
  the names with the figure (`chain*`, `flow*`, `tl*`). The prefix is
  load-bearing: `\providecolor` is a silent no-op when the name is already taken,
  so two figures sharing a name on one page render the second in the first's
  palette. The document is single-palette (white page, print colours) — there is
  no theme to track.
- **Float placement:** `[p]` for a full-page TikZ figure, `[tbp]` otherwise.
  Never `h` — it strands the figure mid-paragraph.
- Every `\caption` takes a short form for the list of figures, with `\label` on
  the line after it. Captions go **below** the content for tables as well as
  figures: `\caption` after `\end{tabularx}`, never before it.
- Chain figures call `\chainfit` just before `\end{tikzpicture}`; it errors if the
  figure has outgrown its page.

## Checking figure work

The PDF is the deliverable, and TikZ fails silently — colliding labels, a figure
that overruns its page and a caption that runs off the bottom all compile clean.
After a figure or layout change, render the page and look at it:

```
pixi exec --spec poppler -- pdftoppm -r 130 -f <page> -l <page> -png build/thesis/main.pdf out
```

## Paper PDFs

`papers/` is a git-ignored clone of the private `thesis-papers` repo, a
[paperstore](https://github.com/DanielChahine004/paperstore) store:
`references.bib` (the bibliography), `<BibKey>.pdf`, `records.json` (each
DOI's doi.org record) and `annotations/<BibKey>.json`. `pixi run papers-pull`
pulls it and copies its bib over `src/thesis/references.bib`. **Never edit
`src/thesis/references.bib`:** edit `papers/references.bib`, then
`pixi run papers check`, `papers-push` and `papers-pull`. Never copy a PDF into
this repo, which is public.

`pixi run papers <command>` runs the CLI on `papers/`:

- `add <doi> --pdf <file>` makes the key and entry from the record and files the
  PDF, refusing one whose first pages show neither that DOI nor that title.
- `check` must pass before a push (CI runs it too): keys and fields agree with
  their records, every entry has its PDF, every quote is still on its page. A
  field the record gets wrong for a reason is excused on the entry,
  `nocheck = {field: reason}`; books and `nopdf = {reason}` need no PDF.
- `search <regex>`, `text <Key> [-p N]`: read a paper there before asking for it.
- `annotate <Key> "<exact quote>" [-p N] [--value 214 --unit ps --what CTR]
  [-t tag] -n "<note>" --by claude`: **every number or claim taken from a paper
  goes in as an annotation**, with the quote that says it. The quote must be
  found on its page or the command fails, so check facts by searching the PDF
  before writing them, and never paraphrase into the quote. Notes say what the
  paper says; a reading of it is flagged as one. `--figure N -p P` boxes a figure.
- `notes [-k Key] [-t tag] [--status unchecked] --json` lists them; `link <Key> <id>`
  gives the viewer URL that opens the PDF at that quote.
- In `src/paper-notes`, a sentence stating a number or finding from a paper ends
  with `\claim{Key/id}`, naming the annotation that quotes it: the map shows a
  page chip that opens the PDF at the quote, and `notes-check` fails on a claim
  with no annotation. Annotate first, then cite it.

The user reads and annotates in the viewer (danielchahine004.github.io/paperstore),
which shows first-page thumbnails from `papers/thumbs/` (`papers check --fix` makes them);
their annotations arrive as commits, so `papers-pull` before relying on them.

For a paywalled paper, use the UTS Library through Claude in Chrome. Open each
paper in its own tab through the EZproxy prefix, e.g.
`https://ieeexplore-ieee-org.ezproxy.lib.uts.edu.au/document/<id>`, or
`https://login.ezproxy.lib.uts.edu.au/login?url=<publisher URL>`. The user,
already signed in, presses PDF and drops the files back here. Chrome blocks a
page from starting several downloads at once, and the PDFs land on the
user's machine, not this server, so pre-opened tabs beat scripted downloads.
Resolve each DOI to its publisher URL first (`curl -sI https://doi.org/<doi>`):
a bare doi.org link leaves the proxy. IOP sometimes shows a CAPTCHA, which is
the user's to tick; J Nucl Med is not on the proxy but is free on its own site.
`paperstore add` checks each returned PDF against its DOI as it files it.
