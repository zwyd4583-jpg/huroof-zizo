#!/usr/bin/env bash
# Builds the native Android project from www/ and applies Zizo World's icons, splash and settings.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d android ]; then
  npx cap add android
fi

# Capacitor's JavaScript runtime: the page has no bundler, so it loads this file directly
cp node_modules/@capacitor/core/dist/capacitor.js www/capacitor.js

# Icons, splash screens and colors
cp -R android-overlay/. android/

# Version number, signing, portrait screen
python3 scripts/patch_android.py

chmod +x android/gradlew
npx cap sync android
