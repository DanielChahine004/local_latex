"""JupyterLab as the shared editor for the paper notes (`pixi run notes-edit`).

Several people open the same .tex and type in it at once; every keystroke is
merged and written straight to the file, so notesmap's watcher picks it up and
the map follows. No save, no commit, no push.

Two settings here are load-bearing:

  root_dir          only src/paper-notes is reachable, so the file browser
                    cannot reach the thesis, the build output or the tooling
  frame-ancestors   Jupyter refuses to be framed by another origin by default;
                    this lets the map at MAP_ORIGIN embed it in a panel

The token is the password. It comes from NOTES_EDIT_TOKEN, which pixi.toml
seeds with a placeholder — change it before sharing the link, and remember that
anyone holding it can edit the notes and upload files.

Reaching it from elsewhere (a tunnel, a phone):

  NOTES_EDIT_PUBLIC=1     Jupyter rejects any request whose Host header is not
                          local, which is every request through a tunnel. This
                          lifts that check, so set it only when you mean to
                          serve the editor beyond this machine.
  NOTES_MAP_ORIGIN        the address the map is served from, so it may embed
                          the editor; through a tunnel that is the https URL,
                          not 127.0.0.1.
"""
import os
from pathlib import Path

MAP_ORIGIN = os.environ.get("NOTES_MAP_ORIGIN", "http://127.0.0.1:8000")
PUBLIC = os.environ.get("NOTES_EDIT_PUBLIC", "").strip() not in ("", "0", "false", "no")
REPO = Path(__file__).resolve().parent.parent

c = get_config()  # noqa: F821  (provided by traitlets when it loads this file)

c.ServerApp.root_dir = str(REPO / "src" / "paper-notes")
c.ServerApp.ip = "127.0.0.1"
c.ServerApp.port = int(os.environ.get("NOTES_EDIT_PORT", "8891"))
c.ServerApp.open_browser = False
c.ServerApp.tornado_settings = {
	"headers": {"Content-Security-Policy": f"frame-ancestors 'self' {MAP_ORIGIN}"},
}
c.IdentityProvider.token = os.environ.get("NOTES_EDIT_TOKEN", "change-me")
c.ServerApp.allow_remote_access = PUBLIC
