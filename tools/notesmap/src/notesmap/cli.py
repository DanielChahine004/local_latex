"""notesmap serve | check | init.

    notesmap serve [--map] [--config notesmap.toml]   the live board or world map
    notesmap check [--config notesmap.toml]           lint the notes, no browser
    notesmap init DIR                                 starter notes for a new lab
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
import time
from pathlib import Path

from . import config as config_mod
from .latex import Converter
from .parse import load_parser
from .source import open_source

TEMPLATES = Path(__file__).parent / "templates"


def _setup(args):
    cfg_path = Path(args.config) if args.config else (Path("notesmap.toml") if Path("notesmap.toml").exists() else None)
    cfg = config_mod.load(cfg_path)
    src = open_source(cfg.path, cfg.root)
    conv = Converter(cfg.units)
    for name, template in cfg.macros.items():
        conv.add_template(name, template)
    conv.load_plugins(cfg.plugins, cfg.root)
    parser = load_parser(cfg.parser, cfg.root)
    return cfg, src, conv, parser


def cmd_check(args) -> int:
    cfg, src, conv, parser = _setup(args)
    try:
        notes = parser(src, cfg)
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}")
        return 1
    problems = list(notes.warnings)
    keys = {e.key for e in notes.all_entries()}
    for e in notes.all_entries():
        for img in e.images:
            if not src.exists(img):
                problems.append(f"{e.file}:{e.line}: {e.key}: image not found: {img}")
        for r in e.refs(cfg.ref_prefixes):
            if r not in keys:
                problems.append(f"{e.file}:{e.line}: {e.key}: \\ref to unknown key {r!r}")
    for p in notes.programmes:
        if p.location is None:
            problems.append(f"{p.file}:{p.line}: {p.key}: no \\location (shelved on the map)")
    files = set(notes.files) | (src.touched - notes.images)
    print(f"{src.describe()}: {len(files)} file(s), {len(notes.programmes)} programmes, "
          f"{sum(len(p.papers) for p in notes.programmes)} papers in programmes, {len(notes.loose)} loose")
    for p in notes.programmes:
        loc = p.location
        where = f"{conv.to_md(loc.place)} ({loc.lat:.2f}, {loc.lon:.2f})" if loc else "no location"
        print(f"  {p.key:<14} {len(p.papers):>2} papers  {where}")
    for msg in problems:
        print(f"warning: {msg}")
    return 0


def cmd_init(args) -> int:
    dest = Path(args.dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "img").mkdir(exist_ok=True)
    for name in ("main.tex", "notesmap.sty"):
        target = dest / name
        if target.exists():
            print(f"kept existing {target}")
        else:
            shutil.copy(TEMPLATES / name, target)
            print(f"wrote {target}")
    toml = Path("notesmap.toml")
    if toml.exists():
        print(f"kept existing {toml}")
    else:
        rel = (dest / "main.tex").as_posix()
        toml.write_text((TEMPLATES / "notesmap.toml").read_text(encoding="utf-8").replace("NOTES_PATH", rel),
                        encoding="utf-8")
        print(f"wrote {toml}")
    print("next: notesmap check, then notesmap serve --map")
    return 0


def cmd_serve(args) -> int:
    import danvas

    from .render import Board
    from .watch import Watcher

    cfg, src, conv, parser = _setup(args)
    if args.map_width:
        cfg.map_width = args.map_width
    if args.edit_url:
        cfg.edit_url = args.edit_url
    watcher = Watcher(src, lambda s: parser(s, cfg), cfg.poll, cfg.lock_files, lambda n: None)
    notes = watcher.load()
    if notes is None:
        return 1
    for w in notes.warnings:
        print(f"[notesmap] warning: {w}", flush=True)

    canvas = danvas.Canvas()
    board = Board(canvas, cfg, src, conv, args.map)
    board.apply(notes)
    snapshots = [0]

    def on_notes(new):
        summary = board.apply(new)
        print(f"[notesmap] reloaded {src.describe()}: {summary}", flush=True)
        if args.snapshot:
            snapshots[0] += 1
            threading.Thread(target=lambda n=snapshots[0]: shoot(f"_reload{n}", 6), daemon=True).start()

    watcher.on_notes = on_notes
    watcher.start()
    print(f"[notesmap] watching {src.describe()} every {cfg.poll:g}s", flush=True)

    port = args.port or cfg.port
    w = cfg.map_width
    view = {"grid": False, "zoom": 0.2, "x": w / 2, "y": w / 4} if args.map else {"grid": True, "zoom": 0.5}

    def shoot(suffix: str, wait: float) -> None:
        time.sleep(wait)
        out = Path(args.snapshot)
        keys = args.frame.split(",") if args.frame else list(board.panels)[:3]
        frame = None if keys == ["all"] else [board.panels[k] for k in keys if k in board.panels]
        path = out.with_name(out.stem + suffix + out.suffix)
        path.with_suffix(".json").write_text(json.dumps(canvas.describe(), indent=1, default=str))
        try:
            canvas.screenshot(frame, path=str(path))
            print(f"[snapshot] wrote {path}", flush=True)
        except TimeoutError as e:
            print(f"[snapshot] {path.name} skipped: {e}", flush=True)

    if not args.snapshot:
        canvas.serve(port=port, view=view, open_browser=not args.no_browser)
        return 0
    canvas.serve(port=port, view=view, block=False, open_browser=not args.no_browser)
    for _ in range(240):
        if canvas.viewers:
            break
        time.sleep(0.5)
    shoot("", 12)
    threading.Event().wait()
    return 0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="notesmap", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="serve the live board")
    s.add_argument("--config", help="notesmap.toml (default: ./notesmap.toml)")
    s.add_argument("--map", action="store_true", help="pin programmes to a world map")
    s.add_argument("--port", type=int)
    s.add_argument("--no-browser", action="store_true")
    s.add_argument("--snapshot", metavar="PNG", help="also write a PNG and layout dump once a browser connects, "
                                                   "and again after every reload")
    s.add_argument("--frame", help="comma-separated panel keys to frame in snapshots, or 'all'")
    s.add_argument("--map-width", type=int, help="override [map] width, e.g. 2400 to capture the whole map")
    s.add_argument("--edit-url", help="override [server] edit_url: where the map's edit button points, "
                                      "for an address only known at startup such as a tunnel's")
    c = sub.add_parser("check", help="lint the notes")
    c.add_argument("--config")
    i = sub.add_parser("init", help="starter notes and config for a new lab")
    i.add_argument("dir", help="folder for main.tex, notesmap.sty and img/")
    args = ap.parse_args(argv)
    sys.exit({"serve": cmd_serve, "check": cmd_check, "init": cmd_init}[args.cmd](args))
