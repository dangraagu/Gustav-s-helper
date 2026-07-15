# Osiris Guide — RuneLite plugin

A step-by-step Old School RuneScape **ironman progression helper**, in the style of
[Quest Helper](https://github.com/Zoinkwiz/quest-helper), that walks you through the
entire [ironman.guide](https://ironman.guide/) route as **one continuous, auto-tracked
"quest."** It shows the current step, points you where to go with world/minimap arrows,
highlights the NPC/object/item you need, lists requirements, and **auto-advances** as it
detects your skills, quests, items, and varbits changing.

> **Attribution.** The route is based on the guide by **Oziris** ([@OzirisLoL](https://twitter.com/ozirislol))
> and the community at ironman.guide. Rendering & requirement display are adapted from
> RuneLite **Quest Helper** (BSD-2-Clause). See [`NOTICE`](NOTICE). Not affiliated with
> Jagex, Oziris, or ironman.guide.

## How it works

- The route is a **data file** (`src/main/resources/com/osirisguide/data/route/*.json`) —
  an ordered list of steps, each with a description, an optional map location, requirements,
  and a **completion condition** (e.g. `skill:PRAYER>=43`, `quest:DRUIDIC_RITUAL=FINISHED`,
  `item:1059`, `varbit:1234=5`).
- A **condition engine** reads live game state each tick and marks steps complete, advancing
  to the next incomplete step automatically.
- Steps the game can't reliably detect are marked `"manual": true` and you tick them off.
- An **item ledger** (a **Ledger** tab) passively tracks, per guide-relevant item, how many you've
  **acquired**, **own**, and **spent** — read-only observation of `ItemContainerChanged`, exactly like
  Loot Tracker. This powers `itemAcquired` conditions, so "collect 5 swamp tar" stays complete even
  after you use them.
- Progress and the ledger are saved **per account** and reconcile on login, so an existing account
  skips everything it has already done.

**Plugin-Hub-legit by design:** no automation, no reflection, no runtime network calls, no extra
dependencies — see [`docs/HUB.md`](docs/HUB.md).

## Build & run (Windows)

1. **Install JDK 11** (required by RuneLite): double-click **`setup-jdk.bat`** (uses winget).
2. Build: `./gradlew build`
3. Launch a dev client with the plugin loaded: `./gradlew run` (or double-click **`run-osiris.bat`**).
   Log in following the [Using Jagex Accounts](https://github.com/runelite/runelite/wiki/Using-Jagex-Accounts) wiki.
4. Sideloadable jar: `./gradlew shadowJar` → `build/libs/osiris-guide-*-all.jar`.

> ⚠️ Only **you** can confirm in-game behaviour. Do not use input automation on RuneScape —
> it violates Jagex's third-party client rules and risks a ban.

## Status

See [`docs/STATUS.md`](docs/STATUS.md) for exactly what is implemented, what content is real
vs. stub, and what remains. The engine, overlays, panel, config, and tests are the stable
core; the 575-step content is transcribed from the guide and tightened over time.

## Config

Ironman mode (Regular / HCIM / UIM / GIM) filters mode-specific steps; toggles for
auto-advance, world arrow, minimap arrow, object/item highlight, arrow colour, and
hide-completed.

## Repo layout

```
setup-jdk.bat            JDK 11 bootstrap (winget)
run-osiris.bat           ./gradlew run launcher
build.gradle             RuneLite plugin build (Java 11, client provided-scope)
src/main/java/com/osirisguide/
  OsirisGuidePlugin.java   config, engine wiring, event handling
  engine/                  Route, RouteStep, Condition tree, evaluator, progression
  requirement/             requirement model (adapted from Quest Helper)
  overlay/                 world arrow, minimap arrow, highlights (adapted from Quest Helper)
  panel/                   side panel UI
src/main/resources/com/osirisguide/data/route/   route JSON, per section
src/test/java/com/osirisguide/                    engine + schema + progression tests
tools/                     guide scraper + enricher (build-time, not shipped)
docs/                      design spec + status
```

## License

BSD-2-Clause. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
