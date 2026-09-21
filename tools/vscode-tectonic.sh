#!/usr/bin/env bash
# The Linux twin of vscode-tectonic.bat, run by LaTeX Workshop through
# `pixi run vscode-build` (tools/biber and tools/ are put on PATH here so
# tectonic finds biber and tikz-external). search-path: paper-notes reads the
# thesis's units.tex and references.bib in place.
#
# All three documents build into the one flat build/ (LaTeX Workshop's
# outDir), so they share main.aux/main.toc. A .toc left by the book-class
# thesis breaks the article-class notes ("missing \item" at main.toc:3), so
# when the document changes from the last build, the shared intermediates
# are removed first. TikZ stamps (main-figure*) are left alone.
set -euo pipefail
tools="$(cd "$(dirname "$0")" && pwd)"
bash "$tools/get-biber.sh"
export PATH="$tools/biber:$tools:$PATH"
out="$tools/../build"
doc="${!#}"
last="$(cat "$out/.last-doc" 2>/dev/null || true)"
if [ "$doc" != "$last" ]; then
	for ext in aux toc lof lot out bbl bcf blg run.xml; do rm -f "$out/main.$ext"; done
	printf '%s\n' "$doc" > "$out/.last-doc"
fi
exec tectonic -Z search-path="$tools/../src/thesis" "$@"
