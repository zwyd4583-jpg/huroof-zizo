"""Start the phone's speech engine only when the app first asks for it.

The text-to-speech plugin starts Android's speech engine as soon as the app opens. Starting the
engine keeps the phone busy for a moment, right while the opening animation plays, and the animation
stutters. Nearly everything Zizo says is recorded, so the engine is only needed later, if at all.

This changes the plugin (in node_modules, before the Android build) so that:
- the engine is created the first time the app calls the plugin, not when the app opens
- stop() does nothing when the engine was never started (it does not start it)
- isLanguageSupported() answers "not ready yet" while the engine is still starting, so the app asks
  again instead of wrongly deciding the Arabic voice is missing
"""
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
java = root / "node_modules/@capacitor-community/text-to-speech/android/src/main/java/com/getcapacitor/community/tts/TextToSpeechPlugin.java"
src = java.read_text(encoding="utf-8")

if "private synchronized TextToSpeech impl()" in src:
    print("speech plugin: already patched")
    sys.exit(0)


def rep(old, new, count=1):
    global src
    if src.count(old) != count:
        raise SystemExit(f"speech plugin: expected {count} of {old!r}, found {src.count(old)}")
    src = src.replace(old, new)


rep("""    @Override
    public void load() {
        implementation = new TextToSpeech(getContext());
    }
""", """    @Override
    public void load() {
        // the engine is started on first use (see impl()), not while the app is opening
    }

    private synchronized TextToSpeech impl() {
        if (implementation == null) {
            implementation = new TextToSpeech(getContext());
        }
        return implementation;
    }
""")
# stop: nothing to stop if the engine never started
rep("""    public void stop(PluginCall call) {
        boolean isAvailable = implementation.isAvailable();""", """    public void stop(PluginCall call) {
        if (implementation == null) {
            call.resolve();
            return;
        }
        boolean isAvailable = implementation.isAvailable();""")
# isLanguageSupported: "not ready yet" while the engine is starting
rep("""        String lang = call.getString("lang", "");
        try {
            boolean isLanguageSupported = implementation.isLanguageSupported(lang);""", """        String lang = call.getString("lang", "");
        if (!impl().isAvailable()) {
            call.unavailable("Not yet initialized or not available on this device.");
            return;
        }
        try {
            boolean isLanguageSupported = implementation.isLanguageSupported(lang);""")
# destroy: only if it was started
rep("""    protected void handleOnDestroy() {
        implementation.onDestroy();""", """    protected void handleOnDestroy() {
        if (implementation == null) {
            return;
        }
        implementation.onDestroy();""")
# every other use goes through impl(), which starts the engine the first time
rep("""        boolean isAvailable = implementation.isAvailable();
        if (!isAvailable) {
            call.unavailable("Not yet initialized or not available on this device.");
            return;
        }

        String text""", """        boolean isAvailable = impl().isAvailable();
        if (!isAvailable) {
            call.unavailable("Not yet initialized or not available on this device.");
            return;
        }

        String text""")
rep("JSArray languages = implementation.getSupportedLanguages();", "JSArray languages = impl().getSupportedLanguages();")
rep("JSArray voices = implementation.getSupportedVoices();", "JSArray voices = impl().getSupportedVoices();")
rep("            implementation.openInstall();", "            impl().openInstall();")

java.write_text(src, encoding="utf-8")
print("speech plugin: engine now starts on first use")
