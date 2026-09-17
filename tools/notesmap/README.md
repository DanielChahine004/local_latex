# notesmap

Research-programme notes, written in LaTeX, shown as a live zoomable board or
a world map. Each programme is a panel with its place, lead line, image and a
row of paper cards. Clicking a card unfolds the full note. Cross-references
between notes become arrows, captioned by the sentence that makes them. The
same `.tex` also builds as a PDF.

The notes file is the only source of truth. Edit it, and every open board
updates in place within a few seconds.

## Start a new set of notes

```
uv tool install ./tools/notesmap      # or: uv run --project tools/notesmap notesmap ...
notesmap init notes                   # notes/main.tex, notes/notesmap.sty, notes/img/, ./notesmap.toml
notesmap check                        # lint: missing images, dangling refs, unplaced programmes
notesmap serve --map                  # opens the map in your browser
```

## Writing notes

```latex
\usepackage{notesmap}                  % beside main.tex; defines everything below

\begin{programnote}{Group -- what they build}{GroupKey}
\location{51.05}{3.72}{Ghent, Belgium}   % the pin; add [dx,dy] to fix the panel's offset
\thumb{img/group.png}                    % the programme's image

\paragraph{What it is}                   % becomes the lead line on the map
...
\paragraph{Why it matters here}
Shares a detector with \ref{prog:OtherKey}.   % an arrow, captioned by this sentence

\begin{papernote}{Author et al.\ 2023 -- Title}{Author2023}   % the year orders the cards
\thumb{img/author-fig3.png}
Journal 1:2, \doi{10.xxxx/yyyy}.                               % the card's link
\paragraph{Summary}
... \gap{still to check}
\includegraphics[width=0.5\linewidth]{img/detail.png}         % inline, in the PDF and the unfolded note
\end{papernote}

\end{programnote}
```

A cross-reference reads as the target's short name on the map. The short
name is the entry's title up to ` -- `, for example "Carra et al. 2022".

Each `\begin{...}` and `\end{...}` goes on its own line. A paper outside any
programme goes on a shelf of its own. A programme without `\location` is
shelved too, and `notesmap check` lists it.

## Keeping your own working off a public map

Notes usually mix what a paper says with why it matters to you. The PDF keeps
both. The map can leave your side out, which matters when the map is public.
Configure this under `[publish]` in `notesmap.toml`:

- **Whole sections.** `hide_sections` lists `\paragraph` headings to leave
  out, such as "why it matters" or "relevance to this thesis". A heading
  matches when it starts with a listed entry, ignoring case.
- **Single sentences.** `\aside{...}` marks one of your own sentences inside
  a factual paragraph. It prints as normal text in the PDF and is left off the
  map.
- **Gaps.** `hide_gaps = true` leaves `\gap{...}` to-do markers off the map.
- **Whole entries.** `hide_programmes` lists programme keys to leave out, and
  `show_loose = false` drops papers that sit outside any programme.

A cross-reference inside hidden text disappears with it. An arrow therefore
stays only if some sentence still shown makes the reference.

## Sharing notes across a lab

Several people can edit one set of notes when it lives in shared storage.

- **One programme per file.** `main.tex` can `\input{programmes/ghent}` and
  so on, and notesmap follows `\input` and `\include`. People editing
  different programmes then never touch the same file, and a lock covers one
  programme rather than the whole set.
- **Locks.** notesmap only reads, so it never takes a lock. While a lock file
  exists it keeps showing the last good version: `.lock` beside `main.tex`,
  or `<file>.tex.lock` beside any notes file. Set other names in
  `[source] lock_files`.
- **Half-written files.** A change is read only after it has stayed the same
  for two polls, and only if it parses. A note left open by a partial upload
  keeps the last good version on screen, and the reason is printed once.
- **Where the notes live.** `[source] path` is either a local path or an
  http(s) URL:
  - A local path works for a checkout, or for a bucket mounted or synced to
    disk with rclone, Syncthing, Dropbox or a network share.
  - A URL works for a public or presigned bucket, or any static file server.
    Changes are detected from `ETag` or `Last-Modified`.
  - Images and `\input` files resolve relative to the main file either way.

## Adapting it to your lab

Everything lab-specific lives in `notesmap.toml`. `notesmap init` writes an
annotated copy.

| Section | What it controls |
|---|---|
| `[source]` | where the notes are, how often to poll, lock file names |
| `[latex]` | environment names, the heading used for the lead line, your macros and units, plugins |
| `[board]` | rows for the non-map view, links not to draw, the shelf for loose papers |
| `[publish]` | what the map leaves out: sections, gaps, programmes, loose papers |
| `[map]` | the map image (any equirectangular image), its width, where unplaced panels go |
| `[server]` | port |

For a macro of your own, add a template under `[latex.macros]`:

```toml
[latex.macros]
kg = "{1} kg"          # \kg{5} -> 5 kg
note = "*{1:md}*"      # {n:md} converts the argument as LaTeX; {n:unit} maps an siunitx unit
```

For anything a template cannot express, write a plugin. This is a module
beside `notesmap.toml`, listed in `[latex] plugins`, with
`register(converter)`. It calls `converter.add(name, nargs, fn)`.

## How it is built

| Module | Role |
|---|---|
| `source.py` | reads files locally or over http(s), and reports versions and locks |
| `parse.py` | turns the `.tex` into programmes, papers, locations, images, links and cross-references |
| `latex.py` | converts note bodies to Markdown, through the extensible macro table |
| `redact.py` | removes the `[publish]` exclusions before anything is rendered |
| `render.py` | turns the notes into danvas panels, pins and arrows, diffed on each reload |
| `layout.py` | handles the map projection and automatic panel placement |
| `watch.py` | polls, waits for changes to settle, respects locks, keeps the last good version |
| `cli.py` | provides `serve`, `check` and `init` |
