# Helper tools

Scripts used while making the app, kept here so any later session has them. None of them run
during the app build.

## Zizo's voice (Gemini, voice "Puck")

Every sentence the app says is a recording in `www/voice/<id>.mp3`; `www/voice/index.json` maps the
sentence (without vowel marks) to its file. The `id` is `<lang>-<crc32 of the sentence>`, so the
same sentence always keeps the same file name.

To add or re-record sentences:

1. **List them.** `python3 tools/voice_phrases.py . <engine-settings.json> voice/phrases-gemini-<name>.json`
   collects every sentence the app can say. For a handful of new sentences it is simpler to write
   a small list by hand in the same shape as `voice/phrases-gemini.json` (copy its `engine` and
   `gemini` settings, then `items`: `{id, lang, text (with vowel marks), key}`), and to add the same
   items to `voice/phrases-gemini.json`, the master list.
2. **Record them in the owner's Google Cloud Shell** (it is signed in to their Google account; the
   Gemini key lives there in `~/.config/zizo-voice/key` and nowhere else):
   ```
   cd ~/huroof-zizo && git pull
   python3 scripts/gemini_voice.py voice/phrases-gemini-<name>.json out
   cloudshell download out.zip
   ```
   The free quota is about 10 requests a day per model (12 sentences per request) and resets at
   07:00 UTC. A stopped run continues where it stopped when started again.
3. **Cut the batches into sentences:** `python3 tools/voice_split.py <unzipped out> <wav_dir>`
   (prints a duration-per-letter check; a sentence that is much too long or short was cut wrong).
4. **Check by ear and with Whisper:** `python3 tools/voice_qa_push.py <wav_dir> voice-qa-<n>` pushes
   the clips to a branch and the "Check Zizo's voice" workflow scores each one (`qa.tsv` on that branch).
5. **Install:** `python3 tools/voice_finish.py . voice/phrases-gemini.json gemini-puck <wav_dir>`
   levels every clip to the same loudness, writes the MP3s and rewrites `www/voice/index.json`.
6. Run `tests/test_voice.py`: it must report 0 sentences without a recording.

Children's names are recorded as `name:<name without vowel marks>` → "يا <name>", and inserted
between the recordings around them; a name that was never recorded is said by the phone's voice.

## Pictures

- `render_assets.py <project_dir>`: the app icon, splash screens and Play Store graphics.
- `store_shots.py <project_dir>`: the eight Play Store screenshots (1080×2160) with example data.
- `voice_reel.py`: joins a few recordings into one MP3 to listen to.
