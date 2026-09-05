#!/usr/bin/env python3
"""Have the wiki-sourced guides drifted from their upstream pages?

osiris-ironman has a full re-scrape drift check; the OTHER guides were scraped from OSRS Wiki
pages once and frozen into tools/data/raw/*.json, so upstream edits are invisible. This check
fetches each wiki source page's raw wikitext, hashes it, and compares against the hashes stored
at the last (re-)scrape. A hash change is a LEAD — a human re-scrapes and runs the gates; the
route itself is never touched automatically.

Only wiki sources are covered (Google Sheets and external sites need different fetch mechanics
and are skipped, listed as SKIP so the gap stays visible).

Usage:
  py -3 tools/check_wiki_drift.py           # compare, exit 1 on drift (CI mode)
  py -3 tools/check_wiki_drift.py --seed    # record current upstream hashes as the baseline
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
RAW = DATA / "raw"
HASHES = DATA / "wiki_source_hashes.json"
UA = "GustavGuide-scraper/1.0 (+https://github.com/dangraagu/Gustav-s-helper; drift check)"
WIKI = "oldschool.runescape.wiki"

# Sources that no longer exist upstream. uim-prifddinas was scraped from the wiki's "Old Route
# Backup" page, which has since been deleted - our bundled copy IS the surviving backup, so there
# is nothing to drift against and a weekly 404 would be pure noise.
KNOWN_GONE = {"uim-prifddinas"}


def sources():
    out = {}
    for f in sorted(RAW.glob("*.json")):
        if f.stem.endswith("_SKIP"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        out[f.stem] = j.get("source", "")
    return out


def fetch_hash(url):
    raw_url = url + ("&" if "?" in url else "?") + "action=raw"
    req = urllib.request.Request(urllib.request.quote(raw_url, safe=":/?=&'"),
                                 headers={"User-Agent": UA})
    text = urllib.request.urlopen(req, timeout=30).read()
    return hashlib.sha256(text).hexdigest()


def main():
    seed = "--seed" in sys.argv
    stored = {}
    if HASHES.exists():
        stored = json.loads(HASHES.read_text(encoding="utf-8"))

    drifted, errors, current = [], [], {}
    for gid, src in sources().items():
        if WIKI not in src:
            print("SKIP  %-26s (non-wiki source)" % gid)
            continue
        if gid in KNOWN_GONE:
            print("SKIP  %-26s (upstream page deleted - bundled copy is the backup)" % gid)
            continue
        try:
            h = fetch_hash(src)
        except Exception as e:  # noqa: BLE001
            errors.append(gid)
            print("ERROR %-26s %s" % (gid, e))
            continue
        current[gid] = h
        if seed:
            print("SEED  %-26s %s" % (gid, h[:12]))
        elif gid not in stored:
            print("NEW   %-26s (no baseline - run --seed)" % gid)
            drifted.append(gid)
        elif stored[gid] != h:
            print("DRIFT %-26s upstream page changed since last scrape" % gid)
            drifted.append(gid)
        else:
            print("OK    %-26s" % gid)

    if seed:
        HASHES.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("baseline written -> %s" % HASHES)
        return
    if drifted:
        print("\n%d guide(s) drifted: %s" % (len(drifted), ", ".join(drifted)))
        print("Re-scrape the page (tools/scrape_wiki_guide.py), rebuild through the gates, "
              "then re-run with --seed.")
        sys.exit(1)
    if errors:
        # A fetch failure is not drift; do not fail the build over wiki availability.
        print("\n%d fetch error(s) - treated as inconclusive, not drift" % len(errors))
    print("no wiki drift")


if __name__ == "__main__":
    main()
