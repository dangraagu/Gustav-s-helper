# Automatic-feel for Gustav's Helper — design

Date: 2026-07-16 · Status: approved, building

## Goal
Make the guide feel automatic like Quest Helper: (1) every step is a single atomic task,
(2) steps auto-proceed when the player has actually done them, (3) NPC dialogue highlights the
option to choose. Everything below is hub-legit (data + engine + overlays — no reflection, no
runtime network, no runtime Quest-Helper dependency). Built on `main`; `fork/questhelper` inherits
via merge.

## Decisions (user)
- **Auto-advance for un-triggerable steps:** proximity + milestone-fold.
- **Dialogue highlight source:** harvest expected options from Quest Helper's source into a
  build-time DB; highlight the matching live option, else draw nothing (named-match only).
- **Atomization:** split at action/location boundaries (not one-line-per-imperative).

## Components

### 1. Build-time step splitter (`tools/scrape_guide.py`, reused by `build_raw_guide.py`)
Pre-pass that splits a raw step at action/location boundaries using an imperative-verb lexicon
(go/head/run/walk/talk/get/pick/buy/sell/mine/chop/fish/use/make/craft/kill/cast/equip/drop/
bank/withdraw/…) and connectors (`, then` / `;` / ` and ` before a new verb). Each atom flows
through the existing `build_step` (skill/quest/item/coord/entity detection) and gets a stable id
suffix (`-a/-b/-c`). Fragments without an action verb merge back into the previous atom, so the
list doesn't bloat. All 5 guides regenerated. `everyBundledGuideParses` guards structure. Fail-safe:
a mis-split atom degrades to a manual step, never a wrong auto-skip.

### 2. Position condition (new engine op)
- `engine/condition/PositionCondition(WorldPoint target, int radius)` — met when the player is on
  the same plane and within `radius` tiles (Chebyshev) of `target`.
- `ConditionContext.playerLocation()` — exposes `client.getLocalPlayer().getWorldLocation()`.
- `ConditionFactory` op `"position"`/`"reached"`: `{x,y,z,radius}` (radius default 8).
- Scraper attaches it as the completion trigger **only to pure-travel atoms** (leading verb
  go/head/run/walk/travel/enter/climb) using the atom's resolved WorldPoint (wider radius for
  area-centre coords). Talk/get/do atoms keep their action trigger or stay manual — proximity
  alone must not complete them (player might walk past).

### 3. Milestone-fold (`engine/Progression`)
After the normal evaluation pass: find the furthest-reached completed applicable step; auto-complete
every **manual** (`isManual()`) incomplete step *before* it — you can't reach a later milestone
without passing the flavor steps. A step with its own **unmet real trigger** is never folded (must
not skip real work). Config-gated (on by default with auto-advance).

### 4. Dialogue DB from Quest Helper (`tools/data/qh_dialogue.py` → `data/qh_dialogue.json`)
Parse QH source (vendored on the fork) for dialogue choices: `.addDialogStep(s)`,
`DialogChoiceStep`, dialog-option widget highlights. Emit
`{ questConst: { npcName: ["expected option", …] } }` plus a global `npc → [options]` fallback.
Same harvest pattern as `qh_entities.json`; attributed in NOTICE. Pure data, ships in both builds.

### 5. Dialogue-option overlay (`overlay/DialogueOverlay`)
When the NPC dialogue-options widget is open, look up the current step's quest/NPC in the DB and
highlight the live option row whose text matches an expected string (normalised equals/contains, in
the config highlight colour). No entry / no confident match → draw nothing. Highlight-only, not an
auto-advance trigger. On the fork, quest-step dialogue is left to QH (avoid double-highlight); our
overlay covers non-quest steps + the whole `main` build.

## Data flow
- **build:** raw guide → split atoms → per atom detect trigger + coord + dialogue-key → JSON;
  separately QH source → `qh_dialogue.json`.
- **runtime:** GameTick → `Progression.process` (skill/quest/item/varbit/**position**) →
  **milestone-fold** → current step → overlays (arrow/tile/npc/object/item + **dialogue**).

## New config
`dialogueHighlight` (on/off), `arrivalRadius` (default 8). `autoAdvance` already defaults on.

## Testing (TDD)
- `PositionCondition`: inside/outside radius, wrong plane, null player.
- `ConditionFactory`: parses `"position"`; bad fields → MANUAL.
- `Progression`: folds manual steps behind a reached milestone; does NOT fold an earlier step with
  an unmet real trigger; fold off ⇒ old behaviour.
- Splitter (Python): multi-action strings → expected atoms; non-action fragment merges back.
- Dialogue extractor (Python): QH snippet → expected options.
- Dialogue match logic (Java): expected + live option texts → highlighted index (or none).
- `everyBundledGuideParses` after regeneration.

## Scope / files
- New: `engine/condition/PositionCondition.java`, `overlay/DialogueOverlay.java`,
  `resources/.../data/qh_dialogue.json`, `tools/data/qh_dialogue.py`.
- Modified: `ConditionFactory`, `ConditionContext`, `Progression`, `OsirisGuidePlugin`
  (register overlay + provide step quest/NPC context), `OsirisGuideConfig`, `RouteStep`
  (dialogue-key field), `scrape_guide.py` / `build_raw_guide.py` (splitter + position/dialogue-key),
  `NOTICE`.
- Built on `main`; merged to `fork/questhelper` (resolve overlay/QH double-highlight there).
