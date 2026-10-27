"""Join a few of the app's recordings into one MP3 to listen to.

Usage: python3 voice_reel.py <list.json> <recordings_dir> <style> <out.mp3>
"""
import json, pathlib, subprocess, sys, tempfile

PICK = [
    "أَهْلاً! أَنا زِيزُو الفِيل. ما اسْمُك؟",
    "حَرْفُ الباء", "بَطَّة", "أَيْنَ حَرْفُ التاء؟", "أحسنت!", "حاول مرة أخرى",
    "واحِد", "اِثْنان", "ثَلاثَة", "ثَلاثَة زائِدُ اِثْنان يُساوي خَمْسَة",
    "الأَسَدُ يَزْأَر", "تُفّاحَة حَمْراء", "بِالعَيْنِ نَرَى", "الطَّبِيبُ يُعالِجُ المَرْضَى",
    "en:A", "en:Apple", "en:B", "en:Ball", "en:How many?", "en:one", "en:two", "en:three",
]


def main(list_path, rec, style, out):
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    ids = {it["key"]: it["id"] for it in spec["items"]}
    files = []
    for k in PICK:
        f = pathlib.Path(rec) / style / f"{ids[k]}.mp3"
        if f.exists():
            files.append(f)
        else:
            print("no recording for", k)
    with tempfile.TemporaryDirectory() as t:
        gap = pathlib.Path(t) / "gap.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.6", str(gap)], check=True)
        lst = pathlib.Path(t) / "list.txt"
        parts = []
        for f in files:
            w = pathlib.Path(t) / (f.stem + ".wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(f), "-ar", "24000", "-ac", "1", str(w)], check=True)
            parts += [f"file '{w}'", f"file '{gap}'"]
        lst.write_text("\n".join(parts) + "\n")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-ac", "1", "-b:a", "64k", out], check=True)
    print(out, len(files), "recordings")


if __name__ == "__main__":
    main(*sys.argv[1:5])
