"""Where the notes live, and whether they have changed.

Two sources, one interface. Paths inside the notes (\\input, \\thumb,
\\includegraphics) are relative to the main file's folder, as LaTeX reads them.

    LocalSource  a folder on disk: a checkout, or a bucket mounted or synced
                 locally (rclone, Syncthing, Dropbox, a network share)
    HttpSource   a folder behind http(s): a public or presigned bucket URL, or
                 any static file server; change detection uses ETag or
                 Last-Modified from a HEAD request

Readers never take a lock. Writers that do lock signal it with a lock file
(by default `.lock` beside the main file, or `<file>.tex.lock`); while one
exists the watcher holds the last good render instead of reading a file that
may be half written.
"""
from __future__ import annotations

import base64
import mimetypes
import posixpath
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin


class Source:
    main: str                                    # the main file, relative to the base

    def read_text(self, rel: str) -> str:
        return self.read_bytes(rel).decode("utf-8")

    def read_bytes(self, rel: str) -> bytes:
        raise NotImplementedError

    def stamp(self, rel: str) -> str | None:
        """An opaque version token, or None if the file does not exist."""
        raise NotImplementedError

    def exists(self, rel: str) -> bool:
        return self.stamp(rel) is not None

    def describe(self) -> str:
        raise NotImplementedError

    def data_url(self, rel: str) -> str | None:
        try:
            data = self.read_bytes(rel)
        except (OSError, urllib.error.URLError):
            return None
        mime = mimetypes.guess_type(rel)[0] or "application/octet-stream"
        return f"data:{mime};base64," + base64.b64encode(data).decode()

    @staticmethod
    def join(base_rel: str, ref: str) -> str:
        """ref as written in base_rel, relative to the source's base folder."""
        return posixpath.normpath(posixpath.join(posixpath.dirname(base_rel), ref))


class LocalSource(Source):
    def __init__(self, main_file: Path) -> None:
        self.base = main_file.parent
        self.main = main_file.name

    def _p(self, rel: str) -> Path:
        return self.base / rel

    def read_bytes(self, rel: str) -> bytes:
        return self._p(rel).read_bytes()

    def stamp(self, rel: str) -> str | None:
        try:
            st = self._p(rel).stat()
        except OSError:
            return None
        return f"{st.st_mtime_ns}:{st.st_size}"

    def describe(self) -> str:
        return str(self._p(self.main))


class HttpSource(Source):
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.base_url = url.rsplit("/", 1)[0] + "/"
        self.main = url.rsplit("/", 1)[1]
        self.timeout = timeout

    def _url(self, rel: str) -> str:
        return urljoin(self.base_url, rel)

    def read_bytes(self, rel: str) -> bytes:
        with urllib.request.urlopen(self._url(rel), timeout=self.timeout) as r:
            return r.read()

    def stamp(self, rel: str) -> str | None:
        req = urllib.request.Request(self._url(rel), method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                h = r.headers
                return h.get("ETag") or h.get("Last-Modified") or h.get("Content-Length") or "present"
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            raise

    def describe(self) -> str:
        return self._url(self.main)


def open_source(path: str, root: Path) -> Source:
    if path.startswith(("http://", "https://")):
        return HttpSource(path)
    return LocalSource((root / path).resolve())
