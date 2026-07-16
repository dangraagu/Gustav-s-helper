#!/usr/bin/env python3
"""
qh_dialogue.py -- harvest dialogue-choice option strings from Quest Helper source.

Derives facts ONLY from source (no guessing/fabrication):
  * byQuest: keyed by the net.runelite.api.Quest enum constant, mapped via
    QuestHelperQuest.java  (`new <Class>(), Quest.<CONST>` ...).
  * byNpc  : best-effort. Options from `<var>.addDialogStep(...)` are attributed
    to the NPC of the `<var> = new NpcStep(this, NpcID.X, ..., "desc")` they target
    (or, for a step-subclass with a bare addDialogStep, the class `super(... NpcID.X ...)`).
    Key = NpcID constant lowercased (underscores->spaces) when resolvable,
    else the cleaned "Talk to <Name>" description; unresolved -> omitted.

Extracted call sites:
  .addDialogStep(...) / .addDialogSteps(...)         -> String-literal args (skip int id / non-literals)
  new DialogChoiceStep(...) / new WidgetChoiceStep(...) -> String-literal args (skip config/int/pattern/var)

Pure-Python, stdlib only.
"""
import os, re, sys, json, collections

ROOT = r"C:\Users\bahs_admin\Documents\Claude\Projects\_osiris-fork-wt\src\main\java\com\questhelper"
HELPERS = os.path.join(ROOT, "helpers")
ENUM_FILE = os.path.join(ROOT, "questinfo", "QuestHelperQuest.java")
OUT_DIR = r"C:\Users\BAHS_A~1\AppData\Local\Temp\claude\C--Users-bahs-admin\1d0da643-2e93-4c42-9a8f-b30452ec9830\scratchpad\dlg"

# ------------------------------------------------------------------ helpers
def strip_comments(s):
    """Replace // and /* */ comments with spaces (preserve length + newlines)."""
    out = list(s)
    i, n = 0, len(s)
    in_s = in_c = False          # double-quote string / single-quote char
    while i < n:
        ch = s[i]
        if in_s:
            if ch == '\\':
                i += 2; continue
            if ch == '"':
                in_s = False
            i += 1; continue
        if in_c:
            if ch == '\\':
                i += 2; continue
            if ch == "'":
                in_c = False
            i += 1; continue
        if ch == '"':
            in_s = True; i += 1; continue
        if ch == "'":
            in_c = True; i += 1; continue
        if ch == '/' and i + 1 < n and s[i+1] == '/':
            while i < n and s[i] != '\n':
                out[i] = ' '; i += 1
            continue
        if ch == '/' and i + 1 < n and s[i+1] == '*':
            out[i] = ' '; out[i+1] = ' '; i += 2
            while i < n and not (s[i] == '*' and i + 1 < n and s[i+1] == '/'):
                if s[i] != '\n':
                    out[i] = ' '
                i += 1
            if i < n:
                out[i] = ' '
                if i + 1 < n:
                    out[i+1] = ' '
                i += 2
            continue
        i += 1
    return ''.join(out)

def match_paren(text, open_idx):
    """open_idx points at '(' -> return index of matching ')'. Respects strings/chars."""
    depth = 0
    i, n = open_idx, len(text)
    in_s = in_c = False
    while i < n:
        ch = text[i]
        if in_s:
            if ch == '\\': i += 2; continue
            if ch == '"': in_s = False
            i += 1; continue
        if in_c:
            if ch == '\\': i += 2; continue
            if ch == "'": in_c = False
            i += 1; continue
        if ch == '"': in_s = True
        elif ch == "'": in_c = True
        elif ch == '(': depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1

def split_args(argtext):
    """Split top-level comma-separated arguments (respect (), [], {}, strings)."""
    args, buf = [], []
    depth = 0
    in_s = in_c = False
    i, n = 0, len(argtext)
    while i < n:
        ch = argtext[i]
        if in_s:
            buf.append(ch)
            if ch == '\\' and i + 1 < n:
                buf.append(argtext[i+1]); i += 2; continue
            if ch == '"': in_s = False
            i += 1; continue
        if in_c:
            buf.append(ch)
            if ch == '\\' and i + 1 < n:
                buf.append(argtext[i+1]); i += 2; continue
            if ch == "'": in_c = False
            i += 1; continue
        if ch == '"': in_s = True; buf.append(ch); i += 1; continue
        if ch == "'": in_c = True; buf.append(ch); i += 1; continue
        if ch in '([{': depth += 1
        elif ch in ')]}': depth -= 1
        if ch == ',' and depth == 0:
            args.append(''.join(buf)); buf = []; i += 1; continue
        buf.append(ch); i += 1
    if ''.join(buf).strip():
        args.append(''.join(buf))
    return args

STR_RE = re.compile(r'"((?:\\.|[^"\\])*)"', re.S)

def unescape(s):
    out = []; i = 0; n = len(s)
    while i < n:
        c = s[i]
        if c == '\\' and i + 1 < n:
            nx = s[i+1]
            simple = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f',
                      '"': '"', "'": "'", '\\': '\\', '/': '/', '0': '\0'}
            if nx in simple:
                out.append(simple[nx]); i += 2; continue
            if nx == 'u' and i + 6 <= n:
                try:
                    out.append(chr(int(s[i+2:i+6], 16))); i += 6; continue
                except ValueError:
                    pass
            out.append(nx); i += 2; continue
        out.append(c); i += 1
    return ''.join(out)

def arg_to_literal(arg):
    """Return decoded string if arg is a pure string-literal (poss. + concatenation), else None."""
    arg = arg.strip()
    if not arg:
        return None
    parts = STR_RE.findall(arg)
    if not parts:
        return None
    remainder = STR_RE.sub('', arg).replace('+', ' ')
    if remainder.strip() != '':
        return None
    val = ''.join(unescape(p) for p in parts)
    val = val.strip()
    return val if val else None

def lineno(text, idx):
    return text.count('\n', 0, idx) + 1

# ------------------------------------------------------------------ NPC naming
TALK_VERBS = ['talk to', 'talk with', 'speak to', 'speak with', 'chat with',
              'return to and talk to', 'return and talk to', 'return to', 'ask ']
CUT_DELIMS = ['.', ',', '!', '?', ';', ':', '(', ' in ', ' at ', ' on ', ' near ',
              ' by ', ' inside', ' outside', ' upstairs', ' downstairs', ' to ',
              ' and ', ' again', ' who ', ' south', ' north', ' east', ' west',
              ' back ', ' with ', ' about', ' for ', ' behind', ' next ', ' from ',
              ' located', ' standing', ' then ', ' after ', ' before ', ' while ',
              ' when ', ' if ', ' -', ' –']

def clean_talk(desc):
    if not desc:
        return None
    low = desc.strip().lower()
    for v in TALK_VERBS:
        if low.startswith(v):
            rest = desc.strip()[len(v):]
            for art in ['the ', 'a ', 'an ']:
                if rest.lower().startswith(art):
                    rest = rest[len(art):]
            low2 = rest.lower()
            idx = len(rest)
            for d in CUT_DELIMS:
                j = low2.find(d)
                if j != -1 and j < idx:
                    idx = j
            name = rest[:idx].strip().rstrip('.,!?;:').strip().lower()
            if name and len(name) <= 40:
                return name
            return None
    return None

def name_from(npc_const, desc):
    if npc_const:
        nm = ' '.join(npc_const.lower().replace('_', ' ').split())
        return nm or None
    return clean_talk(desc)

# ------------------------------------------------------------------ 1. enum map
def build_class_to_quest():
    txt = strip_comments(open(ENUM_FILE, encoding='utf-8', errors='replace').read())
    m = {}
    for mo in re.finditer(r'new\s+(\w+)\s*\(\s*\)\s*,\s*Quest\.([A-Za-z0-9_]+)', txt):
        cls, const = mo.group(1), mo.group(2)
        m.setdefault(cls, const)
    return m

def build_classfile_index():
    idx = {}
    for dp, _dn, fns in os.walk(HELPERS):
        for fn in fns:
            if not fn.endswith('.java'):
                continue
            path = os.path.join(dp, fn)
            try:
                txt = strip_comments(open(path, encoding='utf-8', errors='replace').read())
            except OSError:
                continue
            for mo in re.finditer(r'(?:public\s+)?(?:final\s+|abstract\s+|static\s+)*(?:class|enum|interface)\s+(\w+)', txt):
                idx.setdefault(mo.group(1), path)
    return idx

# ------------------------------------------------------------------ 2. per-file extraction
CALL_DLG = re.compile(r'\b(addDialogSteps?)\s*\(')
CALL_CHOICE = re.compile(r'\bnew\s+(DialogChoiceStep|WidgetChoiceStep)\s*\(')
ASSIGN_NPC = re.compile(r'(\w+)\s*=\s*new\s+NpcStep\s*\(')
SUPER_CALL = re.compile(r'\bsuper\s*\(')
NPCID_TOK = re.compile(r'\bNpcID\.(\w+)')
WORD = re.compile(r'\w')

def prev_nonspace(text, i):
    while i >= 0 and text[i] in ' \t\r\n':
        i -= 1
    return i

def stmt_boundary(text, i):
    """Nearest ; { } before i (respecting strings). Returns index or -1."""
    in_s = in_c = False
    j = 0
    last = -1
    # simple forward scan up to i to know string state accurately
    while j < i:
        ch = text[j]
        if in_s:
            if ch == '\\': j += 2; continue
            if ch == '"': in_s = False
            j += 1; continue
        if in_c:
            if ch == '\\': j += 2; continue
            if ch == "'": in_c = False
            j += 1; continue
        if ch == '"': in_s = True
        elif ch == "'": in_c = True
        elif ch in ';{}':
            last = j
        j += 1
    return last

def first_ident(s):
    mo = re.search(r'[A-Za-z_]\w*', s)
    return mo.group(0) if mo else None

def extract_file(path, quest_const):
    text = strip_comments(open(path, encoding='utf-8', errors='replace').read())

    # var -> list of (lineno, npc_const, desc)
    assigns = collections.defaultdict(list)
    for mo in ASSIGN_NPC.finditer(text):
        var = mo.group(1)
        op = mo.end() - 1
        cp = match_paren(text, op)
        if cp == -1:
            continue
        args = split_args(text[op+1:cp])
        npc_const = None
        if len(args) >= 2:
            t = NPCID_TOK.search(args[1])
            if t:
                npc_const = t.group(1)
        desc = None
        for a in args[2:]:
            lit = arg_to_literal(a)
            if lit:
                desc = lit; break
        assigns[var].append((lineno(text, mo.start()), npc_const, desc))

    # class-level NPC from super(...) containing NpcID.
    class_npc, class_desc = None, None
    for mo in SUPER_CALL.finditer(text):
        op = mo.end() - 1
        cp = match_paren(text, op)
        if cp == -1:
            continue
        args = split_args(text[op+1:cp])
        cand_const = None
        cand_desc = None
        for a in args:
            t = NPCID_TOK.search(a)
            if t and cand_const is None:
                cand_const = t.group(1)
            if cand_desc is None:
                lit = arg_to_literal(a)
                if lit:
                    cand_desc = lit
        if cand_const or (cand_desc and clean_talk(cand_desc)):
            class_npc, class_desc = cand_const, cand_desc
            break

    quest_opts = []                 # ordered options for this file
    prov = []                       # (option, path, line)
    npc_hits = []                   # (npc_name, option)

    def resolve_receiver(call_start):
        """Return (npc_const, desc) or None for the addDialogStep receiver."""
        i = prev_nonspace(text, call_start - 1)
        if i < 0:
            return (class_npc, class_desc)
        if text[i] == '.':
            j = prev_nonspace(text, i - 1)
            if j >= 0 and text[j] == ')':
                # chained: resolve statement head
                b = stmt_boundary(text, call_start)
                stmt = text[b+1:call_start]
                if '=' in stmt:
                    stmt = stmt.rsplit('=', 1)[1]
                head = first_ident(stmt)
                if head == 'this' or head is None:
                    return (class_npc, class_desc)
                return best_assign(head, call_start)
            # simple ident receiver
            end = j + 1
            k = j
            while k >= 0 and WORD.match(text[k]):
                k -= 1
            ident = text[k+1:end]
            if ident == 'this':
                return (class_npc, class_desc)
            return best_assign(ident, call_start)
        # bare call -> implicit this
        return (class_npc, class_desc)

    def best_assign(var, call_start):
        cand = assigns.get(var)
        if not cand:
            return None
        ln = lineno(text, call_start)
        pick = None
        for (aln, const, desc) in cand:
            if aln <= ln and (pick is None or aln > pick[0]):
                pick = (aln, const, desc)
        if pick is None:
            pick = cand[0]
        return (pick[1], pick[2])

    # addDialogStep / addDialogSteps
    for mo in CALL_DLG.finditer(text):
        op = mo.end() - 1
        cp = match_paren(text, op)
        if cp == -1:
            continue
        args = split_args(text[op+1:cp])
        opts = []
        for a in args:
            lit = arg_to_literal(a)
            if lit is not None:
                opts.append(lit)
        if not opts:
            continue
        ln = lineno(text, mo.start())
        for o in opts:
            quest_opts.append(o)
            prov.append((o, path, ln))
        rec = resolve_receiver(mo.start())
        if rec is not None:
            nm = name_from(rec[0], rec[1])
            if nm:
                for o in opts:
                    npc_hits.append((nm, o))

    # new DialogChoiceStep / new WidgetChoiceStep
    for mo in CALL_CHOICE.finditer(text):
        op = mo.end() - 1
        cp = match_paren(text, op)
        if cp == -1:
            continue
        args = split_args(text[op+1:cp])
        ln = lineno(text, mo.start())
        for a in args:
            lit = arg_to_literal(a)
            if lit is not None:
                quest_opts.append(lit)
                prov.append((lit, path, ln))

    return quest_opts, npc_hits, prov

# ------------------------------------------------------------------ main
def main():
    cls2quest = build_class_to_quest()
    clsidx = build_classfile_index()

    # dir -> quest const (dir of each mapped main class). Track collisions
    # (>1 distinct quest sharing a folder, e.g. Rag and Bone Man I/II).
    dir2quest = {}
    dir_consts = collections.defaultdict(set)
    unresolved_classes = []
    for cls, const in cls2quest.items():
        path = clsidx.get(cls)
        if not path:
            unresolved_classes.append(cls)
            continue
        d = os.path.dirname(path)
        dir2quest.setdefault(d, const)
        dir_consts[d].add(const)
    quest_dirs = sorted(dir2quest.keys(), key=len, reverse=True)
    shared_dirs = {d: sorted(cs) for d, cs in dir_consts.items() if len(cs) > 1}

    # path -> quest const when the FILE itself defines a mapped main quest class.
    path2main = {}
    for cls, const in cls2quest.items():
        p = clsidx.get(cls)
        if p:
            path2main.setdefault(p, const)  # clsidx already resolved main class -> its file

    def quest_for(path):
        # 1) file defines its own mapped main class -> exact attribution
        if path in path2main:
            return path2main[path]
        # 2) fall back to folder mapping (sub-step files)
        fdir = os.path.dirname(path)
        for qd in quest_dirs:
            if fdir == qd or fdir.startswith(qd + os.sep):
                return dir2quest[qd]
        return None

    byQuest = collections.OrderedDict()
    byNpc = collections.OrderedDict()
    prov_all = []
    files_scanned = 0

    all_files = []
    for dp, _dn, fns in os.walk(HELPERS):
        for fn in fns:
            if fn.endswith('.java'):
                all_files.append(os.path.join(dp, fn))
    all_files.sort()

    for path in all_files:
        qconst = quest_for(path)
        quest_opts, npc_hits, prov = extract_file(path, qconst)
        files_scanned += 1

        if qconst and quest_opts:
            lst = byQuest.setdefault(qconst, [])
            seen = set(lst)
            for o in quest_opts:
                if o not in seen:
                    lst.append(o); seen.add(o)

        for nm, o in npc_hits:
            lst = byNpc.setdefault(nm, [])
            if o not in lst:
                lst.append(o)

        for (o, p, ln) in prov:
            prov_all.append((qconst or '(none)', o, os.path.relpath(p, ROOT).replace('\\', '/'), ln))

    # drop empty quest lists / sort keys
    byQuest = collections.OrderedDict(
        (k, byQuest[k]) for k in sorted(byQuest) if byQuest[k])
    byNpc = collections.OrderedDict(
        (k, byNpc[k]) for k in sorted(byNpc) if byNpc[k])

    out = collections.OrderedDict()
    out["_source"] = "Quest Helper (BSD-2-Clause) — dialogue choices extracted from source"
    out["byQuest"] = byQuest
    out["byNpc"] = byNpc

    os.makedirs(OUT_DIR, exist_ok=True)
    jpath = os.path.join(OUT_DIR, "qh_dialogue.json")
    with open(jpath, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # provenance sample
    ppath = os.path.join(OUT_DIR, "provenance.txt")
    with open(ppath, 'w', encoding='utf-8') as f:
        f.write("Quest Helper dialogue extraction - provenance sample\n")
        f.write("quest_const | option | source_file:line\n")
        f.write("=" * 78 + "\n")
        # one sample row per quest (first option), plus extra rows, capped
        seen_q = set()
        rows = 0
        for (q, o, sp, ln) in prov_all:
            if q == '(none)':
                continue
            if q in seen_q:
                continue
            seen_q.add(q)
            f.write(f"{q} | {o!r} | {sp}:{ln}\n")
            rows += 1
        f.write("-" * 78 + "\n")
        f.write("Extra detailed rows (first ~120 quest-attributed options):\n")
        cnt = 0
        for (q, o, sp, ln) in prov_all:
            if q == '(none)':
                continue
            f.write(f"{q} | {o!r} | {sp}:{ln}\n")
            cnt += 1
            if cnt >= 120:
                break

    distinct = set()
    for k, v in byQuest.items():
        distinct.update(v)
    for k, v in byNpc.items():
        distinct.update(v)

    print("files_scanned:", files_scanned)
    print("mapped classes (enum->Quest):", len(cls2quest))
    print("unresolved enum classes (no file found):", len(unresolved_classes), unresolved_classes[:10])
    print("quests_with_options:", len(byQuest))
    print("npc_keys:", len(byNpc))
    print("distinct_option_strings:", len(distinct))
    print("json:", jpath)

    # quests that map to a const but produced ZERO options
    mapped_consts = set(cls2quest.values())
    zero = sorted(mapped_consts - set(byQuest.keys()))
    print("mapped_quest_consts_total:", len(mapped_consts))
    print("mapped_quests_with_ZERO_options:", len(zero))
    print("zero_sample:", zero[:25])
    print("shared_folders (2 quests / 1 dir):", {os.path.basename(d): c for d, c in shared_dirs.items()})

if __name__ == '__main__':
    main()
