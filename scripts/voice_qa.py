"""Listen to recorded sentences with Whisper and say how well each one matches its text.

Usage: python scripts/voice_qa.py <clips_dir> <out.tsv> <list.json> [<list.json> ...] [--shard i/n]
<clips_dir> holds <id>.mp3 (or .wav). Writes: id, score (1.0 = exact), heard text, wanted text.
"""
import difflib, json, pathlib, re, sys

AR_MARKS = re.compile("[ً-ٰٟـ]")
DIGITS_AR = {"0": "صفر", "1": "واحد", "2": "اثنان", "3": "ثلاثه", "4": "اربعه", "5": "خمسه", "6": "سته",
             "7": "سبعه", "8": "ثمانيه", "9": "تسعه", "10": "عشره"}
DIGITS_EN = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
             "8": "eight", "9": "nine", "10": "ten"}


def norm(t, lang):
    t = t.lower()
    words = [w.strip(".,!?؟،") for w in t.split()]
    table = DIGITS_AR if lang == "ar" else DIGITS_EN
    t = " ".join(table.get(w, w) for w in words)
    if lang == "ar":
        t = AR_MARKS.sub("", t)
        t = re.sub("[أإآٱ]", "ا", t).replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
        t = t.replace("+", " زائد ").replace("=", " يساوي ")
    return re.sub(r"[^\w]|_", "", t)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--shard")]
    shard = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--shard=")), "0/1")
    k, n = (int(x) for x in shard.split("/"))
    clips, out, lists = pathlib.Path(args[0]), pathlib.Path(args[1]), args[2:]
    items = {}
    for lp in lists:
        for it in json.loads(pathlib.Path(lp).read_text(encoding="utf-8"))["items"]:
            items[it["id"]] = it
    files = sorted(f for f in clips.iterdir() if f.suffix in (".mp3", ".wav") and f.stem in items)[k::n]
    import whisper
    asr = whisper.load_model("medium", device="cpu")
    rows = []
    for f in files:
        it = items[f.stem]
        heard = asr.transcribe(str(f), language=it["lang"], fp16=False, temperature=0)["text"].strip()
        want = [norm(it["text"], it["lang"])] + [norm(a, it["lang"]) for a in it.get("accept", [])]
        h = norm(heard, it["lang"])
        s = max(difflib.SequenceMatcher(None, w, h).ratio() for w in want)
        rows.append(f"{f.stem}\t{s:.2f}\t{heard}\t{it['text']}")
        print(rows[-1], flush=True)
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
