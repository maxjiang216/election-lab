"""Party of each state's governor and legislative chambers, year by year, plus state population,
for the "share of Americans ruled by each party" page.

Sources
- Wikipedia "Political party strength in <State>" (one row per year: governor, chambers, ...).
  Rendered HTML is cached in raw/partystrength/<State>.json.
- Wikipedia "List of U.S. states and territories by historical population": decennial census
  1790-2020 plus annual Census Bureau estimates since 2000, cached in raw/population/. Years
  between censuses are interpolated geometrically.

Output: ../../public/data/partyrule.json (see write_output for the shape).
Run from projects/aed: .venv/bin/python scripts/ingest/party_rule.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lxml import html

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
OUT = ROOT.parents[1] / "public" / "data" / "partyrule.json"
API = "https://en.wikipedia.org/w/api.php"
UA = "aed-ingest/1.0 (election data research script)"

# State, postal code, year of admission (first year counted; the original 13 from 1789).
STATES = [
    ("Alabama", "AL", 1819), ("Alaska", "AK", 1959), ("Arizona", "AZ", 1912), ("Arkansas", "AR", 1836),
    ("California", "CA", 1850), ("Colorado", "CO", 1876), ("Connecticut", "CT", 1789),
    ("Delaware", "DE", 1789), ("Florida", "FL", 1845), ("Georgia", "GA", 1789), ("Hawaii", "HI", 1959),
    ("Idaho", "ID", 1890), ("Illinois", "IL", 1818), ("Indiana", "IN", 1816), ("Iowa", "IA", 1846),
    ("Kansas", "KS", 1861), ("Kentucky", "KY", 1792), ("Louisiana", "LA", 1812), ("Maine", "ME", 1820),
    ("Maryland", "MD", 1789), ("Massachusetts", "MA", 1789), ("Michigan", "MI", 1837),
    ("Minnesota", "MN", 1858), ("Mississippi", "MS", 1817), ("Missouri", "MO", 1821),
    ("Montana", "MT", 1889), ("Nebraska", "NE", 1867), ("Nevada", "NV", 1864),
    ("New Hampshire", "NH", 1789), ("New Jersey", "NJ", 1789), ("New Mexico", "NM", 1912),
    ("New York", "NY", 1789), ("North Carolina", "NC", 1789), ("North Dakota", "ND", 1889),
    ("Ohio", "OH", 1803), ("Oklahoma", "OK", 1907), ("Oregon", "OR", 1859), ("Pennsylvania", "PA", 1789),
    ("Rhode Island", "RI", 1790), ("South Carolina", "SC", 1789), ("South Dakota", "SD", 1889),
    ("Tennessee", "TN", 1796), ("Texas", "TX", 1846), ("Utah", "UT", 1896), ("Vermont", "VT", 1791),
    ("Virginia", "VA", 1789), ("Washington", "WA", 1889), ("West Virginia", "WV", 1863),
    ("Wisconsin", "WI", 1848), ("Wyoming", "WY", 1890),
]
FIRST_YEAR = 1789


def fetch_page(title: str, cache: Path) -> str:
    """Rendered HTML of a Wikipedia article, cached."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        q = urllib.parse.urlencode({"action": "parse", "page": title, "prop": "text", "format": "json",
                                    "formatversion": 2, "redirects": 1})
        req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
        for attempt in range(7):
            try:
                with urllib.request.urlopen(req) as r:
                    data = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 6:
                    raise
                time.sleep(int(e.headers.get("Retry-After") or 0) or 15 * 2 ** attempt)
        if json.loads(data).get("error"):
            raise RuntimeError(f"{title}: {json.loads(data)['error']}")
        cache.write_bytes(data)
        time.sleep(8)
    return json.loads(cache.read_text())["parse"]["text"]


def strength_title(state: str) -> str:
    suffix = {"Washington": " (state)", "New York": " (state)", "Georgia": " (U.S. state)"}
    return f"Political party strength in {state}" + suffix.get(state, "")


# ---------------------------------------------------------------------------------------------
# Table grid

def text(el) -> str:
    for bad in el.xpath('.//sup[contains(@class,"reference")] | .//style'):
        bad.drop_tree()
    return re.sub(r"\s+", " ", el.text_content()).strip()


def grid(table) -> list[list[tuple[str, str] | None]]:
    """Expand rowspan/colspan: grid[r][c] = (text, style) of the cell covering that slot."""
    out: list[list] = []
    pending: dict[int, tuple[int, tuple[str, str]]] = {}  # col -> (rows left, cell)
    for tr in table.xpath("./tr | ./tbody/tr | ./thead/tr"):
        row: list = []
        cells = tr.xpath("./th | ./td")
        ci = 0

        def fill_pending():
            while len(row) in pending:
                left, cell = pending[len(row)]
                row.append(cell)
                if left <= 1:
                    del pending[len(row) - 1]
                else:
                    pending[len(row) - 1] = (left - 1, cell)

        fill_pending()
        while ci < len(cells):
            c = cells[ci]
            ci += 1
            val = (text(c), c.get("style") or "")
            rs = int(re.sub(r"\D", "", c.get("rowspan") or "1") or 1)
            cs = int(re.sub(r"\D", "", c.get("colspan") or "1") or 1)
            for _ in range(cs):
                if rs > 1:
                    pending[len(row)] = (rs - 1, val)
                row.append(val)
                fill_pending()
        fill_pending()
        out.append(row)
    return out


# ---------------------------------------------------------------------------------------------
# Party codes

PARTY_ABBR = {
    "D": "D", "DFL": "D", "D-NPL": "D", "DNPL": "D", "DEM": "D", "ID": "D",
    "R": "R", "REP": "R", "IR": "R",
    "W": "W", "WHIG": "W",
    "DR": "DR", "J": "DR", "AJ": "DR", "A-J": "DR", "NR": "W", "AM": "W",
    "F": "F", "FED": "F", "AF": "F", "PA": "F",  # pro-Administration (1789-1795)
    "AA": "DR",  # anti-Administration
}
# Shading colours Wikipedia's party templates use for the two big parties (lower-case hex).
COALITION_COLORS = {"d9b2d9", "d8bfd8"}
COLOR_PARTY = {"b0ceff": "D", "ffb6b6": "R", "f0c862": "W", "f0dc82": "W", "ea9978": "DR", "ce9e74": "F"}


def norm_abbr(a: str) -> str:
    a = a.strip().upper().replace("–", "-")
    if a.startswith("NP/"):  # nominally nonpartisan, aligned with a party
        a = a[3:]
    return PARTY_ABBR.get(a, "O")


def color_party(style: str) -> str | None:
    m = re.search(r"background(?:-color)?\s*:\s*#([0-9a-fA-F]{6})", style)
    return COLOR_PARTY.get(m[1].lower()) if m else None


def governor_party(cell: tuple[str, str] | None) -> str | None:
    if not cell or not cell[0]:
        return None
    t, style = cell
    if re.search(r"no such office|vacant|military|territor", t, re.I) and "(" not in t:
        return None
    abbrs = re.findall(r"\(([A-Za-z][A-Za-z\-–./ ]{0,8})\)", t)
    abbrs = [a.replace(".", "").strip() for a in abbrs]
    abbrs = [a for a in abbrs if a and not a.isdigit()]
    if abbrs:
        return norm_abbr(abbrs[0])
    return color_party(style)


COUNT_RE = re.compile(r"(\d+)\s*([A-Z][A-Za-z\-–]*)")


def chamber_party(cell: tuple[str, str] | None) -> str | None:
    """Majority party of a chamber from text like '25D, 14R, 1I' or 'DR maj.'"""
    if not cell or not cell[0]:
        return None
    t, style = cell
    t2 = re.sub(r"\[[^\]]*\]", "", t)
    m = re.search(r"background(?:-color)?\s*:\s*#([0-9a-fA-F]{6})", style)
    if m and m[1].lower() in COALITION_COLORS:  # purple: tie or bipartisan coalition runs the chamber
        return "T"
    # Nebraska's nonpartisan unicameral: "43NP(22R, 21D)" -> count the party affiliations.
    inner = re.search(r"\d+\s*NP\s*\(([^)]*)\)", t2)
    if inner:
        t2 = inner[1]
    m = re.match(r"\s*([A-Za-z\-–/]+?)\s*maj", t2)  # "R maj.", "Conservativemajority"
    if m:
        return norm_abbr(m[1])
    counts: dict[str, int] = {}
    for n, p in COUNT_RE.findall(t2):
        if p.upper() in ("V", "VAC", "VACANT"):
            continue
        key = norm_abbr(p) if norm_abbr(p) != "O" else p.upper()
        counts[key] = counts.get(key, 0) + int(n)
    if counts:
        total = sum(counts.values())
        best = max(counts, key=counts.get)
        if counts[best] * 2 > total:
            return best if best in ("D", "R", "W", "DR", "F") else "O"
        # No outright majority: shading says who organised the chamber (coalition/tie).
        return color_party(style) or "T"
    return color_party(style)


# ---------------------------------------------------------------------------------------------
# Per-state parse

YEAR_RE = re.compile(r"(\d{4})(?:\s*[–-]\s*(\d{4}))?")
LEG_GROUP = re.compile(r"legislat|general assembly|general court|assembly", re.I)


def parse_state(state: str, page_html: str) -> dict[int, dict[str, str | None]]:
    doc = html.fromstring(page_html)
    years: dict[int, dict[str, str | None]] = {}
    for tb in doc.xpath('//table[contains(@class,"wikitable")]'):
        g = grid(tb)
        if len(g) < 3 or not g[0] or not g[0][0][0].startswith("Year"):
            continue
        # Header rows: up to the first row whose first cell is a year.
        nh = next((i for i, r in enumerate(g) if r and YEAR_RE.fullmatch(r[0][0])), None)
        if nh is None:
            continue
        heads = g[:nh]
        ncol = max(len(r) for r in heads)

        def label(j: int) -> tuple[str, str]:
            grp = heads[0][j][0] if j < len(heads[0]) else ""
            lab = heads[-1][j][0] if j < len(heads[-1]) else ""
            return grp, lab

        gov = upper = lower = uni = lt = None
        for j in range(1, ncol):
            grp, lab = label(j)
            if gov is None and re.search(r"governor|\bgov\.", lab + " " + grp, re.I) and not re.search(
                    r"lieut|lt\.", lab, re.I):
                gov = j
            if lt is None and re.search(r"lieut|lt\.", lab, re.I):
                lt = j
            if re.search(r"congress|united states|u\.s\.", grp + " " + lab, re.I):
                continue
            if LEG_GROUP.search(grp) or LEG_GROUP.search(lab) or re.search(r"senate|house|unicameral", lab, re.I):
                if re.search(r"unicameral|legislature$", lab, re.I) and state == "Nebraska":
                    uni = j
                elif re.search(r"senate|council", lab, re.I):
                    upper = upper if upper is not None else j
                elif re.search(r"house|assem|delegates|representatives|commons", lab, re.I):
                    lower = lower if lower is not None else j
        if gov is None:
            continue
        if uni is not None:
            upper = lower = uni
        for r in g[nh:]:
            m = YEAR_RE.fullmatch(r[0][0]) if r else None
            if not m:
                continue

            def cell(j):
                return r[j] if j is not None and j < len(r) else None

            row = {
                # Vacant governorship: the lieutenant governor acts.
                "gov": governor_party(cell(gov)) or (governor_party(cell(lt)) if lt is not None
                                                     and re.search(r"vacant", cell(gov)[0] if cell(gov) else "", re.I) else None),
                "upper": chamber_party(cell(upper)),
                "lower": chamber_party(cell(lower)),
            }
            for y in range(int(m[1]), int(m[2] or m[1]) + 1):
                # A year split over several rows: keep the first row's values, fill gaps from later ones.
                have = years.setdefault(y, dict(row))
                for k, v in row.items():
                    if have[k] is None:
                        have[k] = v
    return years


# ---------------------------------------------------------------------------------------------
# Population

def census_pops() -> dict[str, dict[int, int]]:
    """Decennial census populations per state from the historical-population article."""
    page = fetch_page("List of U.S. states and territories by historical population",
                      RAW / "population" / "historical.json")
    doc = html.fromstring(page)
    names = {s: c for s, c, _ in STATES}
    out: dict[str, dict[int, int]] = {}
    for tb in doc.xpath('//table[contains(@class,"wikitable")]'):
        g = grid(tb)
        if not g:
            continue
        head = [c[0] if c else "" for c in g[0]]
        yearcols = {j: int(h[:4]) for j, h in enumerate(head) if re.fullmatch(r"\d{4}", h[:4] if h else "")}
        if not yearcols:
            continue
        for r in g[1:]:
            if not r:
                continue
            nm = re.sub(r"\s*\(.*|\[.*", "", r[0][0]).strip()
            if nm not in names:
                continue
            for j, y in yearcols.items():
                if j < len(r):
                    v = re.sub(r"[^\d]", "", r[j][0])
                    # First table wins (later tables on the page include e.g. enslaved population).
                    if v and int(v) > 0:
                        out.setdefault(names[nm], {}).setdefault(y, int(v))
    return out


def interpolate(points: dict[int, int], years: range) -> list[int | None]:
    ks = sorted(k for k, v in points.items() if v > 0)
    res: list[int | None] = []
    for y in years:
        if not ks or y < ks[0] - 10:
            res.append(None)
            continue
        if y <= ks[0]:
            res.append(points[ks[0]])
            continue
        if y >= ks[-1]:
            res.append(points[ks[-1]])
            continue
        lo = max(k for k in ks if k <= y)
        hi = min(k for k in ks if k >= y)
        if lo == hi:
            res.append(points[lo])
        else:
            f = (y - lo) / (hi - lo)
            res.append(round(points[lo] * (points[hi] / points[lo]) ** f))
    return res


# ---------------------------------------------------------------------------------------------

def main() -> None:
    last = int(sys.argv[1]) if len(sys.argv) > 1 else time.localtime().tm_year
    years = range(FIRST_YEAR, last + 1)
    cens = census_pops()
    est_year = max(max(v) for v in cens.values())
    states_out = {}
    problems = []
    for state, code, admitted in STATES:
        rows = parse_state(state, fetch_page(strength_title(state), RAW / "partystrength" / f"{state}.json"))
        pts = cens[code]
        pop = interpolate(pts, years)
        gov, upper, lower = [], [], []
        prev = {"gov": None, "upper": None, "lower": None}
        for y in years:
            if y < admitted:
                gov.append(None); upper.append(None); lower.append(None)
                continue
            r = rows.get(y)
            if r is None:  # carry forward a missing year (some tables skip rows)
                r = prev
                problems.append(f"{code} {y}: no row")
            gov.append(r["gov"]); upper.append(r["upper"]); lower.append(r["lower"])
            prev = r
        missing = sum(1 for y, g in zip(years, gov) if y >= admitted and g is None)
        if missing:
            problems.append(f"{code}: {missing} years with no governor party")
        states_out[code] = {"name": state, "admitted": admitted, "pop": [p if y >= admitted else None for y, p in zip(years, pop)],
                            "gov": gov, "upper": upper, "lower": lower}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"first": FIRST_YEAR, "last": last, "popEstimateYear": est_year,
                               "states": states_out}, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    for p in problems:
        print("  ", p)


if __name__ == "__main__":
    main()
