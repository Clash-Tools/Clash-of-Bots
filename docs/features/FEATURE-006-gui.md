# FEATURE-006: GUI (PySide6)

Goal: run the farm bot without a terminal. Last item of M2 ("first useful exe").
Design: D-001 (PySide6), D-019 (one exe, console mode hide, Essentials only).

Window (`cob/ui/main_window.py`):
- Device: adb devices + LDPlayer instances (label shows running state and resolution), Refresh.
- Loot filter: the four farm.json values (clamps match `cob/core/config.py`), Save / Defaults; saved
  again on Start so the bot and the file always agree.
- Run: cycle limit (default 5, 0 = no limit), time limit, Start farming / Stop. Controls lock while running.
- Stats: status, cycles, attacks, net gold/elixir/dark, per hour, last cycle line.
- Log: live INFO log (QtLogHandler -> signal), last 2000 lines; full DEBUG log stays in cob.log.

Threading (`cob/ui/worker.py`): FarmWorker(QThread) builds the bot with `cob/tasks/wiring.build_farm`
(same wiring as the CLI) and runs FarmTask; the window only receives signals (cycle_done,
finished_stats, failed). Stop sets the navigator stop event (same as Ctrl+C: current step ends, stats
kept). Closing the window while farming asks first, then stops and waits.

Entry: `cob gui`, or the exe without arguments (double-click). If the GUI cannot start, the old usage
text is shown instead.

Packaging: Nuitka `--enable-plugin=pyside6 --windows-console-mode=hide`; selftest imports QtWidgets.
("attach" was tried first: terminals did not wait for the exe and exit codes were lost.)
CI (Linux) installs Qt's system libraries and runs the GUI tests on QT_QPA_PLATFORM=offscreen.

Tests: offscreen Qt (no pytest-qt): filter round-trip, start without device, worker signals into stats,
Stop, build errors shown, log lines reach the window.

Verified on Windows (2026-10-18):
- Local Nuitka build with the plugin: 624-649 s, 236 MB folder; Qt platforms bundled (qwindows, qoffscreen, ...).
- CLI from PowerShell: waits, prints inline, exit codes 0 / 2 (bad command) / 0 - with mode "hide".
- Launch like a double-click (new console): only the Qt window "Clash of Bots 0.1.0-alpha.2" is visible.
- Live run through the real window + worker (offscreen render): 1 cycle, +988k gold / +1.07M elixir /
  +9.4k dark in 282 s; stats and log filled from signals.

## v2 (branch feat/gui-v2, user-chosen: preview, history, tabs + dark theme, device helper)
- Tabs: Farm (device, run, stat tiles, live view) / Settings (loot filter + breaks) / Setup / History / Log.
- Dark Fusion theme, gold accent, app icon drawn at runtime (no image asset), tray icon with
  Show / Stop farming / Quit and a notification when farming stops or fails.
- Live view: Navigator.on_frame hands the bot's own captures to the worker, which sends a 480x270
  copy every ~2 s with the screen name (no extra adb traffic); Grab button when idle.
- Setup tab: `cob/device/checks.py` (LDPlayer installed/running, instance resolution, adb + ADB
  debugging hint, screen size, CoC installed) with OK / FIX marks and Start LDPlayer / Fix resolution.
- History tab: `history.csv` (user data folder) gets a row per cycle from CLI and GUI; table shows the
  last 500 newest first, totals, Export CSV.
- Blocking calls (checks, fixes, grab) run in a small Job thread so the window never freezes.
- Live (LDPlayer 14): 1 cycle through the window, 72 preview updates across 9 screens incl. battle,
  history row + totals updated (+1.12M gold).

## Log
- 2026-10-18 (Claude Opus 5.5, Windows): v2 tabs, theme, live view, setup helper, history.
- 2026-10-18 (Claude Opus 5.5, Windows): window, worker, entry points, packaging flags.
