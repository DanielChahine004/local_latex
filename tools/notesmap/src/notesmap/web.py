"""The programme panel: a React component and its CSS, rendered by danvas.

Props: key, title, lead, link, html (the programme note), figures, papers
(each: key, title, year, snippet, thumb, link, html) and open (the key of the
unfolded note, or null). Clicks go back to Python as {event: "toggle", key}.
"""

REACT_SRC = r"""
const DESIGN_W = 880;   // the width the panel is laid out at; any other width zooms it

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
  const toggle = (k) => canvas.send({ event: "toggle", key: k });
  const openNode = open === p.key ? p : (p.papers || []).find(x => x.key === open);
  // text you can select: a press here stays with the text instead of reaching
  // the canvas, which would otherwise start a drag of the panel
  const keep = { onPointerDown: e => e.stopPropagation(), onMouseDown: e => e.stopPropagation() };
  return (
    <div ref={root} className="fit">
    <div className="prog" style={{ width: DESIGN_W, zoom: scale }}>
      <div className="head">
        <h1 className="sel" {...keep}>{p.title}</h1>
        {p.place && <span className="place sel" {...keep}>{p.place}</span>}
        {p.link && <a className="chip" href={p.link} target="_blank" rel="noreferrer" title={p.link}>site ↗</a>}
        {p.html && <button className={"chip" + (open === p.key ? " on" : "")} onClick={() => toggle(p.key)}>
          {open === p.key ? "hide programme note" : "programme note"}
        </button>}
      </div>
      {p.lead && <p className="lead sel" {...keep}>{p.lead}</p>}
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
      {p.papers.length > 0 && (
        <div className="cards">
          {p.papers.map(c => (
            <div key={c.key} className={"card" + (open === c.key ? " on" : "")} onClick={() => toggle(c.key)}
                 title="Click to unfold the note">
              {c.thumb ? <img src={c.thumb} alt="" /> : <div className="thumb">{c.title.slice(0, 1)}</div>}
              <div className="t">{c.title}</div>
              <div className="s">{c.snippet}</div>
              <div className="y">
                <span>{c.year}</span>
                <span className="hint">{open === c.key ? "hide note" : "note ▾"}</span>
                {c.link && <a href={c.link} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
                              title={c.link}>{c.link.includes("doi.org") ? "DOI ↗" : "link ↗"}</a>}
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
/* danvas's move handle on a frameless panel: larger and visible, so a panel can be found and dragged */
.pc-drag-handle { width: 22px !important; height: 22px !important; opacity: .7 !important; border-radius: 6px;
                  background: var(--pc-accent, #3b82f6) !important; }
.pc-drag-handle:hover { opacity: 1 !important; }
.prog { box-sizing: border-box; font: 14px/1.45 system-ui, sans-serif; color: var(--pc-text, #ddd); padding: 12px 14px 14px;
        border: 1px solid rgba(127,127,127,.45); border-radius: 10px; background: rgba(127,127,127,.07); }
.head { display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
.prog h1 { font-size: 26px; font-weight: 500; margin: 0; }
.place { font-size: 12px; opacity: .6; }
.chip { font: 12px system-ui, sans-serif; padding: 3px 10px; border-radius: 999px; cursor: pointer;
        border: 1px solid var(--pc-accent, #3b82f6); color: var(--pc-accent, #3b82f6); background: transparent; }
.chip:hover, .chip.on { background: var(--pc-accent, #3b82f6); color: #fff; }
a.chip { text-decoration: none; }
.prog .lead { text-align: center; opacity: .8; margin: 0 auto 14px; max-width: 700px; }
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
.card .y .hint { margin-left: auto; color: var(--pc-accent, #3b82f6); }
.card .y a { color: var(--pc-accent, #3b82f6); text-decoration: none; font-weight: 600; }
.sel, .sel * { -webkit-user-select: text; user-select: text; cursor: text; }
.note { margin-top: 14px; padding: 10px 12px; border-top: 1px solid rgba(127,127,127,.4); }
.note .nh { font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 6px; }
.note .nh { gap: 16px; }
.note .nh .close { cursor: pointer; opacity: .6; font-weight: 400; flex: none; }
.note p, .note li { margin: 0 0 8px; }
.note blockquote { margin: 0 0 8px 12px; opacity: .85; }
.note code { font-size: 12px; }
"""

MAP_CSS = ".prog { background: #12151c; }"   # opaque over terrain

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
