# Status — what's real vs. what's next

*Last updated: 2026-07-15. Honest accounting, not a wishlist.*

## ✅ Built, compiles, unit-tested (13 tests green)

- **Condition engine** — data-driven boolean conditions: `skill`, `quest`, `item`/`itemBank`/`itemEquipped`,
  `varbit`, `varp`, `qp`, and `and`/`or`/`not` combinators, plus `manual`. Fail-safe parsing (a bad
  condition degrades to manual, never crashes, never false-completes).
- **Progression** — ordered route, current-step tracking, auto-advance, **sticky** completion,
  out-of-order completion, login **reconcile** (an existing account resumes at the right place),
  mode filtering (Regular/HCIM/UIM/GIM), progress %, **per-account persistence** via ConfigManager.
- **Overlays** — world arrow + destination tile outline, minimap arrow, object/NPC clickbox highlight.
  Direction-arrow rendering adapted from Quest Helper (BSD-2, attributed). Targets tracked via
  spawn/despawn events + a one-time scene scan on step change (not per tick).
- **Side panel** — overall progress bar, current step (section, instruction, requirements green/red),
  Done / Skip / Reset buttons, wiki link, short lookahead of upcoming steps.
- **Config** — mode, auto-advance toggle, per-overlay toggles, highlight colour, hide-completed.
- **Build** — `./gradlew build` green; `./gradlew shadowJar` produces a sideloadable jar; `./gradlew run`
  launches a dev client with the plugin loaded.

## 📋 Content — all 575 steps present

- Scraped from ironman.guide's schema.org `HowTo` structured data (`tools/scrape_guide.py`), all **7
  sections** in the guide's own order (1.1 → 2.0, plus the optional Sailing track):
  Early Game (286), Thieving/Fishing/Mining (33), Fairy Rings/Prayer/Kingdom (111),
  Skilling/Graceful (50), Diaries & RFD (21), After Barrows Gloves (63), Sailing (11) = **575**.
- Each step has the real instruction text, a location note where the guide gives one, and a wiki link
  where present.

## ⚠️ Known limitations (the honest part)

1. **Auto-detection is partial: 39 / 575 steps.** Only clear skill-training targets ("…until 77 herb")
   are auto-detected so far. The other **536 steps are manual-advance** (tick them in the panel). The
   guide's steps are very granular ("pick up 2 cheese", "bank 7 logs") and the source data exposes no
   machine-checkable state for them, so reliable auto-completion needs per-step **enrichment** (mapping
   quests → `net.runelite.api.Quest`, items → ids, adding varbits). This was the risk called out in the
   design; it is expected, not a regression. Turn off "Auto-advance" in config if a heuristic ever
   mis-fires.
2. **Arrows are dormant until steps get coordinates.** The guide gives location *names* ("Lumbridge"),
   not tile coordinates, so world/minimap arrows and object/NPC highlights only appear once a step is
   enriched with a `world` point / `npc` / `object` id. The overlay code is built and works when the
   data has them.
3. **Not verified in-game.** Per RuneLite's own guidance, only a human can confirm in-game behaviour, and
   automating the game client is a bannable offence — so I did **not** and **will not** drive RuneScape.
   A clean build + passing unit tests is **not** a functional in-game test.
4. **Not on the Plugin Hub.** Runs from source / sideload. Hub submission needs review and, ideally,
   Oziris's OK for the route content.

## Enrichment path (how auto-detection + arrows improve)

Edit the section JSON under `src/main/resources/com/osirisguide/data/route/`:
- add `"complete": { "op": "quest", "quest": "COOKS_ASSISTANT", "state": "FINISHED" }` (or `item`/`varbit`)
  to make a step auto-complete;
- add `"world": [x, y, plane]` and/or `"npc": <id>` / `"object": <id>` to light up arrows/highlights;
- or extend `tools/scrape_guide.py`'s enricher to do it in bulk.
Then rebuild. `RouteLoaderTest` validates the JSON on every build.

## Attribution

Route by **Oziris** (@OzirisLoL) / ironman.guide. Rendering & requirements adapted from
**Quest Helper** (BSD-2, Zoinkwiz). See [`../NOTICE`](../NOTICE). Not affiliated with Jagex.
