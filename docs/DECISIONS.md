# DECISIONS

## D-001: Language/stack = Python 3.13 + PySide6 + OpenCV + Tesseract  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Need fast iteration on vision logic; both references use this stack.
Options:  1) Python stack  2) C#/.NET + Emgu.CV  3) Rust
Chosen:   1
Why:      Same stack as ACBot (proven), richest CV/OCR ecosystem, fastest to prototype.
Trade-off: Bigger exe, Python perf (fine: bottleneck is capture/IO, not CPU).
Revisit if: frame pipeline CPU-bound after profiling.

## D-002: Talk to LDPlayer via ADB (not window capture)  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Options:  1) ADB capture+input  2) Win32 window capture + SendMessage (BasePilot style)
Chosen:   1 for LDPlayer, 2 reserved for Google Play Games backend
Why:      ADB works minimized/background, resolution-exact frames, same as ACBot, multi-instance via serial.
Trade-off: `adb screencap` PNG slow (~0.5s). Mitigate: raw `exec-out screencap` first, scrcpy/minicap stream later.
Revisit if: capture latency > 250ms blocks attack timing.

## D-003: Packaging = Nuitka standalone built on GitHub Actions windows runner  (ACCEPTED 2026-10-18)
Options:  1) PyInstaller onefile  2) Nuitka onefile/standalone  3) build locally on Linux via Wine
Chosen:   2 (PyInstaller kept as fallback)
Why:      Faster startup, compiled C (harder to tamper), same as ACBot. Dev machine is Linux -> CI builds exe.
Trade-off: Slower builds (~10-20 min), occasional plugin quirks with PySide6.
Revisit if: CI build time hurts iteration -> PyInstaller for dev builds.

## D-004: Screen classifier + per-task state machines instead of one bot loop  (ACCEPTED 2026-10-18)
Why: BasePilot's god class is its main weakness; classifier makes recovery generic.

## D-005: Own templates, not ACBot's  (ACCEPTED 2026-10-18)
Why: ACBot assets are its property and tied to its resolution; capture ours with a built-in
"template capture" dev tool. ACBot list used only as checklist of screens.

## D-006: Fixed emulator resolution 1600x900 @ 240 DPI  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Options:  1) 1280x720  2) 1600x900  3) 1920x1080
Chosen:   2
Why:      OCR digits readable, capture ~30% cheaper than 1080p, OK for multi-instance.
Revisit if: OCR error rate on loot digits too high.

## D-007: Dev on Linux, live test on Windows via Claude Code there  (ACCEPTED 2026-10-18)
Context:  LDPlayer Windows-only. User dual-boots into Windows and runs Claude Code there for live tests.
Implication: repo needs a git remote (GitHub) to sync between OSes; code must stay cross-platform
             except `cob/device/` backends; frame-fixture tests runnable on Linux.

## D-008: Template/screen metadata in TOML read by stdlib tomllib  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Options:  1) YAML (pyyaml dep)  2) JSON (no comments)  3) TOML via stdlib tomllib
Chosen:   3
Why:      Hand-edited data needs comments; tomllib is stdlib (no new dep). Files are read-only at runtime.
Trade-off: No TOML writer in stdlib -> tools that generate entries print snippets to paste.
Revisit if: GUI template editor needs to write the file (add tomli-w).

## D-009: OCR = own digit-glyph matcher for numbers, Tesseract for text  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Loot numbers read every search frame (hot path). Tesseract via pytesseract spawns a process per
          call (~80-200 ms) and misreads CoC's outlined font (BasePilot needed heavy preprocessing).
Options:  1) pytesseract everywhere  2) tesserocr in-process (no reliable Windows wheels)
          3) glyph template matching for digits + pytesseract for rare text
Chosen:   3
Why:      CoC digits use a fixed font at a fixed resolution (D-006) -> per-digit templates are ~1 ms, exact.
Trade-off: Need to crop 10 digit glyphs per font size once; text still slow (used rarely: names, labels).
Revisit if: Supercell changes fonts often, or text OCR becomes hot path.

## D-010: Screen classifier = data-driven anchor templates, first match by priority  (ACCEPTED 2026-10-18)
Why:      One place answers "where am I"; recovery/navigation reuse it (fixes BasePilot ad-hoc checks).
Trade-off: Each new screen needs anchors captured; UNKNOWN must be handled by every caller.

## D-011: SemVer 2.0 with alpha/beta/rc/stable channels, version in cob/__init__.py  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  User wants proper GitHub releases with alpha/beta/stable and detailed changelog.
Options:  1) CalVer  2) SemVer + channels, own stdlib script  3) release-please / semantic-release / git-cliff
Chosen:   2
Why:      SemVer pre-release tags map 1:1 to GitHub pre-releases; own script (~250 lines, tested) needs no
          Node tooling or bot PRs, works with signed commits/tags, and renders commit-body bullets as detail.
Trade-off: We maintain the changelog generator ourselves.
Revisit if: multiple contributors or monorepo packages.

## D-012: Feature branches + PR-only CI, Windows build only on release/opt-in  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  User asked to cut GitHub Actions cost; private repo, Windows minutes billed 2x; first exe build ~10 min.
Chosen:   ci.yml on PR (Linux), build-exe.yml opt-in (label/manual), release.yml on tags.
          Merge by local fast-forward so SSH signatures stay intact (GitHub squash/rebase re-signs as GitHub).
Trade-off: Windows-only breakage surfaces late (at release) unless build-exe used on risky PRs.

## D-013: Real-frame test fixtures stored as JPEG q95  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Regression tests need full 1600x900 frames; PNG is ~2.8 MB each and lives in git history forever.
Options:  1) PNG (~45 MB for 16 frames)  2) lossless WebP (-17% only)  3) Git LFS  4) JPEG q95 (~0.6 MB)
Chosen:   4 (user approved)
Why:      Tried on all 80 captured frames: q95 gives identical screen and loot results to PNG (q90 flips one
          faded frame). 16 fixtures = ~10 MB. No LFS setup or extra tooling.
Trade-off: Fixtures are slightly noisier than live captures, so anchors that only pass on JPEG are not proven
          on live frames; templates themselves stay PNG (cut from lossless captures).
Revisit if: a fixture result differs from its PNG original, or fixtures grow past ~30 MB.

## D-014: Anchors exclude every variable number; costs scrambled in tests  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Search / match cost (e.g. 1400 gold) changes with Town Hall and league (user note).
Chosen:   Anchors are labels/icons only (magnifier + "Next", "Find a Match"); cost boxes are declared in
          assets/templates/1600x900/regions.toml [costs] and tests fill them with noise to prove the
          screen is still recognised.
Why:      A cost baked into an anchor would silently break detection after a Town Hall upgrade.
Revisit if: a screen has no stable label to anchor on.

## D-015: No blind input on UNKNOWN screens; recover by app restart only  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Live test: navigator pressed Android Back on an unrecognised screen (builder menu) and CoC exited.
Options:  1) Back/tap-empty-spot heuristics on UNKNOWN  2) no input; restart app when stuck
Chosen:   2. Every screen the bot can meet gets an anchor + explicit to_home action instead.
          Restart early (5 s) when CoC is not the foreground app, else after 45 s; once per go_home.
Why:      A blind tap or Back on an unknown screen can exit the game, open a purchase, or start an
          attack; a restart is slow (~30 s) but always safe.
Trade-off: Any new UI that is not captured costs a 45 s wait + restart until its anchor is added.
Revisit if: restarts become frequent in logs (add the missing screens rather than heuristics).

## D-016: Deploy relative to the detected red border; no camera zoom  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Battle camera zoom and position differ per base; adb `input` has no pinch.
Options:  1) Fixed screen deploy points after zoom-out (pinch via sendevent multi-touch)
          2) Detect the red no-deploy border each battle and deploy just outside it
Chosen:   2
Why:      Pinch worked in the village but was inconsistent in battle (zoomed one base in). The border
          is visible at every zoom, on all scenery seen (green, dark Halloween); fitting it on the two
          isometric axes with percentiles ignores stray red pixels. No zoom = no slow 3.7 s gestures.
Trade-off: Depends on the border colour; a new scenery tint may need the HSV band widened.
Revisit if: deploys land inside the base or off the map in logs.

## D-017: Troop bar read from level badges; bar fixtures stored as PNG strips  (SUPERSEDED by D-021 for card positions)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Card positions depend on army composition; thin card outlines vanish on dark scenery and
          in JPEG; per-troop icon templates would need one template per troop type.
Chosen:   Find cards by their level badge (present on every card type), snap to an outline when one
          is near, classify by count text + background hue. Read once per battle.
          Test strips (1600x170 bar only) are lossless PNG: JPEG chroma subsampling blurs the badges,
          an exception to D-013 for this one feature (~1.5 MB total).
Why:      Generic for any army without per-troop assets; validated on 39 live search frames.
Trade-off: Cannot tell which troop is which (v1 does not need it); spells are only "skipped", not used.
Revisit if: attack strategies need per-troop placement (then add troop icon templates).

## D-018: Detect stalled attacks from the damage bar fill, not by reading the % digits  (SUPERSEDED by D-028)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  Approved plan: surrender when damage stops changing. Needs the damage value every few seconds.
Options:  1) Cut a new digit font for "Overall Damage XX%" (needs all 10 glyphs from live battles)
          2) Measure the cyan progress bar above the number (fill length from its left end)
Chosen:   2
Why:      Only "did it grow?" is needed; the fill is monotonic, needs no glyph set, and reads the same
          on every frame seen (0..90 %). Star markers on the bar are bridged by a 10 px gap tolerance.
Trade-off: Not linear in %, so logs show a rough value; a "stop at X %" rule would need option 1.
Revisit if: a strategy needs exact damage or star thresholds.

## D-019: One exe for GUI and CLI (console mode hide), Qt Essentials only  (ACCEPTED 2026-10-18)
Date: 2026-10-18   Model: Claude Opus 5.5
Context:  M2 GUI. Users double-click the exe; developers and logs need the CLI commands.
Options:  1) Two exes (ClashOfBots.exe CLI + ClashOfBotsGUI.exe)
          2) One exe, Nuitka console mode "attach" (GUI-subsystem exe that attaches to a parent console)
          3) One exe, Nuitka console mode "hide" (console exe; console window hidden on double-click)
          Qt: full `pyside6` meta-package vs `pyside6-essentials`
Chosen:   3, with pyside6-essentials==6.11.2 (user approved; 2 was approved first, replaced after testing)
Why:      One build, one zip. Tried "attach" first: terminals do not wait for a GUI-subsystem exe, so CLI
          output came after the prompt and exit codes were lost (would break the release smoke test).
          "hide" keeps normal console behaviour for CLI use and hides the console on double-click.
          Essentials has QtWidgets; Addons (WebEngine, 3D, ...) would add hundreds of MB for nothing.
          6.11.2 over the 10-day-old 6.12.0 for Nuitka plugin maturity.
Trade-off: Double-click may flash a console briefly; GUI errors go to cob.log and a message box.
Revisit if: the GUI needs a Qt module outside Essentials (e.g. charts -> QtCharts is in Addons).

## D-020: Spending is opt-in, fail-closed and verified  (ACCEPTED 2026-10-19)
Date: 2026-10-19   Model: Claude Opus 5.5
Context:  First feature that spends resources (walls); upgrades/research will follow.
Chosen:   Off by default per feature; gold/elixir only (never gems, rings, books, real money); exact cost
          read or no spend; keep a user reserve; verify the resource drop afterwards and stop the
          feature for the run on any mismatch; snapshots on every refusal.
Why:      A misread or mis-tap can waste millions or gems; refusing is always cheaper than a bad spend.
Trade-off: New cost digits need glyphs before those upgrades happen (first sighting is a refusal).

## D-021: Troop bar cards from the brightness profile in both villages  (ACCEPTED 2026-10-21)
Date: 2026-10-21   Model: Claude Opus 5.5
Context:  Live: the level-badge reader (D-017) lost the wizard ("x1"), the siege and the Archer Queen
          (green upgrade arrows next to the badge), so they were never deployed. The Builder Base
          already used a brightness-profile finder that ignores badges and arrows.
Chosen:   One finder (`find_cards`) for both villages: bright runs in the bar rows, plus a contrast
          check (card art std >= 30; bright scenery through the translucent bar is ~10). Kind (troop /
          spell / single) still from the "xN" count box and the background hue.
Why:      Positions no longer depend on what is drawn on the card; PNG strip fixtures stay.
Trade-off: Greyed-out cards are too dark to be found: the bar is read once before deploying.

## D-022: Zoom out on every screen that is used; check each placement  (ACCEPTED 2026-10-21)
Date: 2026-10-21   Model: Claude Opus 5.5
Context:  Live: each screen keeps its own camera zoom (a battle does not inherit the village zoom;
          a pinch in battle moved the view by 27 grey levels after a village zoom-out). Zoomed in, the
          boat was off screen and parts of the red line were cut. Taps refused by the game (inside the
          red line, on UI) were not noticed, so heroes and BB cards were silently left in the bar.
Chosen:   `Navigator.zoom_out()` pinches until the view changes by < 8 grey levels (max 3) and runs at
          home, on BB home, at battle start and at each BB stage. Single units and BB cards: tap the
          card once, tap a point, and accept only when the card picture changed (>= 10); otherwise
          try other points along the edge, then the same edge 3x further out. Troop cards whose first
          6 taps change nothing move to the outer points. Map-object templates (boat, BB bubbles)
          carry `scales` because they are drawn at the camera zoom (0.9 at full zoom-out).
Why:      Fully zoomed out is the one camera state that repeats; a card change is the game's own
          confirmation that a unit landed.
Trade-off: ~1 s per single unit for the check; partly replaces D-016's "no zoom in battle".
Addendum (2026-10-21): the diamond is a trimmed fit and the real red line follows the buildings, so
          10 of 147 points on saved battles sat on the line. Before deploying, each point is checked
          against the red-line pixels of the same frame (no red within 18 px) and moved outward in
          10 px steps until clear; this also decides the "auto" edge.

## D-023: Phones run in a temporary 1600x900-style display mode  (ACCEPTED 2026-10-21)
Date: 2026-10-21   Model: Claude Opus 5.5
Context:  Real phones are ~20:9 at their own density; every template assumes 1600x900 @ 240 (D-006).
Options:  1) Scale frames/taps for any resolution  2) Override the phone's display while the bot runs
Chosen:   2 (user had no preference; reversible). `wm size` + `wm density 240`, landscape rotation
          locked, screen kept on while plugged in; the phone's own values are saved to a file first and
          restored on stop, on the next run after a crash, or by `cob phone-reset`. The display is
          widened by the camera-cutout inset on both sides (the game pads its HUD by it) and frames are
          cropped / taps shifted to the middle 1600 px. Pinch events follow the panel's capabilities.
Why:      Same templates, regions and timings as LDPlayer; no per-device tuning.
Trade-off: The phone shows black bars and runs landscape while farming; a crash leaves the mode on
          until the next run or phone-reset.
Zoom:     SELinux blocks `sendevent` on real phones (live: moto g84, Android 16, Permission denied);
          the game ignores mouse-wheel `input scroll`. Pinch runs through `su` on rooted phones (shell
          granted in Magisk / KernelSU). A no-root injector (app_process + InputManager, as scrcpy) is
          deferred by the user; phones without root run without zoom and Setup says so.


## D-024: Phone screen record per hardware serial; phones send gzip screenshots  (ACCEPTED 2026-10-21)
Date: 2026-10-21   Model: Claude Opus 5.5
Context:  The user asked for a manual "restore phone screen" that always knows the phone's previous
          aspect ratio, and for wireless ADB (the same phone then has a different adb serial).
          Over Wi-Fi a 6-10 MB raw screencap took 1.5-2.3 s and made the navigator time out.
Chosen:   %LOCALAPPDATA%\ClashOfBots\phones\<ro.serialno>.json = {"original": own values, "active"}:
          written when the bot's mode starts from the phone's own mode, kept after a restore, restored
          on stop / next run / Setup button / `cob phone-reset`. Phones send `screencap | gzip -1 -c`
          (device gzip, stdlib decode); LDPlayer keeps raw frames.
Why:      One record for USB and Wi-Fi; restore works at any time. gzip: USB 0.72 -> 0.32 s,
          Wi-Fi -> 0.34-0.79 s per frame, no new dependency.
Trade-off: Phone CPU ~0.3 s per frame for gzip; a user change made while the bot's mode is on is lost.

## D-025: Wi-Fi phones by QR pairing and mDNS discovery through the adb server  (ACCEPTED 2026-10-26)
Date: 2026-10-26   Model: Claude Opus 5.5
Context:  Wi-Fi setup took typing a pairing IP:port + code, then a second IP:port; the connect port
          changes whenever Wireless debugging is turned on, so remembered addresses went stale.
Options:  1) Own mDNS listener (zeroconf dependency)  2) The adb server's built-in mDNS browser
          (`host:mdns:services`, adb 31+)  3) Keep typing addresses
Chosen:   2, plus QR pairing as Android Studio does: random name + password (secrets) in a
          WIFI:T:ADB QR; pair only with the phone announcing that exact name; then connect to the
          connect service on the same IP (or reuse adb's own mDNS auto-connection). Known phones
          (phone record by hardware serial) are found and connected again by serial, also mid-run.
          QR drawn with `segno` (user-approved dependency).
Why:      No IP typing, no extra network library; adb shipped with the Windows release has mDNS.
Trade-off: Needs Android 11+, same network with multicast (guest Wi-Fi / AP isolation / VPN block it),
          and an adb with mDNS (old distro adb on Linux: falls back to the pairing code). Wireless
          debugging still has to be turned on by hand after a phone restart (no root).
Security: discovery is not trust: adb only connects to phones paired with this PC's key; the QR
          password is never logged and expires after 2 minutes.
Addendum (2026-10-26, #79): live, no mDNS responder answered on the Wi-Fi at all. Fallback when
          remembered addresses and mDNS bring no Wi-Fi phone back: scan the remembered phone IPs (only
          those) for ports 30000-49999 (asyncio connect scan, ~2 s on a LAN; a 1 s probe skips hosts that
          are off) and connect to the open port that takes adb. Connect timeout 5 -> 15 s (~500 ms round
          trips); offline ip:port leftovers are disconnected.

## D-026: Desktop UI v2 follows the Stitch designs; dark Material 3 tokens, bundled SVG icons + fonts  (ACCEPTED 2026-10-26)
Date: 2026-10-26   Model: Claude Opus 5.5
Context:  The user generated desktop + Android designs in Google Stitch (docs/design/stitch, SCREENS.md)
          and wants the GUI rebuilt to match them, wired to real features only.
Options:  icons: 1) Material Symbols SVGs  2) Material Symbols variable font + build-time subsetting
          3) no icons; fonts: bundle Inter / Roboto Flex / JetBrains Mono vs system fonts
Chosen:   1 + bundled fonts (user choice). One token module (`cob/ui/style/tokens.py`) feeds the QSS,
          the palette and the widgets; dark scheme only (the designs have no light palette). Shared
          widgets in `cob/ui/widgets/`; pages come one per PR under epic #61.
Why:      SVGs (Apache 2.0, ~130 files) need no build tool and are tinted at runtime; fonts (OFL, 2.8 MB)
          make the exe look the same on every PC. Elements without a real feature are left out or shown
          disabled, never filled with fake numbers.
Trade-off: +~3 MB of assets; QSS cannot do shadows/blur, so depth comes from surface colour steps.
Revisit if: a light theme is wanted (needs a second token set).

## D-027: Daily limits, quiet hours and the failure limit live in farm.json; a reached rule stops the run  (ACCEPTED 2026-10-26)
Date: 2026-10-26   Model: Claude Opus 5.5
Context:  The Safety & Schedule design (#42) asks for max play time / attacks per day, quiet hours and an
          adjustable consecutive-failure stop. The loop already stopped after 3 failures (hard-coded).
Options:  1) Stop the run when a rule is reached  2) Pause and resume automatically when allowed again
Chosen:   1. New FarmConfig fields daily_minutes, daily_attacks (0 = off), quiet_from / quiet_to (hours,
          equal = off, wraps midnight), max_failures; FarmLimits carries them; `schedule_stop()` runs
          before every cycle. Today's usage = history.csv rows of today (every run appends there), read
          only when a daily limit is set. The GUI shows such a stop as a safety stop.
Why:      Stopping is predictable and safe (no unattended restarts); history.csv already holds per-cycle
          seconds and attacks, so no new storage.
Trade-off: A run that hits quiet hours has to be started again by hand; usage counts finished cycles only
          (a cycle in progress may cross the limit).
Revisit if: users want a scheduler that starts runs at set times.

## D-028: Read the Overall Damage % with scaled loot glyphs; surrender through End Battle too  (ACCEPTED 2026-10-26)
Date: 2026-10-26   Model: Claude Opus 5.5
Context:  #78 live retest on the phone: the bot surrendered a 62 %, 2-star attack as "stalled at 0 %".
          The cyan bar (D-018) is only drawn until the first star; then the game shows stars and the
          red button says End Battle instead of Surrender, so the bar read 0 and the surrender
          template never matched (one snapshot per poll until the timer).
Options:  1) Keep the bar, stop watching after the first star (battle runs to the timer)
          2) Read the % number: cut a new 10-glyph font from live battles
          3) Read the % number with the loot glyphs scaled 1.4x (same Supercell font, larger)
Chosen:   3. attack.toml [damage] = region, digits, scale, threshold; values outside 0..100 are dropped.
          Surrender taps Surrender or End Battle, then Okay on the confirm dialog (also when the dialog
          is not classified). The stall snapshot is saved once per battle.
Why:      Option 3 reads 2, 5, 62 and 94 % on LDPlayer and phone frames at 0.92-0.96 (the % sign
          scores 0.73, threshold 0.85) with no new glyphs; option 1 wastes up to 2 min per attack.
Trade-off: Digits 0, 1, 3, 7 and 8 are not yet confirmed on real damage frames.
Revisit if: a live battle logs a damage value that does not match the screen.

## D-029: Dark, light and AMOLED themes with six accents, applied at start-up  (ACCEPTED 2026-11-03)
Date: 2026-11-03   Model: Claude Opus 5.5
Context:  User request (#102): dark, light and AMOLED modes plus an accent colour. D-026 had one dark
          token set and said to revisit when a light theme is wanted. Widgets read the tokens when they
          are built, and some modules keep token colours in import-time constants.
Options:  1) Switch live: rebuild every page (or restyle every widget) on change
          2) Rebind the tokens at start-up from ui.json; a change asks for a restart (Restart now button)
Chosen:   2. `tokens.apply(theme, accent)` resets to the dark/teal defaults, then overlays the theme set
          (light, amoled) and the accent's four primary roles (separate tones for dark and light).
          Overlays and dividers became tokens (white-based on dark, black-based on light). cob.ui.app
          applies ui.json's choice before importing any UI module; ui.json validates both values.
Why:      Live switching would mean rebuilding the window while a farm run may be going on; a restart
          (refused while farming) keeps every page simple and correct.
Trade-off: A theme change needs a restart.
Revisit if: users switch themes often (then rebuild pages when idle).

## D-030: Update check through GitHub's releases API; manual, plus an opt-in start-up check  (ACCEPTED 2026-11-03)
Date: 2026-11-03   Model: Claude Opus 5.5
Context:  User request (#104): check for updates and show the changelogs. CONSTRAINTS allows only an
          opt-in update check as a network call, and the user approved calling GitHub.
Options:  1) Read the releases API of this repository (public JSON, release notes = changelog sections)
          2) A small latest.json published with each release (needs an extra publish step)
Chosen:   1. `cob.core.updates`: stdlib urllib (no new dependency), 10 s timeout, a User-Agent, no other
          data sent; drafts are skipped. Stable builds only see stable releases; alpha / beta / rc builds
          also see pre-releases. The Release tab shows every newer release's notes in order. The
          start-up check is a switch, off by default; it runs in the background once per start and only
          reports an available update (tray message). Nothing is downloaded or installed.
Why:      The release notes already are the changelog (scripts/release.py), and no extra artefact
          has to be kept in sync.
Trade-off: The repository is private today, so the API answers 404 to the app; the check reports that in
          plain words until the repository or its releases are public.
Revisit if: the repository stays private (publish releases to a public repo or a latest.json instead).

## D-031: Quiet hours, the random rest and daily limits can pause a run instead of ending it (opt-in)  (ACCEPTED 2026-11-04)
Date: 2026-11-04   Model: Claude Opus 5.5
Context:  D-027 stops the run when a schedule rule is reached, so a run that hits quiet hours or the daily
          limit has to be started again by hand. MyBot resumes on its own (#120, from #106).
Options:  1) Keep stopping  2) Opt-in pause: rest and check again every few minutes, optionally closing the
          game  3) Compute the resume time and sleep until then
Chosen:   2. FarmConfig resume_after_rest / close_game_resting (0 / 1, off by default, Safety > Quiet
          Hours). The farm loop calls schedule_stop() as before; with resume on it rests 5 min and checks
          again instead of returning. The next cycle's go_home reopens a closed game (#147).
Why:      Re-checking reuses schedule_stop() unchanged, so quiet hours, the random rest (#121) and both
          daily limits resume the same way without a second notion of "when"; Stop still ends a rest
          within one sleep.
Trade-off: A phone on battery may time out and lock during a long rest (30 min bot timeout); the next
          cycle then stops with PhoneLocked. Emulators and phones on a charger are unaffected.
Supersedes: the "Stop" choice of D-027 when the switch is on; D-027 stays the default.

## D-032: Phone alerts through a Discord webhook or a Telegram bot, opt-in  (ACCEPTED 2026-11-07)
Date: 2026-11-07   Model: Claude Opus 5.5
Context:  #43: a run is often unattended, and tray messages only show on the PC. CONSTRAINTS allows
          notifications the user configures as a network call.
Options:  1) Discord webhook and Telegram bot API, both plain HTTPS POSTs from stdlib urllib
          2) A push service (ntfy, Pushover) or e-mail (extra accounts, SMTP secrets)
Chosen:   1. `cob.core.notify`: the same alerts as the tray (safety stop / error, finished, break, test),
          filtered by the same Settings switches. Targets are typed on the Settings page and kept only in
          ui.json; malformed values are not saved. Only the alert title and text are sent; Discord
          mentions are disabled. Sending runs in a background job with a 10 s timeout; errors name the
          service and HTTP status, never the URL or token.
Why:      Both are free, need no extra app account beyond what most players already use, and need no
          new dependency.
Trade-off: The webhook URL and bot token sit in plain text in ui.json (same as the rest of the user data
          folder); anyone with that file can post to the channel.
Revisit if: users ask for other services, or secrets need the OS keychain.

## D-033: Unit database in its own repository; bar cards recognised by their portrait  (ACCEPTED 2026-11-08)
Date: 2026-11-08   Model: Claude Opus 5.5
Context:  Troop detection: a Super Valkyrie card was read as a spell from its colour. Future attack
          planning needs unit facts (kind, housing, targets, stats per level).
Options:  1) Unit data from the game's own files in a separate, versioned repository, bundled by tag
          2) Read coc.guide or another fan site at run time
          3) Hard-code facts per unit in the bot
Chosen:   1. Clash-Tools/clash-of-bots-data (tools/extract.py from the asset pack, JSON Schema, CI,
          tags data-vN); scripts/update_units.py copies a tag into assets/units. Cards are recognised by a
          colour fingerprint of the portrait band (rows 795-838, 14 px inset: no count, level, pet icon or
          upgrade arrow); same unit >= 0.97, different units <= 0.78 on the fixtures, so match at 0.85.
          Unrecognised cards are saved once to <user data>/cards/unknown for labelling in the app; labels
          go to cards/labelled and are recognised from the next battle on.
Why:      Exact numbers that follow game updates, no network dependency, new and event troops handled by
          labelling a picture instead of a code change.
Trade-off: The database has no card pictures until they are labelled and exported; until then the bar
          still uses card colour and order for the kind.
Revisit if: portraits change with skins (add variants per unit) or another resolution is supported.

## D-034: Profiles: one device per account, run in turn, no account switching  (ACCEPTED 2026-11-08)
Date: 2026-11-08   Model: Claude Opus 5.5
Context:  #2: several accounts / LDPlayer instances, each with its own settings, schedule and history.
Options:  1) Profiles with their own device; "Run in turn" farms them one after another
          2) One device, the bot switches Supercell ID accounts between runs
          3) Several bots at once, one window per device
Chosen:   1. profiles.json in the user data folder (validated on load, bad entries skipped) lists id,
          name, device serial, player tag and "in turn"; each profile's farm settings sit in
          profiles/<id>/farm.json, and the Default profile keeps the old farm.json so an existing install
          needs no migration. history.csv gains a "profile" column; daily limits count only that
          profile's rows and each profile draws its own daily limits and off-period. Running in turn
          starts the next profile when one stops (limits, safety stop or error); Stop ends the turn. An
          LDPlayer instance that is not running is launched when its turn comes. CLI: `cob profiles`,
          `cob farm --profile ID`.
Why:      An instance per account is how multi-account players already work, and the bot never has to
          type into or confirm the Supercell ID sign-in, which would break rule 1 (no input on account
          or consent screens) and risk the account.
Trade-off: Two accounts on one phone need the user to switch accounts by hand; runs in turn are
          sequential, not parallel.
Revisit if: users ask for parallel runs (one worker per device), or a safe, verified account switch is
          possible.

## D-035: Clash of Clans API sync per profile, with the user's own key  (ACCEPTED 2026-11-08)
Date: 2026-11-08   Model: Claude Opus 5.5
Context:  The bot should know each account's real troops, spells, heroes, pets and equipment with levels
          (card labelling, army analysis, planning) without driving the game's menus to read them.
Options:  1) The official Clash of Clans API (developer.clashofclans.com), user's own key, user-started
          2) Read the levels from the game's screens (army, laboratory, hero hall)
          3) A fan site or third-party API by player tag
Chosen:   1. `cob.core.coc_api`: Sync on the Profiles page sends GET /players/{tag} with the key from
          Settings (ui.json, never logged or shown in errors) to the official API or an https address the
          user sets (a fixed-IP proxy). The answer is cached per profile (profiles/<id>/player.json) and
          matched to the unit database by name and village; hero equipment is kept by name. The Cards
          page lists the account's own units first with their level. Rule 8 / 9 / 10 updated.
Why:      Exact levels straight from Supercell, no input on the device, works with the game closed;
          the key and the data stay with the user.
Trade-off: Each user needs a developer account and a key bound to their public IP address; a changed
          address answers 403 until the key is edited (or a proxy is set).
Revisit if: Supercell changes the API terms, or the bot needs data the API lacks (builder upgrades,
          army composition), which still needs screen reading.

