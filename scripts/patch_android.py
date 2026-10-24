"""Patch the generated Android project.

- versionCode / versionName from the VERSION_CODE and VERSION_NAME environment variables
- release signing with signing/upload.jks when KEYSTORE_PASSWORD is set
- debug signing with the fixed test key in ci/debug.keystore
- portrait-only main screen
"""
import os
import re
import pathlib

root = pathlib.Path(__file__).resolve().parent.parent
gradle = root / "android/app/build.gradle"
manifest = root / "android/app/src/main/AndroidManifest.xml"

code = os.environ.get("VERSION_CODE", "1")
name = os.environ.get("VERSION_NAME", "1.0")

g = gradle.read_text(encoding="utf-8")
g = re.sub(r"versionCode\s+\d+", f"versionCode {int(code)}", g)
g = re.sub(r'versionName\s+"[^"]*"', f'versionName "{name}"', g)

if "signingConfigs" not in g:
    signing = '''android {
    signingConfigs {
        // the same debug key on every build machine, so test versions install over each other
        debug {
            storeFile rootProject.file("../ci/debug.keystore")
            storePassword "android"
            keyAlias "androiddebugkey"
            keyPassword "android"
        }
        release {
            def ksPass = System.getenv("KEYSTORE_PASSWORD")
            if (ksPass) {
                storeFile rootProject.file("../signing/upload.jks")
                storePassword ksPass
                keyAlias "zizo"
                keyPassword ksPass
            }
        }
    }
'''
    g = g.replace("android {\n", signing, 1)
    g, n = re.subn(
        r"(buildTypes\s*\{\s*release\s*\{)",
        r'\1\n            if (System.getenv("KEYSTORE_PASSWORD")) { signingConfig signingConfigs.release }',
        g,
        count=1,
    )
    if n != 1:
        raise SystemExit("Could not find buildTypes.release in build.gradle")
gradle.write_text(g, encoding="utf-8")

m = manifest.read_text(encoding="utf-8")
if "screenOrientation" not in m:
    m, n = re.subn(r'(android:name="\.MainActivity")', r'\1\n            android:screenOrientation="portrait"', m, count=1)
    if n != 1:
        raise SystemExit("Could not find MainActivity in AndroidManifest.xml")
manifest.write_text(m, encoding="utf-8")

print(f"Android project patched: versionCode {code}, versionName {name}, signing {'on' if os.environ.get('KEYSTORE_PASSWORD') else 'off'}")
