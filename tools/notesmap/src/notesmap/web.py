"""The programme panel: a React component and its CSS, rendered by danvas.

Props: key, title, lead, link, html (the programme note), figures, papers
(each: key, title, year, snippet, thumb, link, html) and open (the key of the
unfolded note, or null). Clicks go back to Python as {event: "toggle", key}.
"""

REACT_SRC = r"""
function Component({ canvas, props }) {
  const p = props;
  const open = p.open || null;
  const toggle = (k) => canvas.send({ event: "toggle", key: k });
  const openNode = open === p.key ? p : (p.papers || []).find(x => x.key === open);
  return (
    <div className="prog">
      <div className="head">
        <h1>{p.title}</h1>
        {p.place && <span className="place">{p.place}</span>}
        {p.link && <a className="chip" href={p.link} target="_blank" rel="noreferrer" title={p.link}>site ↗</a>}
        {p.html && <button className={"chip" + (open === p.key ? " on" : "")} onClick={() => toggle(p.key)}>
          {open === p.key ? "hide programme note" : "programme note"}
        </button>}
      </div>
      {p.lead && <p className="lead">{p.lead}</p>}
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
          <div className="nh">{openNode.title}<span onClick={() => toggle(open)}>close</span></div>
          <div dangerouslySetInnerHTML={{ __html: openNode.html }} />
        </div>
      )}
    </div>
  );
}
"""

REACT_CSS = """
.prog { font: 14px/1.45 system-ui, sans-serif; color: var(--pc-text, #ddd); padding: 12px 14px 14px;
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
.card img, .card .thumb { width: 100%; height: 96px; object-fit: cover; border-radius: 4px; display: block; }
.card .thumb { display: grid; place-items: center; font-size: 40px; background: rgba(127,127,127,.25); }
.card .t { font-weight: 600; font-size: 12px; margin: 6px 0 2px; display: -webkit-box; -webkit-line-clamp: 3;
           -webkit-box-orient: vertical; overflow: hidden; }
.card .s { font-size: 10.5px; opacity: .8; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical;
           overflow: hidden; }
.card .y { font-size: 11px; opacity: .8; margin-top: 6px; display: flex; gap: 8px; align-items: center; }
.card .y .hint { margin-left: auto; color: var(--pc-accent, #3b82f6); }
.card .y a { color: var(--pc-accent, #3b82f6); text-decoration: none; font-weight: 600; }
.note { margin-top: 14px; padding: 10px 12px; border-top: 1px solid rgba(127,127,127,.4); }
.note .nh { font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 6px; }
.note .nh span { cursor: pointer; opacity: .6; font-weight: 400; }
.note p, .note li { margin: 0 0 8px; }
.note blockquote { margin: 0 0 8px 12px; opacity: .85; }
.note code { font-size: 12px; }
"""

MAP_CSS = ".prog { background: #12151c; }"   # opaque over terrain

PIN_JSX = ('<div style="width:30px;height:30px;border-radius:50%;background:#e5322d;'
           'border:4px solid #fff;box-shadow:0 0 8px #000"></div>')
