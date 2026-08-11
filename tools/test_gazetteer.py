#!/usr/bin/env python3
"""Unit tests for gazetteer place-name matching (scrape_guide.gazetteer_key).

A place name must be matched as a WORD, never as a substring inside a longer word. The
abbreviation keys ("ge", "wt", "pc", "cw", ...) are what make this load-bearing: plain
`key in text` puts "ge" inside "dama(ge)", which pinned 472 route steps — including steps
deep inside the Stronghold of Security, and 212 steps of a HARDCORE IRONMAN guide, where
the player cannot use the Grand Exchange at all — onto the Grand Exchange marker.

Run: py -3 tools/test_gazetteer.py   (exits non-zero on failure)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402

# Stub gazetteer — independent of the harvested gazetteer.json, but keeps the real
# abbreviation keys that caused the bug plus the long names they must lose to.
sg.GAZETTEER.clear()
sg.GAZETTEER.update({
    "ge": (3165, 3490),
    "grand exchange": (3164, 3486),
    "wt": (1630, 3981),
    "pc": (2658, 2625),
    "cw": (2407, 3105),
    "toa": (3345, 2725),
    "ardy": (2624, 3300),
    "ardougne": (2662, 3305),
    "prif": (3263, 6083),
    "prifddinas": (3263, 6083),
    "lumbridge": (3222, 3218),
    "lumbridge castle": (3222, 3218),
    "al-kharid": (3293, 3184),
    "varrock": (3213, 3428),
})

# (text, expected gazetteer_key)
CASES = [
    # --- the regression: abbreviations must not match inside a longer word -----------
    ("On Floor 3, Spider max is 7 so if you take 3 or more damage, drink a wine", None),
    ("Catablepon Max is 9 so drink on any damage", None),
    ("Take the east doors", None),
    ("Manage your inventory", None),
    ("Charge the glory", None),
    ("Watch out for the growth", None),          # 'wt' must not hit "growth"
    ("Upgrade the pickaxe", None),               # 'ge' must not hit "upgrade"
    ("Collect the storage crate", None),         # 'toa' must not hit "storage"

    # --- but a real abbreviation, used as a word, still resolves ---------------------
    ("Bank at GE", "ge"),
    ("Teleport to the ge and buy nothing", "ge"),
    ("Do a CW game", "cw"),
    ("Head to PC for points", "pc"),

    # --- longest key still wins over a shorter one that also matches -----------------
    ("Location: Lumbridge castle", "lumbridge castle"),
    ("Location: Lumbridge", "lumbridge"),
    ("Sell it at the grand exchange", "grand exchange"),

    # --- an abbreviation must not swallow the full name it abbreviates ---------------
    ("Head to Ardougne market", "ardougne"),
    ("Teleport to Prifddinas", "prifddinas"),
    ("Ardy teleport scroll", "ardy"),

    # --- punctuation inside a key must still match -----------------------------------
    ("Run to Al-Kharid", "al-kharid"),
    ("Go to Varrock.", "varrock"),
    ("Varrock, then east", "varrock"),
]


def main():
    fails = 0
    for text, want in CASES:
        got = sg.gazetteer_key(text)
        if got != want:
            fails += 1
            print(f"FAIL gazetteer_key({text!r})\n   got  {got!r}\n   want {want!r}")
    total = len(CASES)
    print(f"{total - fails}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
