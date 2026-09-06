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
    # BEHAVIOUR CHANGE 2026-09-06 (blob atomisation): long steps now split too — sentence-first,
    # then at action boundaries like any short step. This single-sentence action chain used to be
    # pinned as "left whole"; it now atomises cleanly (the leading non-action clause folds forward).
    (("You should be level 51 slayer and make sure you have finished the Curse of the Empty Lord "
      "miniquest, then teleport to Varrock and grab the history book and pray at the altar and buy "
      "supplies before heading north to the dungeon entrance."),
     ["You should be level 51 slayer, make sure you have finished the Curse of the Empty Lord miniquest",
      "teleport to Varrock",
      "grab the history book",
      "pray at the altar",
      "buy supplies before heading north to the dungeon entrance."]),
    # a parenthetical aside never splits, even when it contains ", talk" (depth guard)
    ("Buy the supplies (destroy the lamps, talk to Bob later) and run to the bank",
     ["Buy the supplies (destroy the lamps, talk to Bob later)", "run to the bank"]),
    # a title abbreviation's dot is not a sentence end ("Dr. Harlow" appears in shipped raws) —
    # this long two-sentence step must split at the real boundary only
    (("Head over to the Blue Moon Inn on the south side of Varrock and talk to Dr. Harlow about "
      "his old vampyre hunting days, buying him a beer if he asks for one during the chat. "
      "Buy 3 beers from the bartender before you leave the inn for the road ahead."),
     [("Head over to the Blue Moon Inn on the south side of Varrock, talk to Dr. Harlow about "
       "his old vampyre hunting days, buying him a beer if he asks for one during the chat."),
      "Buy 3 beers from the bartender before you leave the inn for the road ahead."]),
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

# split_atoms_indexed keeps each atom's ORIGINAL index, so the id suffix (-a/-b/-c) of a surviving atom
# does not shift when an earlier pair merges. Without this, "3 atoms -> 2" silently re-points an existing
# step id at different work, and a saved completion marks a step the player never did.
INDEXED_CASES = [
    # (atom, original index, merged?) — a MERGED atom is flagged so the builder can give it a distinct id.
    # Re-using the travel atom's old id would silently re-point it at "travel + talk", marking the talk
    # complete for anyone who had only walked there. A distinct id makes the step reappear instead.
    ("Go to Draynor, talk to Aggie, then mine 3 clay",
     [("Go to Draynor, talk to Aggie", 0, True), ("mine 3 clay", 2, False)]),
    # no merge -> indices consecutive, nothing flagged
    ("Sell your bronze and buy 3 nets and run to the fishing spot",
     [("Sell your bronze", 0, False), ("buy 3 nets", 1, False), ("run to the fishing spot", 2, False)]),
    # single atom
    ("Talk to the Cook", [("Talk to the Cook", 0, False)]),
    # a whole step that is itself travel+talk merges into ONE atom, and is still flagged
    ("Head to Lumbridge, speak to the Cook",
     [("Head to Lumbridge, speak to the Cook", 0, True)]),
]


def fixture_checks():
    """Real-source fixtures (never hand-invented): properties of atomised shipped-guide blobs."""
    import json
    fails = 0

    def check(desc, cond):
        nonlocal fails
        if not cond:
            fails += 1
            print("FAIL fixture: " + desc)

    raw = json.loads((Path(__file__).parent / "data" / "raw" / "bruhsailer.json")
                     .read_text(encoding="utf-8"))
    blob = next(st["name"] for sec in raw["sections"] for st in sec["steps"]
                if st.get("name", "").startswith("Walk to Port Sarim, make 3 pastry doughs"))
    atoms = sg.split_atoms(blob)
    check("Port Sarim wall atomises into 10+ atoms", len(atoms) >= 10)
    check("every atom has balanced parentheses",
          all(a.count("(") == a.count(")") for a in atoms))
    check("Thurgo sentence is its own atom",
          any(a.startswith("Speak with Thurgo") for a in atoms))
    check("the fly-fishing parenthetical stays inside its buy atom",
          any("16k feathers" in a and "fly fishing later" in a for a in atoms))
    check("no atom is a bare conjunction fragment",
          all(len(a) > 3 and not a.lower().startswith(("and ", "then ", "also ")) for a in atoms))

    cur = json.loads((Path(__file__).parent / "data" / "raw" / "uim-prifddinas-current.json")
                     .read_text(encoding="utf-8"))
    emdash = next((st["name"] for sec in cur["sections"] for st in sec["steps"]
                   if len(st.get("name", "")) > sg.MAX_SPLIT_LEN and "—" in st.get("name", "")), None)
    check("an em-dash long step exists to pin against", emdash is not None)
    if emdash is not None:
        check("em-dash note style stays ONE step (notes are advice, not checkboxes)",
              sg.split_atoms(emdash) == [emdash.strip()])
    return fails


def main():
    fails = fixture_checks()
    for src, want in INDEXED_CASES:
        got = sg.split_atoms_indexed(src)
        if got != want:
            fails += 1
            print(f"FAIL split_atoms_indexed({src!r})\n   got  {got}\n   want {want}")
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
    total = len(CASES) + len(TRAVEL_CASES) + len(INDEXED_CASES)
    print(f"{total - fails}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
