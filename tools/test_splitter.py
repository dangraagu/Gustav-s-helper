#!/usr/bin/env python3
"""Unit tests for the step atomiser in scrape_guide.split_atoms / is_travel.
Run: py -3 tools/test_splitter.py   (exits non-zero on failure)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402

CASES = [
    # (input, expected atoms)
    # travel + talk MERGE (the NPC is the target); a following distinct action still splits off
    ("Go to Draynor, talk to Aggie, then mine 3 clay",
     ["Go to Draynor, talk to Aggie", "mine 3 clay"]),
    ("Head to Lumbridge, speak to the Cook", ["Head to Lumbridge, speak to the Cook"]),
    # travel + a NON-interact action (buy/skill) is NOT merged — those are separate targets
    ("Run to Draynor and buy a spade", ["Run to Draynor", "buy a spade"]),
    ("Sell your bronze and buy 3 nets and run to the fishing spot",
     ["Sell your bronze", "buy 3 nets", "run to the fishing spot"]),
    # 'and' NOT followed by an action verb => stays one task (no false split)
    ("Buy a bucket and a rope", ["Buy a bucket and a rope"]),
    ("Pick up the bread and the bucket", ["Pick up the bread and the bucket"]),
    # single action => unchanged
    ("Talk to the Cook", ["Talk to the Cook"]),
    ("Kill goblins for bones", ["Kill goblins for bones"]),
    # leading non-action fragment folds forward into the first real action (not a junk step)
    ("In Lumbridge, talk to Hans", ["In Lumbridge, talk to Hans"]),
    # 'return' still splits (it's an action verb) even though it's no longer a travel/arrival verb
    ("Kill goblins, then return to Aggie", ["Kill goblins", "return to Aggie"]),
    # 'and then'
    ("Head to Varrock and then buy a sword", ["Head to Varrock", "buy a sword"]),
    # semicolon
    ("Head to Varrock; buy a sword", ["Head to Varrock", "buy a sword"]),
    # empty
    ("", []),
    # long prose (>180 chars) is left whole, never shredded into noise
    (("You should be level 51 slayer and make sure you have finished the Curse of the Empty Lord "
      "miniquest, then teleport to Varrock and grab the history book and pray at the altar and buy "
      "supplies before heading north to the dungeon entrance."),
     [("You should be level 51 slayer and make sure you have finished the Curse of the Empty Lord "
       "miniquest, then teleport to Varrock and grab the history book and pray at the altar and buy "
       "supplies before heading north to the dungeon entrance.")]),
]

TRAVEL_CASES = [
    ("Go to Falador", True),
    ("Head to the bank", True),
    ("Make your way to Lumbridge", True),
    ("Run to the fishing spot", True),
    ("Talk to Aggie", False),
    ("Mine 3 clay", False),
    ("Make 5 bronze bars", False),   # 'make' (craft) is NOT travel
    # interaction verbs that read like travel must NOT be arrival-triggers
    ("Return to Aggie", False),
    ("Enter the cave", False),
    ("Climb the ladder", False),
]

def main():
    fails = 0
    for src, want in CASES:
        got = sg.split_atoms(src)
        if got != want:
            fails += 1
            print(f"FAIL split_atoms({src!r})\n   got  {got}\n   want {want}")
    for src, want in TRAVEL_CASES:
        got = sg.is_travel(src)
        if got != want:
            fails += 1
            print(f"FAIL is_travel({src!r}) got {got} want {want}")
    total = len(CASES) + len(TRAVEL_CASES)
    print(f"{total - fails}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
