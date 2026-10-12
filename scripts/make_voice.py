"""Make Zizo's voice: synthesize every phrase of a list into small MP3 files.

Runs on GitHub Actions (it needs the internet once, to fetch the voice models).
Usage: python scripts/make_voice.py <list.json> <out_dir> [shard] [shards]

The list: {"engine": "piper" | "chatterbox",
           "voices": {"ar": "<piper voice>", "en": "<piper voice>"},      (piper)
           "chatterbox": {"exaggeration": 0.5, "cfg_weight": 0.5},          (chatterbox)
           "styles": {"<name>": {"pitch": 1.0, "length": 1.1, "tempo": 1.0}},
           "items": [{"id": "...", "lang": "ar"|"en", "text": "..."}],
           "reels": true, "qa": true}
Each item becomes <out>/<style>/<id>.mp3. With "reels", every style also gets one
<out>/reel-<style>.mp3 with all the items one after another, to listen to in one go.
With "qa", Whisper listens to every recording and qa-<shard>.tsv says how close it is to the text.
With shard/shards, only every shards-th item from shard on is made (to split the work).
"""
import array, difflib, json, os, pathlib, re, subprocess, sys, urllib.request, wave, zlib

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
RATE = 24000


def to_pcm(src, dst):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", str(dst)], check=True)


def read_pcm(path):
    with wave.open(str(path)) as w:
        a = array.array("h", w.readframes(w.getnframes()))
    return a


def write_pcm(path, a):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(a.tobytes())


def keep_speech(a, gap_s=0.4):
    """Keep the speech of ONE sentence: from the first loud moment to the first long pause after it.
    Generated voices sometimes add breaths or babble after a pause at the end; this cuts them off."""
    fr = RATE // 50  # 20 ms
    peaks = [max((abs(x) for x in a[i:i + fr]), default=0) for i in range(0, len(a), fr)]
    if not peaks or max(peaks) == 0:
        return a
    top = max(peaks)
    loud = [p > 0.12 * top for p in peaks]
    if True not in loud:
        return a
    s = loud.index(True)
    e, quiet, gap = s, 0, int(gap_s * 50)
    for k in range(s, len(peaks)):
        if loud[k]:
            e, quiet = k, 0
        else:
            quiet += 1
            if quiet >= gap:
                break
    return a[max(0, s - 2) * fr:min(len(a), (e + 4) * fr)]


def sentences(text):
    parts = [p.strip() for p in re.findall(r"[^.!؟?]+[.!؟?]*", text) if p.strip(" .!؟?")]
    return parts or [text]


def piper_engine(spec, work):
    """Piper voices by name; "<voice>@<speaker>" picks a speaker of a many-speaker voice.
    An item may name its own "voice"; otherwise the list's voice for its language is used."""
    from piper import PiperVoice
    cache = work / "models"
    cache.mkdir(parents=True, exist_ok=True)
    loaded = {}

    def get(full):
        if full in loaded:
            return loaded[full]
        name, _, speaker = full.partition("@")
        # "ar_JO-kareem-medium" -> ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx (+ .onnx.json)
        loc, spk, quality = name.split("-")
        base = f"{HF}/{loc.split('_')[0]}/{loc}/{spk}/{quality}"
        for f in [f"{name}.onnx", f"{name}.onnx.json"]:
            if not (cache / f).exists():
                urllib.request.urlretrieve(f"{base}/{f}", cache / f)
        v = PiperVoice.load(str(cache / f"{name}.onnx"))
        sid = None
        if speaker:
            ids = json.loads((cache / f"{name}.onnx.json").read_text(encoding="utf-8")).get("speaker_id_map", {})
            sid = ids[speaker] if speaker in ids else int(speaker)
        loaded[full] = (v, sid)
        return loaded[full]

    def say(lang, text, st, path, voice=None):
        v, sid = get(voice or spec["voices"][lang])
        raw = path.with_suffix(".piper.wav")
        with wave.open(str(raw), "wb") as wf:
            try:
                from piper import SynthesisConfig
                v.synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=st.get("length", 1.0), speaker_id=sid))
            except ImportError:
                v.synthesize(text, wf, length_scale=st.get("length", 1.0), speaker_id=sid)
        to_pcm(raw, path)
    return say


def chatterbox_engine(spec, work):
    import torch, torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    opts = spec.get("chatterbox", {})
    cache = {}

    def one(lang, text):
        if (lang, text) in cache:
            return cache[(lang, text)]
        # the same text always gives the same recording
        torch.manual_seed(zlib.crc32(f"{lang}|{text}".encode("utf-8")))
        kw = {"language_id": lang, "exaggeration": opts.get("exaggeration", 0.5), "cfg_weight": opts.get("cfg_weight", 0.5)}
        if opts.get("prompt"):
            kw["audio_prompt_path"] = opts["prompt"]
        wav = model.generate(text, **kw)
        tmp = work / "cb-one.wav"
        torchaudio.save(str(tmp), wav, model.sr)
        to_pcm(tmp, work / "cb-one-pcm.wav")
        a = keep_speech(read_pcm(work / "cb-one-pcm.wav"))
        cache[(lang, text)] = a
        return a

    def say(lang, text, st, path, voice=None):
        # Each sentence on its own (short texts are where extra sounds creep in), joined with a short pause
        out = array.array("h")
        for k, s in enumerate(sentences(text)):
            if k:
                out.extend(array.array("h", [0]) * int(RATE * 0.22))
            out.extend(one(lang, s))
        write_pcm(path, out)
    return say


def post(src, dst, pitch, tempo):
    """Raise the pitch (a younger, cartoon voice) keeping the speed; trim the edges; even loudness."""
    f = []
    if abs(pitch - 1.0) > 1e-3 or abs(tempo - 1.0) > 1e-3:
        f.append(f"asetrate={int(RATE * pitch)},aresample={RATE},atempo={tempo / pitch:.5f}")
    # trim only real silence (soft sounds like ف and س start quietly), and leave a little air at both ends
    f.append("silenceremove=start_periods=1:start_threshold=-58dB:start_silence=0.06")
    f.append("areverse,silenceremove=start_periods=1:start_threshold=-58dB:start_silence=0.08,areverse")
    f.append(f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample={RATE}")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af", ",".join(f), "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", str(dst)], check=True)


def mp3(src, dst):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-b:a", "48k", str(dst)], check=True)


AR_MARKS = re.compile("[ً-ْٰـ]")


def norm(t, lang):
    t = t.lower()
    if lang == "ar":
        t = AR_MARKS.sub("", t)
        t = re.sub("[أإآٱ]", "ا", t).replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"[^\w]|_", "", t)


NUM_WORDS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def score(it, heard):
    """How well the listener (Whisper) understood the recording: 1.0 is a perfect match.
    "accept" lists other ways to write a right answer (a letter "W" for "Double you", "3" for "Three")."""
    lang = it["lang"]
    h = norm(" ".join(NUM_WORDS.get(w.strip(".,!?"), w) for w in heard.split()), lang)
    want = [norm(it["text"], lang)] + [norm(a, lang) for a in it.get("accept", [])]
    return max(difflib.SequenceMatcher(None, w, h).ratio() for w in want)


def main(list_path, out_dir, shard=0, shards=1):
    """Each item is recorded a few times ("candidates"); Whisper listens and the clearest one is kept.
    The kept recording then gets every style (pitch/tempo) as its own MP3."""
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path("/tmp/zizo-voice"); work.mkdir(parents=True, exist_ok=True)
    say = chatterbox_engine(spec, work) if spec.get("engine") == "chatterbox" else piper_engine(spec, work)
    asr = None
    if spec.get("qa"):
        import whisper
        asr = whisper.load_model(spec.get("qa_model", "small"), device="cpu")
    items = spec["items"][shard::shards]
    styles = list(spec["styles"].items())
    for style, _ in styles:
        (out / style).mkdir(exist_ok=True)
    report, qa, reels = [], [], {style: [] for style, _ in styles}
    base = {"length": spec.get("length", 1.0)}
    for it in items:
        n = it.get("candidates", spec.get("candidates", 1)) if asr else 1
        best = None
        for c in range(n):
            raw = work / f"{it['id']}-c{c}.wav"
            try:
                say(it["lang"], it["text"], dict(base, **it.get("style", {})), raw, it.get("voice"))
            except Exception as e:  # keep going; the report says which ones failed
                print(f"FAILED {it['id']} try {c}: {type(e).__name__}: {e}", flush=True)
                continue
            sc, heard = 1.0, ""
            if asr:
                heard = asr.transcribe(str(raw), language=it["lang"], fp16=False, temperature=0)["text"].strip()
                sc = score(it, heard)
            if best is None or sc > best[0]:
                best = (sc, raw, heard)
            if sc >= 0.99:
                break
        if best is None:
            report.append(f"-\t{it['id']}\tFAILED\t{it['text']}")
            continue
        if asr:
            qa.append(f"{it['id']}\t{best[0]:.2f}\t{it['text']}\t{best[2]}")
            print("QA", qa[-1], flush=True)
        for style, st in styles:
            clean = work / f"{style}-{it['id']}.wav"
            post(best[1], clean, st.get("pitch", 1.0), st.get("tempo", 1.0))
            mp3(clean, out / style / f"{it['id']}.mp3")
            reels[style].append(clean)
            with wave.open(str(clean)) as w:
                report.append(f"{style}\t{it['id']}\t{w.getnframes() / w.getframerate():.2f}s\t{it['text']}")
    if spec.get("reels"):
        gap = array.array("h", [0]) * int(RATE * 0.7)
        for style, clips in reels.items():
            if not clips:
                continue
            allpcm = array.array("h")
            for c in clips:
                allpcm.extend(read_pcm(c)); allpcm.extend(gap)
            write_pcm(work / f"reel-{style}.wav", allpcm)
            mp3(work / f"reel-{style}.wav", out / f"reel-{style}.mp3")
    (out / f"report-{shard}.tsv").write_text("\n".join(report) + "\n", encoding="utf-8")
    if qa:
        (out / f"qa-{shard}.tsv").write_text("\n".join(qa) + "\n", encoding="utf-8")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]) if len(a) > 2 else 0, int(a[3]) if len(a) > 3 else 1)
