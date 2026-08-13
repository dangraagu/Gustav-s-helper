#!/usr/bin/env python3
"""detect_skill: which phrasings may bind a skill>=N auto-complete.

Safety envelope (the 259-step bug was skill PRAYER>=1): level must be 2..99, resource units
("1 prayer point", "10 energy") never bind, and a step whose number is a dialogue sequence
("Talk to Oziach (1,1,1,1)") never binds. Ticking a training step for a player who already has
the level is CORRECT (they don't need to train), so already-true is not a false completion here.

Run: py -3 tools/test_skill.py   (exits non-zero on failure)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402


def cond(skill, level):
    return {"op": "skill", "skill": skill, "level": level, "cmp": ">="}


CASES = [
    # --- existing behaviour that must not regress ------------------------------------------
    ("Train Woodcutting to 36", cond("WOODCUTTING", 36)),
    ("Get 43 prayer", cond("PRAYER", 43)),
    ("eat a jangerberry for 1 prayer point", None),          # level 1 + resource unit
    ("restore 10 energy", None),
    ("Talk to Oziach (1,1,1,1) [Dragon Slayer]", None),      # dialogue digits, not a level

    # --- widening: verbs guides actually use -------------------------------------------------
    ("Finish 15 Woodcutting & light all the logs", cond("WOODCUTTING", 15)),
    ("Cook all Trout then Salmon (You want 32 Cooking)", cond("COOKING", 32)),
    ("Train fishing until 40", cond("FISHING", 40)),

    # --- widening: whole-step level headers --------------------------------------------------
    ("AFTER 65 Agility:", cond("AGILITY", 65)),
    ("65 Agility:", cond("AGILITY", 65)),

    # --- must stay manual: the number is not this step's training goal ----------------------
    ("Boost from 51 Farming using Garden pies to plant level 54 seeds", None),
    ("OPTIONAL: Bring Sunbeam Ale as well if 69 agility to use shortcut", None),
    ("(if you are 26 construction from passive MH contracts, skip this step else do it)", None),
    ("Build Clockmaker's Bench 1 (Crafting table 1)", None),
    ("Stay until level 60", None),                            # no skill word adjacent
]


def main():
    fails = 0
    for text, want in CASES:
        got = sg.detect_skill(text)
        if got != want:
            fails += 1
            print("FAIL detect_skill(%r)\n   got  %s\n   want %s" % (text, got, want))
    print("%d/%d passed" % (len(CASES) - fails, len(CASES)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
