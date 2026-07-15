#!/usr/bin/env python3
"""
Scrape the ironman.guide route into Osiris Guide route JSON.

The guide pages embed schema.org `HowTo` JSON-LD with ordered `HowToStep` entries
(position, name, and a `HowToDirection` giving a location). We turn each HowToStep into a
route step. Steps default to manual-advance; a conservative enricher adds skill-level
auto-detect conditions where the instruction clearly states a training target.

Route content is the work of Oziris (@OzirisLoL) and the ironman.guide community. See NOTICE.
This tool is build-time only and is not shipped in the plugin jar.

Usage:  py -3 tools/scrape_guide.py
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

# order, slug, display name, id-prefix  (order follows the guide's own 1.1..2.0, S numbering)
SECTIONS = [
    ("01", "early-game",                 "Early Game",                    "eg"),
    ("02", "thieving-fishing-mining",    "Thieving, Fishing & Mining",    "tfm"),
    ("03", "fairy-rings-prayer-kingdom", "Fairy Rings, Prayer & Kingdom", "frp"),
    ("04", "skilling-graceful",          "Various Skilling & Graceful",   "sg"),
    ("05", "diaries-rfd",                "Diaries & RFD",                 "dr"),
    ("06", "after-barrows-gloves",       "After Barrows Gloves",          "abg"),
    ("07", "sailing",                    "Sailing (optional)",            "sail"),
]

OUT_DIR = Path(__file__).resolve().parent.parent / "src" / "main" / "resources" / "com" / "osirisguide" / "data" / "route"

# RuneLite net.runelite.api.Skill enum names, keyed by words that appear in guide text.
SKILL_WORDS = {
    "attack": "ATTACK", "att": "ATTACK",
    "strength": "STRENGTH", "str": "STRENGTH",
    "defence": "DEFENCE", "defense": "DEFENCE", "def": "DEFENCE",
    "ranged": "RANGED", "range": "RANGED", "ranging": "RANGED",
    "prayer": "PRAYER", "pray": "PRAYER",
    "magic": "MAGIC", "mage": "MAGIC",
    "runecraft": "RUNECRAFT", "runecrafting": "RUNECRAFT", "rc": "RUNECRAFT",
    "construction": "CONSTRUCTION", "con": "CONSTRUCTION", "cons": "CONSTRUCTION",
    "hitpoints": "HITPOINTS", "hp": "HITPOINTS",
    "agility": "AGILITY", "agi": "AGILITY",
    "herblore": "HERBLORE", "herb": "HERBLORE",
    "thieving": "THIEVING", "thiev": "THIEVING",
    "crafting": "CRAFTING", "craft": "CRAFTING",
    "fletching": "FLETCHING", "fletch": "FLETCHING",
    "slayer": "SLAYER", "slay": "SLAYER",
    "hunter": "HUNTER", "hunt": "HUNTER",
    "mining": "MINING", "mine": "MINING",
    "smithing": "SMITHING", "smith": "SMITHING",
    "fishing": "FISHING", "fish": "FISHING",
    "cooking": "COOKING", "cook": "COOKING",
    "firemaking": "FIREMAKING", "fm": "FIREMAKING",
    "woodcutting": "WOODCUTTING", "wc": "WOODCUTTING",
    "farming": "FARMING", "farm": "FARMING",
}

# "to/until/reach/get 43 prayer"  and  "prayer to 43"
SKILL_RE_1 = re.compile(r'\b(?:to|until|reach|get|hit|for)\s+(\d{1,2})\s+([a-zA-Z]+)', re.I)
SKILL_RE_2 = re.compile(r'\b([a-zA-Z]+)\s+to\s+(\d{1,2})\b', re.I)


USER_AGENT = "OsirisGuide-scraper/1.0 (+https://github.com/dangraagu/Osiris-guide; build-time content import)"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")


def extract_howto_steps(html: str):
    """Return an ordered list of (position, name, location, url) from all HowTo blocks."""
    out = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("@type") != "HowTo":
            continue
        steps = data.get("step") or data.get("itemListElement") or []
        for s in steps:
            if not isinstance(s, dict):
                continue
            name = (s.get("name") or s.get("text") or "").strip()
            loc = None
            direction = s.get("itemListElement")
            if isinstance(direction, dict):
                txt = direction.get("text") or ""
                loc = re.sub(r'^\s*Location:\s*', '', txt).strip() or None
            out.append((s.get("position"), name, loc, s.get("url")))
    return out


def detect_skill(text: str):
    """Return {'op':'skill',...} if the text states a clear training target, else None."""
    for rx, si, li in ((SKILL_RE_1, 1, 0), (SKILL_RE_2, 0, 1)):
        for m in rx.finditer(text):
            word = m.group(1 + si).lower()
            level = int(m.group(1 + li))
            if word in SKILL_WORDS and 1 <= level <= 99:
                return {"op": "skill", "skill": SKILL_WORDS[word], "level": level, "cmp": ">="}
    return None


# --- Item acquisition detection (conservative) -------------------------------

ACQUIRE_VERBS = ("buy", "purchase", "pick up", "pickup", "collect", "grab", "loot",
                 "obtain", "withdraw", "steal", "gather")
_INT_RE = re.compile(r'\d+')


def fetch_item_map():
    """name(lowercased) -> item id, from the OSRS Wiki tradeable-item mapping."""
    try:
        raw = fetch("https://prices.runescape.wiki/api/v1/osrs/mapping")
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not fetch item map ({e}); skipping item enrichment", file=sys.stderr)
        return {}
    m = {}
    for it in data:
        name = (it.get("name") or "").strip().lower()
        iid = it.get("id")
        # keep the lowest id for a given name (avoids noted/variant ids winning)
        if name and isinstance(iid, int) and (name not in m or iid < m[name]):
            m[name] = iid
    return m


def _norm(s: str) -> str:
    return " " + re.sub(r'[^a-z0-9 ]+', ' ', s.lower()).strip() + " "


def detect_item(text: str, item_map):
    """
    Conservative: only when the step has an acquisition verb AND an exact known item name
    (word-boundary, singular or +s plural) appears. Returns {'op':'itemAcquired',...} or None.
    Fails toward None so a miss stays manual rather than mis-tracking.
    """
    if not item_map:
        return None
    low = text.lower()
    if not any(v in low for v in ACQUIRE_VERBS):
        return None
    padded = _norm(text)
    best_name, best_id = None, None
    for name, iid in item_map.items():
        if len(name) < 4:
            continue  # skip 1-3 char names (too ambiguous)
        if (" " + name + " ") in padded or (" " + name + "s ") in padded:
            if best_name is None or len(name) > len(best_name):
                best_name, best_id = name, iid
    if best_id is None:
        return None
    # quantity: only an integer appearing BEFORE the item name (e.g. "pick up 5 swamp tar").
    # A number after the name usually belongs to a different item in a multi-buy step, so we
    # default to 1 rather than grabbing it — safer (avoids absurd quantities that never complete).
    pos = padded.find(" " + best_name)
    ints = [(m.start(), int(m.group())) for m in _INT_RE.finditer(padded)]
    before = [v for (s, v) in ints if s < pos]
    qty = max(1, min(before[-1] if before else 1, 100000))
    return {"op": "itemAcquired", "id": best_id, "qty": qty}


# --- Location gazetteer (approximate area centres) ---------------------------
# Maps a location phrase from the guide to an approximate WorldPoint so the world-map marker and
# in-scene arrow point toward the right area. Deliberately conservative — only well-known places,
# and only area-level accuracy (the step text still gives the precise spot). Longest key wins.
GAZETTEER = {
    "lumbridge swamp": (3200, 3170), "lumbridge castle": (3222, 3218), "lumbridge": (3222, 3218),
    "draynor manor": (3108, 3352), "draynor": (3093, 3244),
    "rimmington": (2957, 3215), "port sarim": (3050, 3245), "falador": (2965, 3380),
    "wizard tower": (3110, 3167), "varrock": (3213, 3428), "grand exchange": (3164, 3486),
    "edgeville": (3087, 3496), "al-kharid": (3293, 3184), "al kharid": (3293, 3184),
    "barbarian village": (3082, 3420), "ferox": (3151, 3635),
    "yanille": (2605, 3095), "khazard": (2660, 3155), "ardougne": (2662, 3305), "ardy": (2662, 3305),
    "catherby": (2805, 3433), "seers": (2725, 3485), "camelot": (2757, 3477),
    "taverley": (2895, 3443), "burthorpe": (2900, 3543), "canifis": (3495, 3488),
    "gnome stronghold": (2445, 3424), "rellekka": (2660, 3657), "castle wars": (2440, 3090),
    "phasmatys": (3685, 3475),
}


def gazetteer_lookup(loc):
    if not loc:
        return None
    low = loc.lower()
    best = None
    for key, xy in GAZETTEER.items():
        if key in low and (best is None or len(key) > len(best)):
            best = key
    return [GAZETTEER[best][0], GAZETTEER[best][1], 0] if best else None


def heading(name: str, words: int = 6) -> str:
    parts = name.split()
    h = " ".join(parts[:words])
    if len(parts) > words:
        h += " …"
    return h[:70]


def build_step(prefix, position, name, loc, url, item_map):
    sid = f"{prefix}-{position:03d}" if isinstance(position, int) else f"{prefix}-{position}"
    text = name
    if loc:
        text = f"{name}\nLocation: {loc}"
    step = {"id": sid, "title": heading(name), "text": text}
    if url and isinstance(url, str) and url.startswith("http"):
        step["wiki"] = url
    cond = detect_skill(name) or detect_item(name, item_map)
    if cond:
        step["complete"] = cond
    else:
        step["manual"] = True
    # Highlight the acquired item in the inventory/bank.
    if cond and cond.get("op") == "itemAcquired":
        step["item"] = cond["id"]
    # Point the world-map marker / arrow at the step's area, when we know it.
    world = gazetteer_lookup(loc)
    if world:
        step["world"] = world
    return step


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    item_map = fetch_item_map()
    print(f"loaded {len(item_map)} item names for enrichment")
    index = {"_comment": "Auto-generated by tools/scrape_guide.py. Ordered section files.",
             "sections": []}
    grand_total = 0
    grand_skill = 0
    grand_item = 0
    for order, slug, display, prefix in SECTIONS:
        url = f"https://ironman.guide/guide/{slug}"
        try:
            html = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {slug}: fetch failed: {e}", file=sys.stderr)
            continue
        raw = extract_howto_steps(html)
        steps = [build_step(prefix, pos, name, loc, u, item_map) for (pos, name, loc, u) in raw if name]
        skill = sum(1 for s in steps if s.get("complete", {}).get("op") == "skill")
        item = sum(1 for s in steps if s.get("complete", {}).get("op") == "itemAcquired")
        grand_total += len(steps)
        grand_skill += skill
        grand_item += item
        fname = f"{order}-{slug}.json"
        payload = {
            "_source": url,
            "_attribution": "Route by Oziris (@OzirisLoL) / ironman.guide. See NOTICE.",
            "section": display,
            "steps": steps,
        }
        (OUT_DIR / fname).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        index["sections"].append(fname)
        print(f"  {fname:34s} {len(steps):4d} steps  ({skill} skill, {item} item)")

    (OUT_DIR / "route-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    auto = grand_skill + grand_item
    print(f"\nTOTAL: {grand_total} steps — {auto} auto ({grand_skill} skill + {grand_item} item), "
          f"{grand_total - auto} manual")
    print(f"Wrote {len(index['sections'])} section files + route-index.json to {OUT_DIR}")


if __name__ == "__main__":
    main()
