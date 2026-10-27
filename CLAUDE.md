# Zizo World (عالم زيزو) — notes for Claude

An Android app for children aged 4–6 in Iraq, hosted by Zizo the elephant: Arabic and English
letters and numbers, colors, shapes, animals, food, the body, jobs, games, tracing letters with a
finger, audio stories for every letter, and a shop where stars buy Zizo hats and scarves.

## Working with the owner

- Talk to the owner in Arabic (they write in Iraqi dialect), in plain words. They are not a
  programmer and cannot do technical steps themselves: do the work, then tell them what changed and
  give them the download link of the new test app.
- After every change that reaches the app: run the tests, push to `main`, wait for the "Build
  Android app" workflow, and send the link:
  https://github.com/zwyd4583-jpg/huroof-zizo/releases/download/test-build/zizo-world-test.apk
- When something is only checked in the phone simulation (not on a real phone), say so.

## Layout of the repository

- `www/index.html` — the whole app in one file (~3,700 lines): styles at the top, the markup, then
  one script. No build step, no framework. `www/fonts/` (Baloo Bhaijaan 2 for the interface, Noto
  Naskh Arabic for letters), `www/voice/` (926 recordings + `index.json`).
- `capacitor.config.json`, `package.json` — Capacitor 8 wraps the page as an Android app.
  Plugins: `@capacitor/app` (back button), `@capacitor-community/text-to-speech` (the phone's voice,
  only for children's names that have no recording).
- `scripts/prepare-android.sh` — creates the Android project in CI, then `patch_android.py`
  (version, signing, portrait, the "fast" build type) and `patch_tts.py` (the speech engine starts
  on first use instead of at launch, so it does not slow the opening).
- `android-overlay/` icons and splash; `store/` Play Store graphics and `listing-ar.md`.
- `voice/` recording lists (`phrases-gemini.json` is the master list); `scripts/gemini_voice.py`
  records them; `tools/` cuts, checks and installs them — see `tools/README.md`.
- `tests/` phone-simulation tests and speed measurements — see below.

## Building and releasing

- Every push to `main` runs `.github/workflows/android.yml`: `assembleFast` (built like the store
  build, not debuggable, so it runs at full speed) signed with `ci/debug.keystore`, so each test
  version installs over the last and keeps the child's stars and name. The APK replaces the asset
  of the release `test-build`.
- The Play Store build (`bundleRelease`) needs the secrets `KEYSTORE_BASE64` and
  `KEYSTORE_PASSWORD`; they are not set yet. The upload key (`upload.jks`) and its password are kept
  by the owner. **The repository is public: never commit a keystore, password, API key or token.**
  The Gemini key exists only in the owner's Google Cloud Shell (`~/.config/zizo-voice/key`).
- Not done yet: publishing on Google Play, testers, earning money, an iPhone version.

## How the app speaks

- `say(parts, done)` says a sentence or a list of parts; `done` runs when it has been said.
  `playClips` plays the recordings; `clipsFor` finds them; a missing recording falls back to the
  phone's voice. `hush()` stops everything (called when the child moves on).
- `sayThenTimer` moves to the next question only after the praise has been said (praise must never
  be cut off).
- Names: `nameParts` puts the recorded "يا <name>" (`name:<plain name>` in `index.json`) between the
  recordings around it.
- `warm(parts)` fetches and decodes recordings ahead of time (next letter, next page, the answer's
  praise while the question is asked) so the voice starts right away.
- Every sentence the app says must have a recording: `tests/test_voice.py` plays through the whole
  app and must report 0 sentences without one. New sentences need recording (see `tools/README.md`).

## Smoothness rules (learned the hard way on Android)

- Animate only `transform` and `opacity`, and give each element at most one transform animation at
  a time (two on one element cannot run on the graphics chip; use a wrapper element).
- No animations inside SVG drawings on busy screens, and do not rebuild Zizo's SVG mid-animation:
  the opening draws all poses once and fades between them.
- Never read layout (`getBoundingClientRect`, `offsetWidth`) to restart an animation: use `replay()`.
- No `background-attachment: fixed` (Android repaints on every scroll); the sky and hills are fixed
  pseudo-elements on `body`.
- Do not change inherited custom properties on `body` at runtime (the whole page restyles); section
  colors (`--sc`, `--scd`) are set on the `#v-*` sections in CSS.
- Blurred shadows only on a few large surfaces (`--lift`); small tiles use solid shadows.
- The opening waits for fonts, the greeting's recording and calm frames (`whenCalm`) before moving.
- Measure with `tests/perf.py 6` (CPU slowed 6×), `tests/perf_intro.py`, and
  `tests/probe_composite.py` (every animation should run on the graphics chip).

## Look and feel

Zizo's world: sky with clouds and green hills behind every screen, as in the opening. Letters and
numbers are colored toy blocks (darker inner bottom edge, white letter). Everything pressable has
that chunky edge; surfaces (cards, Zizo's bubble, the drawing board) lie flat with the soft `--lift`
shadow. Each section has its color: letters orange, numbers purple, discover teal, play green,
trace pink, stories blue (bottom bar: `--tc`, `--tcd`, `--ts`).

## Testing

```
pip install playwright        # once; python3 -m playwright install chromium if no browser is found
python3 tests/run.py          # the everyday set (~30 min, mostly test_voice); "quick" skips test_voice
python3 tests/run.py test_cheer test_praise
python3 tests/perf.py 6       # speed on a slow phone: stutters, long tasks, voice start delay
python3 tests/shots_all.py after   # pictures of every screen in tests/out/design/
```
`tests/run.py` starts the local server (`www/` on 127.0.0.1:8765) when needed; run the other
scripts with that server up. A test passes when it ends with "no problems". The page's test hooks
are on `window.__zizoTest` (e.g. `target()`, `played`, `missing`, `cheers`, `introDone()`);
`tests/common.py` fakes the Android side. `test_en_shop`, `test_new` and `test_sfx` follow the
phone's voice, so they hide the recordings on purpose.

The voice delays that `perf.py` prints include Playwright's own wait before a click (about 80–200 ms);
`perf_next.py` measures inside the page, where the voice starts within a few milliseconds of a tap.
Before a release, also look at a few screens (`shots_all.py`) — the owner judges by how it looks.
