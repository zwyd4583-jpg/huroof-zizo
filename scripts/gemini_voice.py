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


KEYFILE = pathlib.Path.home() / ".config" / "zizo-voice" / "key"


class DailyQuota(Exception):
    pass


class NoAudio(Exception):
    """The model answered without audio (it gives up on some texts); retrying the same text rarely helps."""


class Auth:
    """Cloud Shell's own sign-in first; if the API wants a key, make one in this project and keep it here."""

    def __init__(self):
        self.project = os.environ.get("GOOGLE_CLOUD_PROJECT") or sh("gcloud", "config", "get-value", "project")
        self.key = os.environ.get("GEMINI_API_KEY", "") or (KEYFILE.read_text().strip() if KEYFILE.exists() else "")
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
        if self.key:
            # kept only in this Cloud Shell home, so later runs need no sign-in
            KEYFILE.parent.mkdir(parents=True, exist_ok=True)
            KEYFILE.write_text(self.key)
            KEYFILE.chmod(0o600)
        return bool(self.key)


def call(auth, url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=auth.headers())
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return 200, one(json.load(r))
    except urllib.error.HTTPError as e:
        try:
            return e.code, one(json.load(e))
        except Exception:
            return e.code, {}
    except (TimeoutError, OSError) as e:  # long answers sometimes time out; treat like a server error
        print(f"  no answer ({type(e).__name__}), trying again")
        return 599, {}


def one(res):
    # some endpoints answer with a list of objects
    if isinstance(res, list):
        res = res[-1] if res and isinstance(res[-1], dict) else {}
    return res


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
    return "per day" in err.get("error", {}).get("message", "")


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
    # older TTS models read the direction from the text itself and know no pause tags
    lines = text.split("\n<long pause>\n")
    if len(lines) > 1:
        text = "\n\n".join(lines)
        style = (style + "; " if style else "") + "read each line below, stopping for two full seconds of silence after every line, and say nothing else"
    return API.format(model=model), {
        "contents": [{"parts": [{"text": f"{style}:\n\n{text}" if style else text}]}],
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
                raise NoAudio(json.dumps(res, ensure_ascii=False)[:200])
        msg = res.get("error", {}).get("message", "")[:200]
        if code == 404 and len(models) > 1:
            print(f"  {model} not available ({msg}); trying {models[1]}")
            models.pop(0)
            continue
        if code != 429:
            print(f"  HTTP {code}: {msg}")
        if code in (401, 403) and auth.switch_to_key():
            continue
        if code == 429:
            if per_day(res):
                raise DailyQuota(msg)
            wait = retry_after(res)
            print(f"  busy, waiting {wait:.0f}s ({msg[:120]})")
            time.sleep(wait)
            continue
        fails += 1
        if code >= 500 and fails <= 6:
            time.sleep(10 * fails)
            continue
        raise RuntimeError(f"HTTP {code}: {msg}")


def chunks(items, g):
    """Consecutive sentences with the same voice and style, up to "batch" of them per request."""
    size, limit = int(g.get("batch", 1)), int(g.get("batch_chars", 1500))
    cur, key, chars = [], None, 0
    for it in items:
        k = (it.get("voice") or g["voice"], it.get("style") or g.get("style", {}).get(it["lang"], ""))
        if cur and (k != key or len(cur) >= size or chars + len(it["text"]) > limit):
            yield key, cur
            cur, chars = [], 0
        cur.append(it)
        key = k
        chars += len(it["text"])
    if cur:
        yield key, cur


def save(f, pcm):
    f.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)


def main(list_path, out, model=None):
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    g = spec["gemini"]
    models = [model] if model else list(g["models"])
    out = pathlib.Path(out)
    auth = Auth()
    print("project:", auth.project or "(none)", "| model:", models[0])
    if not auth.key:
        sh("gcloud", "services", "enable", "generativelanguage.googleapis.com")
    gap = 60.0 / float(g.get("rpm", 4))
    report = out / "report.tsv"
    out.mkdir(parents=True, exist_ok=True)
    items = spec["items"]
    groups = list(chunks(items, g))
    done = stopped = 0
    last = 0.0
    queue = list(groups)
    n = 0
    while queue:
        (voice, style), group = queue.pop(0)
        n += 1
        single = len(group) == 1
        f = out / voice / (f"{group[0]['id']}.wav" if single else f"chunk-{group[0]['id']}-{len(group)}.wav")
        if f.exists():
            done += len(group)
            continue
        # sentences of one request are kept apart by long pauses and cut at those pauses later
        text = group[0]["text"] if single else "\n<long pause>\n".join(it["text"] for it in group)
        time.sleep(max(0.0, gap - (time.time() - last)))
        last = time.time()
        try:
            pcm, used = synth(auth, models, voice, text, style)
        except NoAudio as e:
            # a long text the model will not read in one go: try its two halves instead
            print(f"  no audio for {len(group)} sentence(s): {str(e)[:120]}")
            if len(group) > 1:
                h = len(group) // 2
                queue[:0] = [((voice, style), group[:h]), ((voice, style), group[h:])]
            continue
        except DailyQuota as e:
            print(f"\nDaily quota reached after {done} of {len(items)} ({str(e)[:160]}).")
            print("Run the same command again after the quota resets; finished parts are kept.")
            stopped = 1
            break
        save(f, pcm)
        if not single:
            f.with_suffix(".json").write_text(json.dumps(
                {"model": used, "voice": voice, "items": [{"id": it["id"], "text": it["text"]} for it in group]},
                ensure_ascii=False, indent=1), encoding="utf-8")
        sec = len(pcm) / 48000
        with report.open("a", encoding="utf-8") as r:
            r.write(f"{f.name}\t{voice}\t{used}\t{sec:.2f}\t{len(group)}\t{group[0]['text']}\n")
        done += len(group)
        print(f"request {n} ({len(queue)} left): {voice} {len(group)} sentence(s) {sec:5.1f}s  {group[0]['text']}")
    zp = pathlib.Path("out.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(out.parent))
    print(f"\n{done} of {len(items)} sentences recorded -> {zp.resolve()}")
    return stopped


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
