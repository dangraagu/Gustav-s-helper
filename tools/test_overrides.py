"""Tests for build_raw_guide.apply_override — the manual_conditions.json semantics.

Covers the existing dict/"manual" behavior and the null-strip semantics: an explicit
JSON null for world/npc/npcs/object REMOVES that key from the built step (for steps
whose only correct coordinate is "none", e.g. Player-Owned-House or quest-instance
steps where any overworld tile is wrong).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_raw_guide import apply_override, strip_null_overrides  # noqa: E402

failures = []


def check(name, cond):
    if cond:
        print("ok   %s" % name)
    else:
        failures.append(name)
        print("FAIL %s" % name)


# --- existing behavior stays intact ----------------------------------------------------------
s = {"id": "x", "text": "t", "complete": {"type": "varbit", "id": 1, "value": 1}}
check("'manual' strips complete and marks manual",
      apply_override(s, "manual") and s.get("manual") is True and "complete" not in s)

s = {"id": "x", "text": "t"}
check("world triple is applied",
      apply_override(s, {"world": [3200, 3200, 1]}) and s["world"] == [3200, 3200, 1])

s = {"id": "x", "text": "t", "npcs": [1, 2]}
check("npc replaces npcs",
      apply_override(s, {"npc": 5}) and s["npc"] == 5 and "npcs" not in s)

check("unknown override shape is a no-op", apply_override({"id": "x"}, 42) is False)

# --- null-strip semantics --------------------------------------------------------------------
s = {"id": "x", "text": "t", "manual": True, "world": [3106, 3915, 0]}
check("world:null removes the coordinate",
      apply_override(s, {"world": None}) and "world" not in s)

s = {"id": "x", "text": "t", "manual": True, "world": [2476, 4937, 0], "object": 7348}
check("world:null + object:null strips both",
      apply_override(s, {"world": None, "object": None})
      and "world" not in s and "object" not in s)

s = {"id": "x", "text": "t"}
check("world:null on a step without world is still a clean no-crash change-report",
      apply_override(s, {"world": None}) is True and "world" not in s)

s = {"id": "x", "text": "t", "npc": 9, "npcs": [1]}
check("npc:null and npcs:null strip without cross-clobber",
      apply_override(s, {"npc": None, "npcs": None})
      and "npc" not in s and "npcs" not in s)

s = {"id": "x", "text": "t", "world": [1, 2, 0]}
check("null world does not disturb siblings",
      apply_override(s, {"world": None, "npc": 12}) and s["npc"] == 12 and "world" not in s)

s = {"id": "x", "text": "t", "complete": {"type": "varbit", "id": 1, "value": 1},
     "world": [3, 4, 0]}
apply_override(s, {"world": None})
check("null world never touches the completion condition",
      s.get("complete") == {"type": "varbit", "id": 1, "value": 1})

# --- null strips survive the gap-fill passes -------------------------------------------------
# fill_location_gaps runs AFTER apply_override and re-inherits a neighbor's tile into any step
# missing world — exactly how the POH steps got their wrong tile in the first place. The
# post-fill enforcement pass must strip them again.
steps = [
    {"id": "a-1", "text": "walk", "world": [2869, 10202, 0]},
    {"id": "a-2", "text": "poh step", "manual": True, "world": [2869, 10202, 0]},  # re-filled
    {"id": "a-3", "text": "next", "world": [2900, 10200, 0], "npc": 4},
]
strip_null_overrides(steps, {"a-2": {"world": None}})
check("post-fill pass strips the re-inherited world",
      "world" not in steps[1] and steps[0]["world"] == [2869, 10202, 0]
      and steps[2]["world"] == [2900, 10200, 0])

steps = [{"id": "b-1", "text": "t", "world": [1, 2, 0], "object": 7348}]
strip_null_overrides(steps, {"b-1": {"world": None, "object": None}})
check("post-fill pass strips object null too",
      "world" not in steps[0] and "object" not in steps[0])

steps = [{"id": "c-1", "text": "t", "world": [1, 2, 0]}]
strip_null_overrides(steps, {"c-1": {"world": [5, 6, 0]}, "c-9": "manual"})
check("post-fill pass ignores non-null overrides and 'manual' strings",
      steps[0]["world"] == [1, 2, 0])

print()
if failures:
    print("%d FAILURES: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("all override checks passed")
