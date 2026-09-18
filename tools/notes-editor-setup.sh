#!/usr/bin/env bash
# One-time, as root: `sudo bash tools/notes-editor-setup.sh`. Safe to re-run.
# Lets notes-lab run the public editor as `notes`, a system user holding no SSH
# keys, logins or tokens, instead of as the repo's owner. Even code that slips
# past the lockdown in jupyter-notes-config.py then reaches only the notes.
#
#   notes-edit          group shared by notes and the owner; src/paper-notes is
#                       group-writable and setgid, so either side can edit files
#                       the other created
#   /srv/paper-notes    bind mount of src/paper-notes, so notes needs no way into
#                       the owner's home (mode 750)
#   /opt/notes-editor   root-owned Python with JupyterLab, which notes cannot
#                       change; config.py there is copied from the repo each run
#   sudoers             the owner may start that jupyter-lab as notes, no password
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
OWNER=$(stat -c %U "$REPO")
NOTES="$REPO/src/paper-notes"
UV="$REPO/.pixi/envs/default/bin/uv"
OPT=/opt/notes-editor

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
[ -x "$UV" ] || { echo "no $UV: run 'pixi install' first" >&2; exit 1; }

getent group notes-edit >/dev/null || groupadd --system notes-edit
id notes >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/notes-editor \
	--shell /usr/sbin/nologin --gid notes-edit notes
chmod 750 /var/lib/notes-editor
usermod -aG notes-edit "$OWNER"

chgrp -R notes-edit "$NOTES"
chmod -R g+rwX "$NOTES"
find "$NOTES" -type d -exec chmod g+s {} +

mkdir -p /srv/paper-notes
grep -q ' /srv/paper-notes ' /etc/fstab || echo "$NOTES /srv/paper-notes none bind,nofail 0 0" >> /etc/fstab
mountpoint -q /srv/paper-notes || mount /srv/paper-notes

# a throwaway cache and copied files, so nothing in the venv points back into it
export UV_CACHE_DIR; UV_CACHE_DIR=$(mktemp -d)
export UV_LINK_MODE=copy
[ -x "$OPT/bin/python" ] || "$UV" venv --quiet --python /usr/bin/python3.12 "$OPT"
"$UV" pip install --quiet --python "$OPT/bin/python" --upgrade \
	jupyterlab jupyter-collaboration jupyterlab-iframe
rm -rf "$UV_CACHE_DIR"
install -o "$OWNER" -g notes-edit -m 640 "$REPO/tools/jupyter-notes-config.py" "$OPT/config.py"

RULE=/etc/sudoers.d/notes-editor
echo "$OWNER ALL=(notes) NOPASSWD:SETENV: $OPT/bin/jupyter-lab" > "$RULE.tmp"
chmod 440 "$RULE.tmp"
visudo -cqf "$RULE.tmp"
mv "$RULE.tmp" "$RULE"

echo "done. Restart the lab (Ctrl+C, then pixi run notes-lab); it should print"
echo "'[notes-lab] editor runs as notes'."
