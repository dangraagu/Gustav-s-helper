# Status — what's real vs. what's next

*Last updated: 2026-09-05. Honest accounting, not a wishlist.*

## ✅ Live on the RuneLite Plugin Hub

Installable from the in-client Plugin Hub since 2026-07-30; current hub release pins `dedaf62`.
Every release ships through the same gates: 83 Java tests (including a fresh-account invariant that
proves a brand-new account auto-completes **nothing** in any guide × mode), 8 Python suites for the
route-builder matchers (over 1,000 assertions), and a duplicate-arrival lint that fails the build if
the waypoint pattern behind the old mass-fold bug ever reappears.

## 📋 Content — 15 guides, 6,583 steps

| Source | Guides |
|---|---|
| ironman.guide (Oziris) | osiris-ironman (network-scraped) |
| OSRS Wiki | B0aty HCIM V3, UIM→Prifddinas (current + old-route backup), UIM PvM Route, Optimal Quest (Ironman), Ironman PvM Rush, F2P Champions' Guild speedrun |
| BRUHsailer | bruhsailer |
| heboxjonge | 6 alt/max routes |

- **45% of steps auto-complete** (quest / skill / item-ledger / arrival / diary conditions); the rest
  are manual-advance. Coverage grows only where a condition is safe by construction — a wrong
  auto-complete is treated as worse than a manual click.
- Coordinates are matched whole-word against wiki-grounded gazetteers, amenities, and Quest Helper
  tiles; ~200 human-verified overrides beat every automatic layer.
- **Drift watchdogs**: a weekly GitHub Action re-scrapes ironman.guide and hashes the six wiki source
  pages against a seeded baseline, opening an issue when upstream edits invalidate bundled data.

## ✅ Features

- Condition engine (skill/quest/item/itemAcquired/itemConsumed/varbit/varp/qp/diary/position +
  and/or/not; a bad condition degrades to manual, never crashes, never false-completes).
- Passive item ledger (read-only `ItemContainerChanged` observation, per-tick net accounting).
- Progression with sticky completion, login reconcile, Undo, user-confirmed ⏩ fast-forward, and
  per-guide + per-account persistence.
- Overlays: world/minimap arrows, tile + NPC/object highlight, dialogue-option highlight, inventory
  item highlight, on-screen current-step text.
- Panel: progress, current step with requirements, upcoming steps, step number, per-step user notes,
  completes-when tooltip, wiki link.
- **Opt-in step reports** (default OFF; Plugin Hub requirement): with the toggle enabled and the
  preview confirmed, a report goes to a forwarding endpoint we control — optionally with the
  player's own tile attached as the proposed fix, which maintainers apply directly via
  `tools/apply_report.py`.
- Shortest Path integration (plugin-message bus), birdhouse-run reminder.

## ⚠️ Known limitations (the honest part)

1. **~55% of steps are manual-advance.** The guides' steps are granular and often expose no
   machine-checkable state; coverage grows only through safe-by-construction conditions and
   human-verified overrides.
2. **Not verified in-game by the maintainer.** Automating the game client is bannable, so in-game
   behaviour rests on human spot-checks and player reports. A clean build + green tests is not a
   functional in-game test.
3. **Long multi-action steps** in some guides remain single steps; splitting them further is a
   judgment call deferred until someone reads them in-game.
4. **9 known duplicate-arrival waypoints** are accepted deliberately (revisit-a-town steps complete
   on the revisit); the lint pins the list so no new ones slip in.

## Enrichment path

Per-step fixes: `tools/data/manual_coords.json` (osiris, keyed by exact step text) and
`tools/data/manual_conditions.json` (raw-built guides, keyed by guide + step id) beat every automatic
layer — or paste a player report into `tools/apply_report.py`. Bulk improvements go into
`tools/scrape_guide.py`'s enrichers, guarded by the Python suites. Rebuild with
`py -3 tools/build_raw_guide.py` (osiris: `py -3 tools/scrape_guide.py`); `gradlew check` runs every gate.

## Attribution

Routes by **Oziris** (@OzirisLoL, ironman.guide), **B0aty**, the **OSRS Wiki** community,
**BRUHsailer**, and **heboxjonge**. Rendering & requirements adapted from **Quest Helper**
(BSD-2, Zoinkwiz). See [`../NOTICE`](../NOTICE). Not affiliated with Jagex.
