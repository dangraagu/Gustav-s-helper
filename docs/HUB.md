# Plugin Hub compliance

This documents why Osiris Guide is safe to submit to the [RuneLite Plugin Hub]
(https://github.com/runelite/plugin-hub). The hub reviews for **security** and **Jagex-rule
compliance**; the design below is deliberately conservative so a reviewer can verify it quickly.

## Game-rule compliance (no automation)

- The plugin **never controls the game**: no mouse/keyboard input, no menu invocation, no
  packet sending, no `MenuOptionClicked` injection. It only **reads** game state.
- All game reads go through the official RuneLite API: `GameTick`, `ItemContainerChanged`,
  `GameObjectSpawned/Despawned`, `NpcSpawned/Despawned`, `GameStateChanged`, and getters like
  `getRealSkillLevel`, `Quest.getState`, `getVarbitValue`, `getItemContainer`, `getScene`.
- The **item ledger** is passive bookkeeping over `ItemContainerChanged` snapshots — the same
  mechanism used by hub-approved plugins such as Loot Tracker, Bank Tags, and Inventory Setups.
  It records what you obtained/spent; it does not act.
- No input automation of any kind. Following the guide is entirely manual play; the plugin only
  shows where you are and marks steps done from observed state.

## Security

- **No reflection in plugin code.** No `java.lang.reflect` usage, no `setAccessible`,
  `getDeclaredField/Method`, or `Class.forName`. (Persistence is plain Gson on a small state class.)
- **No native code**, no `ProcessBuilder`/`Runtime.exec`, no external program execution.
- **No runtime network access.** The route is bundled as JSON resources in the jar; the plugin
  makes **zero** HTTP/socket calls at runtime. (The `tools/` scraper runs only at build time on a
  developer machine and is not shipped.) Because nothing is sent to any third party, no
  data-disclosure config warning is required.
- **No third-party runtime dependencies.** Compile-time only: `net.runelite:client` (provided) and
  Lombok (annotation processor — not present in the compiled bytecode). Test-only: JUnit, Mockito, and
  `net.runelite:jshell`. Nothing third-party ships inside the plugin.
- **File I/O:** none outside RuneLite's own storage — progress and the ledger are saved via
  `ConfigManager` (per-account keys). No writes outside `.runelite`.
- **Java only.** No Kotlin/Scala. Licensed **BSD 2-Clause** (`LICENSE`), as the hub requires.

## Attribution

Adapted arrow rendering + requirement display credit **Quest Helper** (BSD-2) in the affected
files and `NOTICE`. The **route content** is **Oziris's** guide (ironman.guide). The code and
behaviour are fully hub-compliant; the remaining item for a public hub release is the guide
author's blessing to redistribute the route text — a permission matter, not a code one.
