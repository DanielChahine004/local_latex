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
pixi run build      # thesis -> build/thesis.pdf
```

In VS Code, Ctrl+Alt+B (LaTeX Workshop) builds the document the open file belongs to
(chapter files declare `% !TeX root = ../../thesis.tex`).
