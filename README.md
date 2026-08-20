# local_latex

LaTeX project built with [Tectonic](https://tectonic-typesetting.github.io/) via [pixi](https://pixi.sh/).

## Layout

Three standalone documents, one folder each. Every folder is self-contained so
its *contents* can be uploaded as an Overleaf project, and every root is named
`main.tex` so Overleaf auto-detects it.

- `src/thesis/` — the thesis: `main.tex`, `chapters/` (one `.tex` per chapter),
  `figures/<NN-name>/` (one subfolder per chapter), `references.bib`
  (biblatex + biber), `acronyms.tex`, and the shared `units.tex` / `theme.tex`
- `src/paper-notes/` — standalone paper-notes document (`pixi run build-notes`).
  Its `units.tex`, `theme.tex` and `references.bib` are **copies made by the
  build task** — edit the canonical ones in `src/thesis/`
- `src/meetings/` — standalone supervisor-meeting log (`pixi run build-meetings`),
  fully self-contained
- `build/` — compiled output, not committed
- `tools/` — standalone `biber.exe` 2.17 (matches biblatex 3.17 in Tectonic's bundle; not available via conda-forge on Windows) and a wrapper batch file used by the VS Code build

## Setup (fresh clone)

Windows only: `pixi.toml` targets `win-64` and `tools/biber/biber.exe` is a
Windows binary. Other platforms need a matching biber and platform added to
`pixi.toml`.

Install [pixi](https://pixi.sh), then in the repo root:

```
pixi install
```

`tools/biber/biber.exe` and `build/` are committed, so no further setup is
needed. In VS Code, open this folder (the one containing `.vscode/`) as the
workspace.

## Build

```
pixi run build            # thesis      -> build/thesis/main.pdf
pixi run build-notes      # paper notes -> build/paper-notes/main.pdf
pixi run build-meetings   # meeting log -> build/meetings/main.pdf
```

In VS Code, Ctrl+Alt+B (LaTeX Workshop) builds the document the open file belongs to
(chapter files declare `% !TeX root = ../main.tex`).

## Publish

One command at the end of a writing session:

```
pixi run publish                    # message defaults to "wip: <today's date>"
pixi run publish "drafted 3.2"      # or give your own commit message
```

It builds `main.pdf` (published as `thesis.pdf`) and `meetings.pdf`, commits every source change (`git add
-A`) and pushes the current branch, then force-pushes the two PDFs to the `pdf`
branch. If either document fails to compile, nothing is committed or pushed.

GitHub renders PDFs in the browser, so the latest build is always readable at
<https://github.com/DanielChahine004/local_latex/blob/pdf/thesis.pdf>.

The `pdf` branch is rebuilt each time as a single *parentless* commit, so it
holds only the current PDFs and never grows. No PDF ever enters the source
history — walking `main` back gives source only, and `pixi run build` rebuilds
the PDF from it.

Publishing refuses to run on a detached HEAD, with unresolved merge conflicts,
or if the tree is somehow still dirty after committing — so the source revision
stamped on each published PDF always describes the source it was built from.
