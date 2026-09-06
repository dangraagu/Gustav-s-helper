"""Deterministic check: a position condition that a player satisfies BEFORE reaching the step.

The engine folds manual steps behind the furthest completed arrival. So if step N carries a position
condition on a tile the route already stood on at step M < N, with no real gate in between, step N
ticks itself at step M -- and everything between folds with it. This is the 259-step bug shape.

Pure data analysis, no agents: for each guide, walk steps in route order and flag any position
condition whose tile was already visited by an earlier position condition in the same guide.
"""
import json, os, glob, sys, collections

BASE = 'src/main/resources/com/gustavguide/data/guides'
REAL_GATES = {'quest', 'skill', 'item', 'itemBank', 'itemEquipped', 'itemAcquired',
              'itemConsumed', 'varbit', 'varp', 'diary', 'qp'}


def gates(cond):
    """Condition ops in this tree that are real gates (not mere arrival)."""
    out = set()
    if not isinstance(cond, dict):
        return out
    op = cond.get('op')
    if op in REAL_GATES:
        out.add(op)
    for k in ('of', 'conditions', 'items'):
        for sub in (cond.get(k) or []):
            out |= gates(sub)
    if isinstance(cond.get('condition'), dict):
        out |= gates(cond['condition'])
    return out


def pos_tile(cond):
    if isinstance(cond, dict) and cond.get('op') == 'position':
        return (cond.get('x'), cond.get('y'), cond.get('z', 0))
    return None


order = {}
for g in sorted(os.listdir(BASE)):
    d = os.path.join(BASE, g)
    if not os.path.isdir(d):
        continue
    idx = os.path.join(d, 'route-index.json')
    files = []
    if os.path.exists(idx):
        try:
            files = [os.path.join(d, f) for f in json.load(open(idx, encoding='utf-8')).get('sections', [])]
        except Exception:
            files = []
    if not files:
        files = sorted(f for f in glob.glob(os.path.join(d, '*.json')) if not f.endswith('route-index.json'))
    steps = []
    for f in files:
        if not os.path.exists(f):
            continue
        for s in json.load(open(f, encoding='utf-8')).get('steps', []):
            s['_file'] = os.path.basename(f)
            steps.append(s)
    order[g] = steps

total_dup = 0
rows = []
for g, steps in order.items():
    seen = {}                      # tile -> first index that arrives there
    gate_since = {}                # tile -> was there a real gate after that first arrival
    for i, s in enumerate(steps):
        c = s.get('complete')
        t = pos_tile(c)
        # any real gate at this step re-arms every earlier tile
        if gates(c):
            for k in list(gate_since):
                gate_since[k] = True
        if t is None:
            continue
        if t in seen and not gate_since.get(t):
            total_dup += 1
            rows.append((g, s['_file'], s['id'], i, steps[seen[t]]['id'], seen[t], t,
                         (s.get('text') or '')[:58]))
        else:
            seen[t] = i
            gate_since[t] = False

print('position conditions that a player already satisfied earlier, with NO real gate between:')
print('  total: %d' % total_dup)
per = collections.Counter(r[0] for r in rows)
for g, c in per.most_common():
    print('   %4d  %s' % (c, g))
print()
for r in rows[:25]:
    print('  %-16s %-24s step#%-5d ticks at %-22s (step#%d)  %s' % (r[0], r[2], r[3], r[4], r[5], r[6]))
    print('  %54s %r' % ('', r[7]))

# ---- lint gate ------------------------------------------------------------------------------
# These cases are KNOWN and accepted as a product decision (arrival at a town the route revisits
# 1-5 steps later completes the revisit, which is usually what the player wants). Anything NOT on
# this list is a new duplicate arrival - the shape that mass-folds a section (the 259-step bug) -
# and fails the build. To accept a new one deliberately, add its (guide, step_id) here with a note.
ACCEPTED = {
    ('b0aty-hcim', 'e3-098'), ('b0aty-hcim', 'e4-051'),
    ('b0aty-hcim', 'e4-309'), ('b0aty-hcim', 'e4-643'),
    ('b0aty-hcim', 'e11-064'), ('b0aty-hcim', 'e11-077'),
    ('osiris-ironman', 'eg-144c'),
}
new = [(g, sid) for g, _, sid, *_ in rows if (g, sid) not in ACCEPTED]
if new:
    print('\nFAIL: %d NEW duplicate arrival(s) not on the accepted list:' % len(new))
    for g, sid in new:
        print('   %s / %s' % (g, sid))
    sys.exit(1)
fixed = ACCEPTED - {(g, sid) for g, _, sid, *_ in rows}
if fixed:
    print('\nNOTE: %d accepted case(s) no longer occur - prune them from ACCEPTED: %s'
          % (len(fixed), sorted(fixed)))
print('\nOK: only known-accepted duplicate arrivals present')
