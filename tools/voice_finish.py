"""Turn cut sentence WAVs into the app's MP3s and install them, keeping old recordings for anything not re-recorded.

Usage: python3 voice_finish.py <project_dir> <list.json> <style> <wav_dir> [<wav_dir> ...]
Each <wav_dir> holds <voice>/<id>.wav (later dirs win). Every clip is levelled to the same loudness,
encoded as 24 kHz mono MP3 and copied to www/voice/<id>.mp3; www/voice/index.json lists every sentence
that has a file (new or old).
"""
import json, pathlib, subprocess, sys, tempfile, wave
import numpy as np

TARGET_DB = -18.0  # loudness of the speech parts (RMS of the louder frames)


def level(x):
    n = len(x) // 240
    if n == 0:
        return x
    fr = x[: n * 240].reshape(n, 240)
    rms = np.sqrt(np.mean(fr ** 2, axis=1) + 1e-9)
    loud = rms[rms >= np.percentile(rms, 60)]
    cur = 20 * np.log10(np.sqrt(np.mean(loud ** 2)) / 32768 + 1e-12)
    g = 10 ** ((TARGET_DB - cur) / 20)
    peak = np.max(np.abs(x)) * g
    if peak > 32768 * 0.89:  # keep 1 dB headroom
        g *= 32768 * 0.89 / peak
    return x * g


def main(proj, list_path, style, *wav_dirs):
    proj = pathlib.Path(proj)
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    dst = proj / "www/voice"
    src = {}
    for d in wav_dirs:
        for f in pathlib.Path(d).rglob("*.wav"):
            if not f.name.startswith("chunk-"):
                src[f.stem] = f
    new = old = 0
    clips, missing = {}, []
    with tempfile.TemporaryDirectory() as t:
        for it in spec["items"]:
            out = dst / f"{it['id']}.mp3"
            f = src.get(it["id"])
            if f:
                with wave.open(str(f)) as w:
                    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
                y = np.clip(level(x), -32768, 32767).astype(np.int16)
                tmp = pathlib.Path(t) / "x.wav"
                with wave.open(str(tmp), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(24000)
                    w.writeframes(y.tobytes())
                subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(tmp),
                                "-ar", "24000", "-ac", "1", "-b:a", "48k", str(out)], check=True)
                new += 1
            elif out.exists():
                old += 1
            else:
                missing.append(it)
                continue
            clips[it["key"]] = it["id"]
    keep = {f"{i}.mp3" for i in clips.values()} | {"index.json"}
    for f in dst.iterdir():
        if f.name not in keep:
            f.unlink()
    (dst / "index.json").write_text(json.dumps({"style": style, "clips": clips}, ensure_ascii=False,
                                               separators=(",", ":")), encoding="utf-8")
    size = sum(f.stat().st_size for f in dst.glob("*.mp3"))
    print(f"{new} new recordings, {old} old kept, {len(missing)} missing; {size / 1e6:.1f} MB")
    for it in missing[:20]:
        print("  missing", it["id"], it["text"])


if __name__ == "__main__":
    main(*sys.argv[1:])
