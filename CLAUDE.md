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

Neither affects the PDF. Both keep diffs to the sentence that actually changed.

## Writing

- **Units:** `\keV{511}`, `\mm{20}`, `\ps{200}` — not raw `\qty`. Add new
  shorthands in `units.tex` beside the existing ones. For a range use siunitx's
  `\qtyrange{4}{12}{\nano\second}` directly.
- **Acronyms:** plain text in the body, no markup. The printed list in
  `src/thesis/acronyms.tex` is hand-maintained.
- **Missing citation:** `\needcite{what would satisfy this}` — prints a visible
  scaffold badge rather than passing silently as sourced fact.
- **Unwritten section:** `\topics{...}` holds its plan.

## Figures

- One directory per chapter, `src/thesis/figures/<NN-name>/`, `\input` from the chapter.
- Declare every colour with `\providecolor` at the top of the figure. The
  document is single-palette (white page, print colours) — there is no theme to
  track.
- Chain figures call `\chainfit` just before `\end{tikzpicture}`; it errors if the
  figure has outgrown its page.

## Checking figure work

The PDF is the deliverable, and TikZ fails silently — colliding labels, a figure
that overruns its page and a caption that runs off the bottom all compile clean.
After a figure or layout change, render the page and look at it:

```
pixi exec --spec poppler -- pdftoppm -r 130 -f <page> -l <page> -png build/thesis/main.pdf out
```
