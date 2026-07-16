#!/usr/bin/env python3
r"""
qh_steps_extract.py -- deterministic extraction of Quest Helper guided steps
(step text + WorldPoint + npc/object ids) from QH source.

Pure stdlib. Rerunnable:
    py -3 qh_steps_extract.py <qh_src_root> <out_dir> [npcid_constants.txt] [objectid_constants.txt]

<qh_src_root> = ...\src\main\java\com\questhelper
Outputs qh_steps.json + provenance.txt into <out_dir>.

Extraction rules (never guess):
 - Only step constructions whose arg list contains a groundable WorldPoint:
   either an inline `new WorldPoint(x, y, z)` with pure int literals, or an
   identifier that is assigned exactly one distinct inline WorldPoint value
   anywhere in the same file.
 - Step text = the first string-literal argument APPEARING AFTER the
   WorldPoint argument (handles the NpcStep(this, id, npcName, wp, text)
   variant where npcName precedes the WorldPoint). Adjacent `"a" + "b"`
   literal concatenations are joined. Non-literal text -> step skipped.
 - npc/object id = arg at index 1 (after the QuestHelper arg) for
   NpcStep/MultiNpcStep/NpcEmoteStep/ObjectStep; resolved numerically via
   javap -constants dumps of net.runelite.api.gameval.{NpcID,ObjectID}
   (the only ID classes imported by helpers). Unresolvable symbol -> the
   symbol string is recorded instead. int[] arrays -> first element.
 - Quest key = RuneLite Quest constant from QuestHelperQuest.java when the
   constant maps to exactly ONE enum entry; otherwise the QH enum name.
 - Steps found in auxiliary .java files of a helper package are attributed
   to that package's quest only when the package hosts exactly one
   registered helper; otherwise they are skipped (counted in stderr).
"""
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

# ---------------------------------------------------------------- constants

# step classes taking (helper, WorldPoint, text, ...)
PLAIN_STEPS = {"DetailedQuestStep", "DigStep", "ItemStep", "SailStep",
               "TileStep", "EmoteStep"}
NPC_STEPS = {"NpcStep", "MultiNpcStep", "NpcEmoteStep", "NpcFollowerStep"}
OBJ_STEPS = {"ObjectStep"}
OTHER_ID_STEPS = {"WorldEntityStep"}     # id arg but neither npc nor object
ALL_STEPS = PLAIN_STEPS | NPC_STEPS | OBJ_STEPS | OTHER_ID_STEPS

CALL_RE = re.compile(
    r"(?:new\s+(" + "|".join(sorted(ALL_STEPS)) + r")\s*\("
    r"|(DigStep)\s*\.\s*withCustomSpadeRequirement\s*\()")

EXTENDS_RE = re.compile(r"\bclass\s+(\w+)\s+extends\s+(\w+)")

WP_INLINE_RE = re.compile(
    r"new\s+WorldPoint\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)")
WP_ASSIGN_RE = re.compile(
    r"\b([A-Za-z_$][\w$]*)\s*=\s*new\s+WorldPoint\s*\(\s*(-?\d+)\s*,"
    r"\s*(-?\d+)\s*,\s*(-?\d+)\s*\)")
STR_LIT_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
IDENT_RE = re.compile(r"^[A-Za-z_$][\w$]*$")

# ------------------------------------------------------------------ helpers


def strip_comments(src):
    """Remove // and /* */ comments, preserving string literals & newlines."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == '"':
                    break
                j += 1
            out.append(src[i:j + 1])
            i = j + 1
        elif c == "'":
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == "'":
                    break
                j += 1
            out.append(src[i:j + 1])
            i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            if j == -1:
                j = n
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append("\n" * src.count("\n", i, j))  # keep line numbers
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def find_close(src, open_idx):
    """Index of the ')' matching the '(' at open_idx, string-aware."""
    depth = 0
    i, n = open_idx, len(src)
    while i < n:
        c = src[i]
        if c == '"' or c == "'":
            q = c
            i += 1
            while i < n:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == q:
                    break
                i += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def split_args(argstr):
    """Split a call arg string on top-level commas, string-aware."""
    args, depth, cur, i, n = [], 0, [], 0, len(argstr)
    while i < n:
        c = argstr[i]
        if c == '"' or c == "'":
            q = c
            cur.append(c)
            i += 1
            while i < n:
                cur.append(argstr[i])
                if argstr[i] == '\\':
                    i += 1
                    if i < n:
                        cur.append(argstr[i])
                elif argstr[i] == q:
                    break
                i += 1
        elif c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            depth -= 1
            cur.append(c)
        elif c == ',' and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    if cur:
        args.append("".join(cur).strip())
    return args


def pure_string_literal(arg):
    """If arg is only string literal(s) joined by '+', return joined text."""
    rest = STR_LIT_RE.sub("\x00", arg)
    if re.fullmatch(r"[\x00+\s]+", rest) and "\x00" in rest:
        parts = STR_LIT_RE.findall(arg)
        return "".join(parts)
    return None


def unescape(s):
    return (s.replace(r'\"', '"').replace(r"\'", "'")
             .replace(r"\n", "\n").replace(r"\t", "\t").replace("\\\\", "\\"))


def load_constants(path):
    table = {}
    rx = re.compile(r"public static final int (\w+) = (-?\d+);")
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = rx.search(line)
            if m:
                table[m.group(1)] = int(m.group(2))
    return table


def resolve_id(arg, npc_tab, obj_tab, kind):
    """Resolve an id argument -> int, or symbol string, or None."""
    arg = arg.strip()
    if re.fullmatch(r"-?\d+", arg):
        return int(arg)
    # int array: new int[]{A, B, ...} -> first element
    m = re.match(r"new\s+int\s*\[\s*\]\s*\{(.*)\}\s*$", arg, re.S)
    if m:
        first = split_args(m.group(1))
        if not first:
            return None
        return resolve_id(first[0], npc_tab, obj_tab, kind)
    m = re.fullmatch(r"(NpcID|ObjectID|NullNpcID|NullObjectID)\s*\.\s*(\w+)", arg)
    if m:
        cls, name = m.groups()
        tab = npc_tab if "Npc" in cls else obj_tab
        if name in tab:
            return tab[name]
        return f"{cls}.{name}"
    return None  # expression / variable -> not groundable cheaply


# ----------------------------------------------------- QuestHelperQuest map


def build_quest_map(qh_root):
    """helper FQCN -> quest key; also package -> [keys]."""
    path = os.path.join(qh_root, "questinfo", "QuestHelperQuest.java")
    src = strip_comments(open(path, encoding="utf-8", errors="replace").read())
    imports = {}   # simple class name -> fqcn
    wildcard_pkgs = []
    for m in re.finditer(r"import\s+(com\.questhelper\.helpers\.[\w.]+?)(\.\*)?\s*;", src):
        fq, star = m.group(1), m.group(2)
        if star:
            wildcard_pkgs.append(fq)
        else:
            imports[fq.rsplit(".", 1)[1]] = fq

    def resolve_class(cls):
        if cls in imports:
            return imports[cls]
        for pkg in wildcard_pkgs:
            rel = pkg[len("com.questhelper."):].replace(".", os.sep)
            if os.path.isfile(os.path.join(qh_root, rel, cls + ".java")):
                return pkg + "." + cls
        return None
    entries = []   # (enum_name, helper_class, quest_const or None)
    entry_rx = re.compile(r"^\s*([A-Z0-9_]+)\s*\(\s*new\s+(\w+)\s*\(", re.M)
    for m in entry_rx.finditer(src):
        enum_name, cls = m.group(1), m.group(2)
        close = find_close(src, src.index("(", m.start() + len(m.group(1))))
        body = src[m.start():close if close != -1 else m.end()]
        qm = re.search(r"\bQuest\s*\.\s*([A-Z0-9_]+)", body)
        entries.append((enum_name, cls, qm.group(1) if qm else None))
    # quest consts used by >1 enum entry -> key those entries by enum name
    const_count = defaultdict(int)
    for _, _, qc in entries:
        if qc:
            const_count[qc] += 1
    fqcn_key = OrderedDict()
    for enum_name, cls, qc in entries:
        key = qc if (qc and const_count[qc] == 1) else enum_name
        fq = resolve_class(cls)
        if fq is None:
            print(f"WARN: cannot resolve helper class {cls}", file=sys.stderr)
            continue
        fqcn_key[fq] = key
    return fqcn_key


# ------------------------------------------------------------- file extract


ID_REF_RE = re.compile(r"\b(NpcID|ObjectID)\s*\.\s*(\w+)")


def discover_subclasses(java_files, sources):
    """Map subclass name -> 'npc'|'object'|'plain' for classes (transitively)
    extending a coordinate-bearing step type. sources: path -> stripped src."""
    parent = {}
    for path in java_files:
        for m in EXTENDS_RE.finditer(sources[path]):
            parent.setdefault(m.group(1), m.group(2))

    def kind_of(cls, seen=()):
        if cls in NPC_STEPS:
            return "npc"
        if cls in OBJ_STEPS:
            return "object"
        if cls in PLAIN_STEPS or cls == "DetailedQuestStep":
            return "plain"
        if cls in seen or cls not in parent:
            return None
        return kind_of(parent[cls], seen + (cls,))

    return {c: k for c in parent
            if c not in ALL_STEPS and (k := kind_of(c)) is not None}


def _pattern_id(args, wp_i, npc_tab, obj_tab):
    """First NpcID./ObjectID. reference in an arg BEFORE the WorldPoint arg
    (ids precede the point in every step signature; requirements follow)."""
    for a in args[:wp_i]:
        m = ID_REF_RE.search(a)
        if m:
            tab = npc_tab if m.group(1) == "NpcID" else obj_tab
            key = "npc" if m.group(1) == "NpcID" else "object"
            return key, tab.get(m.group(2), f"{m.group(1)}.{m.group(2)}")
    return None, None


def extract_file(path, npc_tab, obj_tab, sub_kinds=None, src=None):
    """Yield step dicts (with _line) from one java file, in source order."""
    if src is None:
        src = strip_comments(open(path, encoding="utf-8", errors="replace").read())
    sub_kinds = sub_kinds or {}
    # WorldPoint variable table (unique-value only)
    wp_vars = {}
    for m in WP_ASSIGN_RE.finditer(src):
        name = m.group(1)
        val = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
        if name in wp_vars and wp_vars[name] != val:
            wp_vars[name] = "AMBIGUOUS"
        elif wp_vars.get(name) != "AMBIGUOUS":
            wp_vars[name] = val

    # does this file's top class extend a coordinate-bearing step type?
    file_step_kind = None
    fm = EXTENDS_RE.search(src)
    if fm:
        cls = fm.group(2)
        if cls in NPC_STEPS:
            file_step_kind = "npc"
        elif cls in OBJ_STEPS:
            file_step_kind = "object"
        elif cls in PLAIN_STEPS or cls == "DetailedQuestStep":
            file_step_kind = "plain"
        elif cls in sub_kinds:
            file_step_kind = sub_kinds[cls]

    sites = []   # (match_start, cls_name, mode)  mode: core|sub|super
    for m in CALL_RE.finditer(src):
        sites.append((m.start(), m.group(1) or m.group(2), "core"))
    if sub_kinds:
        sub_rx = re.compile(r"new\s+(" + "|".join(map(re.escape, sorted(sub_kinds))) + r")\s*\(")
        for m in sub_rx.finditer(src):
            sites.append((m.start(), m.group(1), "sub"))
    if file_step_kind is not None:
        for m in re.finditer(r"\bsuper\s*\(", src):
            sites.append((m.start(), None, "super"))
    sites.sort()

    steps = []
    for start, cls, mode in sites:
        open_idx = src.index("(", start + (5 if mode == "super" else 3))
        close_idx = find_close(src, open_idx)
        if close_idx == -1:
            continue
        args = split_args(src[open_idx + 1:close_idx])
        line_no = src.count("\n", 0, start) + 1
        # locate the WorldPoint argument
        wp = None
        wp_i = None
        for i, a in enumerate(args):
            wm = WP_INLINE_RE.fullmatch(a.strip())
            if wm:
                wp = (int(wm.group(1)), int(wm.group(2)), int(wm.group(3)))
                wp_i = i
                break
            if IDENT_RE.match(a.strip()):
                v = wp_vars.get(a.strip())
                if isinstance(v, tuple):
                    wp = v
                    wp_i = i
                    break
        if wp is None:
            continue
        # first string-literal arg after the WorldPoint arg
        text = None
        for a in args[wp_i + 1:]:
            t = pure_string_literal(a)
            if t is not None:
                text = unescape(t)
                break
        if not text:
            continue
        entry = {"text": text, "world": list(wp)}
        if mode == "core":
            if cls in NPC_STEPS and len(args) >= 2:
                rid = resolve_id(args[1], npc_tab, obj_tab, "npc")
                if rid is not None:
                    entry["npc"] = rid
            elif cls in OBJ_STEPS and len(args) >= 2:
                rid = resolve_id(args[1], npc_tab, obj_tab, "object")
                if rid is not None:
                    entry["object"] = rid
        else:   # sub / super: id by NpcID./ObjectID. pattern before the point
            key, rid = _pattern_id(args, wp_i, npc_tab, obj_tab)
            if key:
                entry[key] = rid
        entry["_line"] = line_no
        entry["_cls"] = cls or "super"
        steps.append(entry)
    return steps


# ------------------------------------------------------------------- main


def main():
    qh_root = sys.argv[1] if len(sys.argv) > 1 else "."
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    npc_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(out_dir, "npcid_constants.txt")
    obj_path = sys.argv[4] if len(sys.argv) > 4 else os.path.join(out_dir, "objectid_constants.txt")
    npc_tab = load_constants(npc_path) if os.path.exists(npc_path) else {}
    obj_tab = load_constants(obj_path) if os.path.exists(obj_path) else {}
    print(f"constants: {len(npc_tab)} npc, {len(obj_tab)} object", file=sys.stderr)

    fqcn_key = build_quest_map(qh_root)
    print(f"registered helpers: {len(fqcn_key)}", file=sys.stderr)

    # package -> keys of registered helpers living there
    pkg_keys = defaultdict(list)
    for fq, key in fqcn_key.items():
        pkg_keys[fq.rsplit(".", 1)[0]].append(key)

    helpers_dir = os.path.join(qh_root, "helpers")
    prefix_dir = os.path.dirname(os.path.dirname(qh_root))  # .../src/main/java? no: com dir parent
    result = OrderedDict()
    prov = []
    skipped_files = []
    n_steps = 0

    # walk in a deterministic order following enum ordering first
    file_of_fqcn = {}
    for root, _dirs, files in os.walk(helpers_dir):
        for fn in sorted(files):
            if not fn.endswith(".java"):
                continue
            full = os.path.join(root, fn)
            relq = os.path.relpath(full, qh_root)
            fqcn = "com.questhelper." + os.path.splitext(relq)[0].replace(os.sep, ".")
            file_of_fqcn[fqcn] = full

    # pre-read + comment-strip every helper source once
    sources = {full: strip_comments(open(full, encoding="utf-8",
                                         errors="replace").read())
               for full in file_of_fqcn.values()}
    sub_kinds = discover_subclasses(list(sources), sources)
    print(f"coordinate-step subclasses discovered: {len(sub_kinds)}",
          file=sys.stderr)

    # 1) registered helper files, in enum order
    consumed = set()
    for fq, key in fqcn_key.items():
        full = file_of_fqcn.get(fq)
        if full is None:
            print(f"WARN: source file missing for {fq}", file=sys.stderr)
            continue
        consumed.add(full)
        steps = extract_file(full, npc_tab, obj_tab, sub_kinds, sources[full])
        if steps:
            result.setdefault(key, [])
            for s in steps:
                prov.append((key, s, full, s["_line"]))
                result[key].append(s)

    # 2) auxiliary files: attribute via unique package owner, else via a
    #    UNIQUE registered-helper file that references the aux class name
    aux_used = aux_skipped = 0
    reg_srcs = None   # lazy: registered fqcn -> comment-stripped source
    for fqcn, full in sorted(file_of_fqcn.items()):
        if full in consumed:
            continue
        pkg = fqcn.rsplit(".", 1)[0]
        keys = pkg_keys.get(pkg)
        steps = extract_file(full, npc_tab, obj_tab, sub_kinds, sources[full])
        if not steps:
            continue
        key = None
        if keys and len(keys) == 1:
            key = keys[0]
        else:
            if reg_srcs is None:
                reg_srcs = {rfq: sources[file_of_fqcn[rfq]]
                            for rfq in fqcn_key if rfq in file_of_fqcn}
            cls_name = fqcn.rsplit(".", 1)[1]
            rx = re.compile(r"\b" + re.escape(cls_name) + r"\b")
            referrers = [rfq for rfq, s in reg_srcs.items() if rx.search(s)]
            if len(referrers) == 1:
                key = fqcn_key[referrers[0]]
        if key is not None:
            result.setdefault(key, [])
            for s in steps:
                prov.append((key, s, full, s["_line"]))
                result[key].append(s)
            aux_used += 1
        else:
            skipped_files.append((full, len(steps), keys))
            aux_skipped += 1

    # dedupe identical (text, world) within each quest, keep first, strip meta
    total = 0
    for key, steps in result.items():
        seen = set()
        deduped = []
        for s in steps:
            sig = (s["text"], tuple(s["world"]))
            if sig in seen:
                continue
            seen.add(sig)
            s = {k: v for k, v in s.items() if not k.startswith("_")}
            deduped.append(s)
        result[key] = deduped
        total += len(deduped)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "qh_steps.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)

    # provenance: spread samples across the whole set
    with open(os.path.join(out_dir, "provenance.txt"), "w", encoding="utf-8") as f:
        f.write("quest_key -> step text -> world -> file:line\n")
        f.write("=" * 70 + "\n")
        stride = max(1, len(prov) // 40)
        for key, s, full, line in prov[::stride][:45]:
            f.write(f"{key}\n  text: {s['text'][:100]}\n"
                    f"  world: {s['world']}"
                    + (f"  npc: {s.get('npc')}" if 'npc' in s else "")
                    + (f"  object: {s.get('object')}" if 'object' in s else "")
                    + f"\n  src: {full}:{line}\n\n")
        if skipped_files:
            f.write("\nSKIPPED auxiliary files (ambiguous package, steps not attributed):\n")
            for full, n, keys in skipped_files:
                f.write(f"  {full} ({n} steps; package helpers: {keys})\n")

    # stats
    with_id = sum(1 for ss in result.values() for s in ss
                  if isinstance(s.get("npc"), int) or isinstance(s.get("object"), int))
    sym_id = sum(1 for ss in result.values() for s in ss
                 if isinstance(s.get("npc"), str) or isinstance(s.get("object"), str))
    id_bearing = sum(1 for ss in result.values() for s in ss
                     if "npc" in s or "object" in s)
    print(f"quests: {len(result)}  steps: {total}", file=sys.stderr)
    print(f"id-bearing steps: {id_bearing} (numeric {with_id}, symbol {sym_id})", file=sys.stderr)
    print(f"aux files used: {aux_used}, skipped(ambiguous pkg): {aux_skipped}", file=sys.stderr)


if __name__ == "__main__":
    main()
