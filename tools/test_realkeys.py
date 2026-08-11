#!/usr/bin/env python3
"""Every REAL key in the shipped data files must still match itself under whole-word anchoring.

test_gazetteer.py and test_wholeword.py stub the tables, so they prove the collisions are gone but
cannot prove a real key still resolves. This suite loads tools/data/*.json as the build does. It is
the guard against a lookaround change silently disabling a place or facility whose name carries
punctuation — "mos le'harmless", "harpoon joe's house of 'rum'", "hunter guild (varlamore)",
"al-kharid" — none of which \\b would handle correctly.

Offline: reads only tools/data/*.json, no network.
Run: py -3 tools/test_realkeys.py   (exits non-zero on failure)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape_guide as sg  # noqa: E402

DATA = Path(__file__).parent / "data"

# Contexts a place/facility name really appears in inside guide prose.
CONTEXTS = ["%s", "go to %s", "go to %s.", "go to %s,", "at %s!", "(%s)", "-- %s --",
            "head to %s now", "%s bank", "the %s"]


def load_tables():
    gaz, amen = {}, {}
    for fname in ("gazetteer.json", "location_coords.json"):
        p = DATA / fname
        if p.exists():
            for k, v in json.loads(p.read_text(encoding="utf-8")).items():
                if isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) >= 2:
                    gaz[k.lower()] = (v[0], v[1])
    p = DATA / "amenities.json"
    if p.exists():
        for town, spots in json.loads(p.read_text(encoding="utf-8")).items():
            if isinstance(spots, dict):
                amen.setdefault(town.lower(), {}).update(spots)
    return gaz, amen


def main():
    gaz, amen = load_tables()
    if not gaz:
        print("FAIL: no gazetteer keys loaded — data/gazetteer.json missing?")
        sys.exit(1)

    sg.GAZETTEER.clear()
    sg.GAZETTEER.update(gaz)
    fails = 0

    # 1. Every gazetteer key resolves to ITSELF (longest-match may pick a longer key that
    #    contains it — that is correct behaviour, so accept any key that spans this one).
    for key in gaz:
        for ctx in CONTEXTS:
            got = sg.gazetteer_key(ctx % key)
            if got is None or key not in got:
                fails += 1
                print("FAIL gazetteer_key(%r) -> %r  (key %r must still resolve)"
                      % (ctx % key, got, key))
                break

    # 2. Every amenity key matches its own name whole-word, and its plural.
    facility_keys = sorted({k for spots in amen.values() for k in spots})
    for key in facility_keys:
        if not sg._facility_pattern(key).search(key):
            fails += 1
            print("FAIL _facility_pattern(%r) does not match its own name" % key)
        if not key.endswith("s") and not sg._facility_pattern(key).search(key + "s"):
            fails += 1
            print("FAIL _facility_pattern(%r) does not match its plural" % key)

    # 3. No amenity key is another key plus "s" — that would make the plural ambiguous.
    kset = set(facility_keys)
    for key in facility_keys:
        if key.endswith("s") and key[:-1] in kset:
            fails += 1
            print("FAIL amenity keys %r and %r collide under plural tolerance" % (key[:-1], key))

    total = len(gaz) + len(facility_keys) * 2 + len(facility_keys)
    print("gazetteer keys: %d   amenity keys: %d" % (len(gaz), len(facility_keys)))
    print("%d checks, %d failed" % (total, fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
