#!/usr/bin/env bash
# Builds the native Android project from www/ and applies Huroof Zizo's icons, splash and settings.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d android ]; then
  npx cap add android
fi

# Icons, splash screens and colors
cp -R android-overlay/. android/

# Version number, signing, portrait screen
python3 scripts/patch_android.py

chmod +x android/gradlew
npx cap sync android
