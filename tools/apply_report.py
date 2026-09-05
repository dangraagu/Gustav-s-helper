#!/usr/bin/env python3
"""Turn a pasted step report (from the plugin's Discord channel) into a coordinate override.

The plugin's "Report wrong / missing info" button can attach the player's own tile
("Proposed spot (player-supplied): x, y, plane p") — the reporter was standing where the step
actually happens. This tool closes that loop: paste the report, get the right override written,
rebuild, ship. Nothing is guessed — a report without a proposed spot is refused.

Routing (matches how the builders consume overrides):
  osiris-ironman   -> tools/data/manual_coords.json      keyed by the step's EXACT lowercased text,
                      because scrape_guide.py (the network scraper) resolves through that file;
  every raw-built  -> tools/data/manual_conditions.json  guide id -> step id -> {"world": [x,y,plane]},
  guide               applied by build_raw_guide.apply_override.

Usage:
  py -3 tools/apply_report.py report.txt      # or pipe the report on stdin
Then rebuild: py -3 tools/build_raw_guide.py <guide>   (osiris: py -3 tools/scrape_guide.py)

CAUTION: the "Proposed spot" line is plain text - a reporter could hand-type one rather than using
the plugin's attach-my-position checkbox. Impact is bounded (one step's marker, revertable, and the
rebuild gates still run), but eyeball the proposed tile against the step before shipping it.
"""
import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).parent / "data"
GUIDES_DIR = Path(__file__).parent.parent / "src/main/resources/com/gustavguide/data/guides"

# The one guide that is network-scraped (manual_coords route); everything else is raw-built.
SCRAPED_GUIDES = {"osiris-ironman"}

# Coordinate sanity: the OSRS surface runs roughly x 1000-4500; underground regions sit +6400 in y.
X_RANGE = (1000, 4500)
Y_RANGE = (2000, 13000)
PLANES = (0, 3)

_GUIDE_RE = re.compile(r"^\*\*Step report\*\* — .* \(`([^`]+)`\)", re.MULTILINE)
_STEP_RE = re.compile(r"^Step \d+/\d+\s+`([^`]+)`", re.MULTILINE)
_TEXT_RE = re.compile(r"^• Text: (.+)$", re.MULTILINE)
_SPOT_RE = re.compile(r"^Proposed spot \(player-supplied\): (\d+), (\d+), plane (\d+)\s*$", re.MULTILINE)


class Result:
    def __init__(self, applied, reason, target=None, key=None):
        self.applied = applied
        self.reason = reason
        self.target = target
        self.key = key


def _known_guides():
    if not GUIDES_DIR.is_dir():
        # Running outside the repo (tests exercise routing, not the disk layout): trust SCRAPED_GUIDES
        # plus anything already present in the override files.
        return None
    return {p.name for p in GUIDES_DIR.iterdir() if p.is_dir()}


def apply(report_text, coords_path=None, conditions_path=None):
    coords_path = Path(coords_path or DATA / "manual_coords.json")
    conditions_path = Path(conditions_path or DATA / "manual_conditions.json")

    g = _GUIDE_RE.search(report_text or "")
    s = _STEP_RE.search(report_text or "")
    t = _TEXT_RE.search(report_text or "")
    if not (g and s and t):
        return Result(False, "not a step report: missing the guide/step/Text header lines")
    guide_id, step_id, step_text = g.group(1).strip(), s.group(1).strip(), t.group(1).strip()

    spot = _SPOT_RE.search(report_text)
    if not spot:
        return Result(False, "no 'Proposed spot (player-supplied)' line - nothing grounded to apply. "
                             "Only reports where the player attached their position can set a coordinate.")
    x, y, plane = int(spot.group(1)), int(spot.group(2)), int(spot.group(3))
    if not (X_RANGE[0] <= x <= X_RANGE[1] and Y_RANGE[0] <= y <= Y_RANGE[1]
            and PLANES[0] <= plane <= PLANES[1]):
        return Result(False, "proposed tile (%d, %d, plane %d) is outside the sane OSRS range - refusing"
                      % (x, y, plane))

    known = _known_guides()
    scraped = guide_id in SCRAPED_GUIDES
    if known is not None and guide_id not in known:
        return Result(False, "unknown guide id %r - refusing to guess where the override belongs" % guide_id)
    if known is None and not scraped and guide_id not in _load(conditions_path) \
            and not _plausible_guide_id(guide_id):
        return Result(False, "unknown guide id %r - refusing to guess where the override belongs" % guide_id)

    world = [x, y, plane]
    if scraped:
        data = _load(coords_path)
        key = step_text.strip().lower()
        existing = data.get(key)
        if isinstance(existing, dict):
            existing["world"] = world
        else:
            data[key] = world
        _save(coords_path, data)
        return Result(True, "override written", target=coords_path.name, key=key)

    data = _load(conditions_path)
    guide = data.setdefault(guide_id, {})
    ov = guide.get(step_id)
    if ov == "manual":
        # The dict form of an override cannot express "stay manual AND set a coordinate" - replacing
        # the string would silently re-enable auto-completion. Rare enough to demand a human edit.
        return Result(False, "step %s/%s has a 'manual' demotion override; a coordinate cannot be added "
                             "without dropping it - edit manual_conditions.json by hand" % (guide_id, step_id))
    if isinstance(ov, dict):
        ov["world"] = world
    else:
        guide[step_id] = {"world": world}
    _save(conditions_path, data)
    return Result(True, "override written", target=conditions_path.name, key=guide_id + "/" + step_id)


def _plausible_guide_id(gid):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", gid or ""))


def _load(p):
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(p, data):
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    text = (Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1
            else sys.stdin.read())
    r = apply(text)
    if not r.applied:
        print("REFUSED: " + r.reason)
        sys.exit(1)
    print("Wrote %s -> %s" % (r.target, r.key))
    print("Now rebuild: py -3 tools/%s" % (
        "scrape_guide.py" if r.target == "manual_coords.json" else "build_raw_guide.py"))


if __name__ == "__main__":
    main()
