"""Make Zizo's voice: synthesize every phrase of a list into small MP3 files.

Runs on GitHub Actions (it needs the internet once, to fetch the voice models).
Usage: python scripts/make_voice.py <list.json> <out_dir> [shard] [shards]

The list: {"engine": "piper" | "chatterbox",
           "voices": {"ar": "<piper voice>", "en": "<piper voice>"},      (piper)
           "chatterbox": {"exaggeration": 0.5, "cfg_weight": 0.5},          (chatterbox)
           "styles": {"<name>": {"pitch": 1.0, "length": 1.1, "tempo": 1.0}},
           "items": [{"id": "...", "lang": "ar"|"en", "text": "..."}],
           "reels": true}
Each item becomes <out>/<style>/<id>.mp3. With "reels", every style also gets one
<out>/reel-<style>.mp3 with all the items one after another, to listen to in one go.
With shard/shards, only every shards-th item from shard on is made (to split the work).
"""
import json, os, pathlib, subprocess, sys, urllib.request, wave, zlib

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
RATE = 24000


def piper_engine(spec, work):
    from piper import PiperVoice
    cache = work / "models"
    cache.mkdir(parents=True, exist_ok=True)
    voices = {}
    for lang, name in spec["voices"].items():
        # "ar_JO-kareem-medium" -> ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx (+ .onnx.json)
        loc, speaker, quality = name.split("-")
        base = f"{HF}/{loc.split('_')[0]}/{loc}/{speaker}/{quality}"
        for f in [f"{name}.onnx", f"{name}.onnx.json"]:
            if not (cache / f).exists():
                urllib.request.urlretrieve(f"{base}/{f}", cache / f)
        voices[lang] = PiperVoice.load(str(cache / f"{name}.onnx"))

    def say(lang, text, st, path):
        with wave.open(str(path), "wb") as wf:
            try:
                from piper import SynthesisConfig
                voices[lang].synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=st.get("length", 1.0)))
            except ImportError:
                voices[lang].synthesize(text, wf, length_scale=st.get("length", 1.0))
    return say


def chatterbox_engine(spec, work):
    import torch, torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    opts = spec.get("chatterbox", {})

    def say(lang, text, st, path):
        # the same text always gives the same recording
        torch.manual_seed(zlib.crc32(f"{lang}|{text}".encode("utf-8")))
        kw = {"language_id": lang, "exaggeration": opts.get("exaggeration", 0.5), "cfg_weight": opts.get("cfg_weight", 0.5)}
        if opts.get("prompt"):
            kw["audio_prompt_path"] = opts["prompt"]
        wav = model.generate(text, **kw)
        torchaudio.save(str(path), wav, model.sr)
    return say


def post(src, dst, pitch, tempo):
    """Raise the pitch (a younger, cartoon voice) without changing the speed; trim silence; even loudness."""
    sr = wave.open(str(src)).getframerate()
    f = []
    if abs(pitch - 1.0) > 1e-3 or abs(tempo - 1.0) > 1e-3:
        f.append(f"asetrate={int(sr * pitch)},aresample={sr},atempo={tempo / pitch:.5f}")
    f.append("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03")
    f.append("areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
    f.append(f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample={RATE}")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af", ",".join(f), "-ac", "1", "-ar", str(RATE), str(dst)], check=True)


def mp3(src, dst):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-b:a", "48k", str(dst)], check=True)


def main(list_path, out_dir, shard=0, shards=1):
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path("/tmp/zizo-voice"); work.mkdir(parents=True, exist_ok=True)
    say = chatterbox_engine(spec, work) if spec.get("engine") == "chatterbox" else piper_engine(spec, work)
    items = spec["items"][shard::shards]
    report = []
    for style, st in spec["styles"].items():
        (out / style).mkdir(exist_ok=True)
        reel = []
        for it in items:
            raw, clean = work / f"{style}-{it['id']}-raw.wav", work / f"{style}-{it['id']}.wav"
            try:
                say(it["lang"], it["text"], st, raw)
                post(raw, clean, st.get("pitch", 1.0), st.get("tempo", 1.0))
            except Exception as e:  # keep going; the report says which ones failed
                report.append(f"{style}\t{it['id']}\tFAILED {type(e).__name__}: {e}\t{it['text']}")
                print(report[-1], flush=True)
                continue
            mp3(clean, out / style / f"{it['id']}.mp3")
            reel.append(clean)
            with wave.open(str(clean)) as w:
                report.append(f"{style}\t{it['id']}\t{w.getnframes() / w.getframerate():.2f}s\t{it['text']}")
            print(report[-1], flush=True)
        if spec.get("reels") and reel:
            joined = work / f"reel-{style}.wav"
            with wave.open(str(joined), "wb") as o:
                o.setnchannels(1); o.setsampwidth(2); o.setframerate(RATE)
                gap = b"\x00\x00" * int(RATE * 0.7)
                for c in reel:
                    with wave.open(str(c)) as w:
                        o.writeframes(w.readframes(w.getnframes()))
                    o.writeframes(gap)
            mp3(joined, out / f"reel-{style}.mp3")
    (out / f"report-{shard}.tsv").write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]) if len(a) > 2 else 0, int(a[3]) if len(a) > 3 else 1)
