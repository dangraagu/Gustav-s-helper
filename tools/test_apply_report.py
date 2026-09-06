#!/usr/bin/env python3
"""apply_report.py: turn a pasted step report into the right coordinate override.

The fixture below is assembled line-by-line from the REAL emitters, not invented:
StepReport.details() writes "**Step report** — <name> (`<id>`)", "Step N/Y  `<stepId>`" and
"• <Label>: <value>" lines; GustavGuidePanel appends "\nProposed spot (player-supplied): x, y, plane p"
inside the **Problem:** note when the user ticks attach-my-position.

Routing under test:
  osiris-ironman  -> tools/data/manual_coords.json      (exact-text key; scrape_guide reads this)
  other guides    -> tools/data/manual_conditions.json  (guide id -> step id -> {world}; build_raw_guide)

Run: py -3 tools/test_apply_report.py   (exits non-zero on failure)
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import apply_report as ar  # noqa: E402


def report(guide_id, guide_name, step_id, text, proposed):
    body = ("**Step report** — " + guide_name + " (`" + guide_id + "`)\n"
            + "Step 42/960  `" + step_id + "`\n"
            + "• Section: Some Section\n"
            + "• Text: " + text + "\n"
            + "• Points at: 3220, 3435, plane 0\n"
            + "• Completes on: manual\n"
            + "• Plugin: 1.2.3\n"
            + "\n**Problem:** points at the wrong spot")
    if proposed:
        body += "\nProposed spot (player-supplied): " + proposed
    return body


def run_case(body, coords, conds):
    with tempfile.TemporaryDirectory() as td:
        mc = Path(td) / "manual_coords.json"
        mo = Path(td) / "manual_conditions.json"
        mc.write_text(json.dumps(coords), encoding="utf-8")
        mo.write_text(json.dumps(conds), encoding="utf-8")
        result = ar.apply(body, coords_path=mc, conditions_path=mo)
        return result, json.loads(mc.read_text(encoding="utf-8")), json.loads(mo.read_text(encoding="utf-8"))


fails = 0


def check(desc, cond):
    global fails
    if not cond:
        fails += 1
        print("FAIL: " + desc)


# 1. osiris report routes to manual_coords.json, keyed by lowercased exact text
r, coords, conds = run_case(
    report("osiris-ironman", "Oziris Ironman Guide", "eg-064", "Walk to Ardy with rope", "2662, 3305, plane 0"),
    {}, {})
check("osiris applied", r.applied and r.target == "manual_coords.json")
check("osiris text key", coords.get("walk to ardy with rope") == [2662, 3305, 0])
check("osiris leaves conditions alone", conds == {})

# 1b. a step whose text carries the scraper's "\nLocation:" suffix: the report's Text line holds
# only the first line (the pre-Location `name`), and the manual_coords key must equal exactly that -
# the same string scrape_guide.manual_lookup() looks up. Three-file coupling; this pins it.
full_step_text = "Walk to Ardy with rope\nLocation: Ardougne"
r, coords, conds = run_case(
    report("osiris-ironman", "Oziris Ironman Guide", "eg-064",
           full_step_text.split("\n")[0], "2662, 3305, plane 0"),
    {}, {})
check("pre-Location key", coords.get("walk to ardy with rope") == [2662, 3305, 0])
check("no multi-line key leaked", all("location:" not in k for k in coords))

# 2. raw-built guide routes to manual_conditions.json under guide id + step id, world only
r, coords, conds = run_case(
    report("b0aty-hcim", "B0aty HCIM Guide V3", "e1-234", "Walk back to Falador", "2965, 3380, plane 0"),
    {}, {})
check("b0aty applied", r.applied and r.target == "manual_conditions.json")
check("b0aty routed", conds.get("b0aty-hcim", {}).get("e1-234", {}).get("world") == [2965, 3380, 0])
check("b0aty leaves coords alone", coords == {})

# 3. an existing override for the SAME step is updated, not duplicated; others preserved
r, coords, conds = run_case(
    report("b0aty-hcim", "B0aty HCIM Guide V3", "e1-234", "Walk back to Falador", "3000, 3360, plane 1"),
    {}, {"b0aty-hcim": {"e1-234": {"world": [1, 2, 0]}, "e9-005": "manual"}})
check("update in place", conds["b0aty-hcim"]["e1-234"]["world"] == [3000, 3360, 1])
check("sibling override preserved", conds["b0aty-hcim"]["e9-005"] == "manual")

# 4. no proposed spot -> nothing grounded to apply -> refuse, files untouched
r, coords, conds = run_case(
    report("b0aty-hcim", "B0aty HCIM Guide V3", "e1-234", "Walk back to Falador", None),
    {}, {})
check("no-spot refused", not r.applied and "Proposed spot" in r.reason)
check("no-spot leaves files", coords == {} and conds == {})

# 5. an out-of-range tile is refused (typo / corrupted paste protection)
r, coords, conds = run_case(
    report("b0aty-hcim", "B0aty HCIM Guide V3", "e1-234", "Walk back to Falador", "99, 99, plane 9"),
    {}, {})
check("bad tile refused", not r.applied)

# 5b. a step demoted to "manual" refuses a coordinate rather than silently re-enabling auto-complete
r, coords, conds = run_case(
    report("b0aty-hcim", "B0aty HCIM Guide V3", "e9-005", "Teleport to Priffdinas", "3263, 6083, plane 0"),
    {}, {"b0aty-hcim": {"e9-005": "manual"}})
check("manual demotion protected", not r.applied and "manual" in r.reason)
check("manual demotion untouched", conds["b0aty-hcim"]["e9-005"] == "manual")

# 5c. a step whose coordinate was deliberately REMOVED ({"world": null} - POH/instance steps where
# any overworld tile is wrong) refuses a crowd-reported spot: a player reporting from inside their
# POH proposes an instance tile that must not resurrect the pin.
r, coords, conds = run_case(
    report("uim-prifddinas", "UIM Prifddinas", "fragment-of-seren-013a",
           "Get your Mage Arena cape out of your house", "1934, 5715, plane 0"),
    {}, {"uim-prifddinas": {"fragment-of-seren-013a": {"world": None}}})
check("null-world removal protected", not r.applied and "removed" in r.reason)
check("null-world removal untouched",
      conds["uim-prifddinas"]["fragment-of-seren-013a"] == {"world": None})

# 6. a report for an unknown guide id is refused rather than guessed at
r, coords, conds = run_case(
    report("not-a-guide", "Mystery", "x-001", "Do a thing", "3000, 3360, plane 0"),
    {}, {})
check("unknown guide refused", not r.applied)

print("%d check(s) failed" % fails)
sys.exit(1 if fails else 0)
