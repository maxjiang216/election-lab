import { useEffect, useMemo, useRef, useState } from "react";
import { loadPartyRule } from "../data";
import { GOV_SERIES, TRI_SERIES, yearRows, type PartyRuleFile, type View, type Weight } from "../partyRule";
import { Segmented } from "./Controls";

type Range = "all" | "1857" | "1900" | "1945" | "1980" | "2000";

const RANGES: [Range, string, string?][] = [
  ["all", "1789–", "Whole history"],
  ["1857", "1857–", "Democrats vs. Republicans"],
  ["1900", "1900–"],
  ["1945", "1945–"],
  ["1980", "1980–"],
  ["2000", "2000–"],
];
const VIEWS: [View, string][] = [["gov", "Governors"], ["trifecta", "Trifectas"]];
const WEIGHTS: [Weight, string, string?][] = [
  ["people", "People", "Weight each state by its population"],
  ["states", "States", "Count each state once"],
];

const H = 380;
const M = { top: 12, right: 12, bottom: 28, left: 44 };

function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(900);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, Math.floor(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function parseHash(): { view: View; range: Range; weight: Weight } {
  const [, view, range, weight] = window.location.hash.replace(/^#\/?/, "").split("/");
  return {
    view: view === "trifecta" ? "trifecta" : "gov",
    range: (RANGES.map((r) => r[0]) as string[]).includes(range) ? (range as Range) : "1857",
    weight: weight === "states" ? "states" : "people",
  };
}

const pct = (v: number | undefined) => `${((v ?? 0) * 100).toFixed(1)}%`;

export function PartyRule() {
  const [file, setFile] = useState<PartyRuleFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const init = parseHash();
  const [view, setView] = useState<View>(init.view);
  const [range, setRange] = useState<Range>(init.range);
  const [weight, setWeight] = useState<Weight>(init.weight);
  const [hover, setHover] = useState<number | null>(null);
  const [wrapRef, width] = useWidth<HTMLDivElement>();

  useEffect(() => {
    loadPartyRule().then(setFile, (e) => setError(String(e)));
  }, []);
  useEffect(() => {
    window.history.replaceState(null, "", `#/rule/${view}/${range}/${weight}`);
  }, [view, range, weight]);

  const series = view === "gov" ? GOV_SERIES : TRI_SERIES;
  const all = useMemo(() => (file ? yearRows(file, view, weight) : []), [file, view, weight]);
  const y0 = range === "all" ? (file?.first ?? 1789) : Number(range);
  const rows = useMemo(() => all.filter((r) => r.year >= y0), [all, y0]);
  // Only draw/list series that appear in the window.
  const shown = useMemo(() => series.filter((s) => rows.some((r) => (r.share[s.key] ?? 0) > 0)), [series, rows]);

  const x1 = rows.length ? rows[rows.length - 1].year + 1 : y0 + 1;
  const iw = width - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const sx = (y: number) => M.left + ((y - y0) / (x1 - y0)) * iw;
  const sy = (v: number) => M.top + ih - v * ih;

  // Stacked step areas, one band per series; each year spans [year, year + 1).
  const paths = useMemo(() => {
    const out: Record<string, string> = {};
    let base = rows.map(() => 0);
    for (const s of shown) {
      const top = rows.map((r, i) => base[i] + (r.share[s.key] ?? 0));
      let d = "";
      rows.forEach((r, i) => {
        d += `${i ? "L" : "M"}${sx(r.year)},${sy(top[i])}L${sx(r.year + 1)},${sy(top[i])}`;
      });
      for (let i = rows.length - 1; i >= 0; i--) {
        d += `L${sx(rows[i].year + 1)},${sy(base[i])}L${sx(rows[i].year)},${sy(base[i])}`;
      }
      out[s.key] = d + "Z";
      base = top;
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, shown, width, y0, x1]);

  const years = useMemo(() => {
    const span = x1 - y0;
    const step = [1, 2, 5, 10, 20, 25, 50].find((s) => span / s <= Math.max(4, iw / 70)) ?? 50;
    const out: number[] = [];
    for (let y = Math.ceil(y0 / step) * step; y < x1; y += step) out.push(y);
    return out;
  }, [y0, x1, iw]);

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const y = Math.floor(y0 + ((e.clientX - box.left) / box.width) * (x1 - y0));
    setHover(Math.min(rows.length - 1, Math.max(0, y - y0)));
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const d = e.key === "ArrowLeft" ? -1 : 1;
    setHover((h) => Math.min(rows.length - 1, Math.max(0, (h ?? rows.length - 1) + d)));
  };

  const cur = hover !== null && rows[hover] ? rows[hover] : rows[rows.length - 1];
  const hx = cur ? sx(cur.year + 0.5) : 0;
  const unit = weight === "people" ? "of Americans" : "of states";

  return (
    <div className="app seats party-rule">
      <header className="top">
        <p className="crumb"><a href="#/president">← Election maps</a></p>
        <h1>Share {unit} under each party’s {view === "gov" ? "governors" : "trifectas"}</h1>
        <p className="lede">
          {view === "gov"
            ? "The party of each state's governor, year by year, weighted by state population."
            : "A trifecta is one party holding the governorship and both legislative chambers."}
          {weight === "states" && " Here every state counts once."}
        </p>
      </header>
      <div className="controls">
        <Segmented label="View" value={view} options={VIEWS} onChange={(v) => { setView(v); setHover(null); }} />
        <Segmented label="Count" value={weight} options={WEIGHTS} onChange={(w) => setWeight(w)} />
        <Segmented label="Range" value={range} options={RANGES} onChange={(r) => { setRange(r); setHover(null); }} />
      </div>
      {error && <p className="error">{error}</p>}
      {!file && !error && <div className="map-loading">Loading…</div>}
      {file && cur && (
        <>
          <ul className="seat-legend" aria-label="Legend">
            {[...shown].reverse().map((s) => (
              <li key={s.key}>
                <svg width="12" height="12" aria-hidden="true"><rect width="12" height="12" rx="2" fill={s.color} /></svg>
                {s.label} <b>{pct(cur.share[s.key])}</b>
              </li>
            ))}
            <li className="muted">in {cur.year}</li>
          </ul>
          <div className="seats-chart" ref={wrapRef}>
            <svg width={width} height={H} role="img" aria-label={`Share ${unit} by party over time`}>
              {[0, 0.25, 0.5, 0.75, 1].map((v) => (
                <g key={v}>
                  <line x1={M.left} x2={M.left + iw} y1={sy(v)} y2={sy(v)} className="grid" />
                  <text x={M.left - 6} y={sy(v)} dy="0.32em" textAnchor="end" className="tick">{v * 100}%</text>
                </g>
              ))}
              {shown.map((s) => <path key={s.key} d={paths[s.key]} fill={s.color} />)}
              <line x1={M.left} x2={M.left + iw} y1={sy(0.5)} y2={sy(0.5)} className="majority" />
              {years.map((y) => (
                <text key={y} x={sx(y)} y={H - 8} textAnchor="middle" className="tick">{y}</text>
              ))}
              {hover !== null && <line x1={hx} x2={hx} y1={M.top} y2={M.top + ih} className="crosshair" />}
              <rect
                x={M.left} y={M.top} width={iw} height={ih} fill="transparent" tabIndex={0}
                aria-label="Move through years with the arrow keys"
                onPointerMove={onMove} onPointerLeave={() => setHover(null)} onKeyDown={onKey}
                onBlur={() => setHover(null)}
              />
            </svg>
            {hover !== null && (
              <div className="tooltip seats-tip rule-tip" style={{ left: Math.min(hx + 12, width - 300), top: M.top + 8 }}>
                <b>{cur.year}</b>
                <table>
                  <tbody>
                    {[...shown].reverse().filter((s) => cur.states[s.key]).map((s) => (
                      <tr key={s.key}>
                        <td><i style={{ background: s.color }} />{s.label}</td>
                        <td>{pct(cur.share[s.key])}</td>
                        <td>{cur.states[s.key].length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <YearStates row={cur} series={shown} />
          <p className="source">
            Source: Wikipedia’s “Political party strength in &lt;state&gt;” articles (party of the governor and
            each legislative chamber, one row per year). Population: decennial census counts, interpolated between
            censuses, and the {file.popEstimateYear} Census Bureau estimate. Only states count (not D.C. or
            territories), each from the year it was admitted; a state's year shows whoever the table lists for it.
            Nebraska's nonpartisan unicameral legislature (since 1937) counts by its members' party affiliation;
            other nonpartisan or coalition chambers, and tied ones, never make a trifecta. Fusion tickets such as
            Democratic/Populist count as other.
          </p>
        </>
      )}
    </div>
  );
}

function YearStates({ row, series }: { row: { year: number; states: Record<string, string[]> }; series: typeof GOV_SERIES }) {
  return (
    <div className="rule-states">
      <h2>States in {row.year}</h2>
      <dl>
        {[...series].reverse().filter((s) => row.states[s.key]).map((s) => (
          <div key={s.key}>
            <dt><i style={{ background: s.color }} />{s.label} ({row.states[s.key].length})</dt>
            <dd>{row.states[s.key].join(" ")}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
