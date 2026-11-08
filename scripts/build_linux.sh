#!/usr/bin/env bash
# Builds build/ClashOfBots/clashofbots (Nuitka standalone, D-003) and packs it into
# dist/ClashOfBots-<version>-x86_64.{deb,rpm,AppImage}. Linux counterpart of build_windows.ps1.
# Run from repo root on Linux after: uv sync --python 3.13 --group build
# Needs patchelf, nfpm and appimagetool (+ its type2 runtime file) on PATH, or set
#   NFPM=/path/nfpm APPIMAGETOOL=/path/appimagetool APPIMAGE_RUNTIME=/path/runtime-x86_64
# adb is not bundled: the packages depend on the distro's adb, the AppImage expects it on PATH.
set -euo pipefail

version="${1:-$(uv run python scripts/release.py current)}"
nfpm="${NFPM:-nfpm}"
appimagetool="${APPIMAGETOOL:-appimagetool}"
echo "building Clash of Bots $version"

dist=build/ClashOfBots
rm -rf build dist
mkdir -p dist

# One binary for GUI and CLI: no arguments opens the GUI, any argument runs the command line.
uv run python -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --enable-plugin=pyside6 \
    --python-flag=-m \
    --include-package=cob \
    --include-data-dir=assets=assets \
    --output-dir=build \
    --output-filename=clashofbots \
    cob

# Nuitka names the folder after the package (cob.dist); normalise.
mv build/cob.dist "$dist"

# The app icon is drawn in code (cob/ui/theme.py); render it once for the menu entry.
QT_QPA_PLATFORM=offscreen uv run python - <<'EOF'
from PySide6.QtGui import QGuiApplication

from cob.ui.theme import app_icon

app = QGuiApplication([])
assert app_icon(256).pixmap(256, 256).save("build/clash-of-bots.png")
EOF

# .deb + .rpm (layout, dependencies and launchers in packaging/linux/nfpm.yaml).
for fmt in deb rpm; do
    VERSION="$version" "$nfpm" package --config packaging/linux/nfpm.yaml --packager "$fmt" \
        --target "dist/ClashOfBots-$version-x86_64.$fmt"
done

# AppImage: same tree under opt/, AppRun starts the binary.
appdir=build/AppDir
mkdir -p "$appdir/opt"
cp -a "$dist" "$appdir/opt/clash-of-bots"
install -m 755 packaging/linux/AppRun "$appdir/AppRun"
cp packaging/linux/clash-of-bots.desktop "$appdir/"
cp build/clash-of-bots.png "$appdir/clash-of-bots.png"
ln -s clash-of-bots.png "$appdir/.DirIcon"
runtime=()
if [[ -n "${APPIMAGE_RUNTIME:-}" ]]; then
    runtime=(--runtime-file "$APPIMAGE_RUNTIME")
fi
ARCH=x86_64 VERSION="$version" "$appimagetool" --no-appstream "${runtime[@]}" \
    "$appdir" "dist/ClashOfBots-$version-x86_64.AppImage"

(cd dist && for f in ClashOfBots-*; do sha256sum "$f" > "$f.sha256"; done)
echo "built:" && ls -l dist
