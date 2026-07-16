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

# --- Guide config -------------------------------------------------------------
# To add a NEW guide: give it an id (folder name), a source-URL template, and its section list;
# then also add a matching value to com.osirisguide.Guide and an entry in data/guides.json.
GUIDE_ID = "osiris-ironman"
GUIDE_URL = "https://ironman.guide/guide/{slug}"

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

_RES = Path(__file__).resolve().parent.parent / "src" / "main" / "resources" / "com" / "osirisguide"
OUT_DIR = _RES / "data" / "guides" / GUIDE_ID

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
    t = re.sub(r'[^a-z0-9 ]+', ' ', s.lower().replace("&", " and "))
    return " " + re.sub(r'\s+', ' ', t).strip() + " "


def detect_item_id_qty(text: str, item_map):
    """
    Conservative: only when the step has an acquisition verb AND an exact known item name
    (word-boundary, singular or +s plural) appears. Returns (item_id, qty) or None.
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
    return (best_id, qty)


def item_condition(item_id, cumulative_qty, total_qty):
    """
    Complete a pickup step when EITHER:
      - you've acquired the cumulative amount the guide has asked for through this step (ledger) — so a
        repeated item's later step only completes after you've gathered its own share; OR
      - you currently own the guide's TOTAL need of the item anywhere (inv/bank/equip) — so an existing
        account that already banked enough for the whole run skips the pickup.
    """
    return {"op": "or", "of": [
        {"op": "itemAcquired", "id": item_id, "qty": cumulative_qty},
        {"op": "item", "id": item_id, "qty": total_qty, "scope": "ANY"},
    ]}


# --- Quest detection ---------------------------------------------------------

def load_quest_map():
    """display-name -> RuneLite Quest enum constant, from tools/data/quest_names.json."""
    p = Path(__file__).parent / "data" / "quest_names.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[!] could not read quest map ({e})", file=sys.stderr)
    return {}


# Quest-start tiles: RuneLite quest CONSTANT -> [x,y,z], "where to go to begin/continue the quest".
# Fills the coord on quest steps, which never get a precise NPC/object highlight (enrich_entity skips them).
QUEST_START_BY_CONST = {}


def load_quest_start(quest_map):
    """Bridge data/quest_start_coords.json (keyed by quest DISPLAY name) onto RuneLite quest CONSTANTS
    via quest_map (display -> const). Normalises names on both sides so "Cook's Assistant" matches
    "Cooks Assistant". Returns how many quests got a start tile."""
    p = Path(__file__).parent / "data" / "quest_start_coords.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read quest_start_coords ({e})", file=sys.stderr)
        return 0
    norm_to_const = {_norm(disp): const for disp, const in (quest_map or {}).items()}
    n = 0
    for disp, xy in data.items():
        if not (isinstance(xy, (list, tuple)) and len(xy) >= 2):
            continue
        const = norm_to_const.get(_norm(disp))
        if const:
            QUEST_START_BY_CONST[const] = [int(xy[0]), int(xy[1]), int(xy[2]) if len(xy) > 2 else 0]
            n += 1
    return n


def detect_quest(text: str, quest_map):
    """
    If a quest's display name appears in the step, complete the step when that quest is FINISHED.
    Dynamic: for an existing account this also auto-skips a quest AND its prep steps once it's done.
    Longest name wins. Punctuation is normalised on both sides so "Cook's Assistant" matches.
    """
    if not quest_map:
        return None
    padded = _norm(text)
    best_norm, best_const = None, None
    for name, const in quest_map.items():
        nn = _norm(name)  # _norm handles "&" -> "and" so "Romeo & Juliet" matches either spelling
        if len(nn.strip()) < 4:
            continue
        if nn in padded and (best_norm is None or len(nn) > len(best_norm)):
            best_norm, best_const = nn, const
    if best_const is None:
        return None
    return {"op": "quest", "quest": best_const, "state": "FINISHED"}


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


def load_location_coords():
    """Merge wiki-grounded coords into the built-in gazetteer from, in order:
      - data/gazetteer.json     (broad OSRS town/area centres, for step-text fallbacks)
      - data/location_coords.json (finer per-phrase coords; loaded last so it wins ties)
    More specific / later phrases win via the longest-key match in gazetteer_lookup."""
    n = 0
    for fname in ("gazetteer.json", "location_coords.json"):
        p = Path(__file__).parent / "data" / fname
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[!] could not read {fname} ({e})", file=sys.stderr)
            continue
        for phrase, xy in data.items():
            if isinstance(xy, (list, tuple)) and len(xy) >= 2:
                GAZETTEER[phrase.strip().lower()] = (int(xy[0]), int(xy[1]))
                n += 1
    return n


# --- QH entity references (NPC/object id + coords harvested from Quest Helper) ------
# Generic nouns that must never match an entity id (would false-positive onto unrelated steps).
QH_STOP = {
    "tree", "fire", "range", "well", "onion", "cook", "door", "altar", "ladder", "bank", "chest",
    "rope", "gate", "stall", "wall", "rock", "fish", "bush", "cave", "stairs", "table", "crate",
    "boat", "ship", "sack", "bed", "pot", "pan", "log", "logs", "coin", "coins", "man", "woman",
    "guard", "sign", "box", "bar", "net", "cabbage", "potato", "wheat", "unicorn", "cow", "chicken",
    "rat", "spider", "bones", "food", "drink", "jug", "bowl", "monkey", "knight", "black knight",
    # generic words that collide with skilling/spell/item terms, not the entity of that name:
    "strike", "swamp", "house", "mage", "dragon", "wire", "bird", "hops", "willow", "abyss", "ghost",
    "seaweed", "clay", "flour", "barley", "silver", "gold", "coal", "iron", "steel", "mithril",
}


def load_qh_entities():
    p = Path(__file__).parent / "data" / "qh_entities.json"
    if not p.exists():
        return {"npcs": {}, "objects": {}}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {"npcs": d.get("npcs", {}), "objects": d.get("objects", {})}
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read QH entities ({e})", file=sys.stderr)
        return {"npcs": {}, "objects": {}}


def _match_named(text, table):
    """Longest known entity name (>=4 chars, not generic) appearing as a whole phrase in text.
    Returns (name, id, [x,y,z]) or None."""
    padded = _norm(text)
    best = None
    for name, info in table.items():
        if len(name) < 4 or name in QH_STOP:
            continue
        if (" " + name + " ") in padded and (best is None or len(name) > len(best[0])):
            best = (name, info.get("id"), info.get("world"))
    if best and best[1] is not None and best[2]:
        return best
    return None


def enrich_entity(step, text, cond_op, item_id, entities):
    """Set a precise NPC/object highlight id + tile from the QH reference table where the step names a
    specific entity. Skips quest steps (an arbitrary highlight there would be wrong) and skips object
    matches on item-buy steps (avoids matching a bought vegetable as a scenery object)."""
    if cond_op == "quest":
        return
    hit = _match_named(text, entities["npcs"])
    key = "npc"
    if not hit and item_id is None:
        hit = _match_named(text, entities["objects"])
        key = "object"
    if hit:
        w = hit[2]
        if len(w) < 2 or w[1] >= 6400:
            return  # instance/dungeon coords — not a useful surface target, usually a mis-map
        step[key] = hit[1]
        step["world"] = [w[0], w[1], w[2] if len(w) > 2 else 0]


def heading(name: str, words: int = 6) -> str:
    parts = name.split()
    h = " ".join(parts[:words])
    if len(parts) > words:
        h += " …"
    return h[:70]


# --- Step atomisation: split a multi-action step into single tasks -----------
# Imperative verbs that begin a distinct action; a separator (,/;/./then/and) only starts a NEW atom
# when the text after it begins with one of these, so "buy a bucket and a rope" stays one task but
# "buy a bucket and run to the bank" splits.
TRAVEL_VERBS = {"go", "head", "run", "walk", "travel", "enter", "climb", "cross", "return", "teleport"}
ACTION_VERBS = TRAVEL_VERBS | {
    "talk", "speak", "get", "grab", "pick", "take", "buy", "sell", "mine", "chop", "cut", "fish",
    "catch", "cook", "use", "craft", "smith", "smelt", "kill", "cast", "equip", "wield", "wear",
    "drop", "bank", "withdraw", "deposit", "open", "search", "pray", "pickpocket", "steal", "plant",
    "pay", "fill", "light", "burn", "bury", "board", "ride", "collect", "build", "complete", "attack",
    "trade", "exchange", "read", "operate", "drink", "eat", "unlock", "claim", "hand", "give", "start",
    "finish", "train", "make", "smash", "dig", "loot", "turn", "set", "activate", "toggle", "select",
}
# Steps longer than this are prose/notes (multi-sentence paragraphs with conditionals), not a clean
# imperative action list — atomising them produces noise, so they're left whole.
MAX_SPLIT_LEN = 180
_BOUNDARY_RE = re.compile(r"\s*(?:;|,|\.|\bthen\b|\band\b)\s+", re.IGNORECASE)
_FIRST_WORD_RE = re.compile(r"\s*([a-zA-Z]+)")
_TRAIL_CONN_RE = re.compile(r"(?:[\s,;.]+|\s+(?:and|then))+$", re.IGNORECASE)


def _starts_with_action(fragment):
    m = _FIRST_WORD_RE.match(fragment or "")
    return bool(m) and m.group(1).lower() in ACTION_VERBS


def split_atoms(name):
    """Split a step into single-action atoms at action boundaries, preserving the original wording.
    A separator only splits when the text after it begins with an action verb; trailing 'and'/'then'
    fragments merge back so 'buy a bucket and a rope' stays one task. Returns >=1 atom; a step with no
    internal boundary is returned unchanged."""
    s = (name or "").strip()
    if not s:
        return []
    if len(s) > MAX_SPLIT_LEN:
        return [s]  # long prose isn't a clean action list — don't shred it into noise
    atoms = []
    start = 0
    for m in _BOUNDARY_RE.finditer(s):
        if _starts_with_action(s[m.end():]):
            seg = _TRAIL_CONN_RE.sub("", s[start:m.start()]).strip()
            if seg:
                atoms.append(seg)
            start = m.end()
    tail = _TRAIL_CONN_RE.sub("", s[start:]).strip()
    if tail:
        atoms.append(tail)
    # A fragment that doesn't itself start with an action is a continuation, not a new task: merge back.
    merged = []
    for a in atoms:
        if merged and not _starts_with_action(a):
            merged[-1] = (merged[-1] + " " + a).strip()
        else:
            merged.append(a)
    return merged or [s]


def is_travel(name):
    """True for a pure 'go/head/run to X' atom — the kind that completes just by arriving."""
    s = (name or "").strip().lower()
    if s.startswith("make your way"):
        return True
    m = _FIRST_WORD_RE.match(s)
    return bool(m) and m.group(1) in TRAVEL_VERBS


TRAVEL_RADIUS = 10  # tiles; "arrived at the area" is coarse, so a bit wider than an exact-tile task


def build_step(prefix, position, name, loc, url, item_map, quest_map, cumulative, total_needed, entities,
               sub=None):
    sid = f"{prefix}-{position:03d}" if isinstance(position, int) else f"{prefix}-{position}"
    if sub:
        sid = f"{sid}{sub}"  # atom of a split step (a/b/c…) — keeps ids unique + stable
    text = name
    if loc:
        text = f"{name}\nLocation: {loc}"
    step = {"id": sid, "title": heading(name), "text": text}
    if url and isinstance(url, str) and url.startswith("http"):
        step["wiki"] = url
    # Precedence: skill target > quest completion > item acquisition (different kinds of goal).
    cond = detect_skill(name) or detect_quest(name, quest_map)
    item_id = None
    if not cond:
        iq = detect_item_id_qty(name, item_map)
        if iq:
            item_id, qty = iq
            cumulative[item_id] = cumulative.get(item_id, 0) + qty
            cond = item_condition(item_id, cumulative[item_id],
                                  total_needed.get(item_id, cumulative[item_id]))
    if cond:
        step["complete"] = cond
    else:
        step["manual"] = True
    if item_id is not None:
        step["item"] = item_id  # highlight it in inventory/bank
    # Coordinate resolution, best-first: a precise NPC/object tile (from the QH reference table) wins;
    # else the area centre from the loc field; else the area centre from any place named in the step
    # text ("go to Falador" -> Falador centre). This fills the "no clickable spot" steps.
    enrich_entity(step, name, step.get("complete", {}).get("op"), item_id, entities)
    if "world" not in step:
        # loc-hint (guide's own per-step location) > quest-start tile > any place named in the text.
        world = gazetteer_lookup(loc)
        cq = step.get("complete", {})
        if not world and cq.get("op") == "quest":
            qs = QUEST_START_BY_CONST.get(cq.get("quest"))
            if qs:
                world = list(qs)
        if not world:
            world = gazetteer_lookup(name)
        if world:
            step["world"] = world
    # A pure-travel atom with a destination auto-completes on ARRIVAL: attach a position trigger so
    # "go to X" advances by itself. Only when the atom is still manual (no skill/quest/item goal) — a
    # talk/interact step must not complete just from walking past it.
    if step.get("manual") and "world" in step and is_travel(name):
        x, y, z = step["world"]
        step["complete"] = {"op": "position", "x": x, "y": y, "z": z, "radius": TRAVEL_RADIUS}
        del step["manual"]
    return step


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    item_map = fetch_item_map()
    quest_map = load_quest_map()
    load_location_coords()
    nqs = load_quest_start(quest_map)
    entities = load_qh_entities()
    print(f"loaded {len(item_map)} item names, {len(quest_map)} quest names, {len(GAZETTEER)} "
          f"locations, {nqs} quest-start tiles, {len(entities['npcs'])} npcs + "
          f"{len(entities['objects'])} objects (QH refs)")

    # Fetch every section first (need all steps to total the item needs before building).
    sections = []
    for order, slug, display, prefix in SECTIONS:
        url = GUIDE_URL.format(slug=slug)
        try:
            html = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {slug}: fetch failed: {e}", file=sys.stderr)
            continue
        sections.append((order, slug, display, prefix, url, extract_howto_steps(html)))

    # Pass 1: the "total items needed" database — sum every acquisition qty per item, using the SAME
    # precedence as the build (a step that is a skill/quest goal is not an item-acquisition step).
    total_needed = {}
    for (_o, _s, _d, _p, _u, raw) in sections:
        for (pos, name, loc, u) in raw:
            for atom in split_atoms(name):  # same atoms as the build pass, so item totals line up
                if detect_skill(atom) or detect_quest(atom, quest_map):
                    continue
                iq = detect_item_id_qty(atom, item_map)
                if iq:
                    total_needed[iq[0]] = total_needed.get(iq[0], 0) + iq[1]

    # Pass 2: build steps, carrying a running cumulative per item across the whole guide.
    index = {"_comment": "Auto-generated by tools/scrape_guide.py. Ordered section files.",
             "sections": []}
    cumulative = {}
    grand_total = grand_skill = grand_quest = grand_item = grand_world = grand_entity = 0
    for (order, slug, display, prefix, url, raw) in sections:
        steps = []
        for (pos, name, loc, u) in raw:
            if not name:
                continue
            atoms = split_atoms(name)
            for i, atom in enumerate(atoms):
                sub = None if len(atoms) == 1 else (chr(97 + i) if i < 26 else str(i))
                steps.append(build_step(prefix, pos, atom, loc, u, item_map, quest_map,
                                        cumulative, total_needed, entities, sub=sub))

        def _kind(s):
            return s.get("complete", {}).get("op")
        skill = sum(1 for s in steps if _kind(s) == "skill")
        quest = sum(1 for s in steps if _kind(s) == "quest")
        item = sum(1 for s in steps if _kind(s) == "or")
        world = sum(1 for s in steps if "world" in s)
        grand_entity += sum(1 for s in steps if "npc" in s or "object" in s)
        grand_total += len(steps)
        grand_skill += skill
        grand_quest += quest
        grand_item += item
        grand_world += world
        fname = f"{order}-{slug}.json"
        payload = {
            "_source": url,
            "_attribution": "Route by Oziris (@OzirisLoL) / ironman.guide. See NOTICE.",
            "section": display,
            "steps": steps,
        }
        (OUT_DIR / fname).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        index["sections"].append(fname)
        print(f"  {fname:34s} {len(steps):4d} steps  ({skill} skill, {quest} quest, {item} item, {world} loc)")

    (OUT_DIR / "route-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    auto = grand_skill + grand_quest + grand_item
    print(f"\nTOTAL: {grand_total} steps — {auto} auto ({grand_skill} skill + {grand_quest} quest + "
          f"{grand_item} item), {grand_total - auto} manual; {grand_world} have a location, "
          f"{grand_entity} have a precise NPC/object (QH refs)")
    print(f"item-needs database: {len(total_needed)} distinct items totalled")
    print(f"Wrote {len(index['sections'])} section files + route-index.json to {OUT_DIR}")


if __name__ == "__main__":
    main()
