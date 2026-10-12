"""Print how Piper reads some Arabic words (phonemes and length), to find why some words come out clipped."""
import inspect, io, json, pathlib, sys, urllib.request, wave

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium"
cache = pathlib.Path("/tmp/zizo-voice/models"); cache.mkdir(parents=True, exist_ok=True)
for f in ["ar_JO-kareem-medium.onnx", "ar_JO-kareem-medium.onnx.json"]:
    if not (cache / f).exists():
        urllib.request.urlretrieve(f"{HF}/{f}", cache / f)
import piper
from piper import PiperVoice
out = []
out.append("piper " + getattr(piper, "__version__", "?") + " " + str(pathlib.Path(piper.__file__).parent))
out.append("load: " + str(inspect.signature(PiperVoice.load)))
out.append("methods: " + ", ".join(m for m in dir(PiperVoice) if not m.startswith("_")))
try:
    from piper import SynthesisConfig
    out.append("SynthesisConfig: " + str(inspect.signature(SynthesisConfig)))
except Exception as e:
    out.append("no SynthesisConfig " + str(e))
v = PiperVoice.load(str(cache / "ar_JO-kareem-medium.onnx"))
out.append("config: " + json.dumps({k: str(getattr(v.config, k)) for k in dir(v.config) if not k.startswith("_")}, ensure_ascii=False)[:600])
words = ["فيل", "فِيل", "فِيلٌ", "الفيل", "هذا فيل", "فم", "فَم", "ذئب", "ذِئْب", "عصفور", "عُصْفُور", "أحمر", "أَحْمَر", "بطة", "بَطَّة", "قطة", "قِطَّة", "واحد", "واحِد", "رائع", "رائِع", "خمسة", "خَمْسَة"]
for w in words:
    try:
        ph = v.phonemize(w)
    except Exception as e:
        ph = f"ERR {e}"
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        v.synthesize_wav(w, wf)
    buf.seek(0)
    with wave.open(buf) as r:
        d = r.getnframes() / r.getframerate()
    out.append(f"{w}\t{d:.2f}s\t{ph}")
pathlib.Path(sys.argv[1]).mkdir(parents=True, exist_ok=True)
(pathlib.Path(sys.argv[1]) / "debug.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
