# Gustav's Helper — design spec

*Date: 2026-07-14. Status: approved, in build.*

## Goal
A standalone RuneLite plugin that walks a player through Oziris's ironman.guide route
(575+ steps, 7 sections) as one continuous, **auto-tracked** "quest," in the visual/UX
style of Quest Helper, reusing Quest Helper's rendering (BSD-2, attributed).

## Decisions (locked with the user)
1. **Tracking:** full auto-tracking via live game state; manual-advance fallback for
   steps the game can't detect.
2. **Authoring:** data-driven JSON + a condition engine (not hand-written Java per step).
3. **Scope:** all 575 steps are the target; engine is validated on real content first,
   then content is filled section by section.
4. **Reuse:** standalone plugin in its own repo; **adapt** Quest Helper's direction-arrow
   rendering + requirement display; do **not** use QH's per-quest varbit state machine
   (wrong model for a route).

## Architecture
Ordered list of `RouteStep` loaded from JSON. Each step has a boolean **completion
condition** (a small nested-JSON condition tree). A `ConditionEvaluator` reads game state
on `GameTick` and marks the current step complete + advances. Completion is **sticky**
(persisted), so a consumed item never un-completes a step. On login it **reconciles**:
any already-satisfied step is marked done so an existing account resumes correctly.

### Condition grammar (leaf ops + combinators)
- `skill` — `getRealSkillLevel(skill) >= level`
- `quest` — `Quest.getState(client) == state` (NOT_STARTED / IN_PROGRESS / FINISHED)
- `item` / `itemBank` / `itemEquipped` — container count `>= qty`
- `varbit` / `varp` — value compared with an operator (`=`, `>=`, `<=`, `>`, `<`)
- `qp` — quest points `>= n`
- `and` / `or` / `not` — combinators
- (no condition) + `"manual": true` — advances only via the panel button

### Components
- `GustavGuidePlugin` — lifecycle, event wiring, holds route + progression.
- `GustavGuideConfig` — mode (REGULAR/HCIM/UIM/GIM), auto-advance, overlay toggles, colour, hide-completed.
- `engine/` — `Route`, `RouteSection`, `RouteStep`, `Condition` (+ impls), `ConditionFactory`
  (JSON→Condition), `ConditionContext` (client + cached bank), `ConditionEvaluator`,
  `Progression` (current step, completed set, per-account persistence via `ConfigManager`).
- `requirement/` — `Requirement`, `ItemRequirement`, `SkillRequirement`, `QuestRequirement`
  (green/red display), adapted from Quest Helper.
- `overlay/` — `DirectionArrow` (adapted from QH), `GustavWorldOverlay` (world arrow + tile +
  object/NPC clickbox highlight), `GustavMinimapOverlay`, `GustavWidgetOverlay` (inventory item).
  Targets tracked via spawn/despawn events, not per-tick scene scans.
- `panel/` — `GustavGuidePanel` (sections, current step, requirements, Done/Skip, progress %,
  mode selector, search/jump), `StepPanel`.

### Data / content pipeline (`tools/`, build-time, not shipped)
Scraper pulls ironman.guide section pages → JSON step stubs (text + order). Enricher maps
quest names → `net.runelite.api.Quest`, parses skill targets, resolves item/NPC/object
names → ids. Gaps get `manual: true`. Human review fixes accuracy. Route JSON is bundled as
plugin resources; a later option can load an updated route from disk/URL.

## Testing
- Unit: condition engine (mock state → expected), progression (out-of-order, resume),
  schema validation (all JSON parses; quest/skill enums valid; ids numeric).
- Manual: launch dev client (`./gradlew run`); only the user can confirm in-game. A clean
  JVM start is **not** a passing functional test.

## Non-goals (v1)
- No reimplementation of ironman.guide's calculators (Drop Oracle, gear/money tools).
- Not on the RuneLite Plugin Hub yet (hub review + Oziris's OK needed first).
- No input automation of the game (ban risk).

## Risks
- **Content accuracy at scale** is the dominant ongoing effort; correct ids/coords/conditions
  are error-prone. Ships incrementally with `manual` fallback.
- RuneLite API drift (`latest.release`): compile-verify against the real client jar.

## Attribution / legal
Route credited to Oziris + ironman.guide; rendering/requirements credited to Quest Helper
(BSD-2). BSD-2 headers retained on adapted files. See `NOTICE`.
