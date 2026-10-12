"""Make Zizo's voice: synthesize every phrase of a list into small MP3 files, offline, with Piper.

Runs on GitHub Actions (it needs the internet once, to fetch the voice models).
Usage: python scripts/make_voice.py <list.json> <out_dir>

The list: {"voices": {"ar": "<piper voice>", "en": "<piper voice>"},
           "styles": {"<name>": {"pitch": 1.0, "length": 1.1}},
           "items": [{"id": "...", "lang": "ar"|"en", "text": "..."}],
           "reels": true}
Each item becomes <out>/<style>/<id>.mp3. With "reels", every style also gets one
<out>/reel-<style>.mp3 with all the items one after another, to listen to in one go.
"""
import json, os, pathlib, subprocess, sys, urllib.request, wave

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
RATE = 24000


def voice_files(name, cache):
    # "ar_JO-kareem-medium" -> ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx (+ .onnx.json, MODEL_CARD)
    loc, speaker, quality = name.split("-")
    base = f"{HF}/{loc.split('_')[0]}/{loc}/{speaker}/{quality}"
    cache.mkdir(parents=True, exist_ok=True)
    for f in [f"{name}.onnx", f"{name}.onnx.json", "MODEL_CARD"]:
        dst = cache / (f if f != "MODEL_CARD" else f"{name}.MODEL_CARD.txt")
        if not dst.exists():
            urllib.request.urlretrieve(f"{base}/{f}", dst)
    return cache / f"{name}.onnx"


def synth(voice, text, length, path):
    with wave.open(str(path), "wb") as wf:
        try:
            from piper import SynthesisConfig
            voice.synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=length))
        except ImportError:
            voice.synthesize(text, wf, length_scale=length)


def post(src, dst, pitch):
    """Raise the pitch (a younger, cartoon voice) without changing the speed; trim silence; even loudness."""
    sr = wave.open(str(src)).getframerate()
    f = []
    if abs(pitch - 1.0) > 1e-3:
        f.append(f"asetrate={int(sr * pitch)},aresample={sr},atempo={1 / pitch:.5f}")
    f.append("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03")
    f.append("areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
    f.append(f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample={RATE}")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af", ",".join(f), "-ac", "1", "-ar", str(RATE), str(dst)], check=True)


def mp3(src, dst):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-b:a", "48k", str(dst)], check=True)


def main(list_path, out_dir):
    from piper import PiperVoice
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path("/tmp/zizo-voice"); work.mkdir(parents=True, exist_ok=True)
    voices = {lang: PiperVoice.load(str(voice_files(name, work / "models"))) for lang, name in spec["voices"].items()}
    for name in spec["voices"].values():
        card = work / "models" / f"{name}.MODEL_CARD.txt"
        if card.exists():
            (out / f"MODEL_CARD-{name}.txt").write_text(card.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    report = []
    for style, st in spec["styles"].items():
        (out / style).mkdir(exist_ok=True)
        reel = []
        for it in spec["items"]:
            raw, clean = work / f"{style}-{it['id']}-raw.wav", work / f"{style}-{it['id']}.wav"
            synth(voices[it["lang"]], it["text"], st.get("length", 1.0), raw)
            post(raw, clean, st.get("pitch", 1.0))
            mp3(clean, out / style / f"{it['id']}.mp3")
            reel.append(clean)
            with wave.open(str(clean)) as w:
                report.append(f"{style}\t{it['id']}\t{w.getnframes() / w.getframerate():.2f}s\t{it['text']}")
        if spec.get("reels"):
            joined = work / f"reel-{style}.wav"
            with wave.open(str(joined), "wb") as o:
                o.setnchannels(1); o.setsampwidth(2); o.setframerate(RATE)
                gap = b"\x00\x00" * int(RATE * 0.7)
                for c in reel:
                    with wave.open(str(c)) as w:
                        o.writeframes(w.readframes(w.getnframes()))
                    o.writeframes(gap)
            mp3(joined, out / f"reel-{style}.mp3")
    (out / "report.tsv").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
