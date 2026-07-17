# Submitting Gustav's Helper to the RuneLite Plugin Hub

Short, do-it-once checklist. The Hub does NOT host your code — it just points at *your*
GitHub repo at a specific commit. Reference: <https://github.com/runelite/plugin-hub/blob/master/README.md>

## 0. One-time prep (already done in this repo)
- `runelite-plugin.properties` present with `displayName`, `author`, `description`, `tags`,
  `plugins=com.gustavguide.GustavGuidePlugin`, `build=standard`.
- `LICENSE` (BSD-2), `NOTICE` (attributions), no reflection / no runtime network, deps are `compileOnly`.
- Builds clean: `./gradlew jar` produces `build/libs/gustav-guide.jar`.

## 1. Make sure the exact commit you want to publish is pushed
```
git checkout main
git pull
git rev-parse HEAD        # <-- copy this FULL 40-char SHA; it's what the Hub pins
```
The Hub builds this precise commit. Anything not pushed to `dangraagu/Osiris-guide` won't build.

## 2. Fork the plugin-hub repo
- Go to <https://github.com/runelite/plugin-hub> → **Fork**.
- Clone your fork:
```
git clone https://github.com/<you>/plugin-hub.git
cd plugin-hub
```

## 3. Add ONE manifest file
Create a file named after the plugin (no extension), e.g. `plugins/gustav-helper`, containing:
```
repository=https://github.com/dangraagu/Osiris-guide.git
commit=<the 40-char SHA from step 1>
```
That's the whole file — two lines.

## 4. Commit + push to your fork, open the PR
```
git checkout -b add-gustav-helper
git add plugins/gustav-helper
git commit -m "Add Gustav's Helper"
git push -u origin add-gustav-helper
```
Open a PR from your fork's branch against `runelite/plugin-hub:master`.

## 5. What the reviewers check (so expect questions on)
- The plugin builds and passes their CI (no reflection, no bundled other-plugin code, deps hash-verify).
- **Content/licensing**: this plugin bundles third-party guide text (Oziris's ironman.guide,
  OSRS Wiki CC BY-NC-SA guides, Max's community sheets). Be ready to show permission / that the
  licences allow redistribution with attribution (see `NOTICE`). This is the most likely gating question.
- No "duplicate functionality" — whole-account ironman-route progression is distinct from Quest Helper.

## 6. To update later
Push new commits to `main`, then edit the `commit=` line in your plugin-hub manifest to the new SHA
and push — the Hub rebuilds.

---
Current `main` HEAD when this doc was written: run `git rev-parse HEAD` for the live value.
