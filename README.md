# local_latex

PhD thesis in LaTeX, built with [Tectonic](https://tectonic-typesetting.github.io/)
via [pixi](https://pixi.sh/). The thesis is also on Overleaf, synced through this
GitHub repo.

## Layout

Three standalone documents, one folder each, every root named `main.tex`.

- `src/thesis/` — the thesis: `main.tex`, `chapters/` (one `.tex` per chapter),
  `figures/<NN-name>/` (one subfolder per chapter), `references.bib`
  (biblatex + biber), `acronyms.tex`, `units.tex`
- `src/paper-notes/` — working notes on papers (`pixi run build-notes`). Reads
  the thesis's `units.tex` and `references.bib` in place, via a search path the
  build task passes — there are no copies to keep in sync
- `src/meetings/` — supervisor-meeting log (`pixi run build-meetings`),
  self-contained
- `build/` — compiled output, not committed
- `tools/` — standalone `biber.exe` 2.17 (matches biblatex 3.17 in Tectonic's
  bundle; not on conda-forge for Windows) and a wrapper batch file for the
  VS Code build, plus `tikz-external.bat`, the per-figure compile behind TikZ
  externalisation. Linux twins: `get-biber.sh` (fetches biber 2.17 on first
  build), `tikz-external` and `sync.sh`

## Setup (fresh clone)

Windows (`win-64`) and Linux (`linux-64`). The `pixi run` tasks are the same on
both; on Linux the first build downloads biber 2.17 into `tools/biber/`
(gitignored). VS Code's Ctrl+Alt+B build runs through `pixi run vscode-build`,
so pixi must be on the PATH VS Code sees.

Install [pixi](https://pixi.sh), then in the repo root:

```
pixi install
```

Nothing else to set up. In VS Code, open this folder (the one containing
`.vscode/`) as the workspace.

## Build

```
pixi run build            # thesis      -> build/thesis/main.pdf
pixi run build-notes      # paper notes -> build/paper-notes/main.pdf
pixi run build-meetings   # meeting log -> build/meetings/main.pdf
```

In VS Code, Ctrl+Alt+B (LaTeX Workshop) builds the document the open file
belongs to (chapter files declare `% !TeX root = ../main.tex`).

TikZ figures are externalised: each `tikzpicture` is compiled once to
`build/thesis/main-figureN.pdf` and only recompiled when its source changes, so
the first build after a clone or a `build/` wipe is slow (one full pass per
figure) and the rest are not. Delete `build/thesis/main-figure*` to force a
redo.

## Sync

```
pixi run sync                    # message defaults to "wip: <today's date>"
pixi run sync "drafted 3.2"      # or give your own commit message
```

Commits every source change (`git add -A`), pulls with `--rebase`, then pushes.
It refuses to run on a detached HEAD or with an unfinished merge or rebase.

The thesis is on a paid Overleaf plan linked to this repo through Overleaf's
GitHub Sync. Everything flows local ⇄ GitHub ⇄ Overleaf: run `pixi run sync`
here, then pull from within Overleaf, and vice versa.
