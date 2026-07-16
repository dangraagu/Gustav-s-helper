#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSRS resource-site coordinate harvester (deterministic, OSRS-Wiki-grounded).

Extracts WHERE-YOU-DO-IT coordinates (mine / chop / fish / kill sites) from
https://oldschool.runescape.wiki via the MediaWiki API, using ONLY structured
coordinate data present in page wikitext:

  * {{LocLine}} / {{ObjectLocLine}} spawn/location table rows, whose pin
    parameters are literal game tiles:  |x:3253,y:3270  or bare  |3253,3270
  * the "Fishing spots" overview table, used ONLY to map catch -> which
    "Fishing spot (...)" pages to harvest (coords then come from those pages'
    ObjectLocLine rows).

NO coordinate is ever invented: every emitted [x,y,plane] is the MEDOID of the
pin set of one wiki LocLine row (the actual wiki pin closest to the row's pin
centroid) -- i.e. always a literal coordinate that appears in the wikitext.

Ranking within a key is heuristic-only (never invents data): rows whose
location text matches a curated "canonical site" keyword list come first,
then free-to-play rows, then wiki page order. Rows for quest-instanced /
minigame / tutorial variants are excluded by location-text keywords.

Output (in the same directory as this script, or --outdir):
  resources.json   { "<key>": [[x,y,plane], ...], ... }
  provenance.txt   key -> site -> wiki page / LocLine derivation, per site

Pure stdlib. Re-runnable. Read-only against the wiki (public API GETs).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://oldschool.runescape.wiki/api.php"
UA = "osrs-resource-site-harvest/1.0 (guide-plugin data; contact: dagr95@gmail.com)"
SLEEP = 0.35  # polite delay between API calls

# ---------------------------------------------------------------- wiki fetch

_cache = {}

def fetch_wikitext(title):
    """Fetch page wikitext via the MediaWiki API (follows redirects).
    Returns (resolved_title, wikitext) or (None, None) when missing."""
    if title in _cache:
        return _cache[title]
    q = urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "formatversion": "2", "redirects": "1",
    })
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("  ! fetch error %r: %s" % (title, e), file=sys.stderr)
        _cache[title] = (None, None)
        return _cache[title]
    time.sleep(SLEEP)
    p = data.get("parse")
    if not p:
        _cache[title] = (None, None)
        return _cache[title]
    _cache[title] = (p.get("title", title), p.get("wikitext", ""))
    return _cache[title]

# ------------------------------------------------------------ wikitext parse

PIN_RE = re.compile(r"^\s*(?:x:)?(\d{1,5})\s*,\s*(?:y:)?(\d{1,5})\s*$")
LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]|]*)\]\]")
TMPL_RE = re.compile(r"\{\{[^{}]*\}\}")


def _template_blocks(wt, names=("LocLine", "ObjectLocLine")):
    """Yield the inner content of every {{LocLine ...}} / {{ObjectLocLine ...}}
    template, brace-balanced."""
    for m in re.finditer(r"\{\{\s*(%s)\s*(?=[|}\n])" % "|".join(names), wt):
        i = m.start()
        depth = 0
        j = i
        n = len(wt)
        while j < n - 1:
            if wt[j] == "{" and wt[j + 1] == "{":
                depth += 1
                j += 2
                continue
            if wt[j] == "}" and wt[j + 1] == "}":
                depth -= 1
                j += 2
                if depth == 0:
                    yield wt[i + 2:j - 2]
                    break
                continue
            j += 1


def _split_params(body):
    """Split template body on top-level '|' (respects nested {{}} and [[]])."""
    parts, depth_t, depth_l, cur = [], 0, 0, []
    i, n = 0, len(body)
    while i < n:
        c2 = body[i:i + 2]
        if c2 == "{{":
            depth_t += 1; cur.append(c2); i += 2; continue
        if c2 == "}}":
            depth_t -= 1; cur.append(c2); i += 2; continue
        if c2 == "[[":
            depth_l += 1; cur.append(c2); i += 2; continue
        if c2 == "]]":
            depth_l -= 1; cur.append(c2); i += 2; continue
        if body[i] == "|" and depth_t == 0 and depth_l == 0:
            parts.append("".join(cur)); cur = []; i += 1; continue
        cur.append(body[i]); i += 1
    parts.append("".join(cur))
    return parts


def _plain(text):
    """[[A|B]] -> B, strip templates/refs, collapse whitespace."""
    t = LINK_RE.sub(r"\1", text)
    t = TMPL_RE.sub("", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_loclines(wikitext):
    """All LocLine/ObjectLocLine rows -> dicts with location, members, plane,
    mapID and literal pin list."""
    rows = []
    for body in _template_blocks(wikitext):
        params = _split_params(body)[1:]  # drop template name
        row = {"location": "", "members": None, "plane": 0, "mapID": None,
               "pins": []}
        for p in params:
            pm = PIN_RE.match(p)
            if pm:
                row["pins"].append((int(pm.group(1)), int(pm.group(2))))
                continue
            if "=" not in p:
                continue
            k, _, v = p.partition("=")
            k = k.strip().lower()
            v = v.strip()
            if k == "location":
                row["location"] = _plain(v)
            elif k == "members":
                row["members"] = v.lower().startswith("y")
            elif k == "plane":
                try:
                    row["plane"] = int(v)
                except ValueError:
                    pass
            elif k == "mapid":
                try:
                    row["mapID"] = int(v)
                except ValueError:
                    pass
        if row["pins"]:
            rows.append(row)
    return rows


def medoid(pins):
    """The literal wiki pin closest to the centroid of the row's pins."""
    cx = sum(x for x, _ in pins) / len(pins)
    cy = sum(y for _, y in pins) / len(pins)
    return min(pins, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)

# ------------------------------------------------------------------- ranking

# Rows whose location text contains any of these are dropped (instanced /
# minigame / tutorial / unreachable variants -- not real resource sites).
EXCLUDE_LOC = ("during ", "nightmare zone", "tutorial island", "deadman",
               "clan wars", "witchaven dungeon (history)", "cutscene")


def rank_rows(rows, boosts):
    """Sort: curated canonical-keyword match first, then F2P, then wiki order.
    Boosts only reorder wiki-grounded rows; they never add data."""
    boosts = [b.lower() for b in (boosts or [])]

    def key(iv):
        idx, row = iv
        loc = row["location"].lower()
        brank = len(boosts)
        for bi, b in enumerate(boosts):
            if b in loc:
                brank = bi
                break
        mem = 0 if row["members"] is False else 1
        return (brank, mem, idx)

    keep = [(i, r) for i, r in enumerate(rows)
            if not any(x in r["location"].lower() for x in EXCLUDE_LOC)]
    return [r for _, r in sorted(keep, key=key)]

# ------------------------------------------------------- resource definitions

MAX_SITES_DEFAULT = 8
MAX_SITES_MONSTER = 5

# (key, [candidate page titles], [ranking boosts], max_sites)
MINING = [
    ("clay rocks", ["Clay rocks"],
     ["rimmington", "dwarven mine", "crafting guild", "varrock"], 8),
    ("tin rocks", ["Tin rocks"],
     ["lumbridge swamp", "varrock", "al kharid", "dwarven", "falador"], 8),
    ("copper rocks", ["Copper rocks"],
     ["lumbridge swamp", "varrock", "al kharid", "dwarven", "falador"], 8),
    ("iron rocks", ["Iron rocks"],
     ["al kharid", "varrock south-west", "varrock south-east",
      "mining guild", "legends"], 8),
    ("coal rocks", ["Coal rocks"],
     ["mining guild", "barbarian village", "dwarven mine", "lumbridge swamp"], 8),
    ("silver rocks", ["Silver rocks"],
     ["varrock south-west", "crafting guild", "al kharid"], 8),
    ("gold rocks", ["Gold rocks"],
     ["crafting guild", "al kharid", "rimmington", "brimhaven"], 8),
    ("mithril rocks", ["Mithril rocks"],
     ["mining guild", "al kharid", "lumbridge swamp"], 8),
    ("adamantite rocks", ["Adamantite rocks"],
     ["mining guild", "al kharid", "lumbridge swamp"], 8),
]

TREES = [
    ("oak tree", ["Oak tree"], ["draynor", "varrock", "lumbridge"], 8),
    ("willow tree", ["Willow tree"],
     ["draynor", "port sarim", "barbarian outpost", "seers"], 8),
    ("maple tree", ["Maple tree"], ["seers", "corsair cove"], 8),
    ("yew tree", ["Yew tree"],
     ["edgeville", "varrock palace", "falador", "seers"], 8),
    ("magic tree", ["Magic tree"],
     ["woodcutting guild", "sorcerer", "gnome stronghold"], 8),
]

FLAX = [
    ("flax", ["Flax (plant)"],
     ["seers", "land's end", "gnome stronghold", "lletya"], 8),
]

# fishing: key -> plink item word(s) as they appear in {{plink|Raw X}} on the
# "Fishing spots" overview table; that table tells us WHICH spot pages to
# harvest coordinates from.
FISH = [
    ("fishing shrimp", "shrimps", ["lumbridge swamp", "draynor", "al kharid"]),
    ("fishing anchovies", "anchovies", ["lumbridge swamp", "draynor", "al kharid"]),
    ("fishing sardine", "sardine", ["draynor", "al kharid", "lumbridge swamp"]),
    ("fishing herring", "herring", ["draynor", "al kharid", "lumbridge swamp"]),
    ("fishing trout", "trout", ["barbarian village", "lumbridge", "shilo"]),
    ("fishing salmon", "salmon", ["barbarian village", "lumbridge", "shilo"]),
    ("fishing pike", "pike", ["barbarian village", "lumbridge", "edgeville"]),
    ("fishing tuna", "tuna", ["musa point", "catherby", "fishing guild"]),
    ("fishing lobster", "lobster", ["musa point", "catherby", "fishing guild"]),
    ("fishing swordfish", "swordfish", ["musa point", "catherby", "fishing guild"]),
    ("fishing monkfish", "monkfish", ["piscatoris"]),
    ("fishing shark", "shark", ["catherby", "fishing guild"]),
]

MONSTERS = [
    ("cow", ["Cow"], ["lumbridge east", "champions' guild", "crafting guild",
                      "falador"]),
    ("chicken", ["Chicken"], ["lumbridge east", "lumbridge", "fred",
                              "champions", "falador"]),
    ("goblin", ["Goblin"], ["lumbridge", "goblin village", "port sarim"]),
    ("giant rat", ["Giant rat"], ["lumbridge swamp", "varrock sewers",
                                  "edgeville dungeon"]),
    ("giant spider", ["Giant spider"], ["stronghold of security",
                                        "varrock sewers", "lumbridge"]),
    ("giant frog", ["Giant frog"], ["lumbridge swamp"]),
    ("barbarian", ["Barbarian"], ["barbarian village", "barbarian outpost"]),
    ("guard", ["Guard"], ["falador", "varrock", "edgeville"]),
    ("al kharid warrior", ["Al Kharid warrior", "Al-Kharid warrior"],
     ["al kharid", "palace"]),
    ("hill giant", ["Hill giant"], ["edgeville dungeon", "giant pit",
                                    "lava maze"]),
    ("moss giant", ["Moss giant"], ["varrock sewers", "moss giant island",
                                    "crandor", "brimhaven"]),
    ("hobgoblin", ["Hobgoblin"], ["crafting guild", "peninsula",
                                  "edgeville dungeon", "asgarnian ice"]),
    ("lesser demon", ["Lesser demon"], ["wizards' tower", "karamja volcano",
                                        "melzar"]),
    ("ogre", ["Ogre"], ["combat training camp", "castle wars", "yanille",
                        "gu'tanoth"]),
    ("rock crab", ["Rock Crab", "Rock crab"], ["rellekka", "waterbirth"]),
    ("sand crab", ["Sand Crab", "Sand crab"], ["hosidius", "crabclaw"]),
    ("ammonite crab", ["Ammonite Crab", "Ammonite crab"],
     ["fossil island", "mushroom"]),
    ("monk of zamorak", ["Monk of Zamorak"], ["chaos temple", "paterdomus",
                                              "varrock"]),
    ("seagull", ["Seagull"], ["port sarim", "corsair"]),
    ("wizard", ["Wizard"], ["wizards' tower (", "wizards' tower", "draynor"]),
    ("unicorn", ["Unicorn"], ["lumbridge", "varrock", "edgeville"]),
    ("minotaur", ["Minotaur"], ["stronghold of security"]),
    ("zombie", ["Zombie"], ["varrock sewers", "edgeville dungeon",
                            "graveyard", "wizards' tower"]),
    ("skeleton", ["Skeleton"], ["varrock sewers", "edgeville dungeon",
                                "stronghold of security"]),
    ("flesh crawler", ["Flesh Crawler", "Flesh crawler"],
     ["stronghold of security"]),
    ("ankou", ["Ankou"], ["stronghold of security", "catacombs",
                          "wilderness"]),
    ("dust devil", ["Dust devil"], ["smoke dungeon", "catacombs of kourend"]),
]

# ----------------------------------------------------------------- harvesting


def harvest_page(candidates):
    """First candidate title that yields LocLine rows -> (title, rows)."""
    for t in candidates:
        title, wt = fetch_wikitext(t)
        if not wt:
            continue
        rows = parse_loclines(wt)
        if rows:
            return title, rows
    return None, []


def fishing_spot_pages():
    """Parse the 'Fishing spots' overview table: catch item -> spot pages.
    Deterministic: rows pair [[Fishing spot (...)]] links with {{plink|Raw X}}
    catches."""
    title, wt = fetch_wikitext("Fishing spots")
    if not wt:
        return {}, None
    m = re.search(r"==\s*Overview of fishing spots\s*==", wt)
    sec = wt[m.end():] if m else wt
    tb = sec.find("{|")
    te = sec.find("|}", tb)
    table = sec[tb:te] if tb != -1 and te != -1 else sec
    mapping = {}  # fish word (lowercase) -> [spot page titles]
    for rowtxt in table.split("\n|-"):
        # cells: [ , styles, tools, catches, locations]; take the spot-page
        # link from the Styles cell and {{plink|Raw X}} ONLY from the Catches
        # cell (the Tools cell can mention items like a Raw pike used as bait)
        cells = rowtxt.split("\n|")
        if len(cells) < 4:
            continue
        pages = re.findall(r"\[\[((?:Rod )?Fishing spot \([^\]|#]+\))",
                           cells[1])
        fishes = re.findall(r"\{\{plink\|Raw ([A-Za-z' ]+?)\s*[}|]", cells[3])
        pages = [p for p in pages if "tutorial" not in p.lower()
                 and "scaperune" not in p.lower()]
        if not pages or not fishes:
            continue
        for f in fishes:
            for p in pages:
                mapping.setdefault(f.strip().lower(), [])
                if p not in mapping[f.strip().lower()]:
                    mapping[f.strip().lower()].append(p)
    return mapping, title


def main():
    outdir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 2 and sys.argv[1] == "--outdir":
        outdir = sys.argv[2]
    resources = {}
    prov = []          # provenance lines
    skipped = []       # (key, reason)

    def emit(key, page_title, rows, boosts, max_sites, extra_basis=""):
        ranked = rank_rows(rows, boosts)
        sites, seen = [], set()
        for row in ranked:
            if len(sites) >= max_sites:
                break
            x, y = medoid(row["pins"])
            if (x, y, row["plane"]) in seen:
                continue
            seen.add((x, y, row["plane"]))
            sites.append([x, y, row["plane"]])
            prov.append(
                "%s -> [%d,%d,%d] : page %r LocLine location=%r members=%s"
                " ; medoid of %d wiki pin(s)%s"
                % (key, x, y, row["plane"], page_title, row["location"],
                   {True: "Yes", False: "No", None: "?"}[row["members"]],
                   len(row["pins"]), extra_basis))
        if sites:
            resources[key] = sites
        else:
            skipped.append((key, "page %r had no usable LocLine rows"
                            % page_title))

    # ---- mining rocks / trees / flax (ObjectLocLine tables on the page)
    for group in (MINING, TREES, FLAX):
        for key, cands, boosts, mx in group:
            print("[harvest] %-18s <- %s" % (key, cands[0]))
            title, rows = harvest_page(cands)
            if not rows:
                skipped.append((key, "no LocLine/coordinate table on wiki "
                                "page(s) %s (prose-only locations)" % cands))
                print("  ! no coordinate table; skipped")
                continue
            emit(key, title, rows, boosts, mx)

    # ---- fishing (overview table -> spot pages -> ObjectLocLine rows)
    fishmap, fs_title = fishing_spot_pages()
    print("[harvest] fishing overview: %d catch types mapped" % len(fishmap))
    for key, plink_word, boosts in FISH:
        pages = fishmap.get(plink_word, [])
        if not pages:
            skipped.append((key, "catch %r not found in the %r overview "
                            "table" % (plink_word, fs_title)))
            print("  ! %s: catch not in overview table; skipped" % key)
            continue
        allrows = []
        for p in pages:
            t, rows = harvest_page([p])
            for r in rows:
                r = dict(r)
                r["_page"] = t
                allrows.append(r)
        if not allrows:
            skipped.append((key, "spot pages %s had no LocLine rows" % pages))
            continue
        # emit with per-row page provenance
        ranked = rank_rows(allrows, boosts)
        sites, seen = [], set()
        for row in ranked:
            if len(sites) >= MAX_SITES_DEFAULT:
                break
            x, y = medoid(row["pins"])
            if (x, y, row["plane"]) in seen:
                continue
            seen.add((x, y, row["plane"]))
            sites.append([x, y, row["plane"]])
            prov.append(
                "%s -> [%d,%d,%d] : page %r LocLine location=%r members=%s"
                " ; medoid of %d wiki pin(s) ; spot page chosen because the"
                " %r overview table lists {{plink|Raw %s}} for it"
                % (key, x, y, row["plane"], row["_page"], row["location"],
                   {True: "Yes", False: "No", None: "?"}[row["members"]],
                   len(row["pins"]), fs_title, plink_word))
        if sites:
            resources[key] = sites
        else:
            skipped.append((key, "no usable rows on spot pages %s" % pages))
        print("[harvest] %-18s <- %s (%d sites)" % (key, pages, len(sites)))

    # ---- monsters (LocLine tables on the monster page)
    for key, cands, boosts in MONSTERS:
        print("[harvest] %-18s <- %s" % (key, cands[0]))
        title, rows = harvest_page(cands)
        if not rows:
            skipped.append((key, "no LocLine spawn table on wiki page(s) %s"
                            % cands))
            print("  ! no spawn table; skipped")
            continue
        emit(key, title, rows, boosts, MAX_SITES_MONSTER)

    # ------------------------------------------------------------- outputs
    jpath = os.path.join(outdir, "resources.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(resources, f, indent=2, ensure_ascii=False)
        f.write("\n")

    ppath = os.path.join(outdir, "provenance.txt")
    with open(ppath, "w", encoding="utf-8") as f:
        f.write("# OSRS resource-site provenance\n")
        f.write("# source: https://oldschool.runescape.wiki MediaWiki API, "
                "action=parse&prop=wikitext (redirects followed)\n")
        f.write("# every [x,y,plane] is the MEDOID of the literal pin set of "
                "one {{LocLine}}/{{ObjectLocLine}} row (a pin that appears "
                "verbatim in the wikitext)\n")
        f.write("# harvested: %s\n\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        for line in prov:
            f.write(line + "\n")
        if skipped:
            f.write("\n# SKIPPED KEYS\n")
            for k, why in skipped:
                f.write("# %s : %s\n" % (k, why))

    total = sum(len(v) for v in resources.values())
    print("\n=== DONE: %d keys, %d sites -> %s" % (len(resources), total,
                                                   jpath))
    for k, why in skipped:
        print("  SKIPPED %s: %s" % (k, why))
    for k, v in resources.items():
        if len(v) < 2:
            print("  NOTE %s: only %d site(s)" % (k, len(v)))


if __name__ == "__main__":
    main()
