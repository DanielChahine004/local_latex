# local_latex

LaTeX project built with [Tectonic](https://tectonic-typesetting.github.io/) via [pixi](https://pixi.sh/).

## Layout

- `src/thesis.tex` — thesis master document; inputs one `.tex` per chapter
- `src/chapters/` — one `.tex` per chapter
- `src/figures/<NN-name>/` — figures, one subfolder per chapter
- `src/references.bib` — bibliography (biblatex + biber)
- `build/` — compiled output, not committed
- `tools/` — standalone `biber.exe` 2.17 (matches biblatex 3.17 in Tectonic's bundle; not available via conda-forge on Windows) and a wrapper batch file used by the VS Code build

## Setup (fresh clone)

Install [pixi](https://pixi.sh), then in the repo root:

```
pixi install
```

`tools/biber.exe` is committed to the repo, so no further setup is needed.

## Build

```
pixi run build      # thesis -> build/thesis.pdf
```

In VS Code, Ctrl+Alt+B (LaTeX Workshop) builds the document the open file belongs to
(chapter files declare `% !TeX root = ../../thesis.tex`).
