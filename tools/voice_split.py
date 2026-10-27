"""Cut Gemini chunk recordings (many sentences per request, kept apart by long pauses) into one file per sentence.

Usage: python3 voice_split.py <recordings_dir> <out_dir>
Each <voice>/chunk-*.wav has a .json next to it listing the sentences in order.
The N-1 longest silences become the cuts. Single-sentence files are copied as they are.
Writes <out_dir>/<voice>/<id>.wav and prints a check of each cut (duration per character).
"""
import json, pathlib, shutil, sys, wave
import numpy as np

SR = 24000
FRAME = 240  # 10 ms


def load(f):
    with wave.open(str(f)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)


def write(f, x):
    f.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())


def silences(x):
    """(start, end) frame indices of quiet stretches, using a level relative to the loud parts."""
    n = len(x) // FRAME
    rms = np.sqrt(np.mean(x[: n * FRAME].reshape(n, FRAME) ** 2, axis=1) + 1e-9)
    db = 20 * np.log10(rms / 32768 + 1e-12)
    loud = np.percentile(db, 90)
    quiet = db < max(loud - 35, -60)
    out, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        if not q and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, n))
    return out, n


def trim(x):
    """Remove leading/trailing silence, keeping a short margin."""
    sil, n = silences(x)
    a, b = 0, n
    if sil and sil[0][0] == 0:
        a = sil[0][1]
    if sil and sil[-1][1] == n:
        b = sil[-1][0]
    a = max(0, a - 8)
    b = min(n, b + 15)
    y = x[a * FRAME: b * FRAME]
    fade = min(len(y) // 4, 120)
    if fade:
        y = y.copy()
        y[:fade] *= np.linspace(0, 1, fade)
        y[-fade:] *= np.linspace(1, 0, fade)
    return y


def weight(text):
    return sum(ch.isalpha() for ch in text) + 4


def split(f, meta):
    """Pick the cuts among the pauses so that each piece is about as long as its sentence should be
    (from its letter count), preferring long pauses. Dynamic programming over the pauses."""
    x = load(f)
    items = meta["items"]
    sil, n = silences(x)
    inner = [(s, e) for s, e in sil if s > 0 and e < n and e - s >= 15]  # pauses of 150 ms or more
    need = len(items) - 1
    if len(inner) < need:
        return None, f"only {len(inner)} pauses for {len(items)} sentences"
    pos = [0.0] + [(s + e) / 2 / 100 for s, e in inner] + [n / 100]  # seconds; first and last are the ends
    gap = [9.0] + [(e - s) / 100 for s, e in inner] + [9.0]
    w = [weight(it["text"]) for it in items]
    rate = (n / 100) / sum(w)
    exp = [rate * wi for wi in w]
    C = len(pos)
    INF = float("inf")

    def seg_cost(i, a, b):
        d = pos[b] - pos[a]
        e = exp[i]
        return ((d - e) / (0.3 * e + 0.5)) ** 2 - 3.0 * min(gap[b], 2.5)

    # dp[i][b]: best cost with sentence i ending at boundary b
    dp = [[INF] * C for _ in range(len(items))]
    back = [[-1] * C for _ in range(len(items))]
    for b in range(1, C):
        dp[0][b] = seg_cost(0, 0, b)
    for i in range(1, len(items)):
        for b in range(i + 1, C):
            best, arg = INF, -1
            row = dp[i - 1]
            for a in range(i, b):
                if row[a] == INF:
                    continue
                c = row[a] + seg_cost(i, a, b)
                if c < best:
                    best, arg = c, a
            dp[i][b], back[i][b] = best, arg
    # the last sentence must end at the end of the file
    b = C - 1
    cuts = []
    for i in range(len(items) - 1, 0, -1):
        a = back[i][b]
        cuts.append(a)
        b = a
    cuts = sorted(cuts)
    bounds = [int(pos[c] * SR) for c in cuts]
    edges = [0] + bounds + [len(x)]
    parts = [trim(x[edges[i]: edges[i + 1]]) for i in range(len(items))]
    used = [gap[c] for c in cuts]
    unused = sorted((gap[k] for k in range(1, C - 1) if k not in cuts), reverse=True)
    return parts, f"cuts at pauses >= {min(used) * 1000:.0f} ms; longest pause not cut {unused[0] * 1000 if unused else 0:.0f} ms"


def main(rec, out):
    rec, out = pathlib.Path(rec), pathlib.Path(out)
    rows = []
    for f in sorted(rec.rglob("*.wav")):
        voice = f.parent.name
        if not f.name.startswith("chunk-"):
            dst = out / voice / f.name
            write(dst, trim(load(f)))
            continue
        meta = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
        parts, note = split(f, meta)
        print(f"{voice}/{f.name}: {len(meta['items'])} sentences, {note}")
        if parts is None:
            continue
        for it, p in zip(meta["items"], parts):
            write(out / voice / f"{it['id']}.wav", p)
            sec = len(p) / SR
            letters = sum(ch.isalpha() for ch in it["text"]) or 1
            rows.append((sec / letters, sec, voice, it["id"], it["text"]))
    if rows:
        r = np.array([row[0] for row in rows])
        med = float(np.median(r))
        odd = [row for row in rows if row[0] > med * 2.6 or row[0] < med / 2.6]
        print(f"\n{len(rows)} sentences; median {med:.3f} s per letter; {len(odd)} look too long or too short:")
        for row in odd:
            print(f"  {row[2]} {row[3]} {row[1]:.1f}s  {row[4]}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
