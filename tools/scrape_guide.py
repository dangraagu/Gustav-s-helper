#!/usr/bin/env python3
"""
Scrape the ironman.guide route into Gustav's Helper route JSON.

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
from functools import lru_cache
from pathlib import Path

# --- Guide config -------------------------------------------------------------
# To add a NEW guide: give it an id (folder name), a source-URL template, and its section list;
# then also add a matching value to com.gustavguide.Guide and an entry in data/guides.json.
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

_RES = Path(__file__).resolve().parent.parent / "src" / "main" / "resources" / "com" / "gustavguide"
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
SKILL_RE_1 = re.compile(r'\b(?:to|until|reach|get|hit|for|finish|want)\s+(\d{1,2})\s+([a-zA-Z]+)', re.I)
SKILL_RE_2 = re.compile(r'\b([a-zA-Z]+)\s+(?:to|until)\s+(\d{1,2})\b', re.I)
# A whole step that IS a level header — "65 Agility:" / "AFTER 65 Agility" — states the training
# goal and nothing else, so it may bind. Anchored both ends: a level+skill mention INSIDE a longer
# instruction ("Boost from 51 Farming using…") is context, not this step's goal, and must not bind.
SKILL_RE_HEADER = re.compile(r'^\s*(?:after\s+)?(\d{1,2})\s+([a-zA-Z]+)\s*[:.]?\s*$', re.I)


USER_AGENT = "GustavGuide-scraper/1.0 (+https://github.com/dangraagu/Gustav-s-helper; build-time content import)"

# --- Tuning constants ---------------------------------------------------------
MAX_ITEM_QTY = 100000        # clamp on a detected pickup quantity (guards against absurd totals)
UNDERGROUND_Y_OFFSET = 6400  # underground regions sit +6400 in y above their surface spot
QUEST_NEG_WINDOW = 70        # chars before a matched quest name to scan for a negation/aside cue


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


# A number right after a skill word that counts a RESOURCE, not a level ("1 prayer point",
# "restore 5 hitpoints", "3 run energy"). Such a step must never become a skill-level condition.
_SKILL_UNIT_RE = re.compile(r"^\s*(?:point|pts?|tick|xp|exp|experience|run|energy)\b", re.IGNORECASE)


def detect_skill(text: str):
    """Return {'op':'skill',...} if the text states a clear training target, else None.

    Level 1 is universally true (every account has every skill >= 1), so it can never be a real
    training goal: treating "eat a jangerberry for 1 prayer point" as skill:PRAYER>=1 auto-completes
    the step on EVERY account and the milestone-fold then wipes every prior flavour step. Require
    level >= 2, and reject "<n> <skill> point/tick/energy" phrasings where the number is a resource
    count rather than a level."""
    for rx, si, li in ((SKILL_RE_1, 1, 0), (SKILL_RE_2, 0, 1), (SKILL_RE_HEADER, 1, 0)):
        for m in rx.finditer(text):
            word = m.group(1 + si).lower()
            level = int(m.group(1 + li))
            if word in SKILL_WORDS and 2 <= level <= 99 and not _SKILL_UNIT_RE.match(text[m.end():]):
                return {"op": "skill", "skill": SKILL_WORDS[word], "level": level, "cmp": ">="}
    return None


# --- Item acquisition detection (conservative) -------------------------------

ACQUIRE_VERBS = ("buy", "purchase", "pick up", "pickup", "collect", "grab", "loot",
                 "obtain", "withdraw", "steal", "gather")
_INT_RE = re.compile(r'\d+')
# A number right after "world"/"w" is a world-hop count, not an item quantity (e.g. "gilded altar on
# w330", "hop to world 302 and buy wine") — used to exclude it when reading shop-buy quantities.
_WORLD_HOP_RE = re.compile(r'\b(?:world|w)\s*$', re.IGNORECASE)

# Colloquial guide phrase -> canonical item id, for cases the wiki item names miss ("wine" is sold as
# "Jug of wine"; "jugs of wine" plurals the wrong word). Applied only when the real-name match fails.
ITEM_ALIASES = {}


def load_item_aliases():
    p = Path(__file__).parent / "data" / "item_aliases.json"
    if not p.exists():
        return 0
    try:
        for k, v in json.loads(p.read_text(encoding="utf-8")).items():
            if not k.startswith("_"):
                ITEM_ALIASES[_norm(k).strip()] = int(v)
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read item_aliases.json ({e})", file=sys.stderr)
    return len(ITEM_ALIASES)


# Seller stock: "buy X from <seller>" resolves X against what that seller ACTUALLY sells (so the
# guide's colloquial "wine" -> Fortunato's "Jug of wine"). seller name -> [(normalised item name, id)].
SHOP_STOCK = {}
_SELLER_STOP = {"buy", "buys", "buying", "purchase", "from", "talk", "to", "get", "hop", "worlds",
                "and", "the", "a", "of", "for", "your", "some", "then", "at", "in", "on", "with",
                "world", "each", "one", "few"}


def load_shop_stock():
    p = Path(__file__).parent / "data" / "shop_stock.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read shop_stock.json ({e})", file=sys.stderr)
        return 0
    for seller, info in data.items():
        if seller.startswith("_") or not isinstance(info, dict):
            continue
        items = [(_norm(it["name"]).strip(), int(it["id"]))
                 for it in info.get("items", []) if it.get("name") and it.get("id") is not None]
        if items:
            SHOP_STOCK[seller.strip().lower()] = items
    return len(SHOP_STOCK)


def _content_words(padded):
    return {w for w in padded.split() if len(w) >= 3 and w not in _SELLER_STOP}


def detect_seller(padded):
    """Longest known seller name appearing in the step text."""
    best = None
    for seller in SHOP_STOCK:
        if (" " + seller + " ") in padded and (best is None or len(seller) > len(best)):
            best = seller
    return best


def shop_item_match(text):
    """Match the bought item against the named seller's real stock. Returns (id, qty) or None. Prefers
    a stock item whose name contains all the step's item words; ties -> shortest name, then lowest id."""
    if not SHOP_STOCK:
        return None
    padded = _norm(text)
    seller = detect_seller(padded)
    if not seller:
        return None
    phrase = _content_words(padded) - _content_words(" " + seller + " ")
    if not phrase:
        return None
    best = None
    for name, iid in SHOP_STOCK[seller]:
        ntok = {w for w in name.split() if len(w) >= 3}
        if not (phrase & ntok):
            continue
        subset = phrase <= ntok
        score = (1 if subset else 0, -len(name), -iid)  # all words matched > shorter name > lower id
        if best is None or score > best[0]:
            best = (score, iid, name)
    if best is None:
        return None
    # quantity: the integer immediately before the matched item WORD(S) that actually appear in the
    # step text — not the full stock name, which is often a colloquial alias (guide "wine" -> stock
    # "Jug of wine"). So "buy 5 wine" -> 5, while a number after the item (or none) leaves qty=1.
    _score, best_id, best_name = best
    matched = phrase & {w for w in best_name.split() if len(w) >= 3}
    positions = [p for p in (padded.find(" " + w) for w in matched) if p >= 0]
    pos = min(positions) if positions else len(padded)
    before = [int(m.group()) for m in _INT_RE.finditer(padded)
              if m.start() < pos and not _WORLD_HOP_RE.search(padded[max(0, m.start() - 8):m.start()])]
    qty = max(1, min(before[-1] if before else 1, MAX_ITEM_QTY))
    return (best_id, qty)


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


def _xyz(seq):
    """A [x, y, z] coord as ints, with the plane defaulting to 0 when only [x, y] is given."""
    return [int(seq[0]), int(seq[1]), int(seq[2]) if len(seq) > 2 else 0]


# --- Skill training methods: a grind step shows the wiki's recommended method --
# For "Train Cooking to 15" / "Do Slayer until 60 attack" (a skill-conditioned step, no location), we
# attach a short wiki-sourced tip for the target level band -> step["note"], shown in the panel.
SKILL_METHODS = {}


def load_skill_methods():
    p = Path(__file__).parent / "data" / "skill_methods.json"
    if not p.exists():
        return 0
    try:
        SKILL_METHODS.update(json.loads(p.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read skill_methods.json ({e})", file=sys.stderr)
        return 0
    return len(SKILL_METHODS)


def skill_note(skill_enum, level):
    m = SKILL_METHODS.get(skill_enum)
    if not m:
        return None
    for b in m.get("bands", []):
        if int(b.get("min", 1)) <= int(level) <= int(b.get("max", 99)):
            return b.get("tip"), m.get("page")
    return None


# --- Gear highlight: equip/bring rows point at the ITEM in inventory/bank ------
# "Equip Fire cape" / "Bring Super attack(4)" have no location — the useful cue is highlighting the
# item (GustavItemOverlay draws step.item in inv/bank). This resolves the item name -> id WITHOUT a
# completion condition (equipping is not acquiring): the step stays manual, it just gets a highlight.
_EQUIP_VERB_RE = re.compile(r"^\s*(equip|wield|wear|bring|carry)\b", re.IGNORECASE)
NORM_ITEM_INDEX = {}  # normalised item name -> lowest id


def build_item_index(item_map):
    NORM_ITEM_INDEX.clear()
    for name, iid in item_map.items():
        n = _norm(name).strip()
        if len(n) >= 3 and (n not in NORM_ITEM_INDEX or iid < NORM_ITEM_INDEX[n]):
            NORM_ITEM_INDEX[n] = iid
    # Merge complete ItemID gameval dump (covers untradeables the price-map lacks) + hand-resolved
    # extras (display names whose cache-constant name differs, e.g. Fire cape). Tradeables already set
    # win (lowest-id display name); these only fill gaps.
    for fname in ("item_names.json", "item_ids_extra.json"):
        p = Path(__file__).parent / "data" / fname
        if not p.exists():
            continue
        try:
            for n, iid in json.loads(p.read_text(encoding="utf-8")).items():
                n = _norm(n).strip()  # same normalisation as the matcher (drops apostrophes/parens)
                if len(n) >= 3 and n not in NORM_ITEM_INDEX:
                    NORM_ITEM_INDEX[n] = int(iid)
        except Exception as e:  # noqa: BLE001
            print(f"[!] could not read {fname} ({e})", file=sys.stderr)
    return len(NORM_ITEM_INDEX)


def detect_item_highlight(text):
    """Longest known item name appearing in an equip/bring/wield/wear step -> its id (highlight only)."""
    if not NORM_ITEM_INDEX or not _EQUIP_VERB_RE.match(text or ""):
        return None
    padded = _norm(text)
    best = None
    for n, iid in NORM_ITEM_INDEX.items():
        if len(n) < 4:
            continue
        if (" " + n + " ") in padded and (best is None or len(n) > len(best[0])):
            best = (n, iid)
    return best[1] if best else None


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
    # A named seller's stock is AUTHORITATIVE for "buy X from <seller>" — it beats a greedy generic
    # real-name match ("air staff" -> Staff of air, not the plain Staff). Only fires when the bought
    # item is actually in that seller's stock; otherwise fall through to real-name matching.
    sm = shop_item_match(text)
    if sm:
        return sm
    padded = _norm(text)
    best_name, best_id = None, None
    for name, iid in item_map.items():
        if len(name) < 4:
            continue  # skip 1-3 char names (too ambiguous)
        if (" " + name + " ") in padded or (" " + name + "s ") in padded:
            if best_name is None or len(name) > len(best_name):
                best_name, best_id = name, iid
    if best_id is None:
        # Real item name missed and no seller stock matched — try a colloquial alias ("wine" with no
        # named seller -> Jug of wine).
        for phrase, iid in ITEM_ALIASES.items():
            if (" " + phrase + " ") in padded and (best_name is None or len(phrase) > len(best_name)):
                best_name, best_id = phrase, iid
    if best_id is None:
        return None
    # quantity: only an integer appearing BEFORE the item name (e.g. "pick up 5 swamp tar").
    # A number after the name usually belongs to a different item in a multi-buy step, so we
    # default to 1 rather than grabbing it — safer (avoids absurd quantities that never complete).
    pos = padded.find(" " + best_name)
    ints = [(m.start(), int(m.group())) for m in _INT_RE.finditer(padded)]
    before = [v for (s, v) in ints if s < pos]
    qty = max(1, min(before[-1] if before else 1, MAX_ITEM_QTY))
    return (best_id, qty)


# "Inventory check: Rope, Spade, Coins" — a checklist step. Each named item becomes a REQUIREMENT so the
# panel can show it green (carried) or red (missing) and the overlay can highlight the whole list.
_CHECK_RE = re.compile(r"^\s*(?:inventory|inv|equipment|gear)\s*check\s*:\s*(.+)$",
                       re.IGNORECASE | re.DOTALL)
_PAREN_RE = re.compile(r"\s*\([^)]*\)")


def parse_check_items(text):
    """For an "<Inventory|Equipment> check: A, B, C" step, return requirement dicts for every item name
    we can GROUND in the item index (repeats collapse into a quantity). Unrecognised names are dropped
    rather than guessed, so a requirement never points at the wrong item. Returns [] for other steps."""
    m = _CHECK_RE.match(text or "")
    if not m:
        return []
    counts, order = {}, []
    for raw in m.group(1).split(","):
        name = raw.strip().rstrip(".").strip()
        # Sub-note separators ("—") end the checklist portion of the step.
        name = re.split(r"[—–]", name)[0].strip()
        if not name:
            continue
        iid = None
        for cand in (name, _PAREN_RE.sub("", name).strip()):
            key = _norm(cand).strip()
            if key:
                iid = NORM_ITEM_INDEX.get(key)
            if iid is not None:
                name = cand
                break
        if iid is None:
            continue  # not groundable -> leave it out rather than mis-highlight
        if iid not in counts:
            order.append((iid, name))
        counts[iid] = counts.get(iid, 0) + 1
    return [{"type": "item", "id": iid, "qty": counts[iid], "name": nm, "scope": "ANY"}
            for iid, nm in order]


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
            QUEST_START_BY_CONST[const] = _xyz(xy)
            n += 1
    return n


_QUEST_START_VERB_RE = re.compile(r"^\s*(start|begin)\b", re.IGNORECASE)
# A purpose-form start verb directly governing the quest name ("...to start The Restless Ghost",
# "run to Draynor Manor to start Animal Magnetism"). Requires the infinitive "to start/begin" right
# before the quest name, so a temporal/coordinating aside where starting is NOT the step's action
# ("sell ... when starting One Small Favour", "also start Curse of the Empty Lord during ...") keeps
# its FINISHED binding instead of completing the wrong step the moment that quest is begun. A step
# that literally opens with "Start/Begin <quest>" is caught separately by _QUEST_START_VERB_RE.
_QUEST_START_NEAR_RE = re.compile(r"\b(?:to|and|then)\s+(?:start|begin)(?:\s+the)?$", re.IGNORECASE)
QUEST_START_WINDOW = 24
# "<quest> required/needed/unlocked" right after the name = a prerequisite aside ("burst jellies
# in catacombs (Desert treasure required)"), not the step's action — never bind it.
_QUEST_REQ_AFTER_RE = re.compile(r"^(?:is\s+)?(?:required|needed|unlocked)\b", re.IGNORECASE)
QUEST_REQ_WINDOW = 14

# A step that lists quests you must NOT do (e.g. slayer-lure "DONT complete the following: ...")
# must never bind its completion to one of those quests.
_QUEST_LIST_WARN_RE = re.compile(r"complete the following", re.IGNORECASE)
# Cues that a quest is named in a negative / conditional / optional aside rather than as the
# step's actual action ("dont do X", "if you did X", "you could do X"). Checked on the normalised
# text in a short window immediately before the matched quest name.
_QUEST_NEG_RE = re.compile(
    r"(do ?n.?t|dont|do not|avoid|never|no need|"
    r"if you (?:would|want|did|have|already|plan|like)|would like|"
    r"you could|you can also|you can (?:start|complete|do)|optional|bother|consider|"
    r"until you can|"
    r"before you (?:complete|finish|do|start)|partially complete|progress through)",
    re.IGNORECASE)

# A quest name that is also a spell/mechanic: the word right before the match disambiguates.
# "NPC Contact" / "Astral Contact" is the Lunar spell, never the quest "Contact!".
_QUEST_FALSE_PRECEDERS = {"CONTACT": ("npc", "astral")}
_ROMAN_TOKENS = [(" iii", " 3"), (" ii", " 2"), (" iv", " 4"), (" i", " 1")]

_QUEST_APOS_RE = re.compile(r"[’'`´]")


def _qnorm(s: str) -> str:
    """_norm with apostrophes REMOVED (not spaced): _norm turns "Knight's" into "knight s", which
    can never match the apostrophe-free spellings guides actually use ("Knights Sword", "Monks
    Friend", "dorics quest"). Used on BOTH sides of quest-name matching only."""
    return _norm(_QUEST_APOS_RE.sub("", s or ""))


# Guide misspellings/abbreviations seen in shipped guides -> RuneLite Quest constant. Matched with
# exactly the same substring + negation-window rules as real quest names. Keys are _qnorm cores.
QUEST_ALIASES = {
    "witches house": "WITCHS_HOUSE",
    "fremmenik trials": "THE_FREMENNIK_TRIALS",
    "muder mystery": "MURDER_MYSTERY",
    "vampire slayer": "VAMPYRE_SLAYER",
    "porcine of intrest": "A_PORCINE_OF_INTEREST",
    "enlighted journey": "ENLIGHTENED_JOURNEY",
    "death to the dorg": "DEATH_TO_THE_DORGESHUUN",
    "another slice of ham": "ANOTHER_SLICE_OF_HAM",
    "gerturdes cat": "GERTRUDES_CAT",
    "shades of morton": "SHADES_OF_MORTTON",
    "garden of tranquility": "GARDEN_OF_TRANQUILLITY",
    "one small favor": "ONE_SMALL_FAVOUR",
    "digsite quest": "THE_DIG_SITE",
    "fairy tale pt 1": "FAIRYTALE_I__GROWING_PAINS",
}

# Whole-step-text bindings for names too generic to match as substrings ("waterfall", "rfd" would
# bind every step that merely mentions the place or the lamps). Keyed by the _qnorm'd FULL step
# text (pre-"Location:" name), so only the literal step binds. Always FINISHED.
QUEST_TEXT_EXACT = {
    "finish waterfall": "WATERFALL_QUEST",
    "finish rfd": "RECIPE_FOR_DISASTER",
}


def _quest_candidates(name, fullname_norms):
    """All matchable variants of one quest display name (or alias): the _qnorm'd name; its
    subtitle-stripped head ("Desert Treasure II - The Fallen Empire" -> "desert treasure ii") when
    that head is not another quest's full name (the eleven "Recipe for Disaster - <sub>" names all
    share the base quest's head and must never claim it); an article-optional form (leading
    The/A/An dropped); roman->arabic; and a trailing-" i"-stripped base for long "... I" names so
    a guide's bare "dragon slayer" means DRAGON_SLAYER_I (longest-match still prefers II/2 forms).
    Every variant is padded with spaces for whole-word substring matching."""
    forms = [_qnorm(name)]
    if " - " in name:
        head = _qnorm(name.split(" - ", 1)[0])
        if head not in fullname_norms:
            forms.append(head)
    out = []
    for f in forms:
        cands = [f]
        if f.startswith(" the ") and len(f) - 5 >= 6:
            cands.append(" " + f[5:])
        elif f.startswith(" a ") and len(f) - 3 >= 9:
            cands.append(" " + f[3:])
        elif f.startswith(" an ") and len(f) - 4 >= 9:
            cands.append(" " + f[4:])
        extra = []
        for c in cands:
            av = _arabic_variant(c)
            if av:
                extra.append(av)
            if c.endswith(" i ") and len(c.strip()) >= 13:
                # >= 13 keeps "dragon slayer"/"monkey madness"/"desert treasure" but excludes
                # "mage arena" ("Mage Arena I" strips to the PLACE visited for the bank/lever).
                extra.append(c[:-2])
        out.extend(cands + extra)
    return out


def _arabic_variant(nn):
    """Roman-numeral quest name -> arabic form, so a guide's 'Dragon Slayer 2' matches the canonical
    'Dragon Slayer II'. Returns None if the name has no trailing roman numeral to convert."""
    v = nn
    for roman, arabic in _ROMAN_TOKENS:
        v = re.sub(re.escape(roman) + r"(?=\s|$)", arabic, v)
    return v if v != nn else None


def detect_quest(text: str, quest_map):
    """
    If a quest's display name appears in the step, complete the step when that quest is done.
    Dynamic: for an existing account this auto-skips a quest AND its prep/start steps once it's done.
    Longest name wins. Apostrophes are dropped on both sides so "Knights Sword" matches "The Knight's
    Sword", a leading "The"/"A"/"An" is optional so "Restless ghost" and "Kingdom Divided" still match,
    roman numerals match arabic ("Dragon Slayer 2" -> "Dragon Slayer II"), a bare base name means the
    "... I" quest ("dragon slayer" -> DRAGON_SLAYER_I), subtitles are optional ("Desert Treasure II"
    matches "... - The Fallen Empire"), QUEST_ALIASES covers shipped-guide misspellings, and
    QUEST_TEXT_EXACT binds whole-step texts too generic for substrings. A "Start <quest>" step uses
    IN_PROGRESS (started
    OR finished); other steps use FINISHED. Steps that name a quest negatively/conditionally (warnings,
    "if you did X", asides) do NOT bind, so they can't auto-complete on the wrong / a forbidden quest.
    """
    if not quest_map:
        return None
    if _QUEST_LIST_WARN_RE.search(text or ""):
        return None
    padded = _qnorm(text)
    exact = QUEST_TEXT_EXACT.get(padded.strip())
    if exact:
        return {"op": "quest", "quest": exact, "state": "FINISHED"}
    fullname_norms = {_qnorm(n) for n in quest_map}
    # Collect EVERY occurrence of every candidate, then keep the longest match at each span — so
    # "dragon slayer" (the DS1 base form) can never survive inside "dragon slayer 2", but a step
    # naming several quests ("Dragon Slayer 1, Priest in Peril and Regicide") keeps them all.
    matches = []  # (start, end, core_len, const)
    for name, const in list(quest_map.items()) + list(QUEST_ALIASES.items()):
        for cand in _quest_candidates(name, fullname_norms):
            core = cand.strip()
            if len(core) < 4:
                continue
            start = padded.find(cand)
            while start != -1:
                # span of the CORE only (candidates carry one padding space each side; two adjacent
                # quest names share that space and must not count as overlapping)
                matches.append((start + 1, start + len(cand) - 1, len(core), const))
                start = padded.find(cand, start + 1)
    if not matches:
        return None
    matches.sort(key=lambda m: (-m[2], m[0]))
    kept = []
    for m in matches:
        if any(m[0] < k[1] and k[0] < m[1] for k in kept):
            continue  # overlaps a longer match
        kept.append(m)
    # Per-match guards: a name in a negated/conditional aside, or one immediately followed by
    # "required/needed/unlocked" (a prerequisite, not the action), never binds. A "start/begin"
    # verb governing the name — or heading the step, for the first name — means the quest need
    # only be STARTED (IN_PROGRESS), not finished.
    bound = []
    first_start = min(m[0] for m in kept)
    for start, end, _, const in sorted(kept):
        if start > 0 and _QUEST_NEG_RE.search(padded[max(0, start - QUEST_NEG_WINDOW):start]):
            continue
        if _QUEST_REQ_AFTER_RE.match(padded[end:end + QUEST_REQ_WINDOW].lstrip()):
            continue
        prev_word = padded[:start].rsplit(None, 1)[-1] if padded[:start].strip() else ""
        if prev_word in _QUEST_FALSE_PRECEDERS.get(const, ()):
            continue  # "NPC Contact" is the spell, not the quest
        if any(const == c for c, _ in bound):
            continue  # the same quest named twice ("... Desert Treasure [Desert Treasure]")
        pre = padded[max(0, start - QUEST_START_WINDOW):start].rstrip()
        started = bool(_QUEST_START_NEAR_RE.search(pre)) or (
            start == first_start and bool(_QUEST_START_VERB_RE.match(text or "")))
        bound.append((const, "IN_PROGRESS" if started else "FINISHED"))
    if not bound:
        return None
    if len(bound) == 1:
        return {"op": "quest", "quest": bound[0][0], "state": bound[0][1]}
    # A step that names several quests is done when ALL of them are ("Dragon Slayer 1, Priest in
    # Peril, ..."): an AND can only fire late, never early, so it is fresh-account safe.
    return {"op": "and", "of": [{"op": "quest", "quest": c, "state": s} for c, s in bound]}


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


@lru_cache(maxsize=4096)
def _place_pattern(key):
    """A whole-word matcher for one place name.

    Anchored with lookarounds rather than \\b so keys that start or end with a non-word
    character still work: \\b before "'rana" would demand a word char to its left, which the
    space in "the 'rana" does not provide."""
    return re.compile(r"(?<![0-9A-Za-z])" + re.escape(key) + r"(?![0-9A-Za-z])")


def gazetteer_key(text):
    """The longest gazetteer place name appearing in the text, or None — i.e. the step's context town.

    Matches whole words only. The gazetteer holds abbreviations ("ge", "wt", "pc", "cw"), so a plain
    substring test resolves "take 3 or more damage" to the Grand Exchange — that pinned 472 steps onto
    the GE marker, including steps inside the Stronghold of Security and 212 steps of a hardcore
    ironman guide, which cannot use the Grand Exchange at all."""
    if not text:
        return None
    low = text.lower()
    best = None
    for key in GAZETTEER:
        if (best is None or len(key) > len(best)) and _place_pattern(key).search(low):
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

# "as well" is an idiom, never a reference to the town well. Without this, "grab each elemental rune
# as well" and "bring a rope as well" resolve to a well tile — and whole-word matching cannot help,
# because there "well" genuinely IS a whole word.
_AS_WELL_RE = re.compile(r"\bas\s+well\b", re.IGNORECASE)


@lru_cache(maxsize=2048)
def _facility_pattern(key):
    """Whole-word matcher for one amenity name, tolerating a trailing plural.

    Amenity keys are short common nouns ("bank", "well", "range", "anvil"), so a plain substring test
    matched them inside "banked", "dwellberries", "Ranged" and "ranger" — 19 steps shipped pointing at
    a facility the step never mentions. The optional "s" keeps "use one of the anvils" working."""
    return re.compile(r"(?<![0-9A-Za-z])" + re.escape(key) + r"s?(?![0-9A-Za-z])")


AMENITY_ACTIONS = [
    (re.compile(r"\b(buy|buys|buying|purchase|sell|selling|shop\s?keeper)\b", re.IGNORECASE), "general store"),
    # "rebank" means the building ("rebank in Canifis"), and is not the word "bank", so whole-word
    # facility matching misses it and the step falls through to the route anchor's town — which put a
    # Canifis rebank on Draynor Manor, 420 tiles and a members' barrier away. Bare "banked" is NOT
    # included: in these guides it is almost always "death banked", a UIM death-pile technique that
    # has nothing to do with a bank building.
    (re.compile(r"\b(rebank|rebanking|bank|banker|banking|deposit|withdraw|unnote)\b", re.IGNORECASE), "bank"),
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
    if ay > UNDERGROUND_Y_OFFSET:
        ay -= UNDERGROUND_Y_OFFSET
    if by > UNDERGROUND_Y_OFFSET:
        by -= UNDERGROUND_Y_OFFSET
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
    low = _AS_WELL_RE.sub(" ", (name or "").lower())
    best = None
    for key in spots:  # a named shop/facility mentioned verbatim in the step text
        if (best is None or len(key) > len(best)) and _facility_pattern(key).search(low):
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
    return _xyz(xy)


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
    return _xyz(best) if best else None


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
                    world = _xyz(xy)
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
    # Bracketed tags are metadata naming which diary/quest a step COUNTS TOWARD — they are not part of
    # the instruction. "Enter Fight Caves & wait for Wave 1 [Karamja Easy Diary]" is an errand in the
    # TzHaar city; feeding "karamja/easy/diary" to the helper index matched the Karamja Easy DIARY
    # helper and sent the player to a Brimhaven ropeswing instead. detect_diary already strips these.
    t = re.sub(r"\[[^\]]*\]", " ", text or "").lower().replace("'", "").replace("’", "")
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
            QH_STEPS.append((toks, _xyz(w), s.get("npc"), s.get("object")))
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
        world = _xyz(w)
        toks = [t for t in qkey.lower().split("_") if len(t) >= 3 and t not in ("the", "and", "for")]
        if len(toks) >= 2:
            _register_helper_name(toks, world)
        # RFD subquests are referred to by their tail ("Evil Dave subquest")
        if qkey.startswith("RECIPE_FOR_DISASTER_"):
            tail = [t for t in qkey[len("RECIPE_FOR_DISASTER_"):].lower().split("_") if len(t) >= 3]
            if tail and not (len(tail) == 1 and tail[0] in HELPER_NAME_STOPWORDS):
                _register_helper_name(tail, world)
            # The opener is written "Start RFD (1,2,1,1)", never "Recipe for Disaster start", so the
            # tail token "start" is blocked as too generic — register the abbreviation instead.
            if qkey == "RECIPE_FOR_DISASTER_START":
                _register_helper_name(["rfd"], world)
        # a single, long, distinctive token works alone ("barcrawl")
        for t in toks:
            if len(t) >= 8 and t not in HELPER_NAME_STOPWORDS:
                _register_helper_name([t], world)


# Words that must never identify a quest helper ON THEIR OWN. A single-token key is matched as a bag
# of words, so registering an ordinary English word pins every step containing it: "start" (from
# RECIPE_FOR_DISASTER_START) put 16 steps on the Lumbridge Cook, including "start Fairy Tale Part 2",
# and "woodcutting" (from the WOODCUTTING helper) pinned 14 training grinds to the Lumbridge tutorial
# tile. Only those two fire against today's data — the rest are guards, since the registration paths
# above admit any RFD tail token or any token >= 8 chars. Multi-token keys stay registered, so RFD's
# own subquests still resolve ("dwarf" via {disaster, recipe, dwarf}), as does WOODCUTTING_MEMBER.
HELPER_NAME_STOPWORDS = frozenset({
    "start", "begin", "finish", "complete", "continue",
    "attack", "strength", "defence", "ranged", "prayer", "magic", "runecraft", "construction",
    "hitpoints", "agility", "herblore", "thieving", "crafting", "fletching", "slayer", "hunter",
    "mining", "smithing", "fishing", "cooking", "firemaking", "woodcutting", "farming",
})

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
            out["world"] = _xyz(w)
        ids = v.get("npcs") or ([v["npc"]] if v.get("npc") is not None else None)
        if ids:
            out["npcs"] = [int(i) for i in ids]
        return out or None
    return {"world": _xyz(v)}


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
    return _xyz(best)


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


_TALK_RE = re.compile(r"\b(speak|talk|tell|ask)\b", re.IGNORECASE)
# A step that OPENS with an optional cue is advice, not a required gate. Left as a hard skill/quest
# gate it would block every downstream arrival/fold for a player who skips it (e.g. "(Optional) ...
# 43 Prayer at the start"). Anchored at the start so only genuinely-optional steps are affected.
_OPTIONAL_RE = re.compile(r"^\s*[\(\[]?\s*(optional|optionally|if you (?:want|prefer|like))\b", re.IGNORECASE)


def enrich_entity(step, text, cond_op, item_id, entities):
    """Set a precise NPC/object highlight id + tile from the QH reference table where the step names a
    specific entity. Skips object matches on item-buy steps (avoids matching a bought vegetable as a
    scenery object)."""
    if cond_op == "quest":
        # On a quest step, only highlight the specific NPC the step tells you to TALK to ("speak to
        # Father Urhney", "speak with Duke Horacio to start Rune Mysteries"). Its exact tile then beats
        # the generic quest-START coordinate, which otherwise sends you to the quest's opening NPC even
        # on a later sub-step about a different person. A quest step with no talk verb (e.g. "complete
        # <quest>") still gets no arbitrary highlight — falls through to the quest-start tile.
        tm = _TALK_RE.search(text or "")
        if not tm:
            return
        # Match only the NPC named right AFTER the talk verb ("speak with <NPC> …"), within a short
        # window — otherwise an incidental entity later in the step ("…receive an air talisman") can
        # shadow the real target and, at instanced coords, drop the highlight entirely.
        hit = _match_named(text[tm.start():tm.start() + 45], entities["npcs"])
        if hit:
            w = hit[2]
            if len(w) >= 2 and w[1] < UNDERGROUND_Y_OFFSET:
                step["npc"] = hit[1]
                step["world"] = [w[0], w[1], w[2] if len(w) > 2 else 0]
        return
    hit = _match_named(text, entities["npcs"])
    key = "npc"
    if not hit and item_id is None:
        hit = _match_named(text, entities["objects"])
        key = "object"
    if hit:
        w = hit[2]
        if len(w) < 2 or w[1] >= UNDERGROUND_Y_OFFSET:
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
# Interact verbs whose object is a specific NPC/target. "Travel to X, <interact> Y" is ONE step: the
# NPC Y is the real target (highlight + arrow + completes on the interaction), so a preceding pure-travel
# atom is merged into it rather than shipped as a separate "walk there" waypoint.
INTERACT_VERBS = {"talk", "speak", "tell", "ask"}
# Steps longer than this are prose/notes (multi-sentence paragraphs with conditionals), not a clean
# imperative action list — atomising them produces noise, so they're left whole.
MAX_SPLIT_LEN = 180
_BOUNDARY_RE = re.compile(r"\s*(?:;|,|\.|\bthen\b|\band\b)\s+", re.IGNORECASE)
_FIRST_WORD_RE = re.compile(r"\s*([a-zA-Z]+)")
_TRAIL_CONN_RE = re.compile(r"(?:[\s,;.]+|\s+(?:and|then))+$", re.IGNORECASE)


def _starts_with_action(fragment):
    m = _FIRST_WORD_RE.match(fragment or "")
    return bool(m) and m.group(1).lower() in ACTION_VERBS


def split_atoms_indexed(name):
    """Split a step into (atom, original_index, merged) triples at action boundaries, preserving the original wording.
    A separator only splits when the text after it begins with an action verb; trailing 'and'/'then'
    fragments merge back so 'buy a bucket and a rope' stays one task. Returns >=1 atom; a step with no
    internal boundary is returned unchanged."""
    s = (name or "").strip()
    if not s:
        return []
    if len(s) > MAX_SPLIT_LEN:
        return [(s, 0, False)]  # long prose isn't a clean action list — don't shred it into noise
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
    # Merge "travel to X" + "<interact> Y" into one step — the NPC/target Y is what the player clicks,
    # not a separate arrival waypoint. Only a pure-travel atom directly before a talk/speak atom.
    # Each atom keeps its ORIGINAL index so the id suffix of a later atom does not shift when an earlier
    # pair merges (a shifted suffix silently re-points an existing step id at different work, and a saved
    # completion would then tick a step the player never did).
    combined = []
    i = 0
    while i < len(merged):
        cur = merged[i]
        nxt = merged[i + 1] if i + 1 < len(merged) else None
        nm = _FIRST_WORD_RE.match(nxt) if nxt else None
        if nxt is not None and is_travel(cur) and nm and nm.group(1).lower() in INTERACT_VERBS:
            combined.append(((cur + ", " + nxt).strip(), i, True))
            i += 2
        else:
            combined.append((cur, i, False))
            i += 1
    return combined or [(s, 0, False)]


def split_atoms(name):
    """Atom TEXTS only (see split_atoms_indexed for the (atom, index, merged) triples)."""
    return [a for a, _, _ in split_atoms_indexed(name)]


def is_travel(name):
    """True for a pure 'go/head/run to X' atom — the kind that completes just by arriving."""
    s = (name or "").strip().lower()
    if s.startswith("make your way"):
        return True
    m = _FIRST_WORD_RE.match(s)
    return bool(m) and m.group(1) in TRAVEL_VERBS


TRAVEL_RADIUS = 8  # tiles; wide enough to register an area arrival, tight enough that adjacent
                   # waypoints in one town don't overlap too much (kept small on purpose)


# Achievement-diary completion syncs like skills/quests: a "complete <area> <tier> diary" step
# auto-completes once that tier's completion varbit is set (resolved to a Varbits.DIARY_* id in Java).
# Karamja is intentionally omitted — its completion varbits aren't clean 0/1 flags like the other areas.
_DIARY_AREAS = ("ardougne", "desert", "falador", "fremennik", "kandarin", "kourend",
                "lumbridge", "morytania", "varrock", "western", "wilderness")
# Karamja is a real diary the engine's "diary" op cannot express, so it is not in _DIARY_AREAS. It
# still has to be RECOGNISED as an area name: "claim the easy and medium Karamja diaries" names one
# area, but with karamja unknown the bulk-goal branch below saw no area at all and bound the step to
# every area's easy AND medium diary — 22 conditions, a step that can never complete and stalls the
# route. An area we cannot express means no condition, not a condition over everything else.
_DIARY_AREAS_UNSUPPORTED = ("karamja",)
_DIARY_TIERS = ("elite", "hard", "medium", "easy")


_DIARY_MAX_LEN = 85  # a diary step is a short task/goal; longer = prose where the diary is incidental


def detect_quest_or_diary(name_untagged, name_full, quest_map):
    """Quest completion vs achievement-diary completion for one step — quest first, EXCEPT when the
    step's primary clause (before any ' — ' note) is a diary action and not a quest action: a diary
    step whose notes mention helper quests ("Complete the easy Varrock Diary. — Complete Enter the
    abyss, then ...") must bind the diary, not a note's quest."""
    primary = name_untagged.split("—")[0]
    if detect_diary(primary) is not None and detect_quest(primary, quest_map) is None:
        return detect_diary(primary)
    return detect_quest(name_untagged, quest_map) or detect_diary(name_full)


def detect_diary(text: str):
    """A step whose SUBJECT is an achievement diary (a short "<area> <tier> diary" task/goal) -> a
    diary completion condition, so it auto-syncs like a skill/quest on an already-advanced account.
    Deliberately skips long prose steps that only mention a diary in passing (e.g. a big grind whose
    completion is NOT the same as the whole diary tier being done)."""
    t = (text or "").lower()
    # A bracketed "[<Area> <Tier> Diary]" is a per-task TAG marking which diary a single task feeds,
    # NOT an instruction to complete the whole tier. Strip bracketed spans first so a task like
    # "Pickpocket a man/woman [Ardougne Easy Diary]" is not bound to the entire tier's varbit (which
    # would pre-complete every such task on an account that finished the tier, and make the individual
    # tasks only tick together when the whole tier is done).
    t = re.sub(r"\[[^\]]*\]", " ", t)
    if "diar" not in t or len(text or "") > _DIARY_MAX_LEN:
        return None
    # Whole-word only: "elite" hides inside "RuneLite" and "hard" inside "Khardian"/"shards", which
    # would bind an unrelated step to an AND over all 11 areas' elite diaries — a condition that can
    # never complete, silently stalling the route. Exact match, not the plural-tolerant amenity one:
    # a diary tier has no plural form, so "elites" must not resolve to the elite tier.
    area = next((a for a in _DIARY_AREAS if _place_pattern(a).search(t)), None)
    tiers = [tr for tr in _DIARY_TIERS if _place_pattern(tr).search(t)]
    if area and tiers:
        return {"op": "diary", "area": area, "tier": tiers[0]}  # one specific diary
    # Bulk goal: "do all easy and medium diaries" (tier(s), no single area) -> completed only when
    # every one of the 11 standard areas' listed tiers is done. Karamja is excluded (not in the list).
    if any(_place_pattern(a).search(t) for a in _DIARY_AREAS_UNSUPPORTED):
        return None
    if tiers and not area and ("all" in t or "diaries" in t):
        of = [{"op": "diary", "area": a, "tier": tr} for tr in tiers for a in _DIARY_AREAS]
        return {"op": "and", "of": of}
    return None


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
    # "Inventory check: A, B, C" -> one item requirement per listed item, so the panel marks each carried
    # (green) or missing (red) and the overlay highlights the whole checklist.
    check_reqs = parse_check_items(name)
    if check_reqs:
        step["requirements"] = check_reqs
    # Precedence: skill target > quest completion > achievement-diary completion > item acquisition
    # > quest named only in a [bracket tag]. A tag ("Pick a Cabbage [Black Knight's Fortress]") is
    # context, not the action: the concrete item/action condition beats the distant quest-finish,
    # and the tag must never pull the step to the quest's start tile (see the coordinate fallback).
    # An OPTIONAL step never becomes an auto gate — it stays manual so it can't block the fold/arrivals.
    optional = bool(_OPTIONAL_RE.match(name))
    name_untagged = re.sub(r"\[[^\]]*\]", " ", name)
    cond = None if optional else (detect_skill(name)
                                  or detect_quest_or_diary(name_untagged, name, quest_map))
    item_id = None
    if not cond and not optional:
        iq = detect_item_id_qty(name, item_map)
        if iq:
            item_id, qty = iq
            cumulative[item_id] = cumulative.get(item_id, 0) + qty
            cond = item_condition(item_id, cumulative[item_id],
                                  total_needed.get(item_id, cumulative[item_id]))
        if not cond:
            cond = detect_quest(name, quest_map)  # tag-only quest mention, weakest signal
    if cond:
        step["complete"] = cond
        # Show the wiki's recommended method only on a genuine training grind — NOT on a step that
        # merely names a skill level as a prerequisite ("Complete <quest> when you reach 48 Slayer").
        if cond.get("op") == "skill" and not detect_quest(name, quest_map):
            note = skill_note(cond["skill"], cond["level"])
            if note and note[0]:
                step["note"] = note[0]
                if "wiki" not in step and note[1]:
                    step["wiki"] = note[1]
    else:
        step["manual"] = True
    if item_id is not None:
        step["item"] = item_id  # highlight it in inventory/bank
    elif "item" not in step:
        hi = detect_item_highlight(name)  # equip/bring row -> highlight the item (no completion change)
        if hi is not None:
            step["item"] = hi
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
        if (not world and cq.get("op") == "quest"
                and detect_quest(name_untagged, quest_map) is not None):
            # Guard: a quest named ONLY in a [bracket tag] is route context — sending the player to
            # that quest's start tile mid-quest is wrong AND it drags the anchor for the steps after
            # it ("Pick a Cabbage [Black Knight's Fortress]" must not teleport the route to Falador).
            qs = QUEST_START_BY_CONST.get(cq.get("quest"))
            if qs:
                world = list(qs)
        if not world and quest_map:
            # The step names a quest but did NOT end up with a quest condition — an incidental phrase
            # won the condition instead ("Complete Spirits of the Elid. You can boost to 37 Ranged"
            # took a RANGED>=37 skill condition), so the branch above cannot fire and a grounded
            # start tile goes unused. Coordinate only; the condition is left exactly as detected.
            nq = detect_quest(name_untagged, quest_map)
            if nq and nq.get("op") == "quest":
                qs = QUEST_START_BY_CONST.get(nq.get("quest"))
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
    # ...and NOT when the step also tells you to talk to someone. A merged "travel to X, speak to Y" step
    # leads with a travel verb, but arriving is not doing it — an arrival trigger there would complete the
    # step just for walking past, skipping the conversation.
    if (step.get("manual") and "world" in step and is_travel(name) and not _TALK_RE.search(name)
            and "npc" not in step and "object" not in step):
        x, y, z = step["world"]
        step["complete"] = {"op": "position", "x": x, "y": y, "z": z, "radius": TRAVEL_RADIUS}
        del step["manual"]
    return step


def load_all_enrichers(item_map):
    """Load every enricher table (given an already-fetched item_map) and return the shared pieces both
    entrypoints need plus the counts they print. fetch_item_map() stays the caller's job because the
    item_map is also threaded into the build itself."""
    build_item_index(item_map)
    load_item_aliases()
    load_shop_stock()
    quest_map = load_quest_map()
    load_location_coords()
    nqs = load_quest_start(quest_map)
    nam = load_amenities()
    nres = load_resources()
    nman = load_manual()
    nqsteps = load_qh_steps()
    nsm = load_skill_methods()
    entities = load_qh_entities()
    return {
        "quest_map": quest_map,
        "entities": entities,
        "nqs": nqs,
        "nam": nam,
        "nres": nres,
        "nman": nman,
        "nqsteps": nqsteps,
        "nsm": nsm,
    }


def total_item_needs(step_names, item_map, quest_map):
    """Pass-1 'total items needed' database: sum every acquisition qty per item across the step names,
    using the SAME atomisation + skill>quest>item precedence as build_step so the totals line up."""
    total_needed = {}
    for name in step_names:
        for atom in split_atoms(name):  # same atoms as the build pass, so item totals line up
            if detect_skill(atom) or detect_quest(atom, quest_map):
                continue
            iq = detect_item_id_qty(atom, item_map)
            if iq:
                total_needed[iq[0]] = total_needed.get(iq[0], 0) + iq[1]
    return total_needed


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()  # wipe stale section files so a renamed/removed section never lingers
    item_map = fetch_item_map()
    enr = load_all_enrichers(item_map)
    quest_map = enr["quest_map"]
    entities = enr["entities"]
    print(f"loaded {len(item_map)} item names, {len(quest_map)} quest names, {len(GAZETTEER)} "
          f"locations, {enr['nqs']} quest-start tiles, {enr['nam']} town amenities, {enr['nres']} resource sites, {enr['nman']} manual overrides, {enr['nqsteps']} QH steps, {enr['nsm']} skill-method sets, {len(NORM_ITEM_INDEX)} normalised item index, "
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

    # Pass 1: the "total items needed" database (see total_item_needs) — same atoms + skill>quest>item
    # precedence as the build (a step that is a skill/quest goal is not an item-acquisition step).
    total_needed = total_item_needs(
        (name for (_o, _s, _d, _p, _u, raw) in sections for (_pos, name, _loc, _u2) in raw),
        item_map, quest_map)

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
