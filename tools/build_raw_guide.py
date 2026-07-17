#!/usr/bin/env python3
"""
Build one or more guides from raw extraction JSON (tools/data/raw/<id>.json) by running the SAME
enrichers as the ironman.guide scraper (skill/quest/item+total-needed, coords, QH NPC/object refs).

Raw schema:  { "id","name","source","license", "sections":[ {"section","prefix","steps":[{"name","loc"}]} ] }

Usage:  py -3 tools/build_raw_guide.py            # build every raw/*.json (except *_SKIP)
        py -3 tools/build_raw_guide.py <id> ...   # build only these ids
"""
import json
import sys
from pathlib import Path

import scrape_guide as sg

RAW_DIR = Path(__file__).parent / "data" / "raw"


def build(raw_path, item_map, quest_map, entities):
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    gid, name, source = raw["id"], raw.get("name", raw["id"]), raw.get("source", "")
    sections = raw.get("sections", [])
    out_dir = sg._RES / "data" / "guides" / gid
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()  # wipe stale section files so a renamed/removed section never lingers

    # Pass 1: total items needed (same skill>quest>item precedence + same atom split as build_step).
    total_needed = {}
    for sec in sections:
        for st in sec.get("steps", []):
            for atom in sg.split_atoms(st.get("name") or ""):
                if sg.detect_skill(atom) or sg.detect_quest(atom, quest_map):
                    continue
                iq = sg.detect_item_id_qty(atom, item_map)
                if iq:
                    total_needed[iq[0]] = total_needed.get(iq[0], 0) + iq[1]

    # Pass 2: build (running cumulative per item + route-position anchor across the whole guide).
    cumulative = {}
    anchor = None
    index = {"_comment": f"Auto-generated from raw/{gid}.json by build_raw_guide.py", "sections": []}
    total = enr = 0
    for i, sec in enumerate(sections, 1):
        prefix = sec.get("prefix") or f"s{i}"
        steps = []
        for pos, st in enumerate(sec.get("steps", []), 1):
            nm = st.get("name") or ""
            if not nm:
                continue
            atoms = sg.split_atoms(nm)
            for ai, atom in enumerate(atoms):  # NOT 'i' — that's the section index used for the filename
                sub = None if len(atoms) == 1 else (chr(97 + ai) if ai < 26 else str(ai))
                built = sg.build_step(prefix, pos, atom, st.get("loc"), None,
                                      item_map, quest_map, cumulative, total_needed, entities,
                                      sub=sub, anchor=anchor)
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
    print(f"  {gid:24s} {total:5d} steps, {len(index['sections'])} sections, {enr} precise targets -> {out_dir.name}")


def main():
    ids = sys.argv[1:]
    files = [RAW_DIR / f"{i}.json" for i in ids] if ids else sorted(RAW_DIR.glob("*.json"))
    files = [f for f in files if f.exists() and not f.stem.endswith("_SKIP")]
    if not files:
        print("no raw guide files to build", file=sys.stderr)
        return
    print("loading shared enricher data ...")
    item_map = sg.fetch_item_map()
    sg.build_item_index(item_map)
    sg.load_item_aliases()
    sg.load_shop_stock()
    quest_map = sg.load_quest_map()
    sg.load_location_coords()
    nqs = sg.load_quest_start(quest_map)
    nam = sg.load_amenities()
    nres = sg.load_resources()
    sg.load_manual()
    sg.load_qh_steps()
    sg.load_skill_methods()
    entities = sg.load_qh_entities()
    print(f"  ({nqs} quest-start tiles, {len(sg.GAZETTEER)} locations, {nam} town amenities, "
          f"{nres} resource sites bridged)")
    for f in files:
        build(f, item_map, quest_map, entities)


if __name__ == "__main__":
    main()
