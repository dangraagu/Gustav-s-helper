#!/usr/bin/env python3
"""Unit tests for the amenity resolver (scrape_guide.amenity_lookup / gazetteer_key).
Run: py -3 tools/test_amenity.py   (exits non-zero on failure)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402

# Stub data — independent of the harvested amenities.json.
sg.AMENITIES.clear()
sg.AMENITIES.update({
    "lumbridge": {
        "general store": [3211, 3246, 0],
        "bank": [3208, 3220, 2],
        "bob's brilliant axes": [3231, 3203, 0],
        "range": [3212, 3216, 0],
    },
    "falador": {
        "furnace": [2974, 3369, 0],
    },
})
sg.GAZETTEER.setdefault("lumbridge", (3222, 3218))
sg.GAZETTEER.setdefault("falador", (2965, 3380))

sg.RESOURCES.clear()
sg.RESOURCES.update({
    "clay rocks": [[3180, 3370, 0], [3040, 9760, 0]],   # first = canonical; second elsewhere
    "oak tree": [[3190, 3247, 0]],
    "fishing shrimp": [[3239, 3151, 0]],
    "cow": [[3253, 3270, 0]],
    # first site is UNDERGROUND (y+6400): must still be seen as nearest from a surface anchor
    "hill giant": [[3111, 9841, 0], [3307, 3669, 0]],
})

CASES = [
    # (step name, loc, anchor, expected coord)  — the user's exact complaint:
    ("Buy a spade", "Lumbridge", None, [3211, 3246, 0]),          # general store, NOT town centre
    ("Sell your bronze dagger", "Lumbridge", None, [3211, 3246, 0]),
    # the traded ITEM picks the matching shop over the general store ("axe" -> "...axes")
    ("Buy an axe", "Lumbridge", None, [3231, 3203, 0]),
    # named shop in the text
    ("Buy something from Bob's Brilliant Axes", "Lumbridge", None, [3231, 3203, 0]),
    # action keywords -> facility (with plane preserved)
    ("Bank your logs", "Lumbridge", None, [3208, 3220, 2]),
    ("Cook the shrimp", "Lumbridge", None, [3212, 3216, 0]),
    ("Smelt a bronze bar", "Falador", None, [2974, 3369, 0]),
    # town from the step TEXT when no loc
    ("Buy a spade in Lumbridge", None, None, [3211, 3246, 0]),
    # ROUTE CONTINUITY: no town named anywhere, but the route is currently near Lumbridge
    ("Buy a spade", None, [3225, 3220, 0], [3211, 3246, 0]),
    # anchor too far from any amenity town -> None (never borrow a distant town's shop)
    ("Buy a spade", None, [2000, 5000, 0], None),
    # no amenity keyword -> None (falls through to town centre elsewhere)
    ("Talk to Hans", "Lumbridge", None, None),
    # amenity keyword but town has no such facility -> None
    ("Bank your ore", "Falador", None, None),
    # unknown town -> None
    ("Buy a spade", "Atlantis", None, None),
]

RESOURCE_CASES = [
    # (step name, anchor, expected)
    ("Mine 3 clay", [3170, 3360, 0], [3180, 3370, 0]),       # nearest clay site to the anchor
    ("Mine 3 clay", [3050, 9750, 0], [3040, 9760, 0]),       # ...and the other one when nearer
    ("Mine 3 clay", None, [3180, 3370, 0]),                  # no anchor -> canonical first site
    ("Chop some oak logs", None, [3190, 3247, 0]),
    ("Catch shrimp", None, [3239, 3151, 0]),
    ("Kill cows for cowhides", None, [3253, 3270, 0]),
    # underground normalisation: Edgeville Dungeon (y 9841 ~= surface 3441) beats the far surface site
    ("Kill hill giants", [3087, 3496, 0], [3111, 9841, 0]),
    ("Buy a raw lobster", None, None),                       # verb-gated: buying is not fishing
    ("Mine gold", None, None),                               # unknown resource -> None
    ("Talk to the miner", None, None),                       # no verb+resource
]



def craft_gap_tests():
    fails = 0
    sg.GAZETTEER.setdefault("varrock", (3213, 3428))
    sg.AMENITIES.setdefault("varrock", {})["anvil"] = [3188, 3426, 0]
    steps = [
        {"id": "a", "text": "Enter the raid.", "world": [3345, 2725, 0]},        # prev = a raid, far away
        {"id": "b", "text": "Make a mithril grapple"},                            # needs an anvil
        {"id": "c", "text": "Talk to Bob.", "world": [3209, 3216, 0]},            # next = Lumbridge-ish
        {"id": "d", "text": "Make energy pots"},                                  # no facility -> inherit
        {"id": "e", "text": "Do slayer until 60 attack"},                         # meta: must stay unlocated
    ]
    sg.fill_craft_gaps(steps)
    if steps[1].get("world") != [3188, 3426, 0]:
        fails += 1; print("FAIL grapple should land on the Varrock anvil, got", steps[1].get("world"))
    if steps[3].get("world") != [3209, 3216, 0]:
        fails += 1; print("FAIL energy pots should inherit the previous located coord, got", steps[3].get("world"))
    if "world" in steps[4]:
        fails += 1; print("FAIL meta step must stay unlocated")
    return fails, 3

def main():
    fails = 0
    for name, loc, anchor, want in CASES:
        got = sg.amenity_lookup(name, loc, anchor)
        if got != want:
            fails += 1
            print(f"FAIL amenity_lookup({name!r}, {loc!r}, anchor={anchor})\n   got  {got}\n   want {want}")
    for name, anchor, want in RESOURCE_CASES:
        got = sg.resource_lookup(name, anchor)
        if got != want:
            fails += 1
            print(f"FAIL resource_lookup({name!r}, anchor={anchor})\n   got  {got}\n   want {want}")
    if sg.gazetteer_key("Location: Lumbridge castle") != "lumbridge castle" and \
            sg.gazetteer_key("Location: Lumbridge") != "lumbridge":
        fails += 1
        print("FAIL gazetteer_key basic match")
    cf, ct = craft_gap_tests()
    fails += cf
    total = len(CASES) + len(RESOURCE_CASES) + 1 + ct
    print(f"{total - fails}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
