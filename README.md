# Gustav's Helper — RuneLite plugin

A step-by-step Old School RuneScape **ironman progression helper**, in the style of
[Quest Helper](https://github.com/Zoinkwiz/quest-helper), that walks you through the
entire [ironman.guide](https://ironman.guide/) route as **one continuous, auto-tracked
"quest."** It shows the current step, points you where to go with world/minimap arrows,
highlights the NPC/object/item you need, lists requirements, and **auto-advances** as it
detects your skills, quests, items, and varbits changing.

> **Attribution.** Each bundled route is the work of its authors, used here for a companion tool:
> **Oziris** ([@OzirisLoL](https://twitter.com/ozirislol)) and the **ironman.guide** community (the
> default route); **B0aty** (HCIM guide); **BRUHsailer**; **heboxjonge** (the alt routes); and the
> **OSRS Wiki** (the UIM→Prifddinas walkthroughs, Optimal Quest, and PvM Rush — CC BY-NC-SA 3.0).
> Direction-arrow rendering & requirement display are adapted from RuneLite **Quest Helper**
> (BSD-2-Clause). See [`NOTICE`](NOTICE) for full per-guide sources and licenses. Not affiliated with or
> endorsed by Jagex, Oziris, ironman.guide, B0aty, BRUHsailer, heboxjonge, or the OSRS Wiki.

> **Want another guide added?** Open a [GitHub issue](https://github.com/dangraagu/Gustav-s-helper/issues)
> suggesting the guide (link + author) and it can be considered for a future release.

## How it works

- The route is a **data file** (`src/main/resources/com/gustavguide/data/route/*.json`) —
  an ordered list of steps, each with a description, an optional map location, requirements,
  and a **completion condition** (e.g. `skill:PRAYER>=43`, `quest:DRUIDIC_RITUAL=FINISHED`,
  `item:1059`, `varbit:1234=5`).
- A **condition engine** reads live game state each tick and marks steps complete, advancing
  to the next incomplete step automatically.
- Steps the game can't reliably detect are marked `"manual": true` and you tick them off.
- An **item ledger** (a **Ledger** tab) passively tracks, per guide-relevant item, how many you've
  **acquired**, are **carrying**, **moved to the bank**, and **used/dropped** — so you can see what
  became of everything you collected. It's read-only observation of `ItemContainerChanged`, exactly
  like Loot Tracker (the plugin never moves or touches your items). This also powers `itemAcquired`
  conditions, so "collect 5 swamp tar" stays complete even after you use them.
- Progress and the ledger are saved **per account** and reconcile on login, so an existing account
  skips everything it has already done.

**Plugin-Hub-legit by design:** no automation, no reflection, no runtime network calls, no extra
dependencies — see [`docs/HUB.md`](docs/HUB.md).

## Build & run (Windows)

1. **Install JDK 11** (required by RuneLite): double-click **`setup-jdk.bat`** (uses winget).
2. Build: `./gradlew build`
3. Launch a dev client with the plugin loaded: `./gradlew run` (or double-click **`run-gustav.bat`**).
   Log in following the [Using Jagex Accounts](https://github.com/runelite/runelite/wiki/Using-Jagex-Accounts) wiki.
4. Sideloadable jar: `./gradlew shadowJar` → `build/libs/osiris-guide-*-all.jar`.

> ⚠️ Only **you** can confirm in-game behaviour. Do not use input automation on RuneScape —
> it violates Jagex's third-party client rules and risks a ban.

## Status

See [`docs/STATUS.md`](docs/STATUS.md) for exactly what is implemented and what remains. The
engine, overlays, panel, config, and tests are the stable core; the content — 15 guides,
6,500+ steps — is scraped from its sources and tightened over time, with weekly drift checks
against the upstream pages.

## Config

Ironman mode (Regular / HCIM / UIM / GIM) filters mode-specific steps; toggles for
auto-advance, world arrow, minimap arrow, object/item highlight, arrow colour,
hide-completed, and the on-screen step text overlay.

### Step reports are opt-in (default OFF)

The "Report wrong / missing info" button does nothing until you enable
**Enable step reports** in the plugin config and accept RuneLite's warning dialog —
a Plugin Hub requirement for any plugin that talks to a third-party server. Once
enabled, a report sends only guide data (guide, step id, step text, the tile and ids
the plugin pointed at) plus what you type; never your name, account, or position —
unless you tick **Attach my position** on a specific report, which adds your current
tile as the proposed fix. Standing where the step actually happens and attaching your
position is the single most useful report you can send: maintainers apply it directly
with `tools/apply_report.py`.

### Other quality-of-life

- **✎ Note** — your own note on the current step, saved per guide and account.
- **⏩ Sync** — offers to mark earlier note/travel steps done when your account
  already has the progress behind them; shows the count and asks first, Undo takes
  it back.
- Hover the step text to see exactly what will auto-complete it.

## Repo layout

```
setup-jdk.bat            JDK 11 bootstrap (winget)
run-gustav.bat           ./gradlew run launcher
build.gradle             RuneLite plugin build (Java 11, client provided-scope)
src/main/java/com/gustavguide/
  GustavGuidePlugin.java   config, engine wiring, event handling
  engine/                  Route, RouteStep, Condition tree, evaluator, progression
  requirement/             requirement model (adapted from Quest Helper)
  overlay/                 world arrow, minimap arrow, highlights (adapted from Quest Helper)
  panel/                   side panel UI
src/main/resources/com/gustavguide/data/route/   route JSON, per section
src/test/java/com/gustavguide/                    engine + schema + progression tests
tools/                     guide scraper + enricher (build-time, not shipped)
docs/                      design spec + status
```

## License

BSD-2-Clause. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
