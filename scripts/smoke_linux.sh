#!/usr/bin/env bash
# Smoke test of an installed Linux build (CI, before publishing): version, offline selftest,
# missing system libraries for Qt's xcb plugin, headless GUI start.
# Usage: scripts/smoke_linux.sh <command or AppImage path> <expected version>
set -euo pipefail
cob="$1"
version="$2"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
cd "$(mktemp -d)"  # bundled templates must be found next to the binary, not in the working directory

got="$("$cob" --version)"
[[ "$got" == "cob $version" ]] || { echo "version mismatch: '$got' != 'cob $version'"; exit 1; }
"$cob" selftest

# Installed packages: every system library the binary and the xcb (desktop) plugin load must be
# there, which the offscreen start below cannot show. Bundled Qt libraries resolve at runtime.
root="$(dirname "$(readlink -f "$(command -v "$cob")")")"
xcb="$(find "$root" -name 'libqxcb.so' -print -quit)"
if [[ -n "$xcb" ]]; then
    missing="$(ldd "$root/clashofbots" "$xcb" | grep 'not found' | grep -v 'libQt6\|libpyside\|libshiboken' || true)"
    [[ -z "$missing" ]] || { echo "missing system libraries:"; echo "$missing"; exit 1; }
    echo "xcb plugin libraries ok"
fi

# No arguments = GUI. If it fails to start, main() logs it and exits 0 after printing the usage,
# so the only pass is a GUI still running when the timeout stops it.
rc=0
timeout -k 5 15 "$cob" || rc=$?
[[ $rc -eq 124 ]] || { echo "GUI exited early (code $rc)"; exit 1; }
echo "smoke ok: $cob $version"
