#!/usr/bin/env python3
"""
qh_extract.py — Extract a reusable NPC / object reference table from the
Quest Helper source tree.

Output: qh_entities.json  (two maps keyed by lowercased human name)
    {
      "npcs":    { "duke horacio": {"id": 3210, "world": [3210,3222,1]}, ... },
      "objects": { "bank booth":   {"id": 10083, "world": [x,y,z]}, ... }
    }

The <npcId>/<objectId> in Quest Helper are RuneLite gameval constants
(net.runelite.api.gameval.NpcID / ObjectID), e.g. NpcID.DUKE_HORACIO, or a bare
numeric literal. We resolve constant -> int using the gameval id tables, and we
reverse-resolve bare integers -> a canonical constant name (so numeric-literal
steps still get a human name).

This is factual game data (entity name -> id + coordinates), not QH code.
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Paths (all absolute; overridable via argv)
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))

QH_ROOT = r"C:\Users\bahs_admin\AppData\Local\Temp\claude\C--Users-bahs-admin\1d0da643-2e93-4c42-9a8f-b30452ec9830\scratchpad\quest-helper"
QH_HELPERS = os.path.join(QH_ROOT, "src", "main", "java", "com", "questhelper", "helpers")

SCRATCH = r"C:\Users\BAHS_A~1\AppData\Local\Temp\claude\C--Users-bahs-admin\1d0da643-2e93-4c42-9a8f-b30452ec9830\scratchpad"
NPCID_JAVA = os.path.join(SCRATCH, "NpcID.java")
OBJECTID_JAVA = os.path.join(SCRATCH, "ObjectID.java")
# Quest Helper's own supplementary object-id class (aliases into gameval ObjectID)
QH_OBJECTID_JAVA = os.path.join(QH_ROOT, "src", "main", "java", "com", "questhelper", "util", "QHObjectID.java")

OUT_JSON = os.path.join(HERE, "qh_entities.json")

# ---------------------------------------------------------------------------
# gameval id-table parsing:  public static final int NAME = 1234;
# ---------------------------------------------------------------------------
CONST_RE = re.compile(r"public\s+static\s+final\s+int\s+(\w+)\s*=\s*(-?\d+)\s*;")


def load_gameval(path):
    """Return (name->int, int->first_name) from a gameval id table."""
    name_to_id = {}
    id_to_name = {}
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    for m in CONST_RE.finditer(text):
        name, val = m.group(1), int(m.group(2))
        name_to_id[name] = val
        # keep the FIRST (top-most declared) constant name for a given int
        if val not in id_to_name:
            id_to_name[val] = name
    return name_to_id, id_to_name


QH_ALIAS_RE = re.compile(
    r"public\s+static\s+final\s+int\s+(\w+)\s*=\s*(?:ObjectID\.(\w+)|(-?\d+))\s*;"
)


def load_qh_objectid(path, obj_name_to_id):
    """QHObjectID.NAME = ObjectID.OTHER | <int>  ->  {name: int}."""
    alias = {}
    if not os.path.exists(path):
        return alias
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    for m in QH_ALIAS_RE.finditer(text):
        name, ref, lit = m.group(1), m.group(2), m.group(3)
        if lit is not None:
            alias[name] = int(lit)
        elif ref in obj_name_to_id:
            alias[name] = obj_name_to_id[ref]
    return alias


def humanize(const_name):
    """NpcID.DUKE_HORACIO -> 'duke horacio'."""
    return const_name.replace("_", " ").strip().lower()


# ---------------------------------------------------------------------------
# Quest-step regexes.
#   questHelper arg = [^,()]+  (usually `this`)
#   id             = NpcID.NAME | ObjectID.NAME | bare int | some variable
#   optional String (npcName) may sit between the id and the WorldPoint
#   WorldPoint(x, y, plane) literal required (that's our coordinate source)
# \s matches newlines, so multi-line constructions are handled.
# ---------------------------------------------------------------------------
NPC_RE = re.compile(
    r"new\s+NpcStep\s*\(\s*[^,()]+,\s*"
    r"([A-Za-z0-9_.]+)\s*,\s*"
    r'(?:"[^"]*"\s*,\s*)?'
    r"new\s+WorldPoint\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
)
OBJ_RE = re.compile(
    r"new\s+ObjectStep\s*\(\s*[^,()]+,\s*"
    r"([A-Za-z0-9_.]+)\s*,\s*"
    r'(?:"[^"]*"\s*,\s*)?'
    r"new\s+WorldPoint\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
)
# Bare "new NpcStep(" / "new ObjectStep(" occurrences (for totals)
NPC_ANY = re.compile(r"new\s+NpcStep\s*\(")
OBJ_ANY = re.compile(r"new\s+ObjectStep\s*\(")
# DetailedQuestStep with a WorldPoint but no id (location only) — counted, not keyed
DETAIL_RE = re.compile(
    r"new\s+DetailedQuestStep\s*\(\s*[^,()]+,\s*"
    r"new\s+WorldPoint\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
)


def iter_java_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if name.endswith(".java"):
                yield os.path.join(dirpath, name)


def resolve_id(prefix, token, name_to_id, id_to_name, qh_alias=None):
    """
    Return (id:int, human_name:str, how:str) or None if unresolvable.
    prefix = 'NpcID' or 'ObjectID' (the expected constant namespace).
    how in {'constant', 'qh-alias', 'numeric-reverse'}.
    """
    if qh_alias and token.startswith("QHObjectID."):
        const = token.split(".", 1)[1]
        if const in qh_alias:
            return qh_alias[const], humanize(const), "qh-alias"
        return None
    if token.startswith(prefix + "."):
        const = token.split(".", 1)[1]
        if const in name_to_id:
            return name_to_id[const], humanize(const), "constant"
        return None  # unresolved constant name
    if token.lstrip("-").isdigit():
        val = int(token)
        if val in id_to_name:
            return val, humanize(id_to_name[val]), "numeric-reverse"
        return None  # numeric id not present in gameval table
    return None  # a variable / expression we can't resolve statically


def extract(kind, regex, name_to_id, id_to_name, files, stats, qh_alias=None):
    prefix = "NpcID" if kind == "npcs" else "ObjectID"
    out = {}
    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for m in regex.finditer(text):
            token = m.group(1)
            x, y, z = int(m.group(2)), int(m.group(3)), int(m.group(4))
            r = resolve_id(prefix, token, name_to_id, id_to_name, qh_alias)
            if r is None:
                stats[kind]["unresolved"] += 1
                continue
            ent_id, human, how = r
            stats[kind][how] += 1
            if human in out:
                stats[kind]["dup_dropped"] += 1
                continue  # keep FIRST occurrence
            out[human] = {"id": ent_id, "world": [x, y, z]}
    return out


def main():
    npc_name_to_id, npc_id_to_name = load_gameval(NPCID_JAVA)
    obj_name_to_id, obj_id_to_name = load_gameval(OBJECTID_JAVA)

    files = list(iter_java_files(QH_HELPERS))

    # Totals for the report
    tot_npc = tot_obj = tot_detail = 0
    npc_wp = obj_wp = 0
    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        tot_npc += len(NPC_ANY.findall(text))
        tot_obj += len(OBJ_ANY.findall(text))
        tot_detail += len(DETAIL_RE.findall(text))
        npc_wp += len(NPC_RE.findall(text))
        obj_wp += len(OBJ_RE.findall(text))

    qh_alias = load_qh_objectid(QH_OBJECTID_JAVA, obj_name_to_id)

    stats = {
        "npcs": {"constant": 0, "qh-alias": 0, "numeric-reverse": 0, "unresolved": 0, "dup_dropped": 0},
        "objects": {"constant": 0, "qh-alias": 0, "numeric-reverse": 0, "unresolved": 0, "dup_dropped": 0},
    }

    npcs = extract("npcs", NPC_RE, npc_name_to_id, npc_id_to_name, files, stats)
    objects = extract("objects", OBJ_RE, obj_name_to_id, obj_id_to_name, files, stats, qh_alias)

    data = {"npcs": dict(sorted(npcs.items())), "objects": dict(sorted(objects.items()))}
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)

    # ---- report to stderr so stdout stays clean if piped ----
    def p(*a):
        print(*a, file=sys.stderr)

    p(f"Java files scanned: {len(files)}")
    p(f"gameval NpcID constants: {len(npc_name_to_id)}  ObjectID constants: {len(obj_name_to_id)}")
    p("")
    p(f"NpcStep total constructions:    {tot_npc}")
    p(f"  with inline id + WorldPoint:  {npc_wp}")
    p(f"  -> resolved via constant:     {stats['npcs']['constant']}")
    p(f"  -> resolved via numeric:      {stats['npcs']['numeric-reverse']}")
    p(f"  -> unresolved id (skipped):   {stats['npcs']['unresolved']}")
    p(f"  -> duplicate name dropped:    {stats['npcs']['dup_dropped']}")
    p(f"  DISTINCT npcs written:        {len(npcs)}")
    p("")
    p(f"ObjectStep total constructions: {tot_obj}")
    p(f"  with inline id + WorldPoint:  {obj_wp}")
    p(f"  -> resolved via constant:     {stats['objects']['constant']}")
    p(f"  -> resolved via QHObjectID:   {stats['objects']['qh-alias']}")
    p(f"  -> resolved via numeric:      {stats['objects']['numeric-reverse']}")
    p(f"  -> unresolved id (skipped):   {stats['objects']['unresolved']}")
    p(f"  -> duplicate name dropped:    {stats['objects']['dup_dropped']}")
    p(f"  DISTINCT objects written:     {len(objects)}")
    p("")
    p(f"DetailedQuestStep w/ WorldPoint (location-only, no id, NOT keyed): {tot_detail}")
    p("")
    p(f"NpcStep no inline id+WorldPoint (array id / WP variable / no coords): {tot_npc - npc_wp}")
    p(f"ObjectStep no inline id+WorldPoint: {tot_obj - obj_wp}")
    p(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
