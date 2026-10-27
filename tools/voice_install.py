"""Put recorded voice files into the app.

Usage: python3 voice_install.py <project_dir> <list.json> <recordings_dir> <style>
Copies <recordings_dir>/<style>/<id>.mp3 to www/voice/ and writes www/voice/index.json
({"clips": {sentence: id}}). Old files no longer in the list are removed.
"""
import json, pathlib, shutil, sys


def main(proj, list_path, rec, style):
    proj, rec = pathlib.Path(proj), pathlib.Path(rec)
    spec = json.loads(pathlib.Path(list_path).read_text(encoding="utf-8"))
    dst = proj / "www/voice"
    dst.mkdir(parents=True, exist_ok=True)
    clips, missing, size = {}, [], 0
    for it in spec["items"]:
        src = rec / style / f"{it['id']}.mp3"
        if not src.exists():
            missing.append(it)
            continue
        shutil.copyfile(src, dst / src.name)
        clips[it["key"]] = it["id"]
        size += src.stat().st_size
    keep = {f"{i}.mp3" for i in clips.values()} | {"index.json"}
    for f in dst.iterdir():
        if f.name not in keep:
            f.unlink()
    (dst / "index.json").write_text(json.dumps({"style": style, "clips": clips}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(clips)} recordings, {size / 1e6:.1f} MB; missing {len(missing)}")
    for it in missing[:20]:
        print("  missing", it["id"], it["text"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
