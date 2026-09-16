#!/usr/bin/env bash
# Fetch biber 2.17 for Linux into tools/biber/ (gitignored) on first build.
# 2.17 matches biblatex 3.17 in Tectonic's bundle and is not on conda-forge,
# the same reason tools/biber/biber.exe is committed for Windows.
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)/biber"
[ -x "$dir/biber" ] && exit 0
url="https://sourceforge.net/projects/biblatex-biber/files/biblatex-biber/2.17/binaries/Linux/biber-linux_x86_64.tar.gz/download"
sha="129d2e0332a57e985ffa253e5e9fbd28ef99af5a068d1b141145211969aa8999"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
echo "fetching biber 2.17 for Linux"
curl -fsSL -o "$tmp" "$url"
echo "$sha  $tmp" | sha256sum -c --quiet
tar -xzf "$tmp" -C "$dir" biber
chmod +x "$dir/biber"
