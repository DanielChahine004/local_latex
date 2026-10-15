"""The programme panel: a React component and its CSS, rendered by danvas.

Props: key, kind, title, dates, lead, link, html (the programme note), figures, papers
(each: key, title, year, snippet, thumb, link, pdf, html) and open (the key of the
unfolded note, or null). Clicks go back to Python as {event: "toggle", key}.
"""

REACT_SRC = r"""
const DESIGN_W = 880;   // the width the panel is laid out at; any other width zooms
                        // it. layout.py's PANEL_W is the width it is given, and its
                        // own DESIGN_W must match this one

function Component({ canvas, props }) {
  const p = props;
  // resizing a panel scales its whole content with the width, so a smaller
  // panel is a smaller copy rather than a tall narrow column; its height
  // follows from the scaled content
  const root = React.useRef(null);
  const [scale, setScale] = React.useState(1);
  React.useEffect(() => {
    const el = root.current;
    if (!el) return;
    const fit = () => {
      const w = el.clientWidth;
      if (w) setScale(s => {
        const next = Math.min(3, Math.max(0.25, w / DESIGN_W));
        return Math.abs(next - s) < 0.002 ? s : next;
      });
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // a countdown has to move on its own: the board is only redrawn when the notes
  // change, so the panel keeps its own clock rather than asking Python for the time
  const [now, setNow] = React.useState(() => Date.now());
  const target = p.dates && (p.dates.deadline || p.dates.start);
  React.useEffect(() => {
    if (!target) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [target]);
  const left = (t) => {
    let s = Math.floor((t - now) / 1000);
    if (s < 0) return null;
    const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600);
    const m = Math.floor(s % 3600 / 60);
    s = s % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return d > 0 ? `${d}d ${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(h)}:${pad(m)}:${pad(s)}`;
  };
  const countdown = () => {
    const dl = p.dates.deadline, st = p.dates.start, en = p.dates.end || p.dates.start;
    if (dl && left(dl)) return { cls: "cd", text: `${p.dates.deadlineLabel} close in ${left(dl)}` };
    if (st && left(st)) return { cls: "cd", text: `starts in ${left(st)}` };
    if (en && now <= en) return { cls: "cd now", text: "on now" };
    return { cls: "cd past", text: dl ? `${p.dates.deadlineLabel} closed` : "over" };
  };
  // the corner grip: drag outward to enlarge, inward to shrink. Widths go to
  // Python, which resizes the panel; the height follows the scaled content
  const grip = {
    onMouseDown: e => e.stopPropagation(),
    onPointerDown: e => {
      e.stopPropagation(); e.preventDefault();
      const el = root.current, target = e.currentTarget;
      const w0 = el.clientWidth, h0 = Math.max(1, el.clientHeight);
      const zoom = el.getBoundingClientRect().width / w0 || 1;   // screen px per canvas px
      const x0 = e.clientX, y0 = e.clientY;
      let w = w0, sent = 0;
      target.setPointerCapture(e.pointerId);
      const move = ev => {
        const dw = ((ev.clientX - x0) + (ev.clientY - y0) * (w0 / h0)) / 2 / zoom;
        w = Math.round(Math.min(DESIGN_W * 3, Math.max(DESIGN_W / 4, w0 + dw)));
        const now = Date.now();
        if (now - sent > 60) { sent = now; canvas.send({ event: "resize", w }); }
      };
      const up = () => {
        target.removeEventListener("pointermove", move);
        target.removeEventListener("pointerup", up);
        canvas.send({ event: "resize", w });
      };
      target.addEventListener("pointermove", move);
      target.addEventListener("pointerup", up);
    },
  };
  const open = p.open || null;
  // the search box hands every panel the whole hit list; a panel colours itself
  // and its cards from it, so one typed word repaints the board at once
  const hits = React.useMemo(() => new Set(p.hits || []), [p.hits]);
  const hit = (k) => hits.has(k);
  const toggle = (k) => canvas.send({ event: "toggle", key: k });
  const openNode = open === p.key ? p : (p.papers || []).find(x => x.key === open);
  // text you can select: a press here stays with the text instead of reaching
  // the canvas, which would otherwise start a drag of the panel
  const keep = { onPointerDown: e => e.stopPropagation(), onMouseDown: e => e.stopPropagation() };
  return (
    <div ref={root} className="fit"
         onMouseEnter={() => canvas.send({ event: "focus", on: true })}
         onMouseLeave={() => canvas.send({ event: "focus", on: false })}>
    <div className={"prog " + (p.kind || "programme") + (!p.filtered ? "" : hit(p.key) ? " hit" : " miss")}
         style={{ width: DESIGN_W, zoom: scale }}>
      {/* the image sits beside the heading, not above it: a panel is wider than
          it is tall, so the space next to a thumbnail is free */}
      <div className={"top" + (p.figures.length > 0 ? " withfig" : "")}>
        {p.figures.length > 0 && (
          <div className="figs">
            {p.figures.map((f, i) => (
              <figure key={i}>
                <img src={f.src} alt={f.caption} />
                {f.caption && <figcaption>{f.caption}</figcaption>}
              </figure>
            ))}
          </div>
        )}
        <div className="meta">
          <div className="head">
            <h1 className="sel" {...keep}>{p.title}</h1>
            {p.place && <span className="place sel" {...keep}>{p.place}</span>}
            {p.link && <a className="chip" href={p.link} target="_blank" rel="noreferrer" title={p.link}>site ↗</a>}
            {p.html && <button className={"chip" + (open === p.key ? " on" : "")} onClick={() => toggle(p.key)}>
              {(open === p.key ? "hide " : "") + (p.kind === "conference" ? "conference note" : "programme note")}
            </button>}
          </div>
          {p.dates && (
            <div className="when">
              {p.dates.text && <span className="date sel" {...keep}>{p.dates.text}</span>}
              <span className={countdown().cls}>{countdown().text}</span>
            </div>
          )}
          {p.lead && <p className="lead sel" {...keep}>{p.lead}</p>}
        </div>
      </div>
      {p.papers.length > 0 && (
        <div className="cards">
          {p.papers.map(c => (
            <div key={c.key} onClick={() => toggle(c.key)}
                 className={"card" + (open === c.key ? " on" : "") +
                            (!p.filtered ? "" : hit(c.key) ? " hit" : " miss")}
                 title="Click to unfold the note">
              {c.thumb ? <img src={c.thumb} alt="" /> : <div className="thumb">{c.title.slice(0, 1)}</div>}
              <div className="t">{c.title}</div>
              <div className="s">{c.snippet}</div>
              <div className="y">
                <span>{c.year}</span>
                {c.link && <a href={c.link} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
                              title={c.link}>{c.link.includes("doi.org") ? "DOI ↗" : "link ↗"}</a>}
                {c.pdf && <a href={c.pdf} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
                             title="Open the PDF">PDF ↗</a>}
              </div>
            </div>
          ))}
        </div>
      )}
      {openNode && (
        <div className="note">
          <div className="nh"><span className="sel" {...keep}>{openNode.title}</span>
            <span className="close" onClick={() => toggle(open)}>close</span></div>
          <div className="sel" {...keep} dangerouslySetInnerHTML={{ __html: openNode.html }} />
        </div>
      )}
    </div>
    <div className="grip" title="Drag to resize" {...grip} />
    </div>
  );
}
"""

REACT_CSS = """
.fit { width: 100%; overflow: hidden; position: relative; }
.grip { position: absolute; right: 2px; bottom: 2px; width: 22px; height: 22px; cursor: nwse-resize;
        border-bottom-right-radius: 8px; opacity: .55; transition: opacity .1s;
        background: linear-gradient(135deg, transparent 45%, var(--pc-accent, #3b82f6) 45% 52%, transparent 52% 64%,
                    var(--pc-accent, #3b82f6) 64% 71%, transparent 71% 83%, var(--pc-accent, #3b82f6) 83% 90%, transparent 90%); }
.grip:hover { opacity: 1; }
/* danvas's move handle on a frameless panel, stretched into a bar across the top so a panel is easy to grab;
   .fit leaves headroom for it outside the content's zoom, so the bar never covers the title */
.pc-drag-handle { left: 4px !important; right: 4px !important; top: 4px !important; width: auto !important;
                  height: 18px !important; opacity: .55 !important; border-radius: 6px;
                  background: var(--pc-accent, #3b82f6) !important; }
.pc-drag-handle:hover { opacity: 1 !important; }
.fit { padding-top: 26px; }
.prog { box-sizing: border-box; font: 14px/1.45 system-ui, sans-serif; color: var(--pc-text, #ddd); padding: 12px 14px 14px;
        border: 1px solid rgba(127,127,127,.45); border-radius: 10px; background: rgba(127,127,127,.07); }
/* a conference reads as a different kind of thing at a glance: amber, not grey */
.prog.conference { border-color: rgba(201,138,42,.75); background: rgba(201,138,42,.10); }
.prog.conference .chip { border-color: #c98a2a; color: #d69b3f; }
.prog.conference .chip:hover, .prog.conference .chip.on { background: #c98a2a; color: #fff; }
.when { display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; margin: 0 0 10px; }
.when .date { font-size: 13px; opacity: .85; }
.when .cd { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; padding: 2px 10px; border-radius: 999px;
            background: rgba(201,138,42,.18); border: 1px solid rgba(201,138,42,.55); color: #e0a850;
            font-variant-numeric: tabular-nums; }
.when .cd.now { background: rgba(60,170,90,.18); border-color: rgba(60,170,90,.6); color: #5cc47a; }
.when .cd.past { background: rgba(127,127,127,.15); border-color: rgba(127,127,127,.45); opacity: .7; color: inherit; }
.top { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 12px; }
.top .meta { flex: 1 1 auto; min-width: 0; }
.top.withfig .figs { flex: 0 0 210px; margin: 0; }
.top.withfig .figs img { max-height: 150px; }
.top.withfig .head { justify-content: flex-start; text-align: left; }
.top.withfig .when { justify-content: flex-start; }
.top.withfig .lead { text-align: left; margin-left: 0; }
.head { display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
.prog h1 { font-size: 26px; font-weight: 500; margin: 0; }
.place { font-size: 12px; opacity: .6; }
.chip { font: 12px system-ui, sans-serif; padding: 3px 10px; border-radius: 999px; cursor: pointer;
        border: 1px solid var(--pc-accent, #3b82f6); color: var(--pc-accent, #3b82f6); background: transparent; }
.chip:hover, .chip.on { background: var(--pc-accent, #3b82f6); color: #fff; }
a.chip { text-decoration: none; }
.prog .lead { text-align: center; opacity: .8; margin: 0 auto; max-width: 700px; }
.figs { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 14px; }
.figs figure { margin: 0; max-width: 100%; }
.figs img { max-height: 180px; max-width: 100%; border-radius: 4px; display: block; }
.figs figcaption { font-size: 11px; opacity: .75; text-align: center; margin-top: 4px; max-width: 520px; }
.note img.inl { display: block; max-width: 100%; max-height: 240px; margin: 8px auto; border-radius: 4px; }
.cards { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; }
.card { width: 150px; cursor: pointer; border-radius: 6px; padding: 6px; background: rgba(127,127,127,.12);
        border: 1px solid rgba(127,127,127,.3); transition: border-color .1s, background .1s; }
.card:hover { border-color: var(--pc-accent, #3b82f6); background: rgba(127,127,127,.2); }
.card.on { border-color: var(--pc-accent, #3b82f6); box-shadow: 0 0 0 1px var(--pc-accent, #3b82f6); }
.card img, .card .thumb { width: 100%; height: 96px; border-radius: 4px; display: block; }
.card img { object-fit: fill; background: #fff; }   /* the whole figure, stretched to the box, never cropped */
.card .thumb { display: grid; place-items: center; font-size: 40px; background: rgba(127,127,127,.25); }
.card .t { font-weight: 600; font-size: 12px; margin: 6px 0 2px; display: -webkit-box; -webkit-line-clamp: 3;
           -webkit-box-orient: vertical; overflow: hidden; }
.card .s { font-size: 10.5px; opacity: .8; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical;
           overflow: hidden; }
.card .y { font-size: 11px; opacity: .8; margin-top: 6px; display: flex; gap: 8px; align-items: center; }
.card .y > span:first-child { margin-right: auto; }   /* the year left, the links right */
.card .y a { color: var(--pc-accent, #3b82f6); text-decoration: none; font-weight: 600; }
/* a search underway: what matches keeps its colour and gains a green edge, what
   does not fades, so the eye lands on the hits without anything moving */
.prog.hit { border-color: #4caf78; box-shadow: 0 0 0 2px rgba(76,175,120,.45); }
.prog.miss { opacity: .45; }
.card.hit { border-color: #4caf78; background: rgba(76,175,120,.18); }
.card.miss { opacity: .4; }
.sel, .sel * { -webkit-user-select: text; user-select: text; cursor: text; }
.note { margin-top: 14px; padding: 10px 12px; border-top: 1px solid rgba(127,127,127,.4); }
.note .nh { font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 6px; }
.note .nh { gap: 16px; }
.note .nh .close { cursor: pointer; opacity: .6; font-weight: 400; flex: none; }
.note p, .note li { margin: 0 0 8px; }
.note blockquote { margin: 0 0 8px 12px; opacity: .85; }
.note code { font-size: 12px; }
.note table.lb { border-collapse: collapse; width: 100%; font-size: 12px; margin: 6px 0 10px; }
.note table.lb th, .note table.lb td { padding: 3px 6px; border-bottom: 1px solid rgba(127,127,127,.3);
                                       text-align: left; vertical-align: top; }
.note table.lb th { font-weight: 600; border-bottom: 1px solid rgba(127,127,127,.6); }
.note table.lb tbody tr:nth-child(odd) { background: rgba(127,127,127,.06); }
"""

MAP_CSS = (".prog { background: #12151c; }"                       # opaque over terrain
           ".prog.conference { background: #1d1710; }")

PIN_JSX = ('<div style="width:30px;height:30px;border-radius:50%;background:#e5322d;'
           'border:4px solid #fff;box-shadow:0 0 8px #000"></div>')


def edit_jsx(url: str, label: str, scale: float = 1.0) -> str:
    """A link to the companion editor, opened in a tab of its own.

    Two things this has to survive. The panel swallows pointer-down so the canvas
    does not read the click as the start of a drag, without which the anchor never
    fires. And `scale` sizes it for the camera it will be read at: the map opens
    with the whole world in view, where ordinary panel text is a couple of pixels
    tall, so the signpost is drawn many times larger than a note.
    """
    url = url.replace("\\", "\\\\").replace('"', "&quot;")
    label = label.replace("<", "&lt;").replace(">", "&gt;")

    def px(n: float) -> str:
        return f"{round(n * scale)}px"

    return (
        f'<div style={{{{padding:"{px(12)} {px(14)}",'
        f'font:"{px(11)} system-ui,-apple-system,sans-serif",color:"#8d98a7",'
        'textAlign:"center"}}>'
        f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
        'onPointerDown={e => e.stopPropagation()} onMouseDown={e => e.stopPropagation()} '
        f'style={{{{display:"block",padding:"{px(10)} {px(14)}",borderRadius:"{px(8)}",'
        f'background:"#2b6cb0",color:"#fff",fontSize:"{px(14)}",fontWeight:700,'
        f'textDecoration:"none",boxShadow:"0 {px(2)} {px(6)} rgba(0,0,0,.45)"}}}}>'
        f'{label}</a>'
        f'<div style={{{{marginTop:"{px(7)}",lineHeight:1.4}}}}>'
        'Password required. Edits reach this map on their own.</div></div>'
    )


# --- the search box ------------------------------------------------------------------

SEARCH_SRC = r"""
function Component({ canvas, props }) {
  const p = props;
  const [q, setQ] = React.useState(p.q || "");
  // typing goes to Python, which knows the notes; a short wait keeps a
  // keystroke from costing a round trip each
  React.useEffect(() => {
    const id = setTimeout(() => canvas.send({ event: "search", q }), 180);
    return () => clearTimeout(id);
  }, [q]);
  const keep = { onPointerDown: e => e.stopPropagation(), onMouseDown: e => e.stopPropagation() };
  return (
    <div className="find" style={{ zoom: p.scale }}>
      <div className="row">
        <input className="box" value={q} placeholder="find a word in the notes" spellCheck={false}
               onChange={e => setQ(e.target.value)} {...keep} />
        {q && <button className="clear" onClick={() => setQ("")} {...keep}>clear</button>}
        <span className="count" {...keep}>
          {!q ? "" : p.hits && p.hits.length ? `${p.hits.length} match${p.hits.length > 1 ? "es" : ""}` : "nothing"}
        </span>
      </div>
      {q && p.hits && p.hits.length > 0 && (
        <div className="where" {...keep}>{p.hits.map(h => h.title).join(" · ")}</div>
      )}
    </div>
  );
}
"""

SEARCH_CSS = """
.find { font: 14px system-ui, sans-serif; color: var(--pc-text, #ddd); display: flex; align-items: center;
        gap: 10px; flex-wrap: wrap; padding: 10px 14px; border-radius: 10px;
        border: 1px solid rgba(127,127,127,.45); background: #12151c; }
.find .box { flex: 1 1 260px; min-width: 160px; font: inherit; color: inherit; padding: 6px 10px;
             border-radius: 8px; border: 1px solid rgba(127,127,127,.5); background: rgba(127,127,127,.12); }
.find .box:focus { outline: none; border-color: var(--pc-accent, #3b82f6); }
.find .clear { font: 12px system-ui, sans-serif; padding: 4px 10px; border-radius: 999px; cursor: pointer;
               border: 1px solid rgba(127,127,127,.5); color: inherit; background: transparent; }
.find .count { font-size: 12px; opacity: .7; }
.find .where { flex: 1 1 100%; font-size: 12px; opacity: .75; line-height: 1.4; }
.find { flex-direction: column; align-items: stretch; }
.find .row { display: flex; align-items: center; gap: 10px; }
"""

# A [tables] programme's rows as a sortable, filterable table with links to the
# papers. A number's basis letter (p, r, L...) rides beside it, spelt out on
# hover and filterable from the bar; text columns with few values get a menu.
TABLE_SRC = r"""
function Component({ props }) {
  const p = props;
  const cols = p.columns || [], rows = p.rows || [];
  const [q, setQ] = React.useState("");
  const [sort, setSort] = React.useState({ col: null, dir: 0 });
  const [pick, setPick] = React.useState({});
  const keep = { onPointerDown: e => e.stopPropagation(), onMouseDown: e => e.stopPropagation(),
                 onWheel: e => e.stopPropagation() };
  // a menu for every text column with a handful of values, and every basis
  const menus = [];
  for (const c of cols) {
    const field = c.num ? c.basis : c.name;
    if (!field) continue;
    const vals = [...new Set(rows.map(r => r[field]).filter(v => v != null))].sort();
    if (vals.length > 1 && vals.length <= 12) menus.push({ field, label: c.num ? c.name.split(" ")[0] + " basis" : c.name, vals });
  }
  const text = r => cols.map(c => r[c.name] == null ? "" : String(r[c.name])).join(" ").toLowerCase();
  let shown = rows.filter(r => (!q || text(r).includes(q.toLowerCase()))
                         && Object.entries(pick).every(([f, v]) => !v || r[f] === v));
  if (sort.col && sort.dir) {
    const c = cols.find(c => c.name === sort.col);
    shown = [...shown].sort((a, b) => {
      const x = a[sort.col], y = b[sort.col];
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      const d = c && c.num ? x - y : String(x).localeCompare(String(y));
      return d * sort.dir;
    });
  }
  const cycle = name => setSort(s => s.col !== name ? { col: name, dir: 1 } : { col: name, dir: s.dir === 1 ? -1 : 0 });
  const fmt = (r, c) => {
    const v = r[c.name];
    if (v == null) return <span className="nil">–</span>;
    if (!c.num) return v;
    const f = r["_" + c.name + " flag"];
    const n = Number.isInteger(v) ? String(v) : String(+v.toFixed(2));
    return <span>{n}{f ? <sup title={p.flags[f] || f}>{f}</sup> : null}</span>;
  };
  return (
    <div className="lbt" style={{ zoom: p.scale }}>
      <div className="bar" {...keep}>
        <input className="q" value={q} placeholder="filter rows" spellCheck={false} onChange={e => setQ(e.target.value)} />
        {menus.map(m => (
          <select key={m.field} value={pick[m.field] || ""} onChange={e => setPick({ ...pick, [m.field]: e.target.value })}>
            <option value="">{m.label}: all</option>
            {m.vals.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        ))}
        {(q || Object.values(pick).some(Boolean) || sort.dir !== 0) &&
          <button onClick={() => { setQ(""); setPick({}); setSort({ col: null, dir: 0 }); }}>reset</button>}
        <span className="n">{shown.length} of {rows.length}</span>
      </div>
      <div className="wrap" {...keep}><table>
        <thead><tr>
          {cols.map(c => (
            <th key={c.name} className={c.num ? "num" : ""} onClick={() => cycle(c.name)}>
              {c.name}{sort.col === c.name && sort.dir ? (sort.dir > 0 ? " ▲" : " ▼") : ""}
            </th>
          ))}
          <th>Paper</th>
        </tr></thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={i}>
              {cols.map(c => <td key={c.name} className={c.num ? "num" : ""}>{fmt(r, c)}</td>)}
              <td className="links">
                {r._doi ? <a href={r._doi} target="_blank" rel="noopener">DOI ↗</a> : null}
                {r._pdf ? <a href={r._pdf} target="_blank" rel="noopener">PDF ↗</a> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table></div>
      <div className="legend">
        Superscripts: {Object.entries(p.flags || {}).map(([k, v]) => k + " " + v).join(" · ")}; none = {p.plain}.
      </div>
    </div>
  );
}
"""

TABLE_CSS = """
.lbt { font: 13px system-ui, sans-serif; color: var(--pc-text, #ddd); background: #12151c; padding: 12px 14px;
       border-radius: 10px; border: 1px solid rgba(127,127,127,.45); }
.lbt .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
.lbt .bar .q { flex: 1 1 220px; font: inherit; color: inherit; padding: 5px 9px; border-radius: 8px;
               border: 1px solid rgba(127,127,127,.5); background: rgba(127,127,127,.12); }
.lbt .bar select, .lbt .bar button { font: 12px system-ui, sans-serif; color: inherit; padding: 4px 6px;
               border-radius: 6px; border: 1px solid rgba(127,127,127,.5); background: #1b1f29; cursor: pointer; }
.lbt .bar .n { font-size: 12px; opacity: .7; margin-left: auto; }
.lbt .wrap { overflow-x: auto; }
.lbt table { border-collapse: collapse; width: 100%; }
.lbt th, .lbt td { padding: 3px 7px; border-bottom: 1px solid rgba(127,127,127,.25); text-align: left;
                   white-space: nowrap; }
.lbt th { cursor: pointer; user-select: none; font-weight: 600; position: sticky; top: 0; background: #12151c; }
.lbt th:hover { color: var(--pc-accent, #60a5fa); }
.lbt .num { text-align: right; font-variant-numeric: tabular-nums; }
.lbt sup { font-size: 9px; color: #f0b429; margin-left: 2px; cursor: help; }
.lbt .nil { opacity: .4; }
.lbt tbody tr:hover td { background: rgba(127,127,127,.12); }
.lbt .links a { color: var(--pc-accent, #60a5fa); text-decoration: none; margin-right: 8px; font-size: 12px; }
.lbt .links a:hover { text-decoration: underline; }
.lbt .legend { font-size: 11px; opacity: .65; margin-top: 8px; }
"""

# Demand against supply on shared axes: one row set rates what each use asks for,
# another what each design gives. A radar for the chosen pair, a fit grid for all.
RADAR_SRC = r"""
function Component({ props }) {
  const p = props, axes = p.axes || [], dem = p.demand || [], sup = p.supply || [];
  const [a, setA] = React.useState(0), [b, setB] = React.useState(0);
  const keep = { onPointerDown: e => e.stopPropagation(), onMouseDown: e => e.stopPropagation(),
                 onWheel: e => e.stopPropagation() };
  const fit = (d, s) => {
    let num = 0, den = 0;
    d.forEach((v, i) => { num += v * Math.min(s[i], v); den += v * v; });
    return den ? Math.round(100 * num / den) : 0;
  };
  const short = (d, s) => axes.map((x, i) => [x, d[i] - s[i], d[i]]).filter(t => t[1] > 0)
                              .sort((u, v) => v[1] * v[2] - u[1] * u[2]);
  const N = axes.length, R = 150, cx = 230, cy = 190, top = 5;
  const pt = (v, i) => { const t = -Math.PI / 2 + 2 * Math.PI * i / N, r = R * v / top;
                         return [cx + r * Math.cos(t), cy + r * Math.sin(t)]; };
  const poly = vals => vals.map((v, i) => pt(v, i).join(",")).join(" ");
  const D = dem[a] ? dem[a].values : [], S = sup[b] ? sup[b].values : [];
  const tone = f => f >= 90 ? "#1baf7a" : f >= 80 ? "#7fb069" : f >= 70 ? "#eda100" : "#e34948";
  return (
    <div className="dfit" style={{ zoom: p.scale }} {...keep}>
      <div className="bar">
        <label>Application <select value={a} onChange={e => setA(+e.target.value)}>
          {dem.map((r, i) => <option key={i} value={i}>{r.name}</option>)}</select></label>
        <label>Detector <select value={b} onChange={e => setB(+e.target.value)}>
          {sup.map((r, i) => <option key={i} value={i}>{r.name}</option>)}</select></label>
        <span className="score" style={{ color: tone(fit(D, S)) }}>fit {fit(D, S)}%</span>
      </div>
      <div className="row">
        <svg viewBox="0 0 460 380" className="radar">
          {[1, 2, 3, 4, 5].map(k => <polygon key={k} points={poly(axes.map(() => k))} className="ring" />)}
          {axes.map((x, i) => { const [u, v] = pt(top, i), [lx, ly] = pt(top + 0.95, i);
            return <g key={i}><line x1={cx} y1={cy} x2={u} y2={v} className="spoke" />
              <text x={lx} y={ly} className="lab" textAnchor={lx < cx - 5 ? "end" : lx > cx + 5 ? "start" : "middle"}
                    dominantBaseline="middle">{x}</text></g>; })}
          <polygon points={poly(D)} className="dem" />
          <polygon points={poly(S)} className="sup" />
          {S.map((v, i) => v < D[i] ? <circle key={i} cx={pt(v, i)[0]} cy={pt(v, i)[1]} r="5" className="gap" /> : null)}
        </svg>
        <div className="side">
          <div className="key"><span className="sw dem" /> what {dem[a] && dem[a].name} asks for</div>
          <div className="key"><span className="sw sup" /> what {sup[b] && sup[b].name} gives</div>
          <div className="key"><span className="sw gap" /> shortfall</div>
          <div className="gaps">
            {short(D, S).length ? short(D, S).map(([x, g, w]) =>
              <div key={x}>{x}: short by {g} (weight {w})</div>) : <div>No axis falls short.</div>}
          </div>
        </div>
      </div>
      <table>
        <thead><tr><th></th>{sup.map((r, j) => <th key={j} className={j === b ? "on" : ""}>{r.name}</th>)}</tr></thead>
        <tbody>{dem.map((r, i) => (
          <tr key={i}><th className={i === a ? "on" : ""}>{r.name}</th>
            {sup.map((c, j) => { const f = fit(r.values, c.values);
              return <td key={j} onClick={() => { setA(i); setB(j); }}
                         className={i === a && j === b ? "sel" : ""}
                         style={{ background: tone(f) + "33" }}>{f}</td>; })}</tr>))}
        </tbody>
      </table>
      <div className="note">Fit = sum of demand x min(supply, demand) over sum of demand squared. Ratings 1-5, first principles; edit them in the notes.</div>
    </div>
  );
}
"""

RADAR_CSS = """
.dfit { font: 13px system-ui, sans-serif; color: var(--pc-text, #ddd); background: #12151c; padding: 12px 14px;
        border-radius: 10px; border: 1px solid rgba(127,127,127,.45); }
.dfit .bar { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.dfit select { font: 13px system-ui, sans-serif; color: inherit; background: #1b1f29; border: 1px solid rgba(127,127,127,.5);
               border-radius: 6px; padding: 3px 6px; margin-left: 4px; }
.dfit .score { margin-left: auto; font-size: 18px; font-weight: 600; }
.dfit .row { display: flex; gap: 10px; align-items: flex-start; }
.dfit .radar { width: 62%; height: auto; }
.dfit .ring { fill: none; stroke: rgba(127,127,127,.25); }
.dfit .spoke { stroke: rgba(127,127,127,.3); }
.dfit .lab { fill: #c3c2b7; font-size: 11px; }
.dfit .dem { fill: rgba(42,120,214,.22); stroke: #3987e5; stroke-width: 2; }
.dfit .sup { fill: none; stroke: #eb6834; stroke-width: 2.5; stroke-dasharray: 7 4; }
.dfit .gap { fill: #e34948; }
.dfit .side { flex: 1; font-size: 12px; padding-top: 10px; }
.dfit .key { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.dfit .sw { width: 14px; height: 10px; border-radius: 2px; display: inline-block; }
.dfit .sw.dem { background: rgba(42,120,214,.5); border: 1px solid #3987e5; }
.dfit .sw.sup { border: 2px dashed #eb6834; }
.dfit .sw.gap { background: #e34948; border-radius: 50%; width: 10px; }
.dfit .gaps { margin-top: 10px; line-height: 1.6; opacity: .9; }
.dfit table { border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 12px; }
.dfit th, .dfit td { padding: 3px 6px; border-bottom: 1px solid rgba(127,127,127,.2); text-align: center; }
.dfit th { font-weight: 500; opacity: .8; }
.dfit tbody th { text-align: left; }
.dfit th.on { opacity: 1; color: var(--pc-accent, #60a5fa); }
.dfit td { cursor: pointer; font-variant-numeric: tabular-nums; }
.dfit td.sel { outline: 2px solid #f0efec; outline-offset: -2px; }
.dfit .note { font-size: 11px; opacity: .6; margin-top: 8px; }
"""

# Detectors from a table panel overlaid on a radar of "lower is better" columns,
# each axis scored 1-5 on a log scale between the best and worst value present.
DETRADAR_SRC = r"""
function Component({ props }) {
  const p = props, axes = p.axes || [], rows = p.rows || [];
  const pal = ["#3987e5", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#9085e9"];
  const [sel, setSel] = React.useState(p.initial || []);
  const [q, setQ] = React.useState("");
  const keep = { onPointerDown: e => e.stopPropagation(), onMouseDown: e => e.stopPropagation(),
                 onWheel: e => e.stopPropagation() };
  const span = axes.map(a => { const v = rows.map(r => r.v[a.key]).filter(x => x > 0);
                               return [Math.log(Math.min(...v)), Math.log(Math.max(...v))]; });
  const score = (r, i) => { const v = r.v[axes[i].key]; if (!(v > 0)) return null;
                            const [lo, hi] = span[i]; return hi > lo ? 1 + 4 * (hi - Math.log(v)) / (hi - lo) : 5; };
  const N = axes.length, R = 150, cx = 230, cy = 185;
  const pt = (s, i) => { const t = -Math.PI / 2 + 2 * Math.PI * i / N, r = R * s / 5;
                         return [cx + r * Math.cos(t), cy + r * Math.sin(t)]; };
  const toggle = i => setSel(s => s.includes(i) ? s.filter(x => x !== i) : s.length < pal.length ? [...s, i] : s);
  const shown = rows.map((r, i) => [r, i]).filter(([r]) => !q || (r.name + " " + r.detector + " " + r.set).toLowerCase().includes(q.toLowerCase()));
  const fmt = (r, a) => { const v = r.v[a.key]; return v > 0 ? (+v.toFixed(2)) + (r.f[a.key] ? " " + r.f[a.key] : "") : "–"; };
  return (
    <div className="drad" style={{ zoom: p.scale }} {...keep}>
      <div className="cols">
        <div className="pick">
          <input value={q} placeholder="filter detectors" spellCheck={false} onChange={e => setQ(e.target.value)} />
          <div className="list">{shown.map(([r, i]) => { const k = sel.indexOf(i);
            return <label key={i} className={r.set === p.simSet ? "sim" : ""}>
              <input type="checkbox" checked={k >= 0} onChange={() => toggle(i)} />
              <span className="sw" style={{ background: k >= 0 ? pal[k] : "transparent" }} />
              {r.name} <span className="det">{r.detector}</span></label>; })}</div>
        </div>
        <div className="plot">
          <svg viewBox="-70 0 600 370">
            {[1, 2, 3, 4, 5].map(k => <polygon key={k} className="ring" points={axes.map((_, i) => pt(k, i).join(",")).join(" ")} />)}
            {axes.map((a, i) => { const [u, v] = pt(5, i), [lx, ly] = pt(5.9, i);
              return <g key={i}><line x1={cx} y1={cy} x2={u} y2={v} className="spoke" />
                <text x={lx} y={ly} className="lab" textAnchor={lx < cx - 5 ? "end" : lx > cx + 5 ? "start" : "middle"}
                      dominantBaseline="middle">{a.label}</text></g>; })}
            {sel.map((i, k) => { const r = rows[i], s = axes.map((_, j) => score(r, j));
              const pts = s.map((v, j) => pt(v == null ? 0 : v, j));
              return <g key={i}>
                <polygon points={pts.map(x => x.join(",")).join(" ")} fill={pal[k] + "26"} stroke={pal[k]} strokeWidth="2"
                         strokeDasharray={r.set === p.simSet ? "6 4" : ""} />
                {pts.map((x, j) => s[j] == null ? null :
                  <circle key={j} cx={x[0]} cy={x[1]} r="4" fill={pal[k]}><title>{r.name}, {axes[j].label}: {fmt(r, axes[j])}</title></circle>)}
              </g>; })}
          </svg>
          <table><thead><tr><th></th>{axes.map(a => <th key={a.key}>{a.label}</th>)}</tr></thead>
            <tbody>{sel.map((i, k) => <tr key={i}><th><span className="sw" style={{ background: pal[k] }} />{rows[i].name}</th>
              {axes.map(a => <td key={a.key}>{fmt(rows[i], a)}</td>)}</tr>)}</tbody></table>
        </div>
      </div>
      <div className="note">Outer is better. Each axis is scored 1-5 on a log scale between the best and worst value in the table; a missing value sits at the centre. Dashed outlines are simulations. Letters: {Object.entries(p.flags || {}).map(([a, b]) => a + " " + b).join(", ")}.</div>
    </div>
  );
}
"""

DETRADAR_CSS = """
.drad { font: 13px system-ui, sans-serif; color: var(--pc-text, #ddd); background: #12151c; padding: 12px 14px;
        border-radius: 10px; border: 1px solid rgba(127,127,127,.45); }
.drad .cols { display: flex; gap: 12px; }
.drad .pick { width: 38%; display: flex; flex-direction: column; gap: 6px; }
.drad .pick input[type=text], .drad .pick > input { font: inherit; color: inherit; padding: 4px 8px; border-radius: 6px;
        border: 1px solid rgba(127,127,127,.5); background: rgba(127,127,127,.12); }
.drad .list { max-height: 430px; overflow-y: auto; font-size: 12px; }
.drad .list label { display: flex; align-items: center; gap: 6px; padding: 2px 0; cursor: pointer; white-space: nowrap; }
.drad .list label.sim { opacity: .75; font-style: italic; }
.drad .det { opacity: .55; overflow: hidden; text-overflow: ellipsis; }
.drad .sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; flex: none; border: 1px solid rgba(127,127,127,.5); margin-right: 4px; }
.drad .plot { flex: 1; }
.drad svg { width: 100%; height: auto; }
.drad .ring { fill: none; stroke: rgba(127,127,127,.25); }
.drad .spoke { stroke: rgba(127,127,127,.3); }
.drad .lab { fill: #c3c2b7; font-size: 12px; }
.drad table { border-collapse: collapse; width: 100%; font-size: 12px; }
.drad th, .drad td { padding: 3px 6px; border-bottom: 1px solid rgba(127,127,127,.2); text-align: right; white-space: nowrap; }
.drad thead th { font-weight: 500; opacity: .8; }
.drad tbody th { text-align: left; font-weight: 400; }
.drad .note { font-size: 11px; opacity: .6; margin-top: 8px; }
"""
