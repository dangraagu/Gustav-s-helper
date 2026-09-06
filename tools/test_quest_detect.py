"""Tests for scrape_guide.detect_quest — quest-name matching robustness.

Covers the 2026-09-06 widening (all verified against tools/data/quest_names.json consts):
  - apostrophe-insensitive matching on BOTH sides (_norm turns "Knight's" into "knight s",
    which never matched a guide's "Knights")
  - optional leading "A"/"An" article (like the existing "The")
  - trailing roman-numeral strip for "... I" quests ("dragon slayer" -> DRAGON_SLAYER_I),
    with longest-match still preferring the II/2 forms
  - subtitle strip ("Desert Treasure II - The Fallen Empire" matches "Desert Treasure II"),
    guarded so the eleven "Recipe for Disaster - <sub>" names can never claim the base name
  - a curated typo/alias table (guide misspellings seen in shipped guides)
  - an exact-step-text table for names too generic to alias as substrings ("Finish waterfall")
and pins the existing negative guards (optional/negated asides, quest-list warnings).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402

QM = sg.load_quest_map()
assert QM, "quest_names.json must load"

failures = []


def check(name, cond):
    if cond:
        print("ok   %s" % name)
    else:
        failures.append(name)
        print("FAIL %s" % name)


def q(text):
    d = sg.detect_quest(text, QM)
    return (d.get("quest"), d.get("state")) if d else None


def qc(text):
    """Quest const or None — subscript-safe when the detector misses."""
    d = q(text)
    return d[0] if d else None


# --- apostrophe-insensitive ------------------------------------------------------------------
check("Knights Sword (no apostrophe in guide)",
      q("Complete Knights Sword") == ("THE_KNIGHTS_SWORD", "FINISHED"))
check("Monks Friend", q("Complete Monks Friend") == ("MONKS_FRIEND", "FINISHED"))
check("Twilights Promise", q("Complete Twilights Promise") == ("TWILIGHTS_PROMISE", "FINISHED"))
check("Pirates Treasure",
      qc("Complete Pirates Treasure [Keep Ring for later]") == "PIRATES_TREASURE")
check("apostrophe on the TEXT side",
      q("Do Black knight's fortress") == ("BLACK_KNIGHTS_FORTRESS", "FINISHED"))
check("dorics quest", q("dorics quest") == ("DORICS_QUEST", "FINISHED"))
check("Eagles Peak", qc("Eagles Peak") == "EAGLES_PEAK")

# --- article-optional A/An -------------------------------------------------------------------
check("Kingdom Divided (A dropped)", q("Complete Kingdom Divided") == ("A_KINGDOM_DIVIDED", "FINISHED"))
check("Taste of hope (A dropped)", qc("Taste of hope (xp on agi 3x)") == "A_TASTE_OF_HOPE")

# --- roman-numeral strip for '... I' quests --------------------------------------------------
check("bare dragon slayer = DS1", q("dragon slayer") == ("DRAGON_SLAYER_I", "FINISHED"))
check("Dragon Slayer 2 still wins as DS2", qc("Complete Dragon Slayer 2") == "DRAGON_SLAYER_II")
check("Dragon Slayer II unchanged", qc("Complete Dragon Slayer II") == "DRAGON_SLAYER_II")
check("bare monkey madness = MM1",
      qc("Monkey madness (get the attack and defence training)") == "MONKEY_MADNESS_I")
check("bare Desert Treasure = DT1", qc("Do Desert Treasure") == "DESERT_TREASURE_I")

# --- subtitle strip --------------------------------------------------------------------------
check("Desert Treasure II quest (subtitle dropped)",
      qc("Complete Desert Treasure II quest") == "DESERT_TREASURE_II__THE_FALLEN_EMPIRE")
check("DT2 arabic", qc("Do desert treasure 2") == "DESERT_TREASURE_II__THE_FALLEN_EMPIRE")
# The base name must still be the BASE quest — eleven 'Recipe for Disaster - <sub>' names all
# strip to 'recipe for disaster' and must never claim it.
check("RFD base name stays the base quest",
      q("Complete Recipe for Disaster") == ("RECIPE_FOR_DISASTER", "FINISHED"))
check("RFD subquest full name still matches itself",
      qc("Do Recipe for Disaster - Mountain Dwarf") == "RECIPE_FOR_DISASTER__MOUNTAIN_DWARF")

# --- typo/alias table ------------------------------------------------------------------------
for text, const in [
    ("Complete Witches House quest - Safespot guide", "WITCHS_HOUSE"),
    ("Complete Fremmenik Trials", "THE_FREMENNIK_TRIALS"),
    ("Muder Mystery (3 QP)", "MURDER_MYSTERY"),
    ("vampire slayer", "VAMPYRE_SLAYER"),
    ("a porcine of intrest", "A_PORCINE_OF_INTEREST"),
    ("Do Porcine of intrest for 30 more slayer points", "A_PORCINE_OF_INTEREST"),
    ("Enlighted Journey", "ENLIGHTENED_JOURNEY"),
    ("Death to the Dorg", "DEATH_TO_THE_DORGESHUUN"),
    ("Another slice of HAM", "ANOTHER_SLICE_OF_HAM"),
    ("Gerturde's Cat", "GERTRUDES_CAT"),
    ("Do Shades of morton quest", "SHADES_OF_MORTTON"),
    ("Garden of tranquility quest", "GARDEN_OF_TRANQUILLITY"),
    ("Complete One Small Favor", "ONE_SMALL_FAVOUR"),
    ("Do the Digsite quest", "THE_DIG_SITE"),
    ("Fairy tale pt.1", "FAIRYTALE_I__GROWING_PAINS"),
]:
    got = q(text)
    check("alias: %r -> %s" % (text, const), got is not None and got[0] == const)

# --- exact-step-text table (names too generic for substring aliasing) ------------------------
check("exact: Finish waterfall", q("Finish waterfall") == ("WATERFALL_QUEST", "FINISHED"))
check("exact: Finish RFD", q("Finish RFD") == ("RECIPE_FOR_DISASTER", "FINISHED"))
check("generic 'waterfall' mention does NOT bind", q("Fish trout near the waterfall") is None)
check("generic 'rfd' mention does NOT bind", q("Bank your rfd lamps in Lumbridge") is None)
check("location-only Digsite mention does NOT bind", q("Mine clay at the Digsite") is None)

# --- generic-place guards: quest names that are also place names must not bind ---------------
# "Mage Arena I"'s numeral-stripped base is the PLACE "mage arena" — visited constantly for the
# bank/lever. Binding it would false-complete fetch/bank steps for any account with MA1 done.
check("Mage Arena bank trip does NOT bind",
      q("Grab a knife and go to the Mage Arena. Buy 1250 nature runes") is None)
check("Mage Arena cape fetch does NOT bind",
      q("Get your Mage Arena cape out of your house") is None)
check("explicit Mage Arena I still binds", qc("Complete Mage Arena I") == "MAGE_ARENA_I")

# --- requirement-aside guard: "<quest> required/needed" is a prerequisite, not the action -----
check("'(Desert treasure required)' does NOT bind",
      q("burst jellies/dusts in catacombs (Desert treasure required)") is None)

# --- pre-name aside cues ---------------------------------------------------------------------
check("'before you complete X' does NOT bind",
      q("If you run out of gold bars before you complete Forgettable Tale, tough luck") is None)
check("'Partially complete X' does NOT bind",
      q("Partially complete Fairytale II until you can use fairy rings") is None)
check("'progress through X' does NOT bind",
      q("Head back to Martin and progress through Fairytale II - Curing a Queen until rings") is None)

# --- multi-quest steps bind ALL named quests as an AND ---------------------------------------
d = sg.detect_quest("Dragon Slayer 1, Priest in Peril and Regicide", QM)
check("multi-quest list binds AND of all three",
      d is not None and d.get("op") == "and"
      and sorted(c["quest"] for c in d["of"]) == ["DRAGON_SLAYER_I", "PRIEST_IN_PERIL", "REGICIDE"]
      and all(c["state"] == "FINISHED" for c in d["of"]))
d = sg.detect_quest("Make sure to do the steps for Dragon Slayer and Ides of Milk here", QM)
check("two-quest step binds AND of both",
      d is not None and d.get("op") == "and"
      and sorted(c["quest"] for c in d["of"]) == ["DRAGON_SLAYER_I", "THE_IDES_OF_MILK"])
check("same quest twice binds ONCE, not an AND",
      q("Talk to Malak to continue Desert Treasure [Desert Treasure]")
      == ("DESERT_TREASURE_I", "FINISHED"))
check("neg-dropped siblings leave a single binding, not an AND",
      q("Eagles Peak (dont bother if you did recruitment drive, wanted!)")
      == ("EAGLES_PEAK", "FINISHED"))

# --- "Contact!" vs the NPC Contact / Astral Contact SPELL ------------------------------------
check("'NPC contact unlock' keeps only the real quest",
      q("Lunar diplomacy (NPC contact unlock)") == ("LUNAR_DIPLOMACY", "FINISHED"))
check("'Use Astral Contact' does NOT bind",
      q("Use Astral Contact, can be done from your POH") is None)
check("bare Contact! still binds", qc("Complete Contact!") == "CONTACT")

# --- conditional-aside cues ------------------------------------------------------------------
check("'consider ... until you can complete X' does NOT bind",
      q("consider taking a break until you can complete Sins of the Father") is None)
# "you can start/complete/do X" is a suggestion, not the step's action (deploy-gate CORR-1):
# binding it as an AND member stalls the step on an optional side quest forever.
check("'you can complete X' suggestion does NOT bind",
      q("You can complete Ratcatchers for a wily cat, if you would like a higher success rate "
        "whilst catching rats") is None)
check("'you can start X' suggestion does NOT bind",
      q("While there, you can start Ghosts Ahoy up to the part where you visit the crone") is None)
d = sg.detect_quest("Complete Song of the Elves. — Reclaim your staff. — After you are done with "
                    "it, you can start Perilous Moons and store the staff", QM)
check("instructed quest binds ALONE when the other mention is a 'you can start' aside",
      d == {"op": "quest", "quest": "SONG_OF_THE_ELVES", "state": "FINISHED"})

# --- RFD subquest slash forms (real shipped-guide phrasings) ---------------------------------
check("'Recipe for Disaster/Freeing Evil Dave' binds the SUBQUEST, not base RFD",
      q("Complete Recipe for Disaster/Freeing Evil Dave. If your cat is not grown, do this "
        "when it does grow") == ("RECIPE_FOR_DISASTER__EVIL_DAVE", "FINISHED"))
check("'RFD/Goblin' short form binds Wartface & Bentnoze",
      q("run to the Goblin Village and continue RFD/Goblin to get a Slop of compromise")
      == ("RECIPE_FOR_DISASTER__WARTFACE__BENTNOZE", "FINISHED"))
check("'RFD/Cook' short form binds Another Cook's Quest",
      q("run to the chest and complete RFD/Cook")
      == ("RECIPE_FOR_DISASTER__ANOTHER_COOKS_QUEST", "FINISHED"))
check("'RFD/MM' binds King Awowogei", qc("do RFD/MM") == "RECIPE_FOR_DISASTER__KING_AWOWOGEI")
check("'RFD/Varze' binds Sir Amik Varze",
      qc("speak with the Wise Old Man for RFD/Varze") == "RECIPE_FOR_DISASTER__SIR_AMIK_VARZE")
check("'Freeing the Mountain Dwarf' wiki form",
      qc("Complete Recipe for Disaster/Freeing the Mountain Dwarf")
      == "RECIPE_FOR_DISASTER__MOUNTAIN_DWARF")
check("'Defeating the Culinaromancer' wiki form",
      qc("Complete Recipe for Disaster/Defeating the Culinaromancer")
      == "RECIPE_FOR_DISASTER__CULINAROMANCER")
check("bare 'rfd' still never binds as a substring",
      q("Bank your rfd lamps in Lumbridge") is None)

# --- bare 'start <quest>' adjacency (commas are normalised away: 'tele, start X') -------------
check("', start X' = IN_PROGRESS",
      q("Chronicle tele, start Dragon slayer at champion's guild")
      == ("DRAGON_SLAYER_I", "IN_PROGRESS"))

# --- 'and start X' mid-text is a start step for X --------------------------------------------
check("'and start X' = IN_PROGRESS",
      q("run south to the Mage of Zamorak and start Enter the Abyss")
      == ("ENTER_THE_ABYSS", "IN_PROGRESS"))

# --- diary-primary steps: notes mentioning quests must not steal a diary binding -------------
t = ("Complete the easy Varrock Diary. — Complete Enter the abyss, then craft 1 inventory of "
     "runes at the Ourania Altar. — Complete Temple of the eye.")
d = sg.detect_quest_or_diary(t, t, QM)
check("diary-primary step binds the diary, not a note's quest",
      d == {"op": "diary", "area": "varrock", "tier": "easy"})
d = sg.detect_quest_or_diary("Complete Hazeel Cult ", "Complete Hazeel Cult [Ardougne Easy Diary]", QM)
check("quest-primary step still binds the quest",
      d is not None and d.get("quest") == "HAZEEL_CULT")

# --- existing guards must survive the widening -----------------------------------------------
check("negated aside still refuses",
      q("dont bother with Eagles Peak") is None)
check("optional-cue aside still refuses",
      q("optional: Vampyre Slayer for the xp") is None)
check("quest-list warning still refuses",
      q("DONT complete the following: Eagles Peak, Wanted!") is None)
check("start verb still IN_PROGRESS",
      q("Start Monkey Madness") == ("MONKEY_MADNESS_I", "IN_PROGRESS"))
check("plain unknown text unbound", q("Chop 100 willow logs") is None)

print()
if failures:
    print("%d FAILURES: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("all quest-detect checks passed")
