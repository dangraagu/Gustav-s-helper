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


def heading(name: str, words: int = 6) -> str:
    parts = name.split()
    h = " ".join(parts[:words])
    if len(parts) > words:
        h += " …"
    return h[:70]


def build_step(prefix, position, name, loc, url):
    sid = f"{prefix}-{position:03d}" if isinstance(position, int) else f"{prefix}-{position}"
    text = name
    if loc:
        text = f"{name}\nLocation: {loc}"
    step = {"id": sid, "title": heading(name), "text": text}
    if url and isinstance(url, str) and url.startswith("http"):
        step["wiki"] = url
    cond = detect_skill(name)
    if cond:
        step["complete"] = cond
    else:
        step["manual"] = True
    return step


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = {"_comment": "Auto-generated by tools/scrape_guide.py. Ordered section files.",
             "sections": []}
    grand_total = 0
    grand_auto = 0
    for order, slug, display, prefix in SECTIONS:
        url = f"https://ironman.guide/guide/{slug}"
        try:
            html = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {slug}: fetch failed: {e}", file=sys.stderr)
            continue
        raw = extract_howto_steps(html)
        steps = [build_step(prefix, pos, name, loc, u) for (pos, name, loc, u) in raw if name]
        auto = sum(1 for s in steps if "complete" in s)
        grand_total += len(steps)
        grand_auto += auto
        fname = f"{order}-{slug}.json"
        payload = {
            "_source": url,
            "_attribution": "Route by Oziris (@OzirisLoL) / ironman.guide. See NOTICE.",
            "section": display,
            "steps": steps,
        }
        (OUT_DIR / fname).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        index["sections"].append(fname)
        print(f"  {fname:34s} {len(steps):4d} steps  ({auto} auto-detected)")

    (OUT_DIR / "route-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTOTAL: {grand_total} steps, {grand_auto} auto-detected, {grand_total - grand_auto} manual")
    print(f"Wrote {len(index['sections'])} section files + route-index.json to {OUT_DIR}")


if __name__ == "__main__":
    main()
