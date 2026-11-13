# phd-thesis

PhD thesis in LaTeX, built with [Tectonic](https://tectonic-typesetting.github.io/)
via [pixi](https://pixi.sh/). The thesis is also on Overleaf, kept in step by
`pixi run sync` through Overleaf's git integration. The paper notes and their map are in
[paper-notes](https://github.com/DanielChahine004/paper-notes); the meeting log is
in the private [meetings](https://github.com/DanielChahine004/meetings) repo.

## Layout

- `src/thesis/` — the thesis: `main.tex`, `chapters/` (one `.tex` per chapter),
  `figures/<NN-name>/` (one subfolder per chapter), `references.bib`
  (biblatex + biber; a copy of thesis-papers' bibliography, see Sync),
  `acronyms.tex`, `units.tex`
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
pixi run build            # -> build/thesis/main.pdf
```

In VS Code, Ctrl+Alt+B (LaTeX Workshop) builds the document the open file
belongs to (chapter files declare `% !TeX root = ../main.tex`).

TikZ figures are externalised: each `tikzpicture` is compiled once to
`build/thesis/main-figureN.pdf` and only recompiled when its source changes, so
the first build after a clone or a `build/` wipe is slow (one full pass per
figure) and the rest are not. Delete `build/thesis/main-figure*` to force a
redo.

## CI

`.github/workflows/build.yml` runs on every push. It builds the thesis with
the same Tectonic the lockfile pins and uploads `thesis.pdf` as a run artefact,
so a current PDF is downloadable from any machine without a local toolchain. Tectonic's bundle,
biber and the externalised TikZ figures are cached between runs.

## Sync

```
pixi run sync                    # message defaults to "wip: <today's date>"
pixi run sync "drafted 3.2"      # or give your own commit message
```

Commits every source change (`git add -A`), pulls with `--rebase`, merges the
bibliography with thesis-papers, then pushes. It refuses to run on a detached
HEAD or with an unfinished merge or rebase.

`src/thesis/references.bib` is a copy of
[thesis-papers](https://github.com/DanielChahine004/thesis-papers)'
bibliography, merged both ways on every sync: an entry added or edited here
(on Overleaf, say) is sent to thesis-papers, which then asks for its PDF, and
thesis-papers' own changes come here. An entry changed in both places stops the
sync with both versions shown, before anything is pushed.

The thesis is on a paid Overleaf plan, reached through its git integration: the
clone has the Overleaf project as a second remote, `overleaf`
(`git remote add overleaf https://git@git.overleaf.com/<project id>`, signed in
with an Overleaf git token). `pixi run sync` merges Overleaf's edits and pushes
to it as well as to GitHub, so there is nothing to press in Overleaf. Overleaf's
own GitHub Sync is still linked (Overleaf cannot unlink it) but is not used:
never press its GitHub buttons, or the two routes will diverge.


## Paper PDFs

```
pixi run papers-pull       # clone the store into papers/, or update it
pixi run papers-push       # share PDFs you added to papers/
pixi run papers-status     # which bibliography keys still lack a PDF
pixi run papers-fetch      # download the open-access copies of those
```

The PDFs live in a private repo,
[thesis-papers](https://github.com/DanielChahine004/thesis-papers), cloned into
the git-ignored `papers/`: one file per key in `references.bib`
(`papers/pdfs/Freire2026.pdf`). It is private, and kept out of this public repo and
Overleaf, because most of the papers are under publisher copyright. A
collaborator needs an invite (Settings → Collaborators on that repo), then can
pull and push here or upload through its web page, named by the key.
