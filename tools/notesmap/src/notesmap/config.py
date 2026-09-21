"""notesmap.toml -> Config. Every key is optional; paths resolve from the file's folder."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    root: Path                                   # folder the config lives in
    # [source]
    path: str = "notes/main.tex"                 # local file, or http(s) URL
    poll: float = 2.0                            # seconds between change checks
    parser: str = ""                             # "module:function"; empty: the LaTeX parser
    lock_files: list[str] = field(default_factory=lambda: [".lock"])
    # [latex]
    programme_env: str = "programnote"
    paper_env: str = "papernote"
    ref_prefixes: list[str] = field(default_factory=lambda: ["prog", "note"])
    overview_sections: list[str] = field(
        default_factory=lambda: ["what it is", "summary", "why it matters", "capsule"])
    units: dict[str, str] = field(default_factory=dict)
    macros: dict[str, str] = field(default_factory=dict)
    plugins: list[str] = field(default_factory=list)
    # [board]
    rows: list[list[str]] = field(default_factory=list)
    prune: list[list[str]] = field(default_factory=list)
    loose_key: str = "loose"
    loose_title: str = "Papers without a programme"
    # [publish]
    hide_sections: list[str] = field(default_factory=list)
    hide_gaps: bool = False
    show_loose: bool = True
    hide_programmes: list[str] = field(default_factory=list)
    # [map]
    map_image: str = ""                          # empty: the bundled Blue Marble
    map_width: int = 9000
    unplaced: list[int] = field(default_factory=lambda: [400, 3500])
    # [server]
    port: int = 8000
    title: str = "notesmap"
    edit_url: str = ""                           # a companion editor; empty: no link shown
    edit_label: str = "Edit these notes"

    def resolve(self, p: str) -> Path:
        return (self.root / p).resolve()

    @property
    def is_url(self) -> bool:
        return self.path.startswith(("http://", "https://"))


_SECTIONS = {
    "source": {"path": "path", "poll": "poll", "lock_files": "lock_files", "parser": "parser"},
    "latex": {"programme_env": "programme_env", "paper_env": "paper_env",
              "ref_prefixes": "ref_prefixes", "overview_sections": "overview_sections",
              "units": "units", "macros": "macros", "plugins": "plugins"},
    "board": {"rows": "rows", "prune": "prune", "loose_key": "loose_key",
              "loose_title": "loose_title"},
    "publish": {"hide_sections": "hide_sections", "hide_gaps": "hide_gaps", "show_loose": "show_loose",
                "hide_programmes": "hide_programmes"},
    "map": {"image": "map_image", "width": "map_width", "unplaced": "unplaced"},
    "server": {"port": "port", "title": "title", "edit_url": "edit_url",
               "edit_label": "edit_label"},
}


def load(path: Path | None) -> Config:
    if path is None:
        return Config(root=Path.cwd())
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    cfg = Config(root=path.resolve().parent)
    for section, keys in _SECTIONS.items():
        table = data.get(section, {})
        unknown = set(table) - set(keys)
        if unknown:
            raise SystemExit(f"{path}: unknown key(s) in [{section}]: {', '.join(sorted(unknown))}")
        for key, attr in keys.items():
            if key in table:
                setattr(cfg, attr, table[key])
    extra = set(data) - set(_SECTIONS)
    if extra:
        raise SystemExit(f"{path}: unknown section(s): {', '.join(sorted(extra))}")
    return cfg
