#!/usr/bin/env python3
"""
qh_start_coords.py -- Extract a "where do I go to START this quest" coordinate
for each Quest Helper quest, keyed by the quest's DISPLAY name.

For each real-quest helper class referenced by QuestHelperQuest.java, we take the
WorldPoint of the quest's FIRST actionable step -- i.e. the first step-constructor
(NpcStep / ObjectStep / DetailedQuestStep / ItemStep / ...) in the helper source
that carries an inline `new WorldPoint(x, y, plane)`. Step constructors only appear
in setupSteps()/loadSteps(), AFTER setupZones()/setupRequirements(), so Zone-corner
and requirement WorldPoints are naturally skipped. The first such step is the
"talk to X / go to Y to start" step QH routes the player to first.

Display name resolution (per QuestHelperQuest enum entry):
  * first String literal in the entry  -> use it   (e.g. "RFD - Dwarf",
    "Shield of Arrav - Phoenix Gang", "Animal Magnetism")
  * else the `Quest.XXX` reference      -> net.runelite.api.Quest display name
    (e.g. Quest.COOKS_ASSISTANT -> "Cook's Assistant")

Scope: only entries that reference `Quest.` (real quests, miniquests, and the
RFD / Shield-of-Arrav sub-quests). Achievement diaries, balloon transports,
skills, and misc GENERIC helpers have no `Quest.` reference and are excluded.

Output: quest_start_coords.json = { "<display name>": [x, y, plane], ... }
This is factual game data (start coordinates), not QH code.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

QH_ROOT = r"C:\Users\bahs_admin\AppData\Local\Temp\claude\C--Users-bahs-admin\1d0da643-2e93-4c42-9a8f-b30452ec9830\scratchpad\quest-helper"
QH_JAVA_ROOT = os.path.join(QH_ROOT, "src", "main", "java", "com", "questhelper")
QH_HELPERS = os.path.join(QH_JAVA_ROOT, "helpers")
QHQ = os.path.join(QH_JAVA_ROOT, "questinfo", "QuestHelperQuest.java")

QUEST_JAVA = os.path.join(HERE, "Quest.java")
OUT_JSON = os.path.join(HERE, "quest_start_coords.json")

# ---------------------------------------------------------------------------
# net.runelite.api.Quest : CONST(id, "Display Name")
# ---------------------------------------------------------------------------
QUEST_RE = re.compile(r'^\s*([A-Z][A-Z0-9_]*)\s*\(\s*-?\d+\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)', re.M)


def load_quest_display():
    with open(QUEST_JAVA, "r", encoding="utf-8") as fh:
        text = fh.read()
    out = {}
    for m in QUEST_RE.finditer(text):
        out[m.group(1)] = m.group(2)
    return out


# ---------------------------------------------------------------------------
# Index every .java under com/questhelper : ClassName -> path
# ---------------------------------------------------------------------------
def build_class_index(root):
    idx = {}
    dupes = {}
    for dirpath, _d, files in os.walk(root):
        for name in files:
            if name.endswith(".java"):
                cls = name[:-5]
                p = os.path.join(dirpath, name)
                if cls in idx:
                    dupes.setdefault(cls, [idx[cls]]).append(p)
                else:
                    idx[cls] = p
    return idx, dupes


# ---------------------------------------------------------------------------
# Parse QuestHelperQuest enum entries.
# ---------------------------------------------------------------------------
STRLIT = re.compile(r'"((?:[^"\\]|\\.)*)"')
QUEST_REF = re.compile(r'\bQuest\.([A-Z][A-Z0-9_]*)')  # matches Quest.X (not QuestVarbits/QuestDetails)
NEW_CLASS = re.compile(r'\bnew\s+([A-Z][A-Za-z0-9_]*)\s*\(\s*\)')
ENTRY_START = re.compile(r'^\t([A-Z][A-Z0-9_]*)\s*\(\s*new\s+([A-Z][A-Za-z0-9_]*)\s*\(\s*\)')


def parse_qhq_entries():
    """Return list of dicts: {enum, cls, entry_text, line}."""
    with open(QHQ, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    # Find enum body: from `enum QuestHelperQuest` line to the terminating ';'
    start = None
    for i, ln in enumerate(lines):
        if "enum QuestHelperQuest" in ln:
            start = i
            break
    entries = []
    cur = None
    i = start + 1
    while i < len(lines):
        ln = lines[i]
        # end of enum constants: a line that is exactly ';' (after last entry)
        m = ENTRY_START.match(ln)
        if m:
            if cur:
                entries.append(cur)
            cur = {"enum": m.group(1), "cls": m.group(2), "text": ln, "line": i + 1}
        elif cur is not None:
            # continuation line of the current entry, unless we've hit the field decls
            stripped = ln.strip()
            if stripped == ";" or stripped.startswith("private ") or stripped.startswith("@"):
                entries.append(cur)
                cur = None
                break
            cur["text"] += ln
        i += 1
    if cur:
        entries.append(cur)
    return entries


def resolve_display_name(entry, quest_display):
    text = entry["text"]
    # first string literal wins
    ms = STRLIT.search(text)
    if ms:
        return ms.group(1), "string-literal"
    mq = QUEST_REF.search(text)
    if mq:
        q = mq.group(1)
        if q in quest_display:
            return quest_display[q], "quest-enum"
        return None, "quest-unknown:" + q
    return None, "no-name"


def is_quest_entry(entry):
    return QUEST_REF.search(entry["text"]) is not None


# ---------------------------------------------------------------------------
# First-step WorldPoint extraction from a helper file.
# ---------------------------------------------------------------------------
STEP_CTOR = re.compile(r'\bnew\s+[A-Z][A-Za-z0-9_]*Step\s*\(')
WP_RE = re.compile(r'\bnew\s+WorldPoint\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*(?:,\s*(-?\d+)\s*)?\)')


def extract_balanced(text, open_paren_idx):
    """Given index of a '(', return the substring inside the matching ')',
    honoring string and char literals. Returns (inner, end_idx)."""
    depth = 0
    i = open_paren_idx
    n = len(text)
    start = open_paren_idx + 1
    while i < n:
        c = text[i]
        if c == '"' or c == "'":
            quote = c
            i += 1
            while i < n:
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return text[start:i], i
        i += 1
    return text[start:], n  # unbalanced fallback


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def first_step_worldpoint(path):
    """Return (x, y, plane, step_class, wp_line) or None."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    for m in STEP_CTOR.finditer(text):
        open_idx = m.end() - 1  # the '(' of the step ctor
        inner, end_idx = extract_balanced(text, open_idx)
        wp = WP_RE.search(inner)
        if wp:
            x = int(wp.group(1))
            y = int(wp.group(2))
            z = int(wp.group(3)) if wp.group(3) is not None else 0
            step_cls = m.group(0)[4:].strip().rstrip("(").strip()
            wp_line = line_of(text, open_idx + 1 + wp.start())
            return x, y, z, step_cls, wp_line
    return None


def sane(x, y, z):
    return 0 < x < 16000 and 0 < y < 16000 and 0 <= z <= 3


# ---------------------------------------------------------------------------
def main():
    quest_display = load_quest_display()
    class_idx, dupes = build_class_index(QH_JAVA_ROOT)
    entries = parse_qhq_entries()

    result = {}          # display name -> [x, y, z]
    provenance = {}      # display name -> (class, rel_path, wp_line, step_cls)
    skipped = []         # (display-or-enum, reason)
    non_quest = 0

    for e in entries:
        if not is_quest_entry(e):
            non_quest += 1
            continue
        disp, how = resolve_display_name(e, quest_display)
        if disp is None:
            skipped.append((e["enum"], "name-unresolved(%s)" % how))
            continue
        cls = e["cls"]
        path = class_idx.get(cls)
        if not path:
            skipped.append((disp, "helper-class-not-found:" + cls))
            continue
        fw = first_step_worldpoint(path)
        if fw is None:
            skipped.append((disp, "no-inline-worldpoint-step:" + cls))
            continue
        x, y, z, step_cls, wp_line = fw
        if not sane(x, y, z):
            skipped.append((disp, "insane-coord:%d,%d,%d" % (x, y, z)))
            continue
        if disp in result and result[disp] != [x, y, z]:
            # keep first; note conflict
            skipped.append((disp, "dup-display-name(kept first): also %s@%s" % (cls, wp_line)))
            continue
        result[disp] = [x, y, z]
        rel = os.path.relpath(path, QH_ROOT)
        provenance[disp] = (cls, rel.replace("\\", "/"), wp_line, step_cls)

    data = dict(sorted(result.items()))
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)

    def p(*a):
        print(*a, file=sys.stderr)

    p("Quest display names loaded:", len(quest_display))
    p("Helper classes indexed:", len(class_idx), "| dup basenames:", len(dupes))
    if dupes:
        for k, v in dupes.items():
            p("   DUP CLASS:", k, "->", v)
    p("QuestHelperQuest entries parsed:", len(entries))
    p("  non-quest entries skipped (no Quest. ref):", non_quest)
    p("  START COORDS extracted:", len(result))
    p("  SKIPPED (quest but unresolved):", len(skipped))
    for name, reason in skipped:
        p("     SKIP:", name, "->", reason)
    p("")
    p("Wrote", OUT_JSON)
    p("")
    p("=== 20 provenance examples ===")
    shown = 0
    for disp in sorted(provenance):
        cls, rel, wp_line, step_cls = provenance[disp]
        p('  "%s" -> %s   [%s  %s:%d]' % (disp, result[disp], step_cls, rel, wp_line))
        shown += 1
        if shown >= 20:
            break


if __name__ == "__main__":
    main()
