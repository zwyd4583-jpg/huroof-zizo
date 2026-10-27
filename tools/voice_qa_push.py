"""Push cut clips to a branch and start the Whisper check on GitHub.

Usage: python3 voice_qa_push.py <wav_dir> <branch>
<wav_dir> holds <voice>/<id>.wav; each becomes clips/<id>.mp3 on an orphan branch.
"""
import pathlib, subprocess, sys, tempfile

REPO = "zwyd4583-jpg/huroof-zizo"


def main(wav_dir, branch):
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        (t / "clips").mkdir()
        n = 0
        for f in sorted(pathlib.Path(wav_dir).rglob("*.wav")):
            if f.name.startswith("chunk-"):
                continue
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(f), "-ac", "1", "-b:a", "48k",
                            str(t / "clips" / f"{f.stem}.mp3")], check=True)
            n += 1
        g = ["git", "-C", str(t)]
        subprocess.run(g + ["init", "-q"], check=True)
        subprocess.run(g + ["checkout", "-q", "-b", branch], check=True)
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["-c", "user.name=Claude", "-c", "user.email=noreply@anthropic.com", "commit", "-qm", f"Clips to check ({n})"], check=True)
        subprocess.run(g + ["push", "-q", "-f", f"https://github.com/{REPO}.git", branch], check=True)
    subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/actions/workflows/voice-qa.yml/dispatches",
                    "-f", "ref=main", "-f", f"inputs[branch]={branch}", "-f", "inputs[shards]=6"], check=True)
    print(f"{n} clips pushed to {branch}; check started")


if __name__ == "__main__":
    main(*sys.argv[1:3])
