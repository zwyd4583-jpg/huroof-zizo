"""Run the phone-simulation tests.

    python3 tests/run.py                 # the everyday set (about 30 minutes, most of it test_voice)
    python3 tests/run.py quick           # everything except the long test_voice
    python3 tests/run.py test_cheer perf # only these (names without .py)

Starts a local server for www/ on 127.0.0.1:8765 if none is running, runs each script with that
server, and prints each script's last lines. A test passes when it ends with "no problems".
Needs: pip install playwright (and, the first time, python3 -m playwright install chromium).
"""
import pathlib, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
EVERYDAY = ["test_intro", "test_alive", "test_parents", "test_cheer", "test_names", "test_stories", "test_praise",
            "test_en_shop", "test_new", "test_sfx", "test_voice"]


def server_up():
    try:
        return urllib.request.urlopen("http://127.0.0.1:8765/index.html", timeout=2).status == 200
    except Exception:
        return False


def main(args):
    names = EVERYDAY if not args else [n for n in EVERYDAY if n != "test_voice"] if args == ["quick"] else args
    srv = None
    if not server_up():
        srv = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1", "-d", str(ROOT / "www")],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if server_up(): break
            time.sleep(0.1)
    failed = []
    try:
        for n in names:
            print(f"== {n}", flush=True)
            r = subprocess.run([sys.executable, str(TESTS / f"{n}.py")], cwd=TESTS, capture_output=True, text=True, timeout=1800)
            tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
            print("\n".join(tail), flush=True)
            if n.startswith("test_") and (r.returncode != 0 or not any("no problems" in l for l in tail)):
                failed.append(n)
    finally:
        if srv: srv.terminate()
    print("\nALL PASSED" if not failed else "\nFAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
