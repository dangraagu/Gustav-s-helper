"""Tests for check_wiki_drift's pure logic (no network — the fetch path is CI-only).

Pins the two deploy-gate findings:
  - the wiki-host gate must be a hostname parse, not a substring check (SEC-LOW-1:
    "https://evil.example/oldschool.runescape.wiki" must not pass)
  - --seed must MERGE into the stored baseline, not replace it (CORR-3: a guide whose
    fetch errors during seeding must keep its old baseline, not silently lose it)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_wiki_drift import _is_wiki, _merge_baseline  # noqa: E402

failures = []


def check(name, cond):
    if cond:
        print("ok   %s" % name)
    else:
        failures.append(name)
        print("FAIL %s" % name)


check("real wiki page passes",
      _is_wiki("https://oldschool.runescape.wiki/w/Ultimate_Ironman_Guide"))
check("wiki with query passes",
      _is_wiki("https://oldschool.runescape.wiki/w/X?veaction=edit"))
check("path-embedded host does NOT pass",
      not _is_wiki("https://evil.example/oldschool.runescape.wiki"))
check("suffix-spoofed host does NOT pass",
      not _is_wiki("https://oldschool.runescape.wiki.evil.com/w/X"))
check("empty / junk source does NOT pass",
      not _is_wiki("") and not _is_wiki("Google Sheets export") and not _is_wiki(None))

check("seed merges: fetched hash updates its entry",
      _merge_baseline({"a": "old", "b": "keep"}, {"a": "new"}) == {"a": "new", "b": "keep"})
check("seed merges: errored guide keeps its old baseline",
      _merge_baseline({"a": "old"}, {}) == {"a": "old"})
check("seed merges: brand-new guide is added",
      _merge_baseline({}, {"c": "h"}) == {"c": "h"})

print()
if failures:
    print("%d FAILURES: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("all wiki-drift checks passed")
