#!/usr/bin/env python3
"""
amenities_harvest.py -- deterministic per-town amenity coordinate harvester for OSRS.

Extracts amenity coordinates (bank, general store, furnace, anvil, range,
spinning wheel, prayer altar, well, plus every named shop) for each real
town/settlement in gazetteer.json, exclusively from the OSRS Wiki
(oldschool.runescape.wiki) via the MediaWiki API.

Sources (all wikitext, all deterministic -- no coordinates from memory):
  bank            -> "List of banks" table rows      ({{Map|name=..|x=|y=|plane=}})
  furnace         -> "Furnace" ==Locations== table   ({{Map}} maplink per row)
  anvil           -> "Anvil"   ==Locations== table   ({{Map}} maplink per row)
  altar           -> "Altar/Locations" table         ({{Map}} maplink per row)
  well            -> "Well" {{ObjectLocLine}} rows
  spinning wheel  -> "Spinning wheel" ==Locations== {{ObjectLocLine}} rows
  range           -> individual facility pages with an Infobox {{Map}}
                     (the wiki has no range-locations table; only pages that
                      actually carry a {{Map}} are used, others are omitted)
  named shops     -> every page in Category:Shops with an
                     {{Infobox Shop |location= |map={{Map..}}}}

Coordinate selection rules (deterministic):
  * polygon {{Map}}         -> integer centroid of the vertices
  * multi-point pin {{Map}} -> the point nearest (manhattan) to the town centre
  * plane                   -> the {{Map}}/{{ObjectLocLine}} |plane= param, default 0
Rows/pages that cannot be matched to a town, or whose coordinate falls outside
the per-class sanity radius from the town centre, are OMITTED (absent > wrong).

Usage:  py -3 amenities_harvest.py [--gazetteer PATH] [--outdir PATH]
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://oldschool.runescape.wiki/api.php"
UA = "osrs-amenity-harvest/1.0 (deterministic wikitext extraction for a guide tool)"
SLEEP = 0.35          # politeness delay between API calls
BANK_RADIUS = 45      # a bank must be within this manhattan distance of the town
                      # centre unless its page name names the town explicitly
FACILITY_RADIUS = 150 # furnace/anvil/altar/well/spinning wheel/range
SHOP_RADIUS = 400     # named shops (the Infobox |location= must also name the
                      # town; the radius only guards against instanced-map
                      # coordinates, which are >1500 tiles off in practice)

# Towns whose gazetteer coordinate marks a surface entrance while the town
# interior lives in a separate coordinate region.  After the bank harvest the
# town's wiki-derived bank coordinate replaces the reference centre used for
# the radius sanity checks (output coordinates are unaffected).
INTERIOR_ANCHOR_FROM_BANK = {"mor ul rek"}

STANDARD_KEYS = ("bank", "general store", "furnace", "anvil", "range",
                 "spinning wheel", "altar", "well")

# Facility pages that carry an Infobox {{Map}} for a cooking range.  The wiki
# has no range location table; these are verified at runtime and skipped when
# no map is present.
RANGE_PAGES = [
    "Cooking range (Lumbridge Castle)",
    "Hosidius Kitchen",
    "Mess",
]

# canonical town -> (output gazetteer keys, wiki location-name variants)
# Wiki variants are matched case-insensitively against [[link]] targets (with
# any " (location)" suffix stripped) and against bank-row names.
TOWNS = {
    "al kharid":            (["al kharid", "kharid"], ["al kharid", "al-kharid", "al kharid palace"]),
    "aldarin":              (["aldarin"], ["aldarin"]),
    "arceuus":              (["arceuus"], ["arceuus"]),
    "ardougne":             (["ardougne", "east ardougne"], ["east ardougne", "ardougne"]),
    "barbarian village":    (["barbarian village"], ["barbarian village"]),
    "brimhaven":            (["brimhaven"], ["brimhaven"]),
    "burthorpe":            (["burthorpe"], ["burthorpe", "warriors' guild"]),
    "canifis":              (["canifis"], ["canifis"]),
    "catherby":             (["catherby"], ["catherby"]),
    "civitas illa fortis":  (["civitas illa fortis", "fortis"], ["civitas illa fortis"]),
    "corsair cove":         (["corsair cove"], ["corsair cove"]),
    "darkmeyer":            (["darkmeyer"], ["darkmeyer"]),
    "dorgesh-kaan":         (["dorgesh-kaan"], ["dorgesh-kaan"]),
    "draynor":              (["draynor", "draynor village"], ["draynor village", "draynor"]),
    "edgeville":            (["edgeville"], ["edgeville", "edgeville monastery"]),
    "entrana":              (["entrana"], ["entrana"]),
    "falador":              (["falador"], ["falador"]),
    "ferox enclave":        (["ferox", "ferox enclave"], ["ferox enclave"]),
    "goblin village":       (["goblin village"], ["goblin village"]),
    "hosidius":             (["hosidius"], ["hosidius", "hosidius kitchen"]),
    "jatizso":              (["jatizso"], ["jatizso"]),
    "keldagrim":            (["keldagrim"], ["keldagrim"]),
    "lletya":               (["lletya"], ["lletya"]),
    "lovakengj":            (["lovakengj"], ["lovakengj"]),
    "lumbridge":            (["lumbridge"], ["lumbridge", "lumbridge castle"]),
    "lunar isle":           (["lunar isle"], ["lunar isle"]),
    "menaphos":             (["menaphos"], ["menaphos"]),
    "miscellania":          (["miscellania"], ["miscellania", "etceteria"]),
    "mor ul rek":           (["mor ul rek", "tzhaar", "tzhaar city"], ["mor ul rek", "mor-ul-rek", "tzhaar city"]),
    "mort'ton":             (["mort'ton"], ["mort'ton"]),
    "mos le'harmless":      (["mos le'harmless"], ["mos le'harmless"]),
    "musa point":           (["musa point", "musa"], ["musa point"]),
    "nardah":               (["nardah"], ["nardah"]),
    "neitiznot":            (["neitiznot"], ["neitiznot"]),
    "piscatoris":           (["piscatoris"], ["piscatoris fishing colony", "piscatoris"]),
    "pollnivneach":         (["pollnivneach"], ["pollnivneach"]),
    "port khazard":         (["port khazard", "khazard"], ["port khazard"]),
    "port phasmatys":       (["port phasmatys", "phasmatys"], ["port phasmatys"]),
    "port piscarilius":     (["port piscarilius", "piscarilius"], ["port piscarilius"]),
    "port sarim":           (["port sarim", "sarim"], ["port sarim"]),
    "prifddinas":           (["prifddinas"], ["prifddinas"]),
    "rellekka":             (["rellekka"], ["rellekka"]),
    "rimmington":           (["rimmington"], ["rimmington"]),
    "seers village":        (["seers", "seers village", "seers' village"], ["seers' village", "seers village"]),
    "shayzien":             (["shayzien"], ["shayzien"]),
    "shilo village":        (["shilo village"], ["shilo village"]),
    "sophanem":             (["sophanem"], ["sophanem"]),
    "sunset coast":         (["sunset coast"], ["sunset coast"]),
    "tai bwo wannai":       (["tai bwo wannai"], ["tai bwo wannai"]),
    "taverley":             (["taverley"], ["taverley"]),
    "tree gnome stronghold": (["gnome stronghold", "tree gnome stronghold"], ["tree gnome stronghold", "gnome stronghold"]),
    "tree gnome village":   (["gnome village", "tree gnome village"], ["tree gnome village"]),
    "varrock":              (["varrock"], ["varrock", "varrock palace"]),
    "void knights outpost": (["void knights", "void knights outpost", "void knights' outpost"], ["void knights' outpost", "void knight outpost"]),
    "weiss":                (["weiss"], ["weiss"]),
    "west ardougne":        (["west ardougne"], ["west ardougne"]),
    "witchaven":            (["witchaven"], ["witchaven"]),
    "yanille":              (["yanille"], ["yanille"]),
    "zanaris":              (["zanaris"], ["zanaris"]),
}

# ---------------------------------------------------------------- API helpers

def api_get(params):
    params = dict(params)
    params.update({"format": "json", "formatversion": "2"})
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(SLEEP)
            return data
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def fetch_wikitext(titles):
    """Fetch wikitext for titles (any count; batched by 50). Follows redirects.
    Returns {requested_title: (final_title, wikitext_or_None)}."""
    out = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        data = api_get({
            "action": "query", "prop": "revisions", "rvprop": "content",
            "rvslots": "main", "redirects": "1", "titles": "|".join(batch),
        })
        q = data["query"]
        remap = {}
        for n in q.get("normalized", []):
            remap[n["from"]] = n["to"]
        for r in q.get("redirects", []):
            remap[r["from"]] = r["to"]
        def resolve(t):
            seen = set()
            while t in remap and t not in seen:
                seen.add(t)
                t = remap[t]
            return t
        pages = {p["title"]: p for p in q["pages"]}
        for t in batch:
            ft = resolve(t)
            p = pages.get(ft)
            if p is None or p.get("missing"):
                out[t] = (ft, None)
            else:
                out[t] = (ft, p["revisions"][0]["slots"]["main"]["content"])
    return out


def category_members(cat):
    """All page titles (ns 0) in a category."""
    titles, cont = [], None
    while True:
        params = {"action": "query", "list": "categorymembers",
                  "cmtitle": cat, "cmtype": "page", "cmnamespace": "0",
                  "cmlimit": "500"}
        if cont:
            params["cmcontinue"] = cont
        data = api_get(params)
        titles += [m["title"] for m in data["query"]["categorymembers"]]
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            return titles

# --------------------------------------------------------- wikitext parsing

def split_top_level(s, sep="|"):
    """Split on sep at brace/bracket depth 0."""
    parts, depth, cur, i = [], 0, [], 0
    while i < len(s):
        c2 = s[i:i + 2]
        if c2 in ("{{", "[["):
            depth += 1; cur.append(c2); i += 2; continue
        if c2 in ("}}", "]]"):
            depth -= 1; cur.append(c2); i += 2; continue
        if depth == 0 and s[i] == sep:
            parts.append("".join(cur)); cur = []; i += 1; continue
        cur.append(s[i]); i += 1
    parts.append("".join(cur))
    return parts


def extract_templates(text, name):
    """Return the parameter bodies of every {{name ...}} template in text
    (brace balanced, case-insensitive on the template name)."""
    out = []
    low = text.lower()
    needle = "{{" + name.lower()
    start = 0
    while True:
        j = low.find(needle, start)
        if j < 0:
            return out
        # ensure the name is not a prefix of a longer template name
        after = j + len(needle)
        if after < len(text) and text[after] not in " |\n}":
            start = after
            continue
        depth, k = 0, j
        while k < len(text):
            if text[k:k + 2] == "{{":
                depth += 1; k += 2; continue
            if text[k:k + 2] == "}}":
                depth -= 1; k += 2
                if depth == 0:
                    break
                continue
            k += 1
        out.append(text[j + 2:k - 2])
        start = k


COORD_PAIR = re.compile(r"^\s*(\d{3,5})\s*,\s*(\d{3,5})\s*$")
COORD_XY = re.compile(r"^\s*x\s*:\s*(\d{3,5})\s*,\s*y\s*:\s*(\d{3,5})\s*(?:,\s*icon\s*:[^,]*)?\s*$")


def parse_template_params(body):
    """body = inner text of a template ('Map|x=1|y=2|...').
    Returns (named_params_dict, positional_tokens_list)."""
    parts = split_top_level(body)
    named, positional = {}, []
    for p in parts[1:]:
        if "=" in p:
            k, _, v = p.partition("=")
            k2 = k.strip().lower()
            # 'x:123,y:456' style tokens contain no '=', but guard against
            # tokens like 'x = 3121' (named) vs 'x:3121,y:...' (positional)
            if re.fullmatch(r"[a-z_][a-z0-9_ -]*", k2):
                named[k2] = v.strip()
                continue
        positional.append(p.strip())
    return named, positional


def parse_map(body):
    """Parse one {{Map ...}} body -> {'points': [(x,y),..], 'plane': int,
    'polygon': bool, 'name': str}."""
    named, positional = parse_template_params(body)
    points = []
    if "x" in named and "y" in named:
        try:
            points.append((int(named["x"]), int(named["y"])))
        except ValueError:
            pass
    for tok in positional:
        m = COORD_XY.match(tok) or COORD_PAIR.match(tok)
        if m:
            points.append((int(m.group(1)), int(m.group(2))))
    try:
        plane = int(named.get("plane", "0"))
    except ValueError:
        plane = 0
    return {
        "points": points,
        "plane": plane,
        "polygon": named.get("mtype", "").strip().lower() == "polygon",
        "name": named.get("name", ""),
    }


def maps_in(text):
    return [parse_map(b) for b in extract_templates(text, "Map")]


LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def link_targets(text):
    return [m.group(1).strip() for m in LINK.finditer(text)]


def norm_place(name):
    n = name.strip().lower()
    n = re.sub(r"\s*\(location\)\s*$", "", n)
    return n


WIKI2TOWN = {}
for _t, (_outs, _wikis) in TOWNS.items():
    for _w in _wikis:
        WIKI2TOWN[_w] = _t


def match_town(links):
    for l in links:
        t = WIKI2TOWN.get(norm_place(l))
        if t:
            return t
    return None


def table_rows(text, section=None):
    """Yield row texts of wikitables (optionally only inside ==section==)."""
    if section:
        m = re.search(r"^==+\s*" + re.escape(section) + r"\s*==+\s*$",
                      text, re.M)
        if not m:
            return
        rest = text[m.end():]
        m2 = re.search(r"^==[^=]", rest, re.M)
        text = rest[:m2.start()] if m2 else rest
    for tbl in re.findall(r"\{\|.*?\|\}", text, re.S):
        body = tbl.split("\n", 1)[1] if "\n" in tbl else ""
        # drop the header (everything before the first row separator)
        rows = re.split(r"\n\|-.*", body)
        for row in rows[1:]:
            row = row.strip()
            if row and not row.startswith("|}"):
                yield row


def row_cells(row):
    """Split a wikitable row into cell texts."""
    cells = []
    for line in row.splitlines():
        line = line.rstrip()
        if line.startswith("|}"):
            break
        if line.startswith("|"):
            for c in split_top_level(line[1:], "|"):
                # '||' inline separators produce empty strings between cells
                cells.append(c)
        elif cells:
            cells[-1] += "\n" + line
    # strip css prefixes like 'class="..."|content' handled by split above;
    # remove empty artifacts of '||'
    return [c.strip() for c in cells if c.strip() != ""]


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def choose_point(points, centre, polygon=False):
    if not points:
        return None
    if polygon:
        x = round(sum(p[0] for p in points) / len(points))
        y = round(sum(p[1] for p in points) / len(points))
        return (x, y)
    return min(points, key=lambda p: manhattan(p, centre))

# ------------------------------------------------------------- harvesters

class Harvest:
    def __init__(self, gaz):
        self.gaz = gaz
        self.centres = {}
        for t, (outs, _w) in TOWNS.items():
            key = outs[0]
            if key not in gaz:
                raise KeyError("gazetteer missing town key: " + key)
            self.centres[t] = (gaz[key][0], gaz[key][1])
        # results[town][amenity] = (x, y, plane, provenance_str)
        self.results = {t: {} for t in TOWNS}
        self.notes = []

    def put(self, town, amenity, x, y, plane, prov):
        """Keep the candidate nearest to the town centre on collisions."""
        cur = self.results[town].get(amenity)
        if cur is not None:
            if manhattan((cur[0], cur[1]), self.centres[town]) <= \
               manhattan((x, y), self.centres[town]):
                return
        self.results[town][amenity] = (x, y, plane, prov)

    # -- banks -------------------------------------------------------------
    def harvest_banks(self, text):
        rows = []
        for row in table_rows(text):
            cells = row_cells(row)
            if len(cells) < 2:
                continue
            links = link_targets(cells[0])
            name = links[0] if links else cells[0]
            mp = None
            for c in cells:
                ms = maps_in(c)
                if ms and ms[0]["points"]:
                    mp = ms[0]
                    break
            if not mp:
                continue
            rows.append((name, mp))
        for town, centre in self.centres.items():
            wikis = TOWNS[town][1]
            named, near = [], []
            for name, mp in rows:
                nl = name.lower()
                pt = choose_point(mp["points"], centre)
                d = manhattan(pt, centre)
                if any(w in nl for w in wikis):
                    named.append((d, pt, mp, name))
                elif d <= BANK_RADIUS and "deposit" not in nl:
                    near.append((d, pt, mp, name))
            pool = named or near
            if not pool:
                continue
            d, pt, mp, name = min(pool, key=lambda r: r[0])
            how = ("bank row '%s' names the town" % name) if pool is named \
                else ("nearest bank row '%s', %d tiles from town centre" % (name, d))
            self.put(town, "bank", pt[0], pt[1], mp["plane"],
                     'page "List of banks": {{Map}} of row [[%s]]; %s' % (name, how))

    # -- generic facility tables (furnace, anvil, altar) ---------------------
    def harvest_table(self, amenity, page, text, loc_cell=0, section=None):
        for row in table_rows(text, section=section):
            cells = row_cells(row)
            if len(cells) <= loc_cell:
                continue
            links = link_targets(cells[loc_cell])
            town = match_town(links)
            if not town:
                continue
            mp = None
            for c in cells:
                ms = maps_in(c)
                if ms and ms[0]["points"]:
                    mp = ms[0]
                    break
            if not mp:
                continue
            centre = self.centres[town]
            pt = choose_point(mp["points"], centre, mp["polygon"])
            d = manhattan(pt, centre)
            if d > FACILITY_RADIUS:
                self.notes.append("skip %s/%s from %s: %d tiles from centre"
                                  % (town, amenity, page, d))
                continue
            self.put(town, amenity, pt[0], pt[1], mp["plane"],
                     'page "%s": Locations-table row for "%s", {{Map}} '
                     '%s; %d tiles from town centre'
                     % (page, cells[loc_cell].strip()[:60],
                        "nearest point of %d" % len(mp["points"])
                        if len(mp["points"]) > 1 else "single point", d))

    # -- ObjectLocLine pages (well, spinning wheel) --------------------------
    def harvest_loclines(self, amenity, page, text, want_name, section=None):
        if section:
            m = re.search(r"^==+\s*" + re.escape(section) + r"\s*==+\s*$",
                          text, re.M)
            if m:
                text = text[m.end():]
        for body in extract_templates(text, "ObjectLocLine"):
            named, positional = parse_template_params(body)
            if want_name and named.get("name", "").strip().lower() != want_name.lower():
                continue
            links = link_targets(named.get("location", ""))
            town = match_town(links)
            if not town:
                continue
            points = []
            for tok in positional:
                m2 = COORD_XY.match(tok) or COORD_PAIR.match(tok)
                if m2:
                    points.append((int(m2.group(1)), int(m2.group(2))))
            if not points:
                continue
            try:
                plane = int(named.get("plane", "0"))
            except ValueError:
                plane = 0
            centre = self.centres[town]
            pt = choose_point(points, centre)
            d = manhattan(pt, centre)
            if d > FACILITY_RADIUS:
                self.notes.append("skip %s/%s from %s: %d tiles from centre"
                                  % (town, amenity, page, d))
                continue
            self.put(town, amenity, pt[0], pt[1], plane,
                     'page "%s": {{ObjectLocLine|location=%s|plane=%d}}; '
                     '%d tiles from town centre'
                     % (page, named.get("location", "").strip()[:60], plane, d))

    # -- single facility pages with an infobox map (ranges) ------------------
    def harvest_facility_pages(self, amenity, fetched):
        for req, (final, text) in fetched.items():
            if text is None:
                self.notes.append("range page missing: %s" % req)
                continue
            ib = None
            for tname in ("Infobox Scenery", "Infobox Building", "Infobox"):
                tpl = extract_templates(text, tname)
                if tpl:
                    ib = tpl[0]
                    break
            if ib is None:
                continue
            named, _ = parse_template_params(ib)
            links = link_targets(named.get("location", "")) + link_targets(text[:400])
            town = match_town(links + [final])
            if not town:
                self.notes.append("range page %s: no town match" % final)
                continue
            ms = maps_in(named.get("map", ""))
            ms = [m for m in ms if m["points"]]
            if not ms:
                self.notes.append("range page %s: no {{Map}} coords" % final)
                continue
            mp = ms[0]
            centre = self.centres[town]
            pt = choose_point(mp["points"], centre, mp["polygon"])
            d = manhattan(pt, centre)
            if d > FACILITY_RADIUS:
                self.notes.append("skip %s/%s (%s): %d tiles from centre"
                                  % (town, amenity, final, d))
                continue
            self.put(town, amenity, pt[0], pt[1], mp["plane"],
                     'page "%s": Infobox |map={{Map}}; %d tiles from town centre'
                     % (final, d))

    # -- named shops ---------------------------------------------------------
    @staticmethod
    def shop_key(title):
        k = title.split(" - ")[0]
        k = re.sub(r"\s*\([^)]*\)\s*$", "", k)     # drop disambiguator
        k = k.rstrip("!. ").strip().lower()
        k = re.sub(r"\s+", " ", k)
        return k

    def harvest_shops(self, fetched, general_set):
        for title, (final, text) in fetched.items():
            if text is None:
                continue
            tpl = extract_templates(text, "Infobox Shop")
            if not tpl:
                continue
            named, _ = parse_template_params(tpl[0])
            loc_links = link_targets(named.get("location", ""))
            town = match_town(loc_links)
            if not town:
                continue
            ms = [m for m in maps_in(named.get("map", "")) if m["points"]]
            if not ms:
                self.notes.append("shop %s (%s): no {{Map}} in infobox"
                                  % (final, town))
                continue
            centre = self.centres[town]
            best = min(
                ((choose_point(m["points"], centre, m["polygon"]), m) for m in ms),
                key=lambda pm: manhattan(pm[0], centre))
            pt, mp = best
            d = manhattan(pt, centre)
            if d > SHOP_RADIUS:
                self.notes.append("skip shop %s (%s): %d tiles from centre"
                                  % (final, town, d))
                continue
            key = self.shop_key(final)
            how = "polygon centroid" if mp["polygon"] else (
                "nearest of %d points" % len(mp["points"])
                if len(mp["points"]) > 1 else "single point")
            prov = ('page "%s": {{Infobox Shop|location=%s|map={{Map}}}}, %s; '
                    '%d tiles from town centre'
                    % (final, named.get("location", "").strip()[:50], how, d))
            if key not in STANDARD_KEYS:
                self.put(town, key, pt[0], pt[1], mp["plane"], prov)
            is_general = (final in general_set
                          or "general store" in key
                          or "general store" in named.get("special", "").lower())
            if is_general:
                self.put(town, "general store", pt[0], pt[1], mp["plane"], prov)

    # -- output ---------------------------------------------------------------
    def emit(self, outdir):
        amen = {}
        for town in sorted(TOWNS):
            if not self.results[town]:
                continue
            entry = {a: [v[0], v[1], v[2]]
                     for a, v in sorted(self.results[town].items())}
            for out_key in TOWNS[town][0]:
                amen[out_key] = entry
        amen = {k: amen[k] for k in sorted(amen)}
        with open(os.path.join(outdir, "amenities.json"), "w",
                  encoding="utf-8") as f:
            json.dump(amen, f, indent=1, ensure_ascii=False)
            f.write("\n")

        lines = ["# provenance: town -> amenity -> [x,y,plane] <- wiki basis",
                 "# harvested %s from oldschool.runescape.wiki (MediaWiki API,"
                 % time.strftime("%Y-%m-%d"),
                 "# wikitext {{Map}} / {{ObjectLocLine}} / Infobox Shop maps only)",
                 ""]
        for town in sorted(TOWNS):
            for a, (x, y, p, prov) in sorted(self.results[town].items()):
                lines.append("%s -> %s -> [%d, %d, %d] <- %s"
                             % (town, a, x, y, p, prov))
        if self.notes:
            lines += ["", "# skipped / notes:"]
            lines += ["#   " + n for n in sorted(set(self.notes))]
        with open(os.path.join(outdir, "provenance.txt"), "w",
                  encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return amen


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--gazetteer", default=r"C:\Users\bahs_admin\Documents\Claude"
                    r"\Projects\Osiris-guide\tools\data\gazetteer.json")
    ap.add_argument("--outdir", default=here)
    args = ap.parse_args()

    with open(args.gazetteer, encoding="utf-8") as f:
        gaz = json.load(f)
    h = Harvest(gaz)

    print("fetching facility list pages ...")
    pages = fetch_wikitext(["List of banks", "Furnace", "Anvil",
                            "Altar/Locations", "Well", "Spinning wheel"])
    h.harvest_banks(pages["List of banks"][1])
    for t in INTERIOR_ANCHOR_FROM_BANK:
        if "bank" in h.results[t]:
            b = h.results[t]["bank"]
            h.centres[t] = (b[0], b[1])
            h.notes.append("%s: radius checks anchored on its wiki bank "
                           "coordinate (%d,%d), not the gazetteer surface "
                           "entrance" % (t, b[0], b[1]))
    h.harvest_table("furnace", "Furnace", pages["Furnace"][1],
                    loc_cell=0, section="Locations")
    h.harvest_table("anvil", "Anvil", pages["Anvil"][1],
                    loc_cell=0, section="Locations")
    h.harvest_table("altar", "Altar/Locations", pages["Altar/Locations"][1],
                    loc_cell=1)
    h.harvest_loclines("well", "Well", pages["Well"][1], "Well")
    h.harvest_loclines("spinning wheel", "Spinning wheel",
                       pages["Spinning wheel"][1], "Spinning wheel",
                       section="Locations")

    print("fetching range facility pages ...")
    h.harvest_facility_pages("range", fetch_wikitext(RANGE_PAGES))

    print("enumerating Category:Shops ...")
    shops = category_members("Category:Shops")
    general = set(category_members("Category:General stores"))
    print("  %d shop pages, %d general stores" % (len(shops), len(general)))
    print("fetching shop pages ...")
    fetched = fetch_wikitext(shops)
    h.harvest_shops(fetched, general)

    amen = h.emit(args.outdir)
    towns = sum(1 for t in TOWNS if h.results[t])
    entries = sum(len(v) for v in h.results.values())
    named = sum(1 for v in h.results.values()
                for a in v if a not in STANDARD_KEYS)
    print("towns covered: %d / %d candidates" % (towns, len(TOWNS)))
    print("amenity entries (canonical towns): %d  (named shops: %d)"
          % (entries, named))
    print("output keys written (incl. alias town keys): %d" % len(amen))


if __name__ == "__main__":
    main()
