#!/usr/bin/env python3
"""Quest-helper name matching: what may and may not identify a helper.

qh_helper_lookup matches a helper when ALL tokens of its registered name appear in the step text, and
refuses when two helpers tie. That makes two failure modes, and this suite pins both:

  * an ordinary English word registered as a whole helper name ("start" from
    RECIPE_FOR_DISASTER_START) matches every step containing it, pinning unrelated quests to the
    Lumbridge Cook;
  * a BRACKETED TAG naming the diary a step counts toward ("[Karamja Easy Diary]") is metadata, not
    an instruction — feeding it to the index matched the Karamja Easy diary helper and moved a Fight
    Caves step to a Brimhaven ropeswing, taking the two following bank steps with it.

Uses the real tools/data/qh_steps.json. Offline; skips cleanly if the file is absent.
Run: py -3 tools/test_helper_names.py   (exits non-zero on failure)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402

if not (Path(__file__).parent / "data" / "qh_steps.json").exists():
    print("qh_steps.json absent — skipping")
    sys.exit(0)

sg.load_qh_steps()

fails = 0


def check(desc, got, want):
    global fails
    if got != want:
        fails += 1
        print("FAIL %s\n   got  %r\n   want %r" % (desc, got, want))


# --- generic words must not be registered as a whole helper name ----------------------------
for word in ("start", "woodcutting"):
    key = frozenset({word})
    check("%r registered as a lone helper name" % word, key in sg.QH_HELPER_STARTS, False)

# --- but the RFD opener is still findable, via its abbreviation ------------------------------
check("{'rfd'} registered for the RFD opener",
      frozenset({"rfd"}) in sg.QH_HELPER_STARTS, True)

# --- bracketed diary tags are metadata, not part of the instruction --------------------------
tagged = "Enter Fight Caves & wait for Wave 1 to start then leave [Karamja Easy Diary]"
check("bracketed tag stripped from helper tokens",
      {"karamja", "diary"} & sg._content_tokens(tagged), set())
check("the instruction's own words survive the strip",
      {"fight", "caves"} <= sg._content_tokens(tagged), True)

# A tag naming a diary must not drag the step to that diary's first step.
plain = sg.qh_helper_lookup("Enter Fight Caves & wait for Wave 1 to start then leave")
check("tagged and untagged text resolve identically",
      sg.qh_helper_lookup(tagged), plain)

# --- an unbracketed diary instruction must still resolve normally ----------------------------
# (the strip must remove only bracketed spans, never ordinary words)
check("unbracketed text keeps all its tokens",
      {"karamja", "easy", "diary"} <= sg._content_tokens("Do the Karamja easy diary"), True)

print("%d check(s) failed" % fails)
sys.exit(1 if fails else 0)
