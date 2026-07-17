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


def gazetteer_key(text):
    """The longest gazetteer place name appearing in the text, or None — i.e. the step's context town."""
    if not text:
        return None
    low = text.lower()
    best = None
    for key in GAZETTEER:
        if key in low and (best is None or len(key) > len(best)):
            best = key
    return best


def gazetteer_lookup(loc):
    key = gazetteer_key(loc)
    return [GAZETTEER[key][0], GAZETTEER[key][1], 0] if key else None


# --- Amenities: the actual shop/facility inside a town ------------------------
# "Buy a spade" in Lumbridge should point at the GENERAL STORE, not the town centre. amenities.json
# (wiki-harvested) maps town -> {amenity/shop name -> [x,y,plane]}; the step's action keyword (or a
# named shop in the text) picks the facility, the loc/text picks the town.
AMENITIES = {}

AMENITY_ACTIONS = [
    (re.compile(r"\b(buy|buys|buying|purchase|sell|selling|shop\s?keeper)\b", re.IGNORECASE), "general store"),
    (re.compile(r"\b(bank|banker|banking|deposit|withdraw|unnote)\b", re.IGNORECASE), "bank"),
    (re.compile(r"\b(smelt|furnace)\b", re.IGNORECASE), "furnace"),
    (re.compile(r"\b(smith|anvil)\b", re.IGNORECASE), "anvil"),
    (re.compile(r"\b(cook|range)\b", re.IGNORECASE), "range"),
    (re.compile(r"\b(spin|spinning)\b", re.IGNORECASE), "spinning wheel"),
    (re.compile(r"\b(altar|pray|prayer|church|priest)\b", re.IGNORECASE), "altar"),
    (re.compile(r"\bwell\b", re.IGNORECASE), "well"),
]

_BUY_SELL_RE = re.compile(r"\b(buy|buys|buying|purchase|sell|selling)\b", re.IGNORECASE)
# words too generic to match a shop name by token ("general store" must not match "store the item")
_TOKEN_STOP = {"the", "and", "buy", "sell", "from", "for", "your", "some", "then", "with", "into",
               "out", "all", "you", "get", "now", "them", "they", "this", "that", "run", "use",
               "shop", "store", "general"}


def _dist(a, b):
    ax, ay = int(a[0]), int(a[1])
    bx, by = int(b[0]), int(b[1])
    # Underground regions sit +6400 in y above their surface spot; normalise for DISTANCE ONLY so an
    # Edgeville anchor sees the Edgeville Dungeon site as near, not 6000 tiles away. (The emitted
    # coordinate keeps its true underground y.)
    if ay > 6400:
        ay -= 6400
    if by > 6400:
        by -= 6400
    return max(abs(ax - bx), abs(ay - by))


AMENITY_TOWN_CAP = 100  # tiles: only borrow a town's amenities when the route is actually near it


def town_near(anchor):
    """Nearest amenity-covered town to the anchor coord (route continuity), within a sanity cap."""
    if not anchor or not AMENITIES:
        return None
    best, bd = None, AMENITY_TOWN_CAP + 1
    for town in AMENITIES:
        c = GAZETTEER.get(town)
        if not c:
            continue
        d = _dist(anchor, c)
        if d < bd:
            best, bd = town, d
    return best


def _shop_by_item(low, spots):
    """'Buy an axe' + a town with \"bob's brilliant axes\" -> that shop: match the traded item's word
    against the shop-name tokens (exact, +/-plural, or long-word containment)."""
    words = {w for w in re.findall(r"[a-z]{3,}", low) if w not in _TOKEN_STOP}
    if not words:
        return None
    best = None
    for key in spots:
        for tok in re.findall(r"[a-z]{3,}", key):
            if tok in _TOKEN_STOP:
                continue
            hit = any(w == tok or tok == w + "s" or w == tok + "s"
                      or (len(w) >= 5 and w in tok) for w in words)
            if hit and (best is None or len(key) > len(best)):
                best = key
                break
    return best


def load_amenities():
    p = Path(__file__).parent / "data" / "amenities.json"
    if not p.exists():
        return 0
    try:
        AMENITIES.update(json.loads(p.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read amenities.json ({e})", file=sys.stderr)
        return 0
    return sum(len(v) for v in AMENITIES.values())


def amenity_lookup(name, loc, anchor=None):
    """Precise facility tile for the step's action, or None. Town comes from the loc hint, the step
    text, or — route continuity — the nearest amenity town to the previous step's coord. Facility
    precedence: shop NAMED in the step > shop matching the traded ITEM ("buy an axe" -> the axe shop)
    > the action keyword's default (buy/sell -> general store, bank -> bank, ...)."""
    town = gazetteer_key(loc) or gazetteer_key(name) or town_near(anchor)
    spots = AMENITIES.get(town) if town else None
    if not spots:
        return None
    low = (name or "").lower()
    best = None
    for key in spots:  # a named shop/facility mentioned verbatim in the step text
        if key in low and (best is None or len(key) > len(best)):
            best = key
    if best is None and _BUY_SELL_RE.search(low):
        best = _shop_by_item(low, spots)
    if best is None:
        for rx, amen in AMENITY_ACTIONS:  # else the action keyword's default facility
            if rx.search(low) and amen in spots:
                best = amen
                break
    if best is None:
        return None
    xy = spots[best]
    return [int(xy[0]), int(xy[1]), int(xy[2]) if len(xy) > 2 else 0]


# --- Craft-gap fill: make/smith steps borrow a location from their neighbours ---
# "Make molten glass" carries no place of its own. Infer the FACILITY it needs (furnace/anvil/
# range/wheel) from the product, then pick that facility in the town nearest the PREVIOUS located
# step (else the NEXT) — so the pointer lands on a real anvil, never inside the raid the previous
# step happened to be in. No facility inferable -> inherit the previous step's coord (you craft
# where you are).
CRAFT_VERB_RE = re.compile(r"^\s*(make|craft|mix|string|fletch|create|prepare|brew|smith|smelt|cook)\b",
                           re.IGNORECASE)
_FACILITY_RULES = [
    (re.compile(r"\b(smith|anvil|dart tips?|darts|nails|bolts|grapple|armou?r|scimitar|sword|helm|"
                r"platebody|platelegs)\b", re.IGNORECASE), "anvil"),
    (re.compile(r"\b(smelt|molten|glass|bars?|rings?|amulets?|necklaces?|bracelets?|tiaras?|jewell?ery)\b",
                re.IGNORECASE), "furnace"),
    (re.compile(r"\b(cook|pies?|bread|stew|cake)\b", re.IGNORECASE), "range"),
    (re.compile(r"\b(spin|bowstrings?)\b", re.IGNORECASE), "spinning wheel"),
]
FACILITY_CAP = 300  # tiles: crafting facilities are worth a longer hop than borrowing a shop


def facility_for(text):
    for rx, fac in _FACILITY_RULES:
        if rx.search(text or ""):
            return fac
    return None


def town_near_with(anchor, facility):
    """Nearest amenity town (within FACILITY_CAP of the anchor) that actually HAS the facility."""
    if not anchor or not AMENITIES:
        return None
    best, bd = None, FACILITY_CAP + 1
    for town, spots in AMENITIES.items():
        if facility not in spots:
            continue
        c = GAZETTEER.get(town)
        if not c:
            continue
        d = _dist(anchor, c)
        if d < bd:
            best, bd = town, d
    return best


_BANK_STEP_RE = re.compile(r"\b(bank|deposit|withdraw|unnote)\b", re.IGNORECASE)
# same-place micro-continuation: an atom fragment, or a verb that acts where you already stand.
_CONT_START_RE = re.compile(r"^\s*(equip|wear|wield|take|grab|claim|pick up|drop|use|read|open|search|"
                            r"climb|go up|go down|go back|enter|exit|leave|talk to|continue|deposit|"
                            r"eat|drink|light|burn|fill|empty|note|unnote|cast)\b", re.IGNORECASE)
_ADVICE_START_RE = re.compile(r"^\s*(i |you |prioriti|remember|note that|make sure|should|consider|"
                              r"reminder|recommend|assume|when |while |after |once |if |order of|"
                              r"optional|all settings|repeat|prio |train |do slayer|keep )", re.IGNORECASE)
BANK_CAP = 120  # tiles: a bank step borrows the nearest bank only if the route is actually near one


def nearest_bank(anchor):
    if not anchor or not AMENITIES:
        return None
    best, bd = None, BANK_CAP + 1
    for town, spots in AMENITIES.items():
        b = spots.get("bank")
        c = GAZETTEER.get(town)
        if not b or not c:
            continue
        d = _dist(anchor, c)
        if d < bd:
            best, bd = b, d
    return [int(best[0]), int(best[1]), int(best[2]) if len(best) > 2 else 0] if best else None


def _parent_id(sid):
    return re.sub(r"[a-z]$", "", sid or "")


def fill_location_gaps(steps):
    """Post-pass locating same-place unlocated steps, most-confident first:
      1. atom sibling — an unlocated atom inherits a LOCATED sibling atom's tile (one guide step split
         into a/b/c happens in one place);
      2. a bank/deposit/withdraw step -> the nearest bank to the route position;
      3. a clear same-place micro-continuation ("equip it", "go upstairs", a lowercase fragment) ->
         the previous step's tile.
    Skill grinds / advice are matched by neither 3's verbs nor the fragment test, so they stay
    unlocated (never given a misleading 'where you last were' arrow)."""
    located = {s["id"]: s.get("world") for s in steps}
    by_parent = {}
    for s in steps:
        if s.get("world"):
            by_parent.setdefault(_parent_id(s["id"]), s["world"])
    n_sib = n_bank = n_cont = 0
    anchor = None
    for s in steps:
        if s.get("world"):
            anchor = s["world"]
            continue
        sid = s["id"]
        text = (s.get("text") or "").split("\n")[0]
        sib = by_parent.get(_parent_id(sid))
        if sib and located.get(sid) is None:
            s["world"] = list(sib)
            anchor = s["world"]
            n_sib += 1
            continue
        if _BANK_STEP_RE.search(text):
            nb = nearest_bank(anchor)
            if nb:
                s["world"] = nb
                anchor = nb
                n_bank += 1
                continue
        is_fragment = bool(text[:1].islower())  # mid-sentence atom continuation
        if anchor and not _ADVICE_START_RE.match(text) and (is_fragment or _CONT_START_RE.match(text)):
            s["world"] = list(anchor)
            n_cont += 1
    return n_sib, n_bank, n_cont


def fill_craft_gaps(steps):
    """Post-pass over a built step list: locate unlocated craft steps from their neighbours."""
    n = 0
    for i, s in enumerate(steps):
        if "world" in s:
            continue
        text = (s.get("text") or "").split("\n")[0]
        # Strip a leading label ("Construction method: Make ...") so the craft verb is seen.
        text = re.sub(r"^[A-Za-z][A-Za-z ]{0,24}:\s+", "", text)
        if not CRAFT_VERB_RE.match(text):
            continue
        prev_w = next((steps[j]["world"] for j in range(i - 1, -1, -1) if "world" in steps[j]), None)
        next_w = next((steps[j]["world"] for j in range(i + 1, len(steps)) if "world" in steps[j]), None)
        world = None
        fac = facility_for(text)
        if fac:
            for a in (prev_w, next_w):
                town = town_near_with(a, fac)
                if town:
                    xy = AMENITIES[town][fac]
                    world = [int(xy[0]), int(xy[1]), int(xy[2]) if len(xy) > 2 else 0]
                    break
        if world is None and (prev_w or next_w):
            world = list(prev_w or next_w)
        if world:
            s["world"] = world
            n += 1
    return n


# --- Quest Helper full step map: inherit QH's exact tiles by text match --------
# qh_steps.json holds EVERY Quest Helper step (text + tile + npc/object ids, 7.5k rows). A guide step
# that paraphrases a QH step ("Dig up the clue north of bob's axes" ~ "Dig north of Bob's Brilliant
# Axes...") inherits QH's exact tile + highlight ids. Deliberately conservative: >=3 content tokens,
# >=60% of the guide step's tokens present in the QH text, the QH tile must sit in the step's region
# (near its coarse context/anchor), and the best match must beat the runner-up clearly.
QH_STEPS = []           # [(tokenset, [x,y,z], npc|None, object|None)]
_QH_TOKEN_INDEX = {}    # token -> [step indices]
_QH_STOPWORDS = {
    "the", "a", "an", "to", "of", "up", "in", "at", "on", "for", "and", "or", "with", "your",
    "you", "from", "then", "into", "out", "it", "its", "his", "her", "them", "there", "here",
    "that", "this", "will", "should", "can", "any", "all", "some", "more", "again", "just",
}
QH_MATCH_MIN_TOKENS = 3
QH_MATCH_MIN_SCORE = 0.6
QH_MATCH_MARGIN = 0.15
QH_MATCH_REGION = 250  # tiles: a matched tile must be in the step's own region, never across the map


def _content_tokens(text):
    t = (text or "").lower().replace("'", "").replace("’", "")
    return {w for w in re.findall(r"[a-z]{3,}", t) if w not in _QH_STOPWORDS}


def load_qh_steps():
    p = Path(__file__).parent / "data" / "qh_steps.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read qh_steps.json ({e})", file=sys.stderr)
        return 0
    for steps in data.values():
        for s in steps:
            w = s.get("world")
            toks = _content_tokens(s.get("text"))
            if not w or len(w) < 2 or len(toks) < QH_MATCH_MIN_TOKENS:
                continue
            idx = len(QH_STEPS)
            QH_STEPS.append((toks, [int(w[0]), int(w[1]), int(w[2]) if len(w) > 2 else 0],
                             s.get("npc"), s.get("object")))
            for t in toks:
                _QH_TOKEN_INDEX.setdefault(t, []).append(idx)
    _index_helper_names(data)
    return len(QH_STEPS)


# Helper-NAME table: "Complete Varrock easy diary" -> the VARROCK_EASY helper's first step tile.
# Covers diaries / miniquests / RFD subquests that have no RuneLite Quest constant (so the
# quest-start bridge can't see them). Subset match on the key's tokens; ambiguous -> no match.
QH_HELPER_STARTS = {}   # frozenset(tokens) -> [x,y,z]


def _register_helper_name(tokens, world):
    key = frozenset(tokens)
    if not key:
        return
    if key in QH_HELPER_STARTS and QH_HELPER_STARTS[key] != world:
        QH_HELPER_STARTS[key] = None  # colliding names -> poisoned, never match
    else:
        QH_HELPER_STARTS.setdefault(key, world)


def _index_helper_names(data):
    for qkey, steps in data.items():
        first = next((s for s in steps if s.get("world")), None)
        if not first:
            continue
        w = first["world"]
        world = [int(w[0]), int(w[1]), int(w[2]) if len(w) > 2 else 0]
        toks = [t for t in qkey.lower().split("_") if len(t) >= 3 and t not in ("the", "and", "for")]
        if len(toks) >= 2:
            _register_helper_name(toks, world)
        # RFD subquests are referred to by their tail ("Evil Dave subquest")
        if qkey.startswith("RECIPE_FOR_DISASTER_"):
            tail = [t for t in qkey[len("RECIPE_FOR_DISASTER_"):].lower().split("_") if len(t) >= 3]
            if tail:
                _register_helper_name(tail, world)
        # a single, long, distinctive token works alone ("barcrawl")
        for t in toks:
            if len(t) >= 8:
                _register_helper_name([t], world)


QH_HELPER_REGION = 400  # a diary/quest-start can be a bit further from the route anchor than a step


def qh_helper_lookup(name, context=None):
    """First-step tile of the QH helper whose NAME's tokens all appear in the step text; ambiguous or
    colliding names never match. Region-gated when a context is given (never place across the map)."""
    if not QH_HELPER_STARTS:
        return None
    text_tokens = _content_tokens(name)
    if not text_tokens:
        return None
    hits = {tuple(w) for key, w in QH_HELPER_STARTS.items()
            if w is not None and key <= text_tokens}
    if len(hits) != 1:
        return None
    world = list(next(iter(hits)))
    if context and _dist(world, context) > QH_HELPER_REGION:
        return None
    return world


def qh_step_lookup(name, context):
    """Best QH step matching the guide step's text, region-gated to {@code context} ([x,y,z] or None).
    Returns {"world":..., "npc":?, "object":?} or None. Without a context the region gate can't run,
    so no match is returned (never place a step across the map on text alone)."""
    if not QH_STEPS or not context:
        return None
    gtok = _content_tokens(name)
    if len(gtok) < QH_MATCH_MIN_TOKENS:
        return None
    counts = {}
    for t in gtok:
        for i in _QH_TOKEN_INDEX.get(t, ()):
            counts[i] = counts.get(i, 0) + 1
    best = second = None
    for i, shared in counts.items():
        if shared < QH_MATCH_MIN_TOKENS:
            continue
        toks, world, npc, obj = QH_STEPS[i]
        if _dist(world, context) > QH_MATCH_REGION:
            continue
        score = shared / len(gtok)
        if score < QH_MATCH_MIN_SCORE:
            continue
        if best is None or score > best[0]:
            best, second = (score, i), best
        elif second is None or score > second[0]:
            second = (score, i)
    if best is None:
        return None
    if second is not None and best[0] - second[0] < QH_MATCH_MARGIN \
            and QH_STEPS[best[1]][1] != QH_STEPS[second[1]][1]:
        return None  # two different places score alike — ambiguous, don't guess
    toks, world, npc, obj = QH_STEPS[best[1]]
    out = {"world": list(world)}
    if npc is not None:
        out["npc"] = int(npc)
    if obj is not None:
        out["object"] = int(obj)
    return out


# --- Manual coordinate overrides ----------------------------------------------
# tools/data/manual_coords.json: { "<exact step text, lowercased>": [x, y, plane] } — human-verified
# spots that beat EVERY automatic layer. This is where hand-filled context lands, keyed by step text
# so it survives regeneration and re-scraping.
MANUAL_COORDS = {}


def load_manual():
    p = Path(__file__).parent / "data" / "manual_coords.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read manual_coords.json ({e})", file=sys.stderr)
        return 0
    n = 0
    for k, v in data.items():
        if k.startswith("_"):
            continue  # comment keys
        if (isinstance(v, (list, tuple)) and len(v) >= 2) or isinstance(v, dict):
            MANUAL_COORDS[k.strip().lower()] = v
            n += 1
    return n


def manual_lookup(name):
    """Returns {'world': [x,y,z]?, 'npcs': [ids]?} for a manually-annotated step, else None.
    A plain [x,y,z] value is shorthand for {'world': ...}; the dict form can also carry npc id(s)
    ('npc' single or 'npcs' list) for steps like "thieve any man"."""
    v = MANUAL_COORDS.get((name or "").strip().lower())
    if not v:
        return None
    if isinstance(v, dict):
        out = {}
        w = v.get("world")
        if isinstance(w, (list, tuple)) and len(w) >= 2:
            out["world"] = [int(w[0]), int(w[1]), int(w[2]) if len(w) > 2 else 0]
        ids = v.get("npcs") or ([v["npc"]] if v.get("npc") is not None else None)
        if ids:
            out["npcs"] = [int(i) for i in ids]
        return out or None
    return {"world": [int(v[0]), int(v[1]), int(v[2]) if len(v) > 2 else 0]}


# --- Resource sites: where you actually mine/chop/fish/kill -------------------
# resources.json (wiki-harvested) maps a resource ("clay rocks", "oak tree", "fishing shrimp", "cow")
# to a LIST of sites; the step resolves to the site NEAREST the route's current position (anchor),
# falling back to the first (most canonical) site.
RESOURCES = {}


def load_resources():
    p = Path(__file__).parent / "data" / "resources.json"
    if not p.exists():
        return 0
    try:
        RESOURCES.update(json.loads(p.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read resources.json ({e})", file=sys.stderr)
        return 0
    return sum(len(v) for v in RESOURCES.values())


def _res_match(low, suffix=None, prefix=None, plain=False):
    """Longest resource key whose term (key minus its class affix) appears as a word in the text."""
    best = None
    for k in RESOURCES:
        if suffix is not None and not k.endswith(suffix):
            continue
        if prefix is not None and not k.startswith(prefix):
            continue
        if plain and (k.endswith(" rocks") or k.endswith(" tree") or k.startswith("fishing ") or k == "flax"):
            continue
        term = k[:-len(suffix)] if suffix else (k[len(prefix):] if prefix else k)
        if re.search(r"\b" + re.escape(term) + r"s?\b", low):
            if best is None or len(term) > len(best[0]):
                best = (term, k)
    return best[1] if best else None


def resource_lookup(name, anchor=None):
    """Nearest gathering/combat site for the step's verb+resource, or None. Verb-gated so
    "buy a lobster" never points at a fishing spot."""
    if not RESOURCES:
        return None
    low = (name or "").lower()
    key = None
    if re.search(r"\b(mine|mining)\b", low):
        key = _res_match(low, suffix=" rocks")
    elif re.search(r"\b(chop|cut|woodcut|woodcutting)\b", low):
        key = _res_match(low, suffix=" tree")
    elif re.search(r"\b(fish|fishing|catch)\b", low):
        key = _res_match(low, prefix="fishing ")
    elif re.search(r"\b(kill|slay|attack|fight|farm)\b", low):
        key = _res_match(low, plain=True)
    elif "flax" in low and re.search(r"\b(pick|get|collect|grab)\b", low):
        key = "flax" if "flax" in RESOURCES else None
    sites = RESOURCES.get(key) if key else None
    if not sites:
        return None
    best = min(sites, key=lambda s: _dist(s, anchor)) if anchor else sites[0]
    return [int(best[0]), int(best[1]), int(best[2]) if len(best) > 2 else 0]


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
# PURE-arrival verbs: "go to X" completes just by being at X. Deliberately excludes return/enter/climb/
# cross — those usually head an INTERACTION ("Return to Aggie", "Climb the ladder"), so they must not get
# an arrival trigger; they remain action verbs (below) for splitting only.
TRAVEL_VERBS = {"go", "head", "run", "walk", "travel", "teleport"}  # "make your way" via is_travel special case
ACTION_VERBS = TRAVEL_VERBS | {
    "return", "enter", "climb", "cross",  # split boundaries, but NOT pure-arrival travel
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
    # A leading non-action fragment ("In Lumbridge, talk to Hans") has no previous atom to merge into,
    # so fold it forward into the first real action rather than shipping it as a junk step.
    if len(merged) >= 2 and not _starts_with_action(merged[0]):
        merged[1] = (merged[0] + ", " + merged[1]).strip()
        merged.pop(0)
    return merged or [s]


def is_travel(name):
    """True for a pure 'go/head/run to X' atom — the kind that completes just by arriving."""
    s = (name or "").strip().lower()
    if s.startswith("make your way"):
        return True
    m = _FIRST_WORD_RE.match(s)
    return bool(m) and m.group(1) in TRAVEL_VERBS


TRAVEL_RADIUS = 8  # tiles; wide enough to register an area arrival, tight enough that adjacent
                   # waypoints in one town don't overlap too much (kept small on purpose)


def build_step(prefix, position, name, loc, url, item_map, quest_map, cumulative, total_needed, entities,
               sub=None, anchor=None):
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
    mc = manual_lookup(name)
    if mc:  # human-verified override beats every automatic layer
        if "world" in mc:
            step["world"] = mc["world"]
        if "npcs" in mc:
            step["npcs"] = mc["npcs"]  # "any of these" highlight (e.g. every Man variant)
            step.pop("npc", None)
    if "world" not in step:
        # amenity (the actual shop/facility for the action) > resource site (mine/chop/fish/kill,
        # nearest to the route's current position) > loc-hint centre > quest-start tile > any place
        # named in the text.
        world = amenity_lookup(name, loc, anchor)
        if not world:
            world = resource_lookup(name, anchor)
        if not world:
            # Quest Helper wrote this step too? Inherit its exact tile + highlight ids (region-gated).
            ctx = gazetteer_lookup(loc) or anchor or gazetteer_lookup(name)
            qh = qh_step_lookup(name, ctx)
            if qh:
                world = qh["world"]
                if "npc" in qh and "npc" not in step and "npcs" not in step:
                    step["npc"] = qh["npc"]
                if "object" in qh and "object" not in step:
                    step["object"] = qh["object"]
        if not world:
            # "Complete Varrock easy diary" -> that helper's start tile (region-gated to the anchor).
            world = qh_helper_lookup(name, anchor or gazetteer_lookup(loc))
        # For a quest step, the quest-start NPC's exact tile beats the loc hint: the hint is almost
        # always just the town name (= a coarse centre), while the start tile is a real doorstep.
        cq = step.get("complete", {})
        if not world and cq.get("op") == "quest":
            qs = QUEST_START_BY_CONST.get(cq.get("quest"))
            if qs:
                world = list(qs)
        if not world:
            world = gazetteer_lookup(loc)
        if not world:
            world = gazetteer_lookup(name)
        if world:
            step["world"] = world
    # A pure-travel atom with a destination auto-completes on ARRIVAL: attach a position trigger so
    # "go to X" advances by itself. Only when the atom is still manual (no skill/quest/item goal) AND
    # resolved no interaction target — a talk/interact step (npc/object) must not complete from walking
    # past it, even if phrased with a travel verb ("Return to Aggie").
    if (step.get("manual") and "world" in step and is_travel(name)
            and "npc" not in step and "object" not in step):
        x, y, z = step["world"]
        step["complete"] = {"op": "position", "x": x, "y": y, "z": z, "radius": TRAVEL_RADIUS}
        del step["manual"]
    return step


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()  # wipe stale section files so a renamed/removed section never lingers
    item_map = fetch_item_map()
    quest_map = load_quest_map()
    load_location_coords()
    nqs = load_quest_start(quest_map)
    nam = load_amenities()
    nres = load_resources()
    nman = load_manual()
    nqsteps = load_qh_steps()
    entities = load_qh_entities()
    print(f"loaded {len(item_map)} item names, {len(quest_map)} quest names, {len(GAZETTEER)} "
          f"locations, {nqs} quest-start tiles, {nam} town amenities, {nres} resource sites, {nman} manual overrides, {nqsteps} QH steps, "
          f"{len(entities['npcs'])} npcs + {len(entities['objects'])} objects (QH refs)")

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
    anchor = None  # the route's current position, threaded across ALL sections (route continuity)
    grand_total = grand_skill = grand_quest = grand_item = grand_world = grand_entity = 0
    for (order, slug, display, prefix, url, raw) in sections:
        steps = []
        for (pos, name, loc, u) in raw:
            if not name:
                continue
            atoms = split_atoms(name)
            for i, atom in enumerate(atoms):
                sub = None if len(atoms) == 1 else (chr(97 + i) if i < 26 else str(i))
                built = build_step(prefix, pos, atom, loc, u, item_map, quest_map,
                                   cumulative, total_needed, entities, sub=sub, anchor=anchor)
                steps.append(built)
                if "world" in built:
                    anchor = built["world"]  # route continuity: the next step resolves near here

        fill_craft_gaps(steps)
        fill_location_gaps(steps)

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
