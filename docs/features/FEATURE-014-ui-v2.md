# FEATURE-014: Desktop UI v2 (epic #61)

Goal: rebuild the PySide6 GUI to match the Stitch designs (docs/design/stitch/SCREENS.md), wiring real
features only. Design decisions: D-026.

Order (one PR per item, board: "Clash of Bots Roadmap", epic #61):
1. #62 foundation - tokens, QSS, fonts, icons, shared widgets, `cob ui-gallery`   <- this PR
2. #49 app shell - top bar, navigation rail, status strip, Kill Switch / Esc
3. #63 Dashboard (idle / running / stopped by safety) + FarmTask step signal + session timer
4. #50 Devices, #64 Automation, #42 Safety & Schedule (+ daily limits / quiet hours), #65 History,
   #66 Logs, #67 Settings, #51 First-run wizard

Foundation (#62):
- `cob/ui/style/tokens.py` colours / type / spacing; `qss.py` stylesheet + Fusion palette (`apply`)
- `fonts.py` registers assets/fonts; `icons.py` tinted, cached Material Symbols from assets/icons
- `cob/ui/widgets/`: Card, StatTile, StatusPill, Chip, Banner, UnsavedBar, IconLabel, SegmentedControl,
  Switch, ToggleRow, NumberField, StepPipeline
- Qt rule found: a border-radius above half the widget height is dropped -> pills have fixed heights,
  CTA radius 26 for 52 px buttons
- Old window still uses the old theme until the shell PR switches over.

App shell (#49):
- `cob/ui/shell.py` Shell: 64 px top bar (logo, device pill = device picker + refresh, run-state pill,
  Kill Switch), 96 px navigation rail (7 pages), page stack with 32 px margins, 40 px status strip
  (connection, current step, session timer, safety)
- MainWindow pages: Dashboard (old Farm tab until #63), Devices (old Setup), Automation (old Settings),
  History, Logs; Safety (#42) and Settings (#67) show "coming soon" cards, no fake data
- States: running / break / idle; a stop that is not a user stop or a reached limit (failures in a row,
  device lost, gold below reserve, errors) shows "stopped" (safety) state
- Esc and the Kill Switch both request a stop after the current step; app icon = Stitch logo
- QSS: the dropdown arrow is a tinted PNG written once to the user cache folder (QSS needs files)

Dashboard (#63):
- `cob/ui/pages/dashboard.py` DashboardPage: live view (16:9, scene, "updated Xs ago", Grab), cycle
  pipeline driven by `FarmTask(on_step=...)` -> `FarmWorker.step`, recent activity (last 6 log lines),
  run configuration (Home/Builder segmented, cycles/time limits with hints, Start/Stop swap), 6 stat
  tiles with per-hour subs, last completed cycle, guardrail chips from farm.json, safety-stop banner
- Left out on purpose (no backing data): FPS/latency, detection boxes, stars/%, trophies, thermal,
  confidence %, profile name (SCREENS.md 4.1)

Automation (#64):
- `cob/ui/pages/automation.py` AutomationPage: category list (scrolls to section), sections Farming,
  Builder Base (info), Collectors, Clan Castle (+ "bot never types" note), Clan Games (coming soon, #38),
  Upgrades (spending guard banner, walls switch needing typed SPEND, reserve), Pacing (breaks)
- Every FarmConfig field has exactly one control (test); unsaved-changes bar with Discard / Save;
  Restore defaults marks the form dirty until saved
- Qt gotcha: "&" in button text is a mnemonic -> escape as "&&"

History (#65):
- history.csv gains a `mode` column (home / bb); files from older versions are rewritten once with the
  new header through a temp file (old rows: empty mode = home)
- `cob/ui/pages/history.py`: range (Today / 7 / 30 days / All) and mode filters, search, 6 KPI tiles
  (compact values, exact in tooltip), loot-per-day and attacks-per-day bar charts, cycle log table
- `cob/ui/widgets/chart.py` BarChart drawn with QPainter (no QtCharts in pyside6-essentials)
- Left out: stars, % destruction, town hall, strategy, opponent (no data)

Logs (#66):
- LogBridge also emits `LogLine` records (time, level, module, message); `MainWindow.connect_log`
  routes lines to the dashboard activity and records to the Logs page
- `cob/ui/pages/logs.py`: level chips with counts, keyword/regex search (bad regex = plain text),
  follow tail, wrap, copy visible, clear, open folder; selecting a "snapshot saved: <png>" line shows
  the screenshot
- `cob/core/diagnostics.py`: zip of session logs + farm.json + summary; IPv4 (not 127.x), phone serials,
  adb mDNS names, home folder and user name scrubbed; screenshots never included
- Qt gotcha: the app QSS font beats setFont -> set the mono font in the widget's own stylesheet

Devices (#50):
- `cob/ui/pages/devices.py`: connected devices (Use switches the top-bar device), phones found on the
  network (Connect), Add device (Scan QR), pairing code / connect by address / USB to Wi-Fi / restore
  screen, health checks with Start LDPlayer / Fix resolution; old Setup-tab names kept as aliases
- Left out: battery, latency, "inspect telemetry" (no data)
- Qt gotcha: deleteLater keeps a removed row painted until the next event loop turn -> hide + unparent

Settings (#67):
- `cob/core/ui_settings.py` UiSettings in ui.json (validated: wrong types -> defaults): start minimised,
  notify on safety stop / finished / breaks; `folder_sizes` for the storage bars
- `cob/ui/pages/settings.py`: appearance (dark only, light disabled), tray & notification toggles + test,
  data folder, storage per category, export / import farm.json (import lands unsaved in Automation),
  reset to defaults (confirm), release channel from the version, releases link, privacy card, about
- `_notify(kind)` follows the toggles; breaks can notify; the app starts in the tray when asked
- Left out: language, launch at OS startup, network update check (CONSTRAINTS: no network calls)

Safety & Schedule (#42, D-027):
- farm.json: max_failures, daily_minutes, daily_attacks, quiet_from, quiet_to; `cob/tasks/schedule.py`
  (quiet hours, today's usage from history.csv, stop reasons) checked by FarmTask before every cycle
- `ConfigPage` base (automation.py): pages own a subset of farm.json fields; the window merges them
- `cob/ui/pages/safety.py`: breaks (moved from Automation), daily limits with today's progress, quiet
  hours, stop rules (failures field + read-only descriptions of the built-in rules), spending
  guarantees, emergency stop (Esc / Kill Switch), account notice; dashboard guardrail chips show the
  daily limit and quiet hours
- Left out: presets, detection score, firmware claims, system-wide hotkey

First-run wizard (#51):
- `cob/ui/wizard.py` SetupWizard: Welcome, Risk notice (required checkbox), Target (LDPlayer / USB / Wi-Fi),
  Connect (refresh / Start LDPlayer / Scan QR, "Use this device"), Diagnostics (the window's health
  checks); the window passes its own actions in, no device code in the wizard
- ui.json: wizard_done, risk_accepted; the app opens the wizard until it is finished once; Settings >
  About has "Run setup wizard"
- Left out: handshake stats (transport speed, FPS, test ping), global hotkey claim

## Log
- 2026-10-26 (Claude Opus 5.5): foundation + gallery + 5 tests (fonts, icon tint, every icon used is
  bundled, widget states, gallery render).
- 2026-10-26 (Claude Opus 5.5): app shell + 9 tests (rail, states, Kill Switch/Esc, timer, safety stops).
- 2026-10-26 (Claude Opus 5.5): dashboard + farm on_step; GUI tests moved to the dashboard API; 312 pass.
- 2026-10-26 (Claude Opus 5.5): automation page + 7 page tests.
- 2026-10-26 (Claude Opus 5.5): history page, mode column, charts + 4 tests.
- 2026-10-26 (Claude Opus 5.5): logs page + sanitized diagnostics + 3 tests.
- 2026-10-26 (Claude Opus 5.5): devices page + 2 tests.
- 2026-10-26 (Claude Opus 5.5): settings page + ui.json + 3 tests.
- 2026-10-26 (Claude Opus 5.5): safety page + schedule engine (D-027) + 7 tests.
- 2026-10-26 (Claude Opus 5.5): first-run wizard + 2 tests; epic #61 screens complete.
