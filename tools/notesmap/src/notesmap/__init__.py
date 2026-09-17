"""notesmap: LaTeX research-programme notes as a live, zoomable board or world map.

The pipeline is four layers, each replaceable on its own:

    source  (source.py)  where the notes and their images live: a folder, a
                         synced bucket mount, or an http(s) URL; records what a
                         parser reads and says when it changed
    parse   (parse.py)   files -> Notes: programmes, their papers, locations,
                         images, links and cross-references. The LaTeX parser
                         is the default; [source] parser names one of your own
    latex   (latex.py)   note bodies -> Markdown, through a macro table a lab
                         extends from notesmap.toml or a plugin module
    render  (render.py)  Notes -> danvas panels, pins and arrows, updated in
                         place when the notes change

cli.py wires them together; config.py reads notesmap.toml.
"""
__version__ = "0.1.0"
