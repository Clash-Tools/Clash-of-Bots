# TESTING

## Every change (Linux or Windows)
```
uv run ruff check .        # expect: All checks passed!
uv run pytest -q           # expect: N passed, 0 failed
uv run cob selftest        # expect: selftest ok: ...
```

The pre-push hook runs the first two before every push (`git config core.hooksPath .githooks`, once
per clone; `git push --no-verify` skips it). PR CI is Linux-only (D-012): for a change that may behave
differently on Windows (signals, paths, subprocess), add the `build-exe` label to the PR or run the
build-exe workflow on the branch, which runs the tests on Windows before building.

## Live device (Windows + LDPlayer, instance at 1600x900@240)
LDPlayer ships with ADB debugging off: Settings > Other settings > ADB debugging (local), then restart the instance.
```
uv run cob devices                       # instance listed as running, emulator-5554
uv run cob capture -s emulator-5554      # PNG in captures/, no size warning
uv run cob bench -s emulator-5554 --tap  # capture/tap mean and p95
```

## Exe (CI artifact or scripts/build_windows.ps1)
Local build needs VS 2022 C++ tools; set `$env:NUITKA_CACHE_DIR="$PWD\.nuitka-cache"` for fast rebuilds.
```
ClashOfBots.exe selftest         # prints qt version too; exit code 0
ClashOfBots.exe devices
```
Double-click the exe: only the "Clash of Bots" window opens (no console). Start farming with Cycles = 1.

## Release check (stable)
Built exe against a live instance: `farm --cycles 2` (collect + both attack endings), `bb --attacks 1`
(boat both ways), `logs --last 3` shows one session file per bot run; resource gains plausible
(a misread drop below half is logged as "looks like a misread").
