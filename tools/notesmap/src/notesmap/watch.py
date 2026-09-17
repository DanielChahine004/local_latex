"""Poll the source and hand every good new version of the notes to a callback.

A version is taken only when it has been stable for two polls and no lock file
is present, and only if it parses; otherwise the last good one stays up.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from .parse import Notes, ParseError, parse
from .source import Source


class Watcher:
    def __init__(self, src: Source, programme_env: str, paper_env: str, poll: float,
                 lock_files: list[str], on_notes: Callable[[Notes], None]) -> None:
        self.src, self.envs, self.poll = src, (programme_env, paper_env), poll
        self.lock_files, self.on_notes = lock_files, on_notes
        self.files: list[str] = [src.main]
        self.images: set[str] = set()
        self.last: tuple | None = None
        self.reported: str | None = None

    def fingerprint(self) -> tuple:
        watched = list(self.files) + sorted(self.images)
        return tuple((f, self.src.stamp(f)) for f in watched)

    def locked(self) -> str | None:
        for name in list(self.lock_files) + [f"{f}.lock" for f in self.files]:
            rel = self.src.join(self.src.main, name)
            if self.src.exists(rel):
                return rel
        return None

    def load(self) -> Notes | None:
        """Parse now; None (and one message per distinct problem) if it fails."""
        try:
            notes = parse(self.src, *self.envs)
        except (ParseError, OSError, UnicodeDecodeError) as e:
            msg = f"[notesmap] keeping the last good version: {e}"
            if msg != self.reported:
                print(msg, flush=True)
                self.reported = msg
            return None
        self.reported = None
        self.files, self.images = notes.files, notes.images
        return notes

    def run(self) -> None:
        self.last = self.fingerprint()
        pending: tuple | None = None
        while True:
            time.sleep(self.poll)
            try:
                if (lock := self.locked()) is not None:
                    if self.reported != lock:
                        print(f"[notesmap] {lock} present, waiting", flush=True)
                        self.reported = lock
                    continue
                if self.reported is not None and not self.reported.startswith("[notesmap]"):
                    print(f"[notesmap] {self.reported} released", flush=True)
                    self.reported = None       # so the next lock is announced too
                fp = self.fingerprint()
                if fp == self.last:
                    pending = None
                    continue
                if fp != pending:          # changed since the last poll: wait for it to settle
                    pending = fp
                    continue
                notes = self.load()
                self.last = self.fingerprint() if notes else fp
                pending = None
                if notes is not None:
                    self.on_notes(notes)
            except Exception as e:         # the watcher must outlive a bad poll
                print(f"[notesmap] watch error: {e!r}", flush=True)

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self.run, name="notesmap-watch", daemon=True)
        t.start()
        return t
