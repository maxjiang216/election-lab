/** Share of Americans (or of states) under each party's governors and trifectas, year by year
 *  (public/data/partyrule.json, built by projects/aed/scripts/ingest/party_rule.py). */

/** D, R, W (Whig), DR (Democratic-Republican), F (Federalist), O (other party / nonpartisan),
 *  T (tied chamber); null = no data. */
export type Party = "D" | "R" | "W" | "DR" | "F" | "O" | "T";

export interface StateSeries {
  name: string;
  admitted: number;
  /** Indexed by year - first. null before admission. */
  pop: (number | null)[];
  gov: (Party | null)[];
  upper: (Party | null)[];
  lower: (Party | null)[];
}

export interface PartyRuleFile {
  first: number;
  last: number;
  popEstimateYear: number;
  states: Record<string, StateSeries>;
}

export type View = "gov" | "trifecta";
export type Weight = "people" | "states";

export interface Series {
  key: string;
  label: string;
  color: string;
}

export const GOV_SERIES: Series[] = [
  { key: "D", label: "Democratic", color: "var(--s-dem)" },
  { key: "DR", label: "Democratic-Republican", color: "var(--pr-dr)" },
  { key: "O", label: "Other / independent", color: "var(--pr-other)" },
  { key: "none", label: "No data", color: "var(--pr-none)" },
  { key: "F", label: "Federalist", color: "var(--pr-fed)" },
  { key: "W", label: "Whig", color: "var(--pr-whig)" },
  { key: "R", label: "Republican", color: "var(--s-rep)" },
];

export const TRI_SERIES: Series[] = [
  { key: "DT", label: "Democratic trifecta", color: "var(--s-dem)" },
  { key: "Dd", label: "Democratic governor, divided", color: "var(--pr-dem-light)" },
  { key: "O", label: "Other trifecta or divided", color: "var(--pr-other)" },
  { key: "none", label: "No data", color: "var(--pr-none)" },
  { key: "Rd", label: "Republican governor, divided", color: "var(--pr-rep-light)" },
  { key: "RT", label: "Republican trifecta", color: "var(--s-rep)" },
];

/** Category of one state-year for a view. */
export function category(view: View, gov: Party | null, upper: Party | null, lower: Party | null): string {
  if (view === "gov") return gov === null || gov === "T" ? "none" : gov;
  if (gov === null) return "none";
  const tri = upper === gov && lower === gov;
  if (gov === "D") return tri ? "DT" : "Dd";
  if (gov === "R") return tri ? "RT" : "Rd";
  return "O";
}

export interface YearRow {
  year: number;
  /** Category -> share (0..1) of the year's total. */
  share: Record<string, number>;
  /** Category -> state codes, most populous first. */
  states: Record<string, string[]>;
  total: number;
}

export function yearRows(file: PartyRuleFile, view: View, weight: Weight): YearRow[] {
  const rows: YearRow[] = [];
  const codes = Object.keys(file.states);
  for (let y = file.first; y <= file.last; y++) {
    const i = y - file.first;
    const w: Record<string, number> = {};
    const members: Record<string, [string, number][]> = {};
    let total = 0;
    for (const c of codes) {
      const s = file.states[c];
      const pop = s.pop[i];
      if (y < s.admitted || pop == null) continue;
      const k = category(view, s.gov[i], s.upper[i], s.lower[i]);
      const v = weight === "people" ? pop : 1;
      w[k] = (w[k] ?? 0) + v;
      total += v;
      (members[k] ??= []).push([c, pop]);
    }
    const share: Record<string, number> = {};
    const states: Record<string, string[]> = {};
    for (const k of Object.keys(w)) {
      share[k] = total ? w[k] / total : 0;
      states[k] = members[k].sort((a, b) => b[1] - a[1]).map(([c]) => c);
    }
    rows.push({ year: y, share, states, total });
  }
  return rows;
}
