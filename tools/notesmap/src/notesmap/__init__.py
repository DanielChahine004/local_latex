"""notesmap: LaTeX research-programme notes as a live, zoomable board or world map.

The pipeline is four layers, each replaceable on its own:

    source  (source.py)  where the .tex and its images live: a folder, a synced
                         bucket mount, or an http(s) URL; says when they changed
    parse   (parse.py)   .tex -> Notes: programmes, their papers, locations,
                         images, links and cross-references
    latex   (latex.py)   note bodies -> Markdown, through a macro table a lab
                         extends from notesmap.toml or a plugin module
    render  (render.py)  Notes -> danvas panels, pins and arrows, updated in
                         place when the notes change

cli.py wires them together; config.py reads notesmap.toml.
"""
__version__ = "0.1.0"
