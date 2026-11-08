# Changelog

All notable changes to Clash of Bots. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [SemVer 2.0](https://semver.org/) with release channels (see docs/RELEASING.md):

- **Alpha** (`X.Y.Z-alpha.N`): early, features incomplete, may break. Testers only.
- **Beta** (`X.Y.Z-beta.N`): feature complete for the cycle, bug hunting.
- **Release Candidate** (`X.Y.Z-rc.N`): ship-ready unless a blocker is found.
- **Stable** (`X.Y.Z`): recommended for everyone.

Sections below are generated from Conventional Commits by `scripts/release.py`;
hand-written highlights go under Unreleased and are moved into the next release.

## [Unreleased]

First public release, now under [Clash-Tools](https://github.com/Clash-Tools) with GPL-3.0, the
[hard rules](docs/RULES.md) and the unit database in
[clash-of-bots-data](https://github.com/Clash-Tools/clash-of-bots-data).

- **Attack:** super troops (red cards) are deployed again, and spell cards are cast after the troops and
  hero abilities, a little inside the attacked edge ("Cast spells", on by default).
- **Attack:** "Deploy on two sides" spreads troops along two neighbouring edges around a corner (off by
  default).
- **Phone alerts:** safety stops, errors, finished runs and breaks can also go to a Discord webhook or a
  Telegram bot (Settings > Tray & Notifications).
- **Profiles:** several accounts or LDPlayer instances, each with its own device, settings, daily limits
  and history rows. Switch the active profile in the top bar, manage them on the new Profiles page, and
  "Run in turn" farms the ticked profiles one after another (`cob profiles`, `cob farm --profile ID`).
- **Army detection:** every troop, spell, hero and pet card in the bar is recognised from portraits
  rendered from the game's own icons (unit database data-v2), event units included; the recognised unit
  decides whether a card is a troop, spell or hero, so red super troop cards are never cast as spells.
  Siege machines still use pictures labelled on the Cards page.
- **Clash of Clans API sync:** with your own key from developer.clashofclans.com (Settings) and a
  player tag per profile, Sync reads that account's troops, spells, heroes, pets and equipment with
  levels; the Cards page lists your own units first. Opt-in, only the player tag is sent.
- **Maintenance:** a game stuck on the loading screen (maintenance, server outage) is closed and retried
  after 10, 20, then 30 min instead of ending the run (Safety > Stop Rules).

## [0.6.2] - 2026-11-07

Channel: **Stable**

### Features

- **army:** load a chosen Saved Recipe as the army when a run starts (#186)

### Bug Fixes

- **army:** tap again when a freshly opened screen ignores the tap (#187)

### Performance

- **vision:** match dialogs at the phone's 2 % larger scale (#184)

## [0.6.1] - 2026-11-06

Channel: **Stable**

### Bug Fixes

- **ui:** clear the last error on a new run and tidy the dashboard (#177)
  - A new run clears the previous run's "Stopped: ..." pipeline note.
  - Errors (phone locked, device gone) get their own "Farming stopped" banner instead of the safety-rule one.
  - The live picture fills its card instead of a 240 px band. On tall windows the last-cycle card sits under the run controls, on short ones it stays in the bottom row.
  - The device picker and status strip show 'moto g84 5G  •  Wi-Fi'; the adb serial moves to the tooltip.
  - The status strip stops saying 'Looking for Wi-Fi phones…' once the lookup ends.
  - No loot icons without numbers before the first cycle.
- **attack:** fit red-scenery bases on the line alone; keep the shade out (#179)
  - find_base falls back to line_mask when the colour fit is implausible: only 1-2 px ridges that are redder than both sides across an isometric direction and run straight along it. Party stripes, striped tents and an orange carpet under the line no longer skip the base. Deploy points are checked against that line, not the scenery.
  - "army not ready" is matched exactly, and waiting for the army no longer counts towards the failures-in-a-row stop.
  - A timed-out wait keeps the frame it saw instead; search failure reports save it as seen.png.
  - The notification shade counts as another app: reports blank it, and the navigator closes it (cmd statusbar collapse) instead of restarting the game.
- **search:** wait for the army when the attack menu says it is training (#181)

### CI

- keep build artifacts for 3 days instead of 14 (#182)
- release through a draft release, without workflow artifacts (#183)
  - release.yml creates a draft release first. The Windows and Linux builds upload their files straight to it, and publish un-drafts it once all builds have passed.
  - The Linux .deb and .rpm smoke tests run in docker containers inside the build job (the AppImage on the runner), so no artifact carries the packages to another job.
  - Manual build-exe / build-linux runs still upload an artifact, but a full quota no longer fails them (continue-on-error).

## [0.6.0] - 2026-11-05

Channel: **Stable**

### Features

- **schedule:** random daily attack limit and a random rest each day (#154)
  - daily_attacks_max: above daily_attacks, each day's attack limit is drawn from daily_attacks..daily_attacks_max.
  - off_hours: one rest of this many hours a day, starting at a random hour (it may run past midnight). The run stops in it like in quiet hours.
  - Both are drawn once per day from the date and a per-install seed, so every run that day sees the same values and two computers differ.
  - Safety > Daily Limits shows today's drawn limit; Safety > Quiet Hours shows today's random rest.
- **automation:** wait out a village opened on another device, then reload (#155)
  - New template other_device_reload (the popup's RELOAD), cut from the other_device fixture; the old reload_button template does not match it.
  - Navigator.reload_other_device() taps it only on that popup.
- **schedule:** rest through quiet hours and daily limits, then farm on (#156)
- **device:** restart LDPlayer when the game keeps failing (#157)
  - AdbDevice.crashed() also spots Android's 'isn't responding' dialog (Application Not Responding: <package>), so a hung game gets the same one app restart as a crash.
  - When the game fails again after that restart (GameCrashed), the farm restarts the LDPlayer instance once per run through ldconsole (quit, launch, wait for adb) and carries on. Phones have no such hook and stop as before.
  - LdConsole.restart(index, serial).
- **ui:** pause and resume a run (#158)
  - FarmTask.pause (threading.Event), checked at the top of each cycle.
  - FarmWorker.set_paused() / is_paused(); the status pill shows Paused.
  - Material Symbols 'pause' icon added to assets/icons.
- **automation:** stop attacking while gold and elixir storages are full (#160)
  - cob.attack.storage reads the fill of the gold and elixir bars on the home screen: the run of fill colour from the icon end of each bar. Dark elixir is left out (its fill is near black).
  - The farm stops the run with 'storages full (gold N%, elixir N%)', or, with 'Farm on after a rest' (D-031), skips the attack and looks again every 5 min while maintenance (collect, walls) keeps running.
  - Each check logs the measured fill, to verify the reading live.
- **diagnostics:** save a failure report for every failure and export them as a zip (#171)
- **diagnostics:** log what was on screen when a wait times out (#174)

### Bug Fixes

- **ui:** show devices at once and a loader while work runs (#163)
  - fix(ui): show devices at once and a loader while work runs
  - The adb / LDPlayer list is shown at once; the Wi-Fi reconnect runs after it in the background and lists the phone again if it came back.
  - Remembered addresses keep one (the newest) port per IP; reconnects and the scan fallback run in parallel with a 3 s timeout.
  - build: commit the pre-push hook as executable
- **attack:** attack bases whose red line reaches the map edge (#165)
  - The outline is fitted on the thin red line only: thick red (buildings, painted ground, tents, UI) is removed with a morphological opening.
  - When the mask is clean (at most 30 % of it thick), the outline may be up to 1720 x 1260 px. With much thick red about (scenery), the old limit stays, so a polluted fit is still skipped rather than deploying into the scenery.
- **attack:** keep waiting for the battle screen when captures are slow (#169)
- **diagnostics:** keep other apps out of failure reports (#172)

### Performance

- **attack:** batch deploy taps and log where each cycle's time goes (#167)
- **attack:** remember deploy points the game took or refused (#173)
- **device:** capture only the troop bar rows for deploy checks (#175)

### Build

- run ruff and the tests before every push (#159)

## [0.5.1] - 2026-11-04

Channel: **Stable**

### Features

- **attack:** end the battle when loot stops coming in (#152)
  - loot_stall_s: when the Available Loot rows have not changed for this long (read with the search's loot reader; they read cleanly on all 16 battle frames of a real capture, and stood still for about 14 s once mid-battle, so the timer should be generous).
  - end_at_damage: once damage reaches this %.

### Tests

- **device:** raise SIGINT with raise_signal, not os.kill (#153)

## [0.5.0] - 2026-11-04

Channel: **Stable**

### Features

- **ui:** give health checks their own page and add a device recheck
- **ui:** show settings pages one category at a time
- **ui:** add light and AMOLED themes and an accent colour
- **ui:** prepare translations with tr() and JSON catalogs
- **release:** check GitHub for a newer release and show its changelog
- **ui:** translate every page, the wizard, the QR dialog and the tray (#146)
  - StatusPill shows a translated caption instead of the raw state key.
  - The status strip takes its icon as a parameter instead of checking whether the English text starts with 'stopped' or 'error'.
  - Logs level chips show translated names; the filter keeps raw levels.
  - New test: a pseudo-translation of every string must leave no English on any page or in the wizard.
- **search:** lower the loot minimums gradually while searching (#151)

### Bug Fixes

- **attack:** verify troop deployment completion
- **ui:** compact dashboard and stabilize controls
- **ui:** animate the switch thumb instead of moving the switch
- **attack:** place large troop stacks in full
- **ui:** fit the dashboard on screen without scrolling
- **attack:** end the battle watch on a 3-star win (#144)
  - fix(device): restore screen timeout and stay-on, never save the bot's mode as the phone's own
  - fix(attack): end the battle watch on a 3-star win
  - Search for Return Home over a wider area, so a shifted button on the 3-star results layout still marks BATTLE_END.
  - Treat the home village during the watch as the end of the battle.
  - Save one snapshot of the first non-battle screen after 100 %, to build a dedicated template from the next live run.
  - Report a user stop mid-battle as 'stopped', not 'battle did not end'.
- **device:** restore screen timeout and stay-on, never save the bot's mode as the phone's own (#145)
- **device:** open the game at once over another app, never restore stay-awake (#148)
- **device:** finish the phone restore even when Ctrl+C comes twice (#149)
  - end() holds SIGINT back until the settings are put back and the record is saved, then passes it on (main thread only).
  - Screen-on and the timeout are restored before size and density: a phone left awake is worse than one left at the bot's size.
- **nav:** stop the run when Clash of Clans keeps crashing (#150)
  - AdbDevice.crashed() spots Android's crash dialog for the game.
  - The first crash gets one force-stop restart, which also closes the dialog. A second one before the village shows raises GameCrashed with a message saying what to do. Each crash saves a snapshot.
  - PhoneLocked and GameCrashed share a RunBlocked base; the farm stops at once on either instead of retrying.

## [0.4.0] - 2026-10-27

Channel: **Stable**

### Features

- **ui:** UI v2 foundation - design tokens, fonts, icons and shared widgets
  - cob/ui/style: tokens from the Stitch design system, generated QSS + Fusion palette, bundled font registration, tinted and cached Material Symbols icons
  - cob/ui/widgets: Card, StatTile, StatusPill, Chip, Banner, UnsavedBar, SegmentedControl, M3 Switch, ToggleRow, NumberField, StepPipeline
  - assets: Inter, Roboto Flex, JetBrains Mono (OFL) and 132 Material Symbols SVGs (Apache 2.0)
  - cob ui-gallery shows every widget; --screenshot renders it offscreen
  - tests: fonts, icon tint, every icon used by UI code is bundled, widget states, gallery render
- **ui:** app shell with navigation rail, top bar and status strip
  - Shell: top bar (logo, device picker pill, run-state pill, Kill Switch), 96 px navigation rail with seven pages, page stack, 40 px status strip (connection, current step, session timer, safety)
  - MainWindow moves its tabs into rail pages; Safety and Settings show coming-soon cards (#42, #67)
  - Run states running / break / idle / stopped; stops other than a user stop or a reached limit are shown as safety stops
  - Esc and the Kill Switch stop after the current step; new app icon from the Stitch logo
  - App uses the UI v2 stylesheet; dropdown arrow drawn from the bundled icon
  - 9 tests: rail, states, Kill Switch and Esc, session timer, safety-stop classification
- **ui:** Mission Control dashboard with live view, cycle pipeline and guardrails
  - FarmTask reports its step (collect, search, attack, return, break) through on_step; the worker forwards it as a signal; a failing display hook never stops the loop
  - DashboardPage: live view with detected scene and age, cycle pipeline, recent activity, run configuration with Home/Builder Base switch and limit hints, Start/Stop swap, six stat tiles with per-hour rates, last completed cycle, guardrail chips from farm.json, safety-stop banner
  - Status strip shows stop and error messages without the current-step prefix
  - GUI tests use the dashboard; new farm tests for the step order and a failing step callback
- **ui:** Automation settings page with categories and spending guard
  - AutomationPage: category list that scrolls to its section; Farming, Builder Base, Collectors, Clan Castle, Clan Games (coming soon), Upgrades and Pacing sections built from the farm.json fields
  - Wall upgrades stay off until SPEND is typed; turning the switch off sets walls to 0
  - Unsaved-changes bar with Discard and Save; Restore defaults is not saved until Save
  - Card can show its header row without a title; ampersands escaped in button text
  - 7 page tests: dashboard numbers and states, automation dirty tracking, walls confirmation, one control per FarmConfig field
- **ui:** History and analytics page with filters and per-day charts
  - history.csv records the run mode (home village or Builder Base); older files get the new header once, written through a temp file
  - HistoryPage: range and mode filters, search, totals, attacks, run time and yield per hour tiles, loot-per-day and attacks-per-day charts, newest-first cycle log with export and reload
  - BarChart widget drawn with QPainter
  - Tests for filtering, totals, per-day buckets, the page table and chart axis rounding
- **ui:** Logs page with level filters and sanitized diagnostics
  - Log bridge emits structured records; the window routes them to the Logs page and the formatted lines to the dashboard activity card
  - LogsPage: level chips with counts, keyword or regex filter, follow tail, wrap, copy visible, clear view, open folder; a line that saved a snapshot shows the screenshot when selected
  - Save diagnostics: zip of session logs, farm.json and a summary with IP addresses, phone serials, adb mDNS names, home folder and user name removed; screenshots are never included
  - Tests for filtering, counts, snapshot preview and scrubbing
- **ui:** Devices page with QR pairing, nearby phones and health checks
  - DevicesPage: connected devices with a Use button that switches the top-bar device, phones found on the network with Connect, Add device (Scan QR), pairing code, connect by address, USB to Wi-Fi and restore phone screen, health checks with Start LDPlayer and Fix resolution
  - The window keeps the Setup-tab widget names as aliases
  - Rows are detached at once when lists refresh, so old rows never overlap new ones
  - Tests for the lists, signals, device icons and the top-bar switch
- **ui:** Settings page with tray, notifications and data management
  - ui.json preferences (validated on load): start minimised to tray, notifications for safety stops, finished runs and breaks; the app honours start minimised and the window filters notifications
  - SettingsPage: dark theme (light not built yet), tray and notification toggles with a test button, data folder with storage per category, export and import of farm.json, reset to defaults, release channel from the version, releases link, privacy and about cards
  - No network update check: the app makes no network calls of its own
  - Icon test only reads (key, Title, icon) tuples; tests for ui.json, the page and notification rules
- **safety:** daily limits, quiet hours and the Safety & Schedule page
  - farm.json gains max_failures, daily_minutes, daily_attacks, quiet_from and quiet_to; the farm loop stops before a cycle when a rule is reached, using today's history.csv totals (D-027)
  - ConfigPage base lets the Automation and Safety pages each own part of farm.json; the window saves them as one file
  - SafetyPage: breaks (moved from Automation), daily limits with today's progress, quiet hours, stop rules, spending guarantees, emergency stop and account notice
  - Dashboard guardrail chips show the daily limit and quiet hours
  - Tests for quiet hours, today's usage, stop reasons, the loop stopping, config round trip and the page
- **ui:** first-run setup wizard
  - SetupWizard: welcome, risk notice with required consent, target choice (LDPlayer, USB phone, Wi-Fi phone), connect step with refresh, Start LDPlayer and QR pairing, and the health checks
  - The wizard uses the window's own device actions; it opens until finished once, and Settings can run it again; consent and completion are kept in ui.json
  - Tests for the step gating (consent, device), device pick, checks summary and saved state

### Bug Fixes

- **ui:** look up devices in the background so the window never freezes
  - The app runs the device lookup (adb reconnects, network discovery, LDPlayer list) in a Job; the status strip shows 'Looking for devices…' and Refresh is disabled until it finishes
  - A second refresh while one runs is folded into the running one
  - devices_refreshed signal updates the Devices page and the wizard's device list
  - Tests keep the synchronous path with fast fakes; new test for the background path
- **ui:** wizard tells you to keep the phone unlocked
  - Connect step for USB and Wi-Fi phones asks to keep the phone unlocked with the screen on
  - Diagnostics names the fix when the phone-unlocked check fails
- **device:** find a Wi-Fi phone without mDNS and clean up dead entries
  - reconnect_all falls back to scanning remembered phone IPs for the new Wireless debugging port when remembered addresses and mDNS bring no Wi-Fi phone back; hosts that do not answer are skipped
  - Connect timeout 15 s and remembered-address retries 8 s for slow Wi-Fi
  - Offline ip:port leftovers are disconnected after a connect or a reconnect
  - D-025 addendum and FEATURE-012 notes with the live result; tests for the scan, the fallback choice and the cleanup
- **attack:** give troops time to reach the base and read resources once settled
  - No-damage grace: while the damage bar is still empty (under 6 px) the attack waits up to 45 s before surrendering; the 15 s stall rule applies once damage has started
  - Every stall surrender saves a snapshot for later checks
  - Own resources are read only when two reads 1.5 s apart agree, so collected loot or battle rewards still flying into the storages are not counted as farmed; no agreement records no gain
  - Tests for the grace period and the snapshot; FEATURE-012 notes on the live case
- **phone:** keep the screen awake during a run and stop when the phone locks
  - The phone's screen timeout is saved, set to 30 min while the bot runs and restored afterwards, so a phone on battery (stay-on only works while plugged in) no longer times out mid-run
  - On an unknown screen the navigator checks a phone's lock screen first: a dark screen is woken, a locked phone raises PhoneLocked instead of restarting the game for minutes
  - The farm loop stops the run on PhoneLocked with a clear reason (shown as a safety stop)
  - Tests for the timeout round trip, the lock check and the farm stop
- **search:** notice the next base by its loot and attack when the scout timer runs out
  - After Next the next base counts as shown once the screen changes or the loot read changes; with ~1 s captures over Wi-Fi the short cloud transition was never seen and the bot waited through the next base's scout timer
  - A battle that starts during the search (scout timer ran out) is handed to the attack instead of failing with 'no search screen' and idling until it ends
  - Tests for both cases
- **attack:** read the damage percentage and surrender through End Battle
  - fix(attack): read the damage percentage and surrender through End Battle
  - chore(attack): log each new damage reading at debug level
- **search:** keep the first digit of the elixir and dark loot rows
  - fix(search): keep the first digit of the elixir and dark loot rows
  - chore(farm): log own resources before and after each cycle
- **attack:** see a troop placement in the card's count
- **phone:** only the device that started the bot's display mode ends it

### Documentation

- **design:** add Stitch screens, implementation spec and UI v2 decision
  - docs/design/stitch: SCREENS.md (tokens, shell, per-screen spec, feature mapping, order), desktop and mobile previews + HTML, logo; full-size screenshots stay local (gitignored)
  - D-026 dark Material 3 tokens, bundled SVG icons and fonts; bundled assets logged in DEPENDENCIES
  - FEATURE-014 plan for epic #61

### Tests

- **ui:** split a long assertion; document the Devices page
  - FEATURE-014 Devices section and log entry

## [0.3.0] - 2026-10-26

Channel: **Stable**

### Highlights

- **Pair a phone by scanning a QR code**: Setup > Phone > *Scan QR to pair (Wi-Fi)*, then on the phone
  Wireless debugging > *Pair device with QR code*. No IP addresses or codes to type (Android 11+).
- **Phones found on the network**: *Nearby phones* lists phones with Wireless debugging on; phones the
  bot used before reconnect by themselves, also after the phone restarts on a new port.
- CLI: `cob pair-qr` (QR code in the terminal) and `cob discover`.

### Features

- **phone:** pair by QR code and find phones on the network (mDNS)
  - discovery: browse the adb server's mDNS (_adb-tls-connect / _adb-tls-pairing), phone serial from the service name, nearby list (known / connected), auto-connect known phones, address by serial
  - qr_pair: random name + password (secrets) as WIFI:T:ADB QR, pair only with the phone announcing our name, then connect to the service on the same IP or reuse adb's own mDNS connection; 2 min expiry
  - wireless.pair accepts QR passwords; reconnect_all = remembered addresses + mDNS
  - farm-loop reconnect follows a Wi-Fi phone to its new port or mDNS name (AdbDevice.rebind)
  - GUI Setup > Phone: Scan QR dialog (QR, steps, countdown, live status), Nearby phones Find/Connect
  - CLI: cob pair-qr (QR in the terminal), cob discover
  - segno for QR codes; 11 new tests

### Bug Fixes

- **phone:** avoid listing a Wi-Fi phone twice after pairing or reconnect
  - QR flow gives adb 5 s to auto-connect the freshly paired phone by its mDNS name before connecting by address (live: adb did it ~1-3 s after pairing, the phone then showed up twice)
  - reconnect_known skips remembered addresses of phones adb already holds by mDNS name
  - FEATURE-012: live results on the moto g84 (discover, QR pairing in 11.6 s, reconnect on a new port)
- **release:** keep wrapped commit-body bullets whole in the changelog
  - Continuation lines of a bullet are joined to it instead of being dropped
  - Plain paragraphs between bullets are still ignored

### Documentation

- bring v0.2.0 phone decisions and GPG findings onto main
  - D-024: phone screen record per hardware serial, gzip screenshots on phones
  - ROADMAP: M6 devices and platforms; Google Play Games marked parked
  - FEATURE-012: wireless ADB and manual phone restore notes
  - FEATURE-013: Google Play Games for PC spike findings and open decision
- record QR pairing and network discovery (D-025)
  - D-025 decision, segno in DEPENDENCIES, FEATURE-012 section, CHANGELOG highlights
- **design:** add Google Stitch prompts for desktop and Android UI
  - Material 3 design system, 9 desktop screens, 8 Android screens, prototype flows, safety rules

## [0.2.0] - 2026-10-21

Channel: **Stable**

### Highlights

- **Real Android phones** over ADB, by USB or **Wi-Fi** (pair with the Android 11+ code, connect by
  IP:port, or switch a USB phone to Wi-Fi with one button). While farming the bot puts the phone in a
  landscape 1600x900-style mode and restores it afterwards; **Restore phone screen** (Setup > Phone)
  brings back the phone's own screen settings at any time. Zooming out needs root on a phone.
- **Linux packages** next to the Windows zip: `.deb`, `.rpm` and AppImage (x86_64), each installed and
  smoke-tested before publishing. On Linux the bot drives a real Android phone.
- **Fewer refused deploys:** every deploy point is checked against the real red line and moved to
  clear ground when it sits on or next to it (about 7 % of points on saved battles).
- Faster phone screenshots (compressed on the phone): about 0.3 s over USB, under 1 s over Wi-Fi.

### Features

- **release:** Linux .deb, .rpm and AppImage packages
  - scripts/build_linux.sh: Nuitka standalone build (clashofbots, same assets and PySide6 plugin as Windows), icon rendered from the in-code app icon, packed with nfpm (.deb/.rpm) and appimagetool
  - packaging/linux: nfpm config (/opt/clash-of-bots, clashofbots + cob in /usr/bin, menu entry, icon; depends on distro adb and the Qt xcb runtime libs), .desktop entry, AppImage AppRun
  - _build-linux.yml: build on ubuntu-22.04 (glibc 2.35), pinned + checksum-verified nfpm, appimagetool and AppImage runtime; smoke-test the .deb in ubuntu:24.04, the .rpm in fedora:44, the AppImage on the runner
  - scripts/smoke_linux.sh: --version match, selftest from another folder, no missing system libs for the binary and the xcb plugin, headless GUI still running after 15 s
  - release.yml: Linux build in parallel with Windows; publish waits for both and attaches ClashOfBots-<version>-x86_64.{deb,rpm,AppImage} + .sha256
  - build-linux.yml: opt-in build + smoke on a branch (label build-linux or manual), never publishes
  - app_root uses sys.executable when frozen: a launch through the /usr/bin symlink gives a bare argv[0]
  - selftest checks the bundled templates are found next to the binary
  - docs: Linux install (real Android phone over adb, no LDPlayer) in README and RELEASING
- **device:** real Android phones over ADB
  - PhoneDevice: temporary 1600x900-style display (wm size/density, landscape rotation lock, screen on while plugged in); the phone's own values are saved first and restored on stop, after a crash on the next run, or with `cob phone-reset SERIAL`
  - display widened by the camera-cutout inset on both sides (the game pads its HUD by it); frames cropped and taps shifted to the middle 1600 px
  - pinch mapped to the touch panel's own units and orientation; sends only events the panel supports; detects panels that refuse writes (SELinux) and uses su on rooted phones
  - phones listed by model in `cob devices` and the GUI, own Setup checks (unlocked, display mode), reconnect after a USB drop
- **phone:** wireless ADB and a Restore phone screen button
  - wireless: pair (Android 11+ pairing code), connect by IP:port, switch a USB phone to Wi-Fi; connected addresses are remembered and reconnected on refresh and after a drop during a run
  - the phone's own screen values are kept per phone (hardware serial, so USB and Wi-Fi share them) and refreshed at each start while the bot's mode is off
  - Setup > Phone: Wi-Fi connect, pairing, Switch USB phone to Wi-Fi, Restore phone screen; CLI pair / connect / wifi; phone-reset restores any time

### Bug Fixes

- **release:** single Section field in the .deb control file
  - nfpm already writes Section from the top-level section key; the extra deb field duplicated it and dpkg refused the package
- **phone:** zoom through root, boat and army screen on phones
  - raw touch events are refused by SELinux on normal phones: pinch now runs through su on rooted phones; Setup shows "Zoom (pinch)" and how to grant root
  - boat bubble: more in-between scales and threshold 0.72 (phones draw it softer: 0.76 at 0.9, look-alikes <= 0.54)
  - smaller map drags (6 max) towards the BB dock so the bubble lands between the resource bars and Shop
  - army screen templates also try 1.02: phones draw dialogs ~2 % larger
- **attack:** deploy points clear of the red line; phone HUD and damage bar
  - every deploy point is checked against the red-line pixels of the same frame and moved outward until clear (10 of 147 points on saved battles sat on the line, so those troops were refused); the auto edge counts only clear points
  - damage bar anchored to the "Overall Damage" label (phones: +19 px; it read 0 % at 89 % and surrendered)
  - phones: the game pads its HUD by the rounded-corner radius, not the cutout; display width 1600 + 2 x radius
- **phone:** clear error when phone and PC are on different networks
  - usb_to_wifi checks the phone's Wi-Fi IP against this PC's addresses before switching (live: phone and PC on different subnets)
  - connect turns adbutils timeouts into a DeviceError with the hint, so retries and the GUI handle it

### Performance

- **phone:** gzip screenshots on the phone
  - phones send `screencap | gzip -1 -c` (built-in gzip, decoded with the stdlib): moto g84 USB 0.72 -> 0.32 s, Wi-Fi 1.54-1.96 -> 0.34 s per frame; slow Wi-Fi frames made the navigator time out before Builder Base
  - LDPlayer keeps raw frames (local connection, already fast)

### Documentation

- 0.2.0 release note

## [0.1.2] - 2026-10-21

Channel: **Stable**

### Highlights

- Zoom-out is reliable on every screen the bot uses, so the boat between the villages is found again.
- Troops, siege and heroes are no longer left in the bar: cards are found by brightness and every
  hero / Builder Base placement is checked and retried along the red line.
- Builder Base: no more swapped troops (taps avoid the upgrade arrow); collectors are now collected.

### Bug Fixes

- reliable zoom-out, checked deploys, Builder Base collection
  - zoom out by pinching until the view stops moving, on every screen used (home, BB home, battle start, each BB stage); the battle camera does not inherit the village zoom
  - boat bubbles matched at the camera zoom (template scales); BB home goes zoom -> drag -> boat
  - troop bar cards found by brightness in both villages: upgrade arrows and x1 counts made the badge reader skip troops, siege and heroes
  - every hero / single / BB card placement is checked (card changed) and retried at other edge points, then further out
  - card taps stay clear of the green upgrade arrow, which opened the BB troop picker
  - Builder Base collectors: every gold, elixir and gem bubble tapped before BB cycles (collect_minutes)

### Documentation

- 0.1.2 release note

## [0.1.1] - 2026-10-20

Channel: **Stable**

### Highlights

Builder Base fix release.

- **Troops are deployed again:** with the new Builder Base card layout (x1 counts, upgrade arrows) only
  the machine was deployed. Now every card goes in, in both stages of each battle.
- **Attack cooldown:** "Attack available in ..." no longer makes attacks fail; the bot waits for Find Now.
- **Builder Base gains are shown:** gold and elixir won per attack appear in stats and history.
- **Correct attack count:** a battle where nothing was deployed is counted as failed, not done.

### Bug Fixes

- **bb:** deploy every Builder Base card, wait out the attack cooldown, count BB loot
  - new BB bar (x1 counts + green upgrade arrows) broke the level-badge reader: purple Night Witch cards
  - find_bb_cards: cards from the bar's brightness profile; BB has no spells, every unused card is deployed
  - only the machine (leftmost) is re-tapped for its ability: re-tapping a stage-2 reinforcement opened
  - Start Attack dialog with "Attack available in": wait up to 3 min for Find Now instead of failing
  - an attack that deployed nothing is "failed", not "done" (Attacks count was wrong)
  - Builder Base gold / elixir read before and after each attack (retries while the counters animate)
  - live: 2/2 two-stage attacks, 7+3 and 7+4 cards, +477k gold +225k elixir

### Documentation

- 0.1.1 release note

## [0.1.0] - 2026-10-20

Channel: **Stable**

### Highlights

First stable release. Everything from the 0.1.0 alphas, tested end to end on LDPlayer 14 (1600x900 @ 240 DPI).

**Farming**
- Home village: loot filter (gold + elixir or dark elixir, max Nexts), attack along the best edge of the
  base, heroes and their abilities, surrender when damage stops growing, return home, repeat.
- Builder Base: boat over, both stages of every battle (200 %), daily Star Bonus, boat back.
- Upkeep before each cycle: zoom out, collect collectors and the loot cart; opt-in wall upgrades (cheapest
  first, exact cost read, reserve kept, spend verified) and clan castle troop requests.

**Runs unattended**
- Recognises 26 screens and popups; offers and gem dialogs are only ever closed via their X.
- Recovers from disconnects, "Try again later", the idle "Anyone there?" dialog and LDPlayer stopping
  (relaunches it); stops by itself if the village is opened on another device.
- Random breaks between cycles and taps that land anywhere inside a button.

**App**
- Window with Farm / Settings / Setup / History / Log tabs, live view of what the bot sees, stat tiles,
  cycle history with CSV export, setup checks with fix buttons, tray icon. Full command line too.
- New in this release: one log file per session in `%LOCALAPPDATA%\ClashOfBots\logs\sessions\`,
  `ClashOfBots.exe logs --follow` to watch a running bot, Open logs folder in the Log tab.

**Upgrading from an alpha:** settings in `farm.json` are kept; new options start with safe defaults
(walls and troop requests off).

Botting breaks Supercell's terms of service: use an alt account.

### Features

- **farm:** collect resources and zoom out at home before each cycle
  - CollectTask: one bubble per resource type per round (one tap collects all of that type; a second tap
  - BOOST_DIALOG screen: the gem offer is only ever closed with its X
  - AdbDevice.pinch: two-finger zoom via raw multi-touch events on the detected touch node
  - farm maintenance before each cycle: zoom out at home, then collect when due (farm.json
  - live: collected +102k gold / +96k elixir; after zoom-out 2/2 attacks (+3.42M gold)
- **collect:** collect the loot cart
  - loot cart label on the map -> tap the wagon -> "Loot Cart" panel -> Collect button; acts only on matches
  - HUD exclusion boxes narrowed to the real buttons (the cart sits next to the trophy button)
  - tombstones left out: 15 px template either missed most or hit decorations, and clearing them gives nothing
  - live: cart +138,824 gold +135,733 elixir +1,694 dark; bubbles one tap per type
- **walls:** upgrade walls with gold or elixir, off by default
  - builder menu -> cheapest wall row -> panel -> gold/elixir hammer (never the Wall Ring) -> confirm
  - spend safety (D-020): exact cost read (digits/cost glyphs 0 1 4 5), not red, icon matches, reserve kept,
  - farm.json wall_upgrades (0 = off) and wall_reserve (1M); Settings tab fields; runs in maintenance
  - live: refused a 4M wall with an unknown digit, then upgraded the cheapest wall for 5,000 gold (verified)
- **request:** ask the clan for castle troops, off by default
  - Request label over the clan castle -> castle panel -> Request -> "Request Reinforcements" -> Send
  - uses the game's saved request message; nothing typed by the bot
  - opt-in: farm.json request_minutes (0 = off) because Send posts to clan chat; Settings field
  - REQUEST_DIALOG screen goes home by Cancel, never Send
  - mapped live up to the dialog and cancelled (nothing sent); fast anchor tests
- **screens:** recognise and close the Events window
  - EVENTS_WINDOW (calendar icon) with its own close X; Claim / Go! inside are never tapped
  - found while looking for Clan Games: no Clan Games running now (Portal Panic, Battle Options, ...)
  - live: Events window closed, home in 3 s
- **log:** one log file per session and a way to watch the running bot
  - logs/sessions/session-YYYYMMDD-HHMMSS.log per CLI or window run (newest 30 kept), plus rolling cob.log
  - console lines now carry a timestamp; first line names the session file
  - cob logs: list sessions, --show prints the latest, --follow watches it live from a second terminal
  - GUI Log tab shows this session's file and an Open logs folder button

### Bug Fixes

- **screens:** close LDPlayer top-up offers and the welcome-back dialog
  - found live after an emulator start: LDPlayer's real-money "Top-Up via LDPlayer" offer over the game
  - LDPLAYER_TOPUP (priority 98) only ever taps the offer's small X, never items or Top Up
  - WELCOME_BACK ("Welcome Back Chief!") closed with Back; it ate all map drags meant for the boat
  - live: offer closed, then boat home in 7 s
- **request:** find the castle label at any zoom; record the live send
  - template cut as the "Request" text only (the old one included selection arrows) with a scale search
  - test: the gem "Request Now!" button never matches the Request template
  - live: one request sent with the user's OK; castle then on cooldown
  - docs: FEATURE-010, HANDOVER, ROADMAP
- **farm:** never count a covered resource bar as millions lost
  - found in the release test: the daily "Star Bonus Received!" dialog hides the left of the resource bar
  - HOME_STAR_BONUS screen, closed with its Okay
  - a resource read that drops below half of the previous one is treated as a misread: no gain recorded
  - only bot runs (farm, bb, attack, search, home, bench, gui) start a session log; quick tools do not

### Documentation

- add FEATURE-008 collect and camera zoom
  - design, live results, safety screens found while building it
  - HANDOVER (alpha.5 released, M3 next steps), ROADMAP
- record loot cart and the tombstone decision
  - FEATURE-008 section, HANDOVER next steps (walls/upgrades need budget rules), ROADMAP
- keep private notes out of the repository; README for the stable release
  - untrack (kept locally, now gitignored): session bootstrap prompt, third-party bot research notes,
  - CONSTRAINTS / comments no longer point at the removed notes
  - README: features, requirements, usage, settings, logs, development
- stable 0.1.0 release notes; flush logs --follow output
  - CHANGELOG highlights covering the whole 0.1.0 line, upgrade note from the alphas
  - TESTING: release check run against the built exe
  - logs --follow printed nothing when its output was redirected (first read not flushed)

### Tests

- cut suite time from 51 s to 22 s
  - slow tests simulated 2-4 min timeouts polling every 0.5 s (hundreds of full-frame classifications)
  - same assertions with poll_s=5 and shorter timeouts where the outcome does not depend on them

## [0.1.0-alpha.5] - 2026-10-18

Channel: **Alpha**

### Highlights

Builder Base, a reworked window and more human-like play.

- **Builder Base:** pick "Builder Base attacks" in the window (or `ClashOfBots.exe bb`). The bot takes
  the boat over, fights both stages of each battle (200 % total), collects the daily Star Bonus and
  sails back home when done.
- **New window:** Farm / Settings / Setup / History / Log tabs, dark theme and tray icon. Live view of
  what the bot sees, big stat tiles, a cycle history you can export to CSV.
- **Setup tab:** checks LDPlayer, resolution, ADB debugging and Clash of Clans, with buttons to start
  LDPlayer or fix the resolution.
- **More human:** taps land anywhere inside buttons instead of the exact centre, and the bot takes
  short random breaks between cycles (Settings: break every ~N cycles, ~minutes, 0 = off).
- Botting breaks Supercell's terms of service: use an alt account.

### Features

- **core:** vary tap positions inside buttons and cards
  - Humanizer: taps land in the middle 60 % of the matched template, deploy taps within 6 px
  - navigator, search and attack tap through it (navigator owns one, tasks share it)
  - tests pin exact centres with a disabled Humanizer; jitter has its own tests
- **farm:** rest between cycles like a person
  - farm.json break_every (cycles, randomised +-2, 0 = off) and break_minutes (0.6x..1.4x); defaults 8 / 5
  - farm loop rests at home; Stop interrupts the break; time limit counts it
  - GUI: both fields in the settings group, status shows "on a break until HH:MM"
  - cob farm prints the break settings; farm_limits() builds limits from farm.json
- **device:** add setup checks and per-cycle history
  - run_checks(serial): LDPlayer installed/running, instance resolution, adb connection (with the ADB
  - AdbDevice.has_package
  - history.csv in the user data folder: one row per farm cycle from CLI and GUI, read newest N
- **ui:** tabs, dark theme, live view, setup helper and history
  - Farm / Settings / Setup / History / Log tabs; dark Fusion theme and a generated app icon
  - live view: the farm worker forwards the bot's own frames (~every 2 s, no extra captures); Grab when idle
  - Setup tab: run checks with tick/cross results, Start LDPlayer and Fix resolution buttons
  - History tab: last 500 cycles from history.csv, newest first, totals, Export CSV
  - tray icon with Show / Stop farming / Quit and a notification when farming stops
  - device/checks/grab callables injectable; offscreen tests for checks, preview, history and theme
- **ui:** stat tiles, clearer setup marks, live history summary
  - Stats as coloured tiles (cycles, attacks, gold, elixir, dark, per hour) plus status / last cycle
  - Setup results marked OK / FIX in colour (the tick glyphs rendered as purple emoji)
  - History summary updates with every new cycle; row numbers hidden
- **screens:** recognise Builder Base and find the way home from it
  - BB_HOME, BB_ATTACK_MENU, BB_RESULTS screens; BB battles share the BATTLE screen
  - BB_HOME towards home: tap the boat bubble, else drag the map to bring the dock into view
  - navigator actions: swipe x1 y1 x2 y2, and "A else B" fallback
  - fixtures from a live two-stage BB battle; FEATURE-007 plan for the BB attack
- **bb:** two-stage Builder Base attack and cob bb
  - BB_STAGE_WAIT (Attacker label + "Battle starts in") and BB_SEARCHING screens
  - go_to_builder_base: boat bubble (both villages), drag the map when it is off screen, never blind taps
  - BbAttackTask: Find Now -> deploy unused cards at each stage countdown -> results -> Return Home
  - stage 2 deploys only what is still unused (reinforcement card); spells skipped
  - Navigator.go_home(arrive=...) so BB tasks do not sail back while clearing popups
  - cob bb --attacks N, then back to the home village; scripted two-stage tests with PNG bar strips
- **ui:** Builder Base mode in the window
  - Run box has a Mode: Home village farming / Builder Base attacks
  - BB mode reuses the farm loop (limits, breaks, Stop, emulator relaunch, history); every cycle is a BB attack
  - FarmParts carries the BB task; bb_farm_task in wiring; GUI and loop tests
  - docs: FEATURE-007 attack section with live results, HANDOVER, ROADMAP

### Bug Fixes

- **bb:** close the Star Bonus dialog and cap map drags
  - found live: the daily "Star Bonus!" reward covers BB home (Battle shows through), blocking Find Now
  - navigator drags the map at most 4 times per go_home (was ~75 drags until the timeout)
  - live: bonus closed, 2/2 BB attacks, boat back to the home village in 4.6 min

### Documentation

- record humanisation and alpha.4
  - FEATURE-005 humanisation section with the live check
  - HANDOVER: alpha.4 published, alpha.3 never published; next: UI improvements, Builder Base
  - ROADMAP: breaks/humanization done
- record GUI v2
  - FEATURE-006 v2 section: tabs, theme, live view, setup helper, history, live results
  - HANDOVER: GUI v2 branch, Builder Base next
- add alpha.5 highlights to the changelog
  - user-facing summary under Unreleased: Builder Base, new window, setup tab, humanisation

## [0.1.0-alpha.4] - 2026-10-18

Channel: **Alpha**

### Highlights

First published build of everything listed under 0.1.0-alpha.3 below (GUI, smarter attacks,
recovery, failure snapshots): the alpha.3 release build failed before publishing, so its tag has no
download. This release only adds the release-pipeline fix.

### Bug Fixes

- **ci:** install Qt libraries in the release verify job
  - v0.1.0-alpha.3 verify failed: libEGL.so.1 missing for the GUI tests (only ci.yml had the fix)
  - same apt packages and offscreen platform as ci.yml; nothing was built or published

### Documentation

- point alpha.4 notes at the unpublished alpha.3 section
  - alpha.3 failed before publishing, so its highlights would otherwise never reach a GitHub release

## [0.1.0-alpha.3] - 2026-10-18

Channel: **Alpha**

### Highlights

First release with a window: double-click ClashOfBots.exe and press Start farming.

- **GUI:** pick the LDPlayer instance, set the loot filter, cycle/time limits, Start/Stop, live stats
  (gold/elixir/dark gained, per hour) and log. The command line still works from a terminal.
- **Smarter attacks:** surrenders when damage stops growing for 15 s (loot already taken is kept),
  spells no longer misread as heroes, bases with an unclear outline are skipped for free.
- **Keeps running:** relaunches LDPlayer if it dies, retries ignored taps, waits out
  "Try again later" matchmaking blocks, stops quickly when the connection drops mid-battle.
- **Failure snapshots** in `%LOCALAPPDATA%\ClashOfBots\snapshots` show what the bot saw when it gave up.
- Reads full 8-digit storages (e.g. 23 000 000 elixir).
- Botting breaks Supercell's terms of service: use an alt account.

### Features

- **farm:** relaunch LDPlayer when the device is lost
  - LdConsole.ensure_running launches a stopped instance and waits until adb sees it
  - index_for_serial maps emulator-5554+2n / 127.0.0.1:5555+2n to the instance
  - farm loop calls the relaunch hook on device lost, at most 2 times per run, then continues
  - cob farm enables it automatically for LDPlayer serials
- **core:** save a snapshot when a task fails or the game is restarted
  - frames go to snapshots/ in the user data folder, newest 50 kept, never raises
  - navigator saves the unknown screen before restarting the game; search/attack save on failure
  - tests run with an isolated user data folder
- **screens:** handle "Unable to attack Village! Try again later."
  - found by the new failure snapshot: matchmaking refused after an interrupted battle
  - SEARCH_BLOCKED screen leaves via the cloud screen's Return Home button
  - search fails with a clear reason; farm loop waits 2 min before retrying
  - fixture search_blocked.jpg
- **screens:** add surrender dialog anchors
  - surrender_button, surrender_title and okay_button cut from a live surrender
  - SURRENDER_CONFIRM screen above BATTLE; towards home it confirms with Okay
  - damage bar settings in attack.toml; fixture surrender_confirm.jpg
- **attack:** surrender when the damage bar stops growing
  - read the Overall Damage bar fill (cyan run from its left end, star markers tolerated)
  - after full deploy: no growth for 15 s -> Surrender -> Okay; loot taken so far is kept
  - connection popups still end the watch early; outcome reports ended_by and rough damage %
  - load_attack_config also returns the damage settings; Navigator.now for task clocks
- **ui:** add PySide6 window to run the farm bot
  - device picker (adb + LDPlayer instances), loot filter saved to farm.json, cycle/time limits
  - Start/Stop: farm loop in a QThread, window updated only through signals; Stop = Ctrl+C semantics
  - live stats (cycles, attacks, gains, per hour, last cycle) and live log
  - cob gui, and the exe without arguments opens the window (help text if the GUI cannot start)
  - offscreen Qt tests for filter round-trip, worker signals, stop and errors

### Bug Fixes

- **search:** tap Battle again when a fresh village ignores the first tap
  - found live after an emulator relaunch: the attack menu opened only after the 30 s wait
  - retry up to 3 Battle taps, 8 s apart, only while HOME is still on screen
  - separate failure reasons for the attack menu and Find a Match
- **attack:** stop waiting when the battle is cut off by a popup
  - found by a failure snapshot: "Connection lost" mid-battle, attack waited the full 240 s
  - wait for BATTLE_END or a reload / other-device popup; fail fast with the popup as reason
- **attack:** stop reading spell cards as single units
  - snap a card to its own left outline (badge-15..badge-2), never the previous card's right edge
  - count text threshold follows the bar's brightest pixels, so faded frames still show the count
  - 44 live search frames: spell slots misread 0 (was 4), full-army reads 33
- **attack:** skip bases whose outline is unclear; read 8-digit resources
  - painted red/orange scenery passed the border colour filter and ballooned the fit (2 deploy points)
  - outlines larger than 1500 x 1150 px are rejected: nothing is deployed, End Battle is free
  - own-resource rows widened: full elixir storage (23 000 000) lost its first digit
  - fixture search_painted_scenery.jpg

### Refactoring

- **tasks:** share farm wiring between CLI and GUI
  - build_farm(serial) returns navigator, search, attack, resource reader and relaunch hook
  - FarmParts.farm_task builds the loop; cob attack / cob farm use it

### Documentation

- record robustness work and alpha.2 release
  - FEATURE-005 robustness section with live relaunch and interrupted-battle results
  - HANDOVER: alpha.2 published, new risks (connection drops, matchmaking blocks, spell misread)
- record attack v2 and D-018 damage bar
  - FEATURE-004 v2 section with live surrender and natural-end results
  - D-018 stall detection from the damage bar fill
  - HANDOVER and ROADMAP updated
- add FEATURE-006 GUI and D-019 packaging decision
  - window, worker, entry points, local exe and live GUI results
  - D-019 one exe with console mode hide, Qt Essentials only
  - HANDOVER, ROADMAP (M2 GUI done), TESTING exe checks
- add alpha.3 highlights to the changelog
  - user-facing summary under Unreleased; release.py moves it into the alpha.3 section

### Tests

- **ui:** shut Qt down before the interpreter exits
  - CI (Linux) passed all tests, then crashed with SIGBUS while destroying leftover windows at exit
  - stop workers, close and delete windows, process events and call QApplication.shutdown

### Build

- **deps:** add pyside6-essentials 6.11.2 for the GUI
  - essentials only (QtCore/Gui/Widgets): the pyside6 meta-package adds Addons not needed
  - 6.11.2 rather than 6.12.0 (10 days old) for Nuitka plugin maturity; logged in DEPENDENCIES.md
- bundle the GUI in the exe with console mode hide
  - Nuitka --enable-plugin=pyside6 --windows-console-mode=hide: one exe for GUI and CLI
  - attach mode was tried first: terminals did not wait for the exe and exit codes were lost
  - selftest also imports QtWidgets and prints the Qt version
  - CI installs Qt system libraries and runs tests on the offscreen platform

## [0.1.0-alpha.2] - 2026-10-18

Channel: **Alpha**

### Highlights

First working farm bot, tested live on LDPlayer 14 (1600x900 @ 240 DPI).

- `ClashOfBots.exe farm -s emulator-5554 --cycles 5`: searches bases, attacks the ones that pass
  your loot filter, returns home and repeats. Live: 3/3 cycles in 11.6 min.
- Loot filter in `%LOCALAPPDATA%\ClashOfBots\farm.json` (default: gold + elixir >= 800k or
  dark >= 8k, max 40 Nexts, keep 50k gold).
- Recognises 13 screens and recovers from popups, disconnects, the shop and a closed game.
- Stops by itself if the village is opened on another device, gold runs low or the emulator dies.
- Attack v1: whole army along one edge of the base, heroes and abilities; spells not used yet.
- Needs LDPlayer's ADB debugging enabled (Settings > Other settings). Botting breaks Supercell's
  terms of service: use an alt account.

### Features

- **screens:** add real 1600x900 anchors for all screens
  - anchors cut from LDPlayer 14 frames: home, attack menu, army, search, battle, battle end, loading, popups
  - new ATTACK_MENU screen for the Battle / Ranked Battle menu
  - ARMY ranks above POPUP_GENERIC (army window has its own close X)
  - BATTLE keys on the Overall Damage panel (search also shows End Battle)
  - two close X variants (army style, log style); okay_button still to capture
- **vision:** add search-loot digit glyphs and SEARCHING screen
  - glyphs 0-9 for the Available Loot font, cut from LDPlayer 14 frames
  - DigitReader reads all 78 loot values on 26 search/battle frames (19 bases)
  - SEARCHING screen for the cloud transition, anchored on "for opponents"
- **vision:** read own resources from the top-right bar
  - bar digits use the same font as search loot, so digits/loot glyphs are reused
  - regions.toml [bar] rows for gold, elixir, dark
  - checked on 46 live frames: own gold drops by exactly the 1400 search cost each Next
  - tests on home, search and battle-end fixtures
- **screens:** add SHOP screen and drop okay_button
  - SHOP (real-money offers) detected by its own close X, priority above popups
  - current CoC dialogs all close with a red X, so POPUP_GENERIC no longer waits for okay_button
  - fixtures shop.jpg and popup_upgrade.jpg
- **screens:** add BUILDER_MENU, end_battle and per-screen to_home actions
  - to_home action per screen in screens.toml: wait, back, or tap <template>
  - BUILDER_MENU screen (Buildings & Heroes panel) closed by its own X
  - end_battle anchor so the search screen can leave without attacking
  - fixture builder_menu.jpg
- **screens:** add navigator to return home from any screen
  - act only after two equal classifications, re-confirm after every action
  - no blind input on UNKNOWN; restart the game when it is not in front or stuck (D-015)
  - cob screen (live classify) and cob home (navigate, prints steps)
  - tests replay fixture frames on a fake device with a fake clock
- **attack:** add farm config and loot filter
  - FarmConfig in farm.json under the user data folder, clamped and type-checked on load
  - worth_attacking: gold+elixir or dark threshold; better() tracks the richest skipped base
  - LootReader reads gold/elixir/dark rows from regions.toml
- **screens:** add wait_for/wait_leave and army review Attack! anchor
  - Navigator.wait_for confirms a screen before any tap; wait_leave waits for the old base to go
  - army_attack anchor: Find a Match opens the army review with a green Attack! button
  - fixture army_review.jpg
- **tasks:** add search loop with dry run
  - home -> Battle -> Find a Match -> army review -> read loot -> Next until the filter passes
  - stops on max_nexts (takes current base), low own gold, or any unconfirmed screen
  - cob search: dry run that always ends the battle unattacked
  - shared fake device/clock for task tests; 20 new tests
- **attack:** find the base border and read the troop bar
  - deploy geometry from the red no-deploy border on the two isometric axes; works at any zoom (D-016)
  - deploy points just outside one edge, auto-picked, off-screen and UI points dropped
  - troop bar cards from level badges, kinds from count text and card hue (D-017)
  - attack.toml holds colours, UI boxes, deploy and bar settings; PNG bar strips for tests
- **tasks:** add attack v1 and one-cycle cob attack command
  - deploy troops until each card greys out, then siege/heroes, then hero abilities; spells skipped
  - wait for the battle to end by itself, then Return Home
  - cob attack: search with the loot filter, attack, go home
  - Navigator.sleep for tasks; tests for geometry, bar reading and the attack flow
- **tasks:** add farm loop with stats and stop rules
  - repeat search + attack; net gain per cycle from own resources before/after
  - stop on cycle/minute limit, Ctrl+C, low gold, village open on another device, 3 failures in a row
  - army not ready: wait 60 s and retry; random 3-8 s pause between cycles
  - cob farm --cycles/--minutes prints totals and per-hour rates; shared wiring with cob attack

### Bug Fixes

- **cli:** keep console open when exe is double-clicked
  - No arguments now prints usage and a how-to-run hint instead of an argparse error
  - Pause for Enter when Explorer started the exe in its own console
  - Never pause with non-interactive stdin (CI, pipes)
  - Log unexpected exceptions to the log file before exiting
- **device:** find ldconsole for LDPlayer 14 installs
  - read InstallDir from HKCU\Software\XuanZhi\LDPlayer<major> (real key), newest major first
  - keep legacy Software\leidian vendor key as fallback
  - add C:\ and D:\ LDPlayer14 to default install folders
- **build:** let local Windows PowerShell 5.1 builds finish
  - 5.1 turns redirected Nuitka stderr into terminating errors under Stop
  - relax ErrorActionPreference around the Nuitka call, check LASTEXITCODE
  - ignore .nuitka-cache/ used for faster local rebuilds
- **screens:** detect idle-disconnect dialog as POPUP_RELOAD
  - "Anyone there?" dialog has RELOAD GAME instead of TRY AGAIN; it was classified as HOME
  - POPUP_RELOAD now matches either button (reload_button, reload_game)
  - fixture idle_reload.jpg
- **device:** start apps without monkey and report the foreground app
  - LDPlayer 14 has no monkey binary, so app_start silently did nothing
  - resolve the launcher activity and use am start; raise if it cannot be resolved
  - add foreground_package() (dumpsys window mCurrentFocus) to the Device protocol
- **screens:** stop when the village is opened on another device
  - "Another device is connecting to this Village" was classified as HOME (Battle button shows through)
  - POPUP_OTHER_DEVICE screen with a new "stop" action: no Reload, which would kick the other player off
  - navigator reports stopped_on; search fails with that reason; fixture other_device.jpg
- **tasks:** survive capture glitches and report a lost device
  - capture retries twice on short failures before raising
  - farm loop catches errors per cycle: device gone -> stop with "device lost", other errors count as failures
  - found live: LDPlayer stopped mid-battle and the error escaped the loop

### Performance

- **device:** read screencap stream in linear time
  - adbutils read_until_close appends 4 KiB chunks to bytes (quadratic copy)
  - read the socket in 1 MiB chunks and join once
  - LDPlayer 14, 1600x900: capture mean 1740 -> 456 ms, p95 1994 -> 524 ms

### Documentation

- add Windows session bootstrap prompt and update handover
  - docs/handoff/WINDOWS_SESSION.md recreates context, rules and memories in a new Claude Code session
  - Handover records alpha.1 release and the double-click fix
- record Windows live test results and LDPlayer 14 setup
  - HANDOVER: signing key on Windows, live device/bench numbers, local exe build, new risks
  - TESTING: enable LDPlayer ADB debugging, local build cache tip
- record live tap and capture bench on CoC home screen
  - capture mean 398 ms, p95 488 ms; tap mean 61 ms, p95 75 ms (LDPlayer 14, 1600x900)
  - drop slow-tap risk; note LAN-reachable adb port accepted on home network
- record M1 template results and fixture decisions
  - D-013 fixtures as JPEG q95, D-014 anchors exclude variable numbers
  - FEATURE-002 status, screen notes, measured accuracy, next steps
  - HANDOVER updated for feat/m1-templates
- record M1 finish results
  - FEATURE-002: SHOP, reload variants, bar reading, builder-menu gap; next is classifier speed
  - HANDOVER: feat/m1-finish status, M2 needs loot thresholds
- add FEATURE-003 navigator and record M2 plan
  - M2 plan and approved farm defaults, live recovery results
  - D-015 no blind input on UNKNOWN screens
  - HANDOVER and ROADMAP updated
- record search loop design and live results
  - FEATURE-003 PR 2 section; max_nexts takes the current base (no going back)
  - HANDOVER and ROADMAP updated
- add FEATURE-004 attack v1 and record D-016, D-017
  - live results of two battles, deviations from the approved plan
  - HANDOVER and ROADMAP updated; risks for other-device play and account choice
- add FEATURE-005 farm loop with live results
  - 3/3 cycles in 11.6 min after an LDPlayer relaunch; first run lost the emulator mid-battle
  - HANDOVER next steps (GUI or robustness), ROADMAP M2 items checked
- add alpha.2 highlights to the changelog
  - short user-facing summary under Unreleased; release.py moves it into the alpha.2 section
- drop duplicate Highlights heading (release.py adds it)

### Tests

- **vision:** add real-frame regression tests and read regions
  - 16 LDPlayer 14 fixtures (JPEG q95): every screen plus 5 search bases, battle, launcher
  - classify each fixture; read gold/elixir/dark loot on 6 frames
  - regions.toml: loot rows and variable cost boxes (Next, Find a Match)
  - scramble cost boxes with noise and require the same screen (costs vary by Town Hall)

## [0.1.0-alpha.1] - 2026-10-18

Channel: **Alpha**

### Features

- M0 skeleton with LDPlayer ADB device layer and Windows exe CI
  - uv project, cob package, CLI (devices, capture, bench, ld-resize, selftest)
  - Device protocol; AdbDevice with raw exec:screencap decode and input shell
  - LdConsole list2 parsing, launch/quit/resize; LDPlayerDevice with 1600x900 check
  - Unit tests for raw decode, ldconsole parsing, selftest
  - GitHub Actions: lint+tests, Nuitka standalone Windows build, smoke test, zip+sha256
- **vision:** add template matching, OCR and screen classifier
  - Frame wrapper caching gray/HSV per capture
  - TemplateStore with lazy cached PNGs and per-template region, threshold, gray
  - match and match_all with greedy NMS on the score map
  - HSV fraction checks, DigitReader glyph OCR, lazy Tesseract wrapper
  - read_stable for multi-frame agreement
  - Data-driven ScreenClassifier over screens.toml; screens with missing anchors disabled
  - CLI crop, match, classify dev tools; assets bundled into exe
  - 14 new tests on synthetic frames

### Bug Fixes

- **ci:** pin setup-uv to v10.3.0

### Documentation

- add research, architecture, decisions and roadmap for Clash of Bots
- **decisions:** record M1 vision design choices
- add release process and record branching and versioning decisions
  - RELEASING.md: branch flow, channels, cutting releases, CI cost controls, rollback
  - D-011 SemVer channels, D-012 PR-only CI and fast-forward merges
  - Constraints and handover updated

### Build

- **release:** add SemVer channel versioning and changelog generator
  - Single version source in cob/__init__.py, read by hatch for pyproject
  - Version set to 0.1.0-alpha.0 (in development, unreleased)
  - scripts/release.py cuts alpha/beta/rc/stable releases: bump, CHANGELOG section from
  - Windows file version mapping X.Y.Z.B so channels sort correctly
  - CHANGELOG.md in Keep a Changelog format with channel legend
  - 14 tests for version bumps, parsing and changelog editing

### CI

- run checks on PRs only and build Windows exe on release tags
  - ci.yml: Linux lint and tests on pull requests to main, docs-only changes skipped
  - build-exe.yml: opt-in Windows build via build-exe label or manual dispatch
  - release.yml: tag push verifies version and changelog, builds exe, publishes
  - Reusable Windows build with Nuitka compile cache, version smoke test, sha256
  - Build script takes version and file version, stamps exe description
  - Actions bumped to Node 24 majors; Ubuntu runner pinned to 24.04
