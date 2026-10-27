"""Shared pieces of the phone-simulation tests.

Every test opens the app in a headless phone-sized Chromium (Playwright) from the local server that
tests/run.py starts (http://127.0.0.1:8765, serving www/). BRIDGE stands in for the Android app around
the page: the phone's speech engine (what it would say is collected in window.__spoken) and the back
button (window.__back). window.__zizoTest turns on the app's test hooks.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "out"          # screenshots and reports; not committed
URL = "http://127.0.0.1:8765/index.html"


def out(name):
    """A folder under tests/out for a test's pictures."""
    p = OUT / name
    p.mkdir(parents=True, exist_ok=True)
    return p


BRIDGE = """
window.__spoken = []; window.__back = null; window.__zizoTest = {};
window.Capacitor = {
  isNativePlatform: () => true,
  registerPlugin: (name) => {
    if (name === 'TextToSpeech') return {
      speak: (o) => { window.__spoken.push((o.lang.startsWith('en') ? 'EN:' : '') + o.text); return Promise.resolve(); },
      stop: () => Promise.resolve(),
      isLanguageSupported: () => Promise.resolve({ supported: true }),
      openInstall: () => Promise.resolve()
    };
    return { addListener: (ev, fn) => { if (ev === 'backButton') window.__back = fn; }, exitApp: () => { window.__exited = true; } };
  }
};
"""
