#!/usr/bin/env python3
"""
qh_extract.py — Extract a reusable NPC / object reference table from the
Quest Helper source tree.

Output: qh_entities.json  (two maps keyed by lowercased human name)
    {
      "npcs":    { "duke horacio": {"id": 3210, "world": [3210,3222,1]}, ... },
      "objects": { "bank booth":   {"id": 10083, "world": [x,y,z]}, ... }
    }

Two kinds of keys are produced and MERGED into the same maps:

  1. gameval-codename keys — humanised RuneLite constant names
     (NpcID.DUKE_HORACIO -> "duke horacio"). These rarely match how a guide
     actually *words* an entity.

  2. display-name keys (added 2026-07-15) — the name a Quest Helper step
     SPEAKS in its description text. Every NpcStep(...) / ObjectStep(...) carries
     a String description ("Talk to Duke Horacio.", "Speak to Wizard Mizgog").
     We lift the proper-noun phrase out of that text and pair it with the SAME
     step's id + WorldPoint. This is the key that matches a guide's prose
     ("Duke Horacio" -> the tile), which the codename form ("duke of lumbridge")
     usually misses.

The <npcId>/<objectId> in Quest Helper are RuneLite gameval constants
(net.runelite.api.gameval.NpcID / ObjectID), e.g. NpcID.DUKE_HORACIO, or a bare
numeric literal. We resolve constant -> int using the gameval id tables, and we
reverse-resolve bare integers -> a canonical constant name (so numeric-literal
steps still get a human name).

Merge precedence (first wins, never overwrite):
    existing qh_entities.json  >  fresh codename keys  >  display-name keys
so re-running is idempotent and existing keys (incl. hand edits) are preserved.

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
# Display-name extraction from a step's description text.
#
#   "Talk to Duke Horacio."          -> "duke horacio"
#   "Speak to Wizard Mizgog"         -> "wizard mizgog"
#   "Give the Cook in Lumbridge ..." -> "cook"
#   "Use some shears on Unferth ..." -> "unferth"
#   "Kill a giant rat"               -> None   (lowercase / generic)
#
# Strategy: keep only the FIRST sentence; strip a leading interaction-verb /
# particle run; then take the leading run of Capitalised words (allowing inner
# connectors like "of"). A capitalised CONTENT word after position 0 is never
# stripped even if it doubles as a verb ("Give the Cook" -> Cook, not the town).
# A name is accepted only if a leading verb was actually consumed, which rejects
# sentence-initial verbs we don't know ("Destroy ...", "Shake ...").
# ---------------------------------------------------------------------------
VERBS = set("""
talk speak go walk head travel run continue follow meet find catch kill attack
pickpocket fight lure defeat search open close enter exit leave climb pick fill
operate give milk collect grab take get board read pray steal trade buy purchase
sell mine chop cut light cook drop wield equip wear drink eat plant dig examine
inspect check push pull turn ring cross ride bring deliver hand show ask tell
report approach visit reach touch activate investigate look order repair craft
smith build burn bank teleport retrieve pass unlock loot offer jump put place
pay attempt keep prepare complete make add fish try enable return cast use
destroy shake peer browse either disable avoid protect navigate spin smelt net
trap grapple slash squeeze swim throw wait kick wave blow pour mix water rake
harvest hunt smash remove hold click select choose sail fly dive descend ascend
hop hide sneak distract free rescue escort heal feed tag mark discover uncover
reveal deposit withdraw pickup strike stand step move
""".split())

# Pure glue words: stripped after position 0 even when capitalised (they are
# never an entity name on their own).
PARTICLES = set("""
to at on the a an your some from into up down back in and then off out over
through toward towards near next another again all this that both
""".split())

# Words allowed INSIDE a proper-noun phrase, between two capitalised words.
CONNECTORS = {"of", "de", "del", "la", "le", "von", "van"}

# Single-word captures that are too generic to be a reliable entity key.
GENERIC_SKIP = set("""
green general both either other some many more most next first second third
final last main upper lower north south east west nearby around inside outside
here there giant large small
""".split())

SENT_END = re.compile(r"[.!?\n]")
_CAP_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*$")


def _is_cap(tok):
    return bool(_CAP_RE.match(tok)) and tok[0].isupper()


def extract_display_name(desc):
    """Lift the entity's display name from a step description, or return None."""
    if not desc:
        return None
    s = desc.strip()
    m = SENT_END.search(s)
    if m:
        s = s[:m.start()]          # first sentence only
    verb_consumed = False
    low = s.lower()
    # "use/cast ... on X" -> the entity is what follows the last ' on '
    if low.startswith(("use ", "cast ")) and " on " in low:
        s = s[low.rfind(" on ") + 4:]
        verb_consumed = True
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]*", s)
    i = 0
    while i < len(toks):
        t = toks[i]
        tl = t.lower()
        if i == 0:
            if tl in VERBS or tl in PARTICLES:
                i += 1
                continue
            break
        # after position 0: only strip pure particles, or a LOWERCASE verb.
        if tl in PARTICLES:
            i += 1
            continue
        if (not t[0].isupper()) and tl in VERBS:
            i += 1
            continue
        break
    if i > 0:
        verb_consumed = True
    toks = toks[i:]
    if not toks or not verb_consumed:
        return None
    name = []
    j = 0
    while j < len(toks):
        t = toks[j]
        if _is_cap(t):
            name.append(t)
            j += 1
        elif t.lower() in CONNECTORS and j + 1 < len(toks) and _is_cap(toks[j + 1]):
            name.append(t)
            j += 1
        else:
            break
    while name and name[-1].lower() in CONNECTORS:
        name.pop()
    if not name:
        return None
    phrase = " ".join(name).lower().strip()
    if phrase.endswith("'s"):
        phrase = phrase[:-2].strip()
    if len(phrase) < 4:
        return None
    if len(name) == 1 and phrase in GENERIC_SKIP:
        return None
    return phrase


# ---------------------------------------------------------------------------
# Quest-step regexes.
#   questHelper arg = [^,()]+  (usually `this`)
#   id             = NpcID.NAME | ObjectID.NAME | bare int | some variable
#   optional String (npcName) may sit between the id and the WorldPoint
#   WorldPoint(x, y, plane) literal required (that's our coordinate source)
#   optional String (description text) may follow the WorldPoint -> group 5
# \s matches newlines, so multi-line constructions are handled.
# ---------------------------------------------------------------------------
NPC_RE = re.compile(
    r"new\s+NpcStep\s*\(\s*[^,()]+,\s*"
    r"([A-Za-z0-9_.]+)\s*,\s*"
    r'(?:"[^"]*"\s*,\s*)?'
    r"new\s+WorldPoint\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
    r'(?:\s*,\s*"((?:[^"\\]|\\.)*)")?'
)
OBJ_RE = re.compile(
    r"new\s+ObjectStep\s*\(\s*[^,()]+,\s*"
    r"([A-Za-z0-9_.]+)\s*,\s*"
    r'(?:"[^"]*"\s*,\s*)?'
    r"new\s+WorldPoint\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
    r'(?:\s*,\s*"((?:[^"\\]|\\.)*)")?'
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
    """
    Return (codename_map, display_map):
      codename_map = { humanised-constant-name: {"id", "world"} }
      display_map  = { spoken-display-name:     {"id", "world"} }
    Both keyed off the SAME resolved step (id + WorldPoint). First occurrence
    wins in each map.
    """
    prefix = "NpcID" if kind == "npcs" else "ObjectID"
    out = {}
    disp = {}
    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for m in regex.finditer(text):
            token = m.group(1)
            x, y, z = int(m.group(2)), int(m.group(3)), int(m.group(4))
            desc = m.group(5)
            r = resolve_id(prefix, token, name_to_id, id_to_name, qh_alias)
            if r is None:
                stats[kind]["unresolved"] += 1
                continue
            ent_id, human, how = r
            stats[kind][how] += 1
            entry = {"id": ent_id, "world": [x, y, z]}
            if human in out:
                stats[kind]["dup_dropped"] += 1
            else:
                out[human] = entry
            # display-name pass: pair the spoken name with this step's id+coords
            name = extract_display_name(desc)
            if name:
                stats[kind]["display_seen"] += 1
                if name not in disp:
                    disp[name] = entry
                else:
                    stats[kind]["display_dup"] += 1
    return out, disp


def merge_first_wins(existing, codenames, display):
    """existing > codenames > display; never overwrite. Return (merged, n_added_display)."""
    merged = {}
    merged.update(existing)                     # preserve on-disk keys (+ hand edits)
    for k, v in codenames.items():
        merged.setdefault(k, v)
    added = 0
    for k, v in display.items():
        if k not in merged:
            merged[k] = v
            added += 1
    return merged, added


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
        "npcs": {"constant": 0, "qh-alias": 0, "numeric-reverse": 0, "unresolved": 0,
                 "dup_dropped": 0, "display_seen": 0, "display_dup": 0},
        "objects": {"constant": 0, "qh-alias": 0, "numeric-reverse": 0, "unresolved": 0,
                    "dup_dropped": 0, "display_seen": 0, "display_dup": 0},
    }

    npcs, npcs_disp = extract("npcs", NPC_RE, npc_name_to_id, npc_id_to_name, files, stats)
    objects, objs_disp = extract("objects", OBJ_RE, obj_name_to_id, obj_id_to_name, files, stats, qh_alias)

    # ---- merge: existing file (if present) > codenames > display names ----
    existing = {"npcs": {}, "objects": {}}
    if os.path.exists(OUT_JSON):
        try:
            with open(OUT_JSON, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        except Exception:
            existing = {"npcs": {}, "objects": {}}

    merged_npcs, added_npc = merge_first_wins(existing.get("npcs", {}), npcs, npcs_disp)
    merged_objs, added_obj = merge_first_wins(existing.get("objects", {}), objects, objs_disp)

    data = {
        "npcs": dict(sorted(merged_npcs.items())),
        "objects": dict(sorted(merged_objs.items())),
    }
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
    p(f"  -> duplicate codename dropped:{stats['npcs']['dup_dropped']}")
    p(f"  DISTINCT npc codenames:       {len(npcs)}")
    p(f"  display-names lifted (seen):  {stats['npcs']['display_seen']} (dup {stats['npcs']['display_dup']})")
    p(f"  DISTINCT npc display-names:   {len(npcs_disp)}")
    p(f"  NEW npc display keys added:   {added_npc}")
    p("")
    p(f"ObjectStep total constructions: {tot_obj}")
    p(f"  with inline id + WorldPoint:  {obj_wp}")
    p(f"  -> resolved via constant:     {stats['objects']['constant']}")
    p(f"  -> resolved via QHObjectID:   {stats['objects']['qh-alias']}")
    p(f"  -> resolved via numeric:      {stats['objects']['numeric-reverse']}")
    p(f"  -> unresolved id (skipped):   {stats['objects']['unresolved']}")
    p(f"  -> duplicate codename dropped:{stats['objects']['dup_dropped']}")
    p(f"  DISTINCT object codenames:    {len(objects)}")
    p(f"  display-names lifted (seen):  {stats['objects']['display_seen']} (dup {stats['objects']['display_dup']})")
    p(f"  DISTINCT object display-names:{len(objs_disp)}")
    p(f"  NEW object display keys added:{added_obj}")
    p("")
    p(f"DetailedQuestStep w/ WorldPoint (location-only, no id, NOT keyed): {tot_detail}")
    p("")
    p(f"FINAL merged npc keys:    {len(merged_npcs)}")
    p(f"FINAL merged object keys: {len(merged_objs)}")
    p(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
