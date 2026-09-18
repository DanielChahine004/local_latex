"""JupyterLab as the shared editor for the paper notes (`pixi run notes-edit`).

Several people open the same .tex and type in it at once; every keystroke is
merged and written straight to the file, so notesmap's watcher picks it up and
the map follows. No save, no commit, no push.

Three settings here are load-bearing:

  root_dir          only src/paper-notes is reachable, so the file browser
                    cannot reach the thesis, the build output or the tooling
  frame-ancestors   Jupyter refuses to be framed by another origin by default;
                    this lets the map at MAP_ORIGIN embed it in a panel
  NotesOnly         the server runs as whoever started it, so a terminal, kernel
                    or server extension would hand a visitor that account and
                    everything it holds (SSH keys, logins). Only file editing is
                    left; root_dir limits the file API, not code that runs.

The token is the password. It comes from NOTES_EDIT_TOKEN, falling back to
the placeholder below when unset — change it before sharing the link, and remember that
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

from jupyter_server.auth import Authorizer

MAP_ORIGIN = os.environ.get("NOTES_MAP_ORIGIN", "http://127.0.0.1:8000")
PUBLIC = os.environ.get("NOTES_EDIT_PUBLIC", "").strip() not in ("", "0", "false", "no")
REPO = Path(__file__).resolve().parent.parent

c = get_config()  # noqa: F821  (provided by traitlets when it loads this file)

# notes-lab points this at /srv/paper-notes when the editor runs as the notes
# user (tools/notes-editor-setup.sh), whose copy of this file is not in the repo
c.ServerApp.root_dir = os.environ.get("NOTES_EDIT_ROOT", str(REPO / "src" / "paper-notes"))
os.umask(0o002)  # files the editor creates stay writable by the notes-edit group
c.ServerApp.ip = "127.0.0.1"
c.ServerApp.port = int(os.environ.get("NOTES_EDIT_PORT", "8891"))
c.ServerApp.open_browser = False
c.ServerApp.tornado_settings = {
	"headers": {"Content-Security-Policy": f"frame-ancestors 'self' {MAP_ORIGIN}"},
}
c.IdentityProvider.token = os.environ.get("NOTES_EDIT_TOKEN", "change-me")
c.ServerApp.allow_remote_access = PUBLIC


class NotesOnly(Authorizer):
	"""Refuse everything that runs code or stops the server; files stay editable."""
	DENIED = {"kernels", "sessions", "terminals", "lsp", "server"}

	def is_authorized(self, handler, user, action, resource):
		return resource not in self.DENIED


c.ServerApp.authorizer_class = NotesOnly
c.ServerApp.terminals_enabled = False
# jupyterlab_iframe's server half serves any file on disk (/iframes/local) and
# proxies any URL (/iframes/proxy), past both root_dir and the authorizer. Its
# lab half, "Open IFrame" on a URL, needs neither.
c.ServerApp.jpserver_extensions = {"jupyterlab_iframe": False, "jupyter_lsp": False}
c.LabApp.extension_manager = "readonly"  # installing an extension runs pip as this account
