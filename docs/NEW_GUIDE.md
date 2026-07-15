# Adding a new guide

The plugin bundles multiple guides and lets the player pick one in **Config → Osiris Guide →
Guide**. Progress and the item ledger are tracked **separately per guide** (keys are namespaced by
guide id). Everything except the route data and the source-extractor is reused across guides:

- **Reused (guide-agnostic):** the whole plugin engine (condition engine, overlays, ledger, panel,
  RouteLoader) and every enricher — skill / quest / item(+total-needed) detection, the location
  gazetteer + wiki coords, and the Quest-Helper NPC/object id+tile references.
- **Per-guide:** the route JSON under `data/guides/<id>/`, plus the scraper's source config (and, if
  the source site isn't schema.org `HowTo`, its HTML extractor).

## Steps

1. **Pick an id** — a folder-safe slug, e.g. `osiris-ironman`, `some-skiller-guide`.

2. **Scrape it.** In `tools/scrape_guide.py`, set the guide config block:
   ```python
   GUIDE_ID  = "your-guide-id"
   GUIDE_URL = "https://example.com/guide/{slug}"   # {slug} filled per section
   SECTIONS  = [ ("01", "slug", "Display Name", "prefix"), ... ]
   ```
   Then `py -3 tools/scrape_guide.py`. It writes `data/guides/<GUIDE_ID>/`.
   - The extractor (`extract_howto_steps`) reads schema.org `HowTo` JSON-LD. If the new source
     uses a different structure, adapt that one function; the rest of the pipeline is unchanged.
   - The shared enrichers run automatically — no per-guide work.

3. **Register it** in two places:
   - `src/main/resources/com/osirisguide/data/guides.json` — add `{ "id", "name", "description" }`.
   - `src/main/java/com/osirisguide/Guide.java` — add an enum value:
     `YOUR_GUIDE("your-guide-id", "Your Guide Name")`.

4. **Build** (`./gradlew build`). The guide now appears in the picker. Selecting it live reloads the
   route + that account's per-guide progress/ledger.

## Notes
- Quest detection needs `tools/data/quest_names.json` (RuneLite Quest enum); coords use
  `tools/data/location_coords.json`; NPC/object ids use `tools/data/qh_entities.json`. These are
  shared build inputs — regenerate them only when RuneLite / Quest Helper change.
- Keep `main` as the reference guide; there is no per-guide branch — all guides ship in one plugin.
