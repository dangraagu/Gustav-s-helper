#!/usr/bin/env python3
"""
Build one or more guides from raw extraction JSON (tools/data/raw/<id>.json) by running the SAME
enrichers as the ironman.guide scraper (skill/quest/item+total-needed, coords, QH NPC/object refs).

Raw schema:  { "id","name","source","license", "sections":[ {"section","prefix","steps":[{"name","loc"}]} ] }

Usage:  py -3 tools/build_raw_guide.py            # build every raw/*.json (except *_SKIP)
        py -3 tools/build_raw_guide.py <id> ...   # build only these ids
"""
import json
import re
import sys
from pathlib import Path

import scrape_guide as sg

RAW_DIR = Path(__file__).parent / "data" / "raw"

# "Inventory check:" / "Equipment check" with nothing after it — a section header the source guide emits
# before the real list. Carries no action and no items, so it is not shipped as a step.
HEADER_ONLY_RE = re.compile(r"^\s*(?:inventory|inv|equipment|gear)\s*check\s*[:.\s]*$", re.IGNORECASE)


def load_manual_conditions():
    """guide id -> { step id -> "manual" | {complete, item} }. A human override (like manual_coords.json)
    that beats the enricher for a specific built step without touching the shared detectors, so it can
    never ripple onto another guide. "manual" drops the auto completion+highlight; the object form
    replaces them."""
    p = Path(__file__).parent / "data" / "manual_conditions.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[!] could not read manual_conditions.json ({e})", file=sys.stderr)
        return {}
    return {gid: steps for gid, steps in data.items()
            if not gid.startswith("_") and isinstance(steps, dict)}


def apply_override(step, ov):
    """Replace a built step's completion/highlight from the manual_conditions override. Returns True
    if it changed the step. World/coord is left untouched (that is manual_coords.json's job)."""
    if ov == "manual":
        for k in ("complete", "note", "item"):
            step.pop(k, None)
        step["manual"] = True
        return True
    if isinstance(ov, dict):
        changed = False
        if "complete" in ov:
            step["complete"] = ov["complete"]
            step.pop("manual", None)
            step.pop("note", None)
            changed = True
        if "item" in ov:
            step["item"] = ov["item"]
            changed = True
        # Human-grounded coordinate / highlight override (from the NPC-id sweep). Beats the enricher.
        if "world" in ov:
            w = ov["world"]
            step["world"] = [int(w[0]), int(w[1]), int(w[2]) if len(w) > 2 else 0]
            changed = True
        if "npc" in ov:
            step["npc"] = int(ov["npc"])
            step.pop("npcs", None)
            changed = True
        if "npcs" in ov:
            step["npcs"] = [int(i) for i in ov["npcs"]]
            step.pop("npc", None)
            changed = True
        if "object" in ov:
            step["object"] = int(ov["object"])
            changed = True
        return changed
    return False


def build(raw_path, item_map, quest_map, entities, overrides=None):
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    gid, name, source = raw["id"], raw.get("name", raw["id"]), raw.get("source", "")
    guide_ov = (overrides or {}).get(gid, {})
    sections = raw.get("sections", [])
    out_dir = sg._RES / "data" / "guides" / gid
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()  # wipe stale section files so a renamed/removed section never lingers

    # Pass 1: total items needed (same skill>quest>item precedence + same atom split as build_step).
    total_needed = sg.total_item_needs(
        (st.get("name") or "" for sec in sections for st in sec.get("steps", [])),
        item_map, quest_map)

    # Pass 2: build (running cumulative per item + route-position anchor across the whole guide).
    cumulative = {}
    anchor = None
    index = {"_comment": f"Auto-generated from raw/{gid}.json by build_raw_guide.py", "sections": []}
    total = enr = forced = 0
    for i, sec in enumerate(sections, 1):
        prefix = sec.get("prefix") or f"s{i}"
        steps = []
        for pos, st in enumerate(sec.get("steps", []), 1):
            nm = st.get("name") or ""
            if not nm:
                continue
            # A bare "Inventory check:" header (the item list lives in the NEXT raw step) is a step with
            # nothing to do — drop it instead of making the player tick an empty checklist. Skipped INSIDE
            # the enumerate loop so the surviving steps keep their original position ids (overrides in
            # manual_conditions.json are keyed by step id and must not shift).
            if HEADER_ONLY_RE.match(nm):
                continue
            atoms = sg.split_atoms(nm)
            for ai, atom in enumerate(atoms):  # NOT 'i' — that's the section index used for the filename
                sub = None if len(atoms) == 1 else (chr(97 + ai) if ai < 26 else str(ai))
                built = sg.build_step(prefix, pos, atom, st.get("loc"), None,
                                      item_map, quest_map, cumulative, total_needed, entities,
                                      sub=sub, anchor=anchor)
                ov = guide_ov.get(built["id"])
                if ov is not None and apply_override(built, ov):
                    forced += 1
                steps.append(built)
                if "world" in built:
                    anchor = built["world"]  # route continuity: the next step resolves near here
        sg.fill_craft_gaps(steps)
        sg.fill_location_gaps(steps)
        if not steps:
            continue
        total += len(steps)
        enr += sum(1 for s in steps if "npc" in s or "object" in s)
        fname = f"{i:02d}-{prefix}.json"
        (out_dir / fname).write_text(json.dumps(
            {"_source": source, "_license": raw.get("license", ""), "section": sec.get("section", prefix),
             "steps": steps}, indent=2, ensure_ascii=False), encoding="utf-8")
        index["sections"].append(fname)
    (out_dir / "route-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    extra = f", {forced} overridden" if forced else ""
    if guide_ov and forced != len(guide_ov):
        print(f"  [!] {gid}: manual_conditions listed {len(guide_ov)} id(s) but matched {forced} "
              f"(stale override? ids may have shifted after a re-scrape)", file=sys.stderr)
    print(f"  {gid:24s} {total:5d} steps, {len(index['sections'])} sections, {enr} precise targets{extra} -> {out_dir.name}")


def main():
    ids = sys.argv[1:]
    files = [RAW_DIR / f"{i}.json" for i in ids] if ids else sorted(RAW_DIR.glob("*.json"))
    files = [f for f in files if f.exists() and not f.stem.endswith("_SKIP")]
    if not files:
        print("no raw guide files to build", file=sys.stderr)
        return
    print("loading shared enricher data ...")
    item_map = sg.fetch_item_map()
    enr = sg.load_all_enrichers(item_map)
    quest_map = enr["quest_map"]
    entities = enr["entities"]
    print(f"  ({enr['nqs']} quest-start tiles, {len(sg.GAZETTEER)} locations, {enr['nam']} town amenities, "
          f"{enr['nres']} resource sites bridged)")
    overrides = load_manual_conditions()
    for f in files:
        build(f, item_map, quest_map, entities, overrides)


if __name__ == "__main__":
    main()
