#!/usr/bin/env python3
"""Whole-word matching regressions for the remaining name->coord matchers.

Same bug class as the gazetteer one (see tools/test_gazetteer.py): a short key tested with a plain
`key in text` fires inside a longer word. Each case below is a wrong coordinate that shipped.

Run: py -3 tools/test_wholeword.py   (exits non-zero on failure)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402

sg.GAZETTEER.clear()
sg.GAZETTEER.update({
    "lumbridge": (3222, 3218),
    "ardougne": (2624, 3300),
    "hosidius": (1744, 3517),
    "burthorpe": (2900, 3543),
    "varrock": (3213, 3428),
})
sg.AMENITIES.clear()
sg.AMENITIES.update({
    "lumbridge": {"range": [3212, 3215, 0], "bank": [3208, 3220, 2], "anvil": [3188, 3425, 0]},
    "ardougne": {"well": [2612, 3255, 0], "bank": [2615, 3332, 0]},
    "hosidius": {"range": [1679, 3618, 0]},
    "burthorpe": {"bank": [2843, 3543, 0]},
    "varrock": {"well": [3227, 3410, 0], "anvil": [3188, 3425, 0], "bank": [3185, 3441, 0]},
})

# (step text, loc hint, expected amenity tile)
AMENITY_CASES = [
    # --- shipped wrong coordinates: key matched INSIDE a longer word --------------------
    ("Bring Void ranger helm", "Hosidius", None),                       # 'range' in "ranger"
    ("fast Ranged training with chinchompas", "Lumbridge", None),       # 'range' in "Ranged"
    ("Claim a Training bow from the Ranged combat tutor", "Lumbridge", None),
    ("Walk to Ardy with rope, dwellberries, hangover cure", "Ardougne", None),  # 'well' in "dwellberries"
    ("Obtain a Fighter Torso while still death banked", "Burthorpe", None),     # 'bank' in "banked"
    ("Sell the jewellery", "Varrock", None),                            # 'well' in "jewellery"

    # --- "as well" is an idiom, never a reference to the town well ---------------------
    ("Grab each elemental rune as well, maybe 500 runes each", "Varrock", None),
    ("Bring a rope as well", "Ardougne", None),

    # --- but the real facility word still resolves -------------------------------------
    ("Cook the trout on the range", "Lumbridge", [3212, 3215, 0]),
    ("Draw water from the well", "Ardougne", [2612, 3255, 0]),
    ("Deposit everything in the bank", "Burthorpe", [2843, 3543, 0]),

    # --- plurals must keep working (a bare word-boundary copy would break these) --------
    ("Use one of the anvils", "Varrock", [3188, 3425, 0]),
    ("Both banks are close by", "Varrock", [3185, 3441, 0]),
]

# (step text, expected detect_diary result)
DIARY_CASES = [
    # 'elite' inside "RuneLite" and 'hard' inside "Khardian"/"shards" must not make a diary
    ("Install RuneLite for the diary tracker", None),
    ("Collect Khardian shards for the diary", None),
    # a real single diary still resolves
    ("Pickpocket a man for the Ardougne easy diary", {"op": "diary", "area": "ardougne", "tier": "easy"}),
]


def main():
    fails = 0
    for text, loc, want in AMENITY_CASES:
        got = sg.amenity_lookup(text, loc, None)
        if got != want:
            fails += 1
            print("FAIL amenity_lookup(%r, %r)\n   got  %s\n   want %s" % (text, loc, got, want))
    for text, want in DIARY_CASES:
        got = sg.detect_diary(text)
        if got != want:
            fails += 1
            print("FAIL detect_diary(%r)\n   got  %s\n   want %s" % (text, got, want))
    total = len(AMENITY_CASES) + len(DIARY_CASES)
    print("%d/%d passed" % (total - fails, total))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
