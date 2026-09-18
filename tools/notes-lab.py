"""Start the whole shared setup: the map, the editor, and a public link for each.

`pixi run notes-lab`. One command on a machine that stays on, so a lab reads the
map from anywhere and edits the notes through the link on it.

Both tunnels come from danvas's `ensure_tunnel`, which hands the port to a
detached keeper process. The keeper outlives this script, so stopping and
restarting the lab keeps the same two addresses -- the reason this works without
paying for a domain. Stop a keeper deliberately with:

    uv run --project tools/notesmap python -m danvas.tunnel --stop --port 8000

The map's edit button has to point at the editor's public address, which is only
known once its tunnel is up, so the order here is: editor tunnel, editor, map
tunnel, map. The address is passed to the map on the command line rather than
written into notesmap.toml, so nothing in the repo changes when an address does.

NOTES_EDIT_TOKEN is the editor's password. Set it before sharing the link:
anyone holding it can edit the notes and upload files. The map itself has no
password; a restart clears anything a visitor draws on it.
"""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAP_PORT = int(os.environ.get("NOTES_MAP_PORT", "8000"))
EDIT_PORT = int(os.environ.get("NOTES_EDIT_PORT", "8891"))
TOKEN = os.environ.get("NOTES_EDIT_TOKEN", "change-me")

UV = ["uv", "run", "--quiet", "--python", "3.12"]
EDITOR = ["--with", "jupyterlab", "--with", "jupyter-collaboration", "--with", "jupyterlab-iframe",
          "--no-project",
          "jupyter", "lab", "--config=tools/jupyter-notes-config.py"]

# Set up by tools/notes-editor-setup.sh: the editor runs as the `notes` user,
# which holds none of this account's keys or logins, on a bind mount of the notes
ISOLATED = Path("/opt/notes-editor")
PASSED = ["NOTES_EDIT_PUBLIC", "NOTES_EDIT_TOKEN", "NOTES_EDIT_PORT", "NOTES_MAP_ORIGIN",
          "NOTES_EDIT_ROOT"]


def tunnel(port: int, what: str, given: str):
    """The public address for a port: one you supplied, or a fresh tunnel.

    Setting NOTES_MAP_URL / NOTES_EDIT_URL skips tunnelling altogether, for a
    domain of your own pointed at these ports -- or to run the pair locally
    without exposing anything.
    """
    if given:
        print(f"[notes-lab] {what} address (given): {given}", flush=True)
        return given.rstrip("/")
    from danvas.tunnel import ensure_tunnel
    try:
        t = ensure_tunnel(port)
    except RuntimeError as e:                 # no cloudflared binary, or it never announced
        sys.exit(f"[notes-lab] could not open the {what} tunnel: {e}")
    print(f"[notes-lab] {what} tunnel: {t.url}", flush=True)
    return t.url.rstrip("/")


def spawn(args, env):
    return subprocess.Popen(UV + args, cwd=REPO, env=env)


def editor(env):
    """The editor: as the notes user when set up, else as this account."""
    if os.name != "nt" and (ISOLATED / "bin" / "jupyter-lab").exists():
        shutil.copyfile(REPO / "tools" / "jupyter-notes-config.py", ISOLATED / "config.py")
        env = dict(env, NOTES_EDIT_ROOT="/srv/paper-notes")
        print("[notes-lab] editor runs as notes", flush=True)
        return subprocess.Popen(
            ["sudo", "-n", "-u", "notes", "--preserve-env=" + ",".join(PASSED),
             str(ISOLATED / "bin" / "jupyter-lab"), f"--config={ISOLATED / 'config.py'}"],
            cwd="/", env=env)
    print("[notes-lab] WARNING: the editor runs as this account, so anyone with the"
          " password is one Jupyter bug away from its keys and logins."
          " Run `sudo bash tools/notes-editor-setup.sh` once to isolate it.", flush=True)
    return spawn(EDITOR, env)


def main() -> int:
    edit_url = tunnel(EDIT_PORT, "editor", os.environ.get("NOTES_EDIT_URL", ""))
    map_url = tunnel(MAP_PORT, "map", os.environ.get("NOTES_MAP_URL", ""))
    env = dict(os.environ,
               NOTES_EDIT_PUBLIC="1",         # Jupyter otherwise refuses non-local Hosts
               NOTES_EDIT_TOKEN=TOKEN,
               NOTES_EDIT_PORT=str(EDIT_PORT),
               NOTES_MAP_ORIGIN=map_url)      # so the map may embed the editor
    procs = [
        editor(env),
        spawn(["--project", "tools/notesmap", "notesmap", "serve", "--map", "--no-browser",
               "--port", str(MAP_PORT), "--edit-url", f"{edit_url}/lab"], env),
    ]
    print("\n".join([
        "",
        "  the lab reads:  " + map_url,
        "  and edits at:   " + edit_url + "/lab",
        "  password:       " + TOKEN + ("   <-- change NOTES_EDIT_TOKEN before sharing"
                                        if TOKEN == "change-me" else ""),
        "",
        "  Ctrl+C stops both. The tunnels keep their addresses for the next run.",
        "",
    ]), flush=True)
    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"[notes-lab] a service exited ({p.returncode}); stopping", flush=True)
                    raise KeyboardInterrupt
            time.sleep(1.0)
    except KeyboardInterrupt:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
