"""Show Piper's word timing (alignments) for a carrier sentence, to cut single words out cleanly."""
import json, pathlib, sys, urllib.request

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium"
cache = pathlib.Path("/tmp/zizo-voice/models"); cache.mkdir(parents=True, exist_ok=True)
for f in ["ar_JO-kareem-medium.onnx", "ar_JO-kareem-medium.onnx.json"]:
    if not (cache / f).exists():
        urllib.request.urlretrieve(f"{HF}/{f}", cache / f)
from piper import PiperVoice
out = []
v = PiperVoice.load(str(cache / "ar_JO-kareem-medium.onnx"), include_alignments=True)
for text in ["هذا فِيل.", "هذا بَطَّة."]:
    for ch in v.synthesize(text):
        out.append("chunk attrs: " + ", ".join(a for a in dir(ch) if not a.startswith("_")))
        for a in dir(ch):
            if a.startswith("_"):
                continue
            val = getattr(ch, a)
            if callable(val):
                continue
            r = repr(val)
            out.append(f"  {a} = {r[:300]}")
pathlib.Path(sys.argv[1]).mkdir(parents=True, exist_ok=True)
(pathlib.Path(sys.argv[1]) / "debug.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
