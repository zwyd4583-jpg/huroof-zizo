"""Record the app's sentences with a Gemini voice from Google, inside Google Cloud Shell.

Cloud Shell is already signed in to the owner's Google account, so nothing has to be pasted:
    git clone --depth 1 https://github.com/zwyd4583-jpg/huroof-zizo && cd huroof-zizo
    python3 scripts/gemini_voice.py voice/samples-gemini.json out
    cloudshell download out.zip

Only the Python standard library is used. Each sentence becomes out/<voice>/<id>.wav (24 kHz mono).
The run can be repeated: sentences already recorded are skipped, so after a daily-quota stop
it carries on from where it stopped.
"""
import base64, io, json, os, pathlib, subprocess, sys, time, urllib.error, urllib.request, wave, zipfile

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Gemini 3.8 TTS uses the Interactions API: the text is read verbatim and the delivery goes in "style"
INTERACTIONS = "https://generativelanguage.googleapis.com/v1beta/interactions"


def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print("  [" + " ".join(cmd[:4]) + "] " + r.stderr.strip()[-300:])
    return r.stdout.strip()


class DailyQuota(Exception):
    pass


class Auth:
    """Cloud Shell's own sign-in first; if the API wants a key, make one in this project and keep it here."""

    def __init__(self):
        self.project = os.environ.get("GOOGLE_CLOUD_PROJECT") or sh("gcloud", "config", "get-value", "project")
        self.key = os.environ.get("GEMINI_API_KEY", "")
        self.token, self.t0 = "", 0.0

    def headers(self):
        h = {"Content-Type": "application/json"}
        if self.key:
            h["x-goog-api-key"] = self.key
            return h
        if not self.token or time.time() - self.t0 > 1800:
            self.token, self.t0 = sh("gcloud", "auth", "print-access-token"), time.time()
        h["Authorization"] = "Bearer " + self.token
        if self.project:
            h["x-goog-user-project"] = self.project
        return h

    def switch_to_key(self):
        if self.key:
            return False
        print("  using an API key of this project instead of the sign-in token")
        sh("gcloud", "services", "enable", "apikeys.googleapis.com")
        find = ("gcloud", "services", "api-keys", "list", "--filter=displayName=zizo-voice", "--format=value(name)")
        names = sh(*find).split()
        if not names:
            sh("gcloud", "services", "api-keys", "create", "--display-name=zizo-voice",
               "--api-target=service=generativelanguage.googleapis.com")
            names = sh(*find).split()
        if not names:
            raise SystemExit("could not make an API key in this project")
        self.key = sh("gcloud", "services", "api-keys", "get-key-string", names[0], "--format=value(keyString)")
        return bool(self.key)


def call(auth, url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=auth.headers())
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return 200, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {}


def retry_after(err):
    for d in err.get("error", {}).get("details", []):
        if d.get("@type", "").endswith("RetryInfo"):
            try:
                return float(d.get("retryDelay", "30s").rstrip("s")) + 1
            except ValueError:
                pass
    return 30.0


def per_day(err):
    for d in err.get("error", {}).get("details", []):
        for v in d.get("violations", []):
            if "PerDay" in v.get("quotaId", "") or "per_day" in v.get("quotaId", "").lower():
                return True
    return False


def new_api(model):
    return model.startswith("gemini-3.8") or model.startswith("gemini-4")


def request(model, voice, text, style):
    if new_api(model):
        part = {"type": "text", "text": text}
        if style:
            part["annotations"] = [{"type": "speech_metadata", "style": style}]
        return INTERACTIONS, {
            "model": model,
            "input": [{"type": "user_input", "content": [part]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice}]},
        }
    # older TTS models read the direction from the text itself
    return API.format(model=model), {
        "contents": [{"parts": [{"text": f"{style}:\n{text}" if style else text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }


def pcm_of(model, res):
    if new_api(model):
        audio = [c for st in res.get("steps", []) if st.get("type") == "model_output"
                 for c in st.get("content", []) if c.get("type") == "audio"]
        data = base64.b64decode(audio[-1]["data"])
    else:
        data = base64.b64decode(res["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    if data[:4] == b"RIFF":
        with wave.open(io.BytesIO(data)) as w:
            if w.getframerate() != 24000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise RuntimeError(f"unexpected audio format {w.getparams()}")
            data = w.readframes(w.getnframes())
    return data


def synth(auth, models, voice, text, style):
    """Returns 16-bit PCM bytes at 24 kHz, trying the models in order."""
    fails = 0
    while True:
        model = models[0]
        url, body = request(model, voice, text, style)
        code, res = call(auth, url, body)
        if code == 200:
            try:
                return pcm_of(model, res), model
            except (KeyError, IndexError):
                fails += 1
                if fails > 4:
                    raise RuntimeError("no audio in the answer: " + json.dumps(res)[:300])
                continue
        msg = res.get("error", {}).get("message", "")[:200]
        if code == 404 and len(models) > 1:
            print(f"  {model} not available ({msg}); trying {models[1]}")
            models.pop(0)
            continue
        if code in (401, 403):
            print(f"  HTTP {code}: {msg}")
        if code in (401, 403) and auth.switch_to_key():
            continue
        if code == 429:
            if per_day(res):
                raise DailyQuota(msg)
            wait = retry_after(res)
            print(f"  busy, waiting {wait:.0f}s")
            time.sleep(wait)
            continue
        fails += 1
        if code >= 500 and fails <= 6:
            time.sleep(10 * fails)
            continue
        raise RuntimeError(f"HTTP {code}: {msg}")


def main(list_path, out):
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    g = spec["gemini"]
    models = list(g["models"])
    out = pathlib.Path(out)
    auth = Auth()
    print("project:", auth.project or "(none)")
    sh("gcloud", "services", "enable", "generativelanguage.googleapis.com")
    gap = 60.0 / float(g.get("rpm", 8))
    report = out / "report.tsv"
    out.mkdir(parents=True, exist_ok=True)
    items = spec["items"]
    done = stopped = 0
    last = 0.0
    for n, it in enumerate(items, 1):
        voice = it.get("voice") or g["voice"]
        f = out / voice / f"{it['id']}.wav"
        if f.exists():
            done += 1
            continue
        style = it.get("style") or g.get("style", {}).get(it["lang"], "")
        time.sleep(max(0.0, gap - (time.time() - last)))
        last = time.time()
        try:
            pcm, model = synth(auth, models, voice, it["text"], style)
        except DailyQuota as e:
            print(f"\nDaily quota reached after {done} of {len(items)} ({e}). Run the same command again tomorrow.")
            stopped = 1
            break
        f.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(f), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        sec = len(pcm) / 48000
        with report.open("a", encoding="utf-8") as r:
            r.write(f"{it['id']}\t{voice}\t{model}\t{sec:.2f}\t{it['text']}\n")
        done += 1
        print(f"{n}/{len(items)} {voice} {sec:4.1f}s {it['text']}")
    zp = pathlib.Path("out.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(out.parent))
    print(f"\n{done} of {len(items)} recorded -> {zp.resolve()}  (download it with: cloudshell download out.zip)")
    return stopped


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
