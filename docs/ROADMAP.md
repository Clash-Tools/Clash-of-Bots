# ROADMAP (fastest path to a working farm bot)

Each milestone ends with something runnable. One feature file in docs/features/ per item.

## M0 Foundations (1-2 sessions)
- [x] Repo skeleton `cob/`, pyproject (uv), ruff, pytest, logging
- [x] CI: GitHub Actions windows build -> Nuitka exe artifact + smoke test (`--selftest`)
- [x] Device protocol + LDPlayerDevice: connect by serial, capture (raw screencap), tap, swipe; latency bench
- [x] Dev tool: `cob capture` saves frames; `cob crop` makes templates from frames

## M1 See the game (1-2 sessions)
- [x] Template store (cached, per resolution) + match/match_all + NMS
- [x] OCR wrapper (digits for loot/resources), frame-agreement helper
- [x] Screen classifier (engine; anchors not captured yet): HOME, ATTACK_SEARCH, BATTLE, BATTLE_END, ARMY, LOADING, POPUP, UNKNOWN
- [x] Recorded-frame fixtures + tests for classifier and OCR

## M2 Farm loop MVP  <- first useful exe
- [x] Navigator go_to(HOME) with popup recovery
- [x] Search -> read loot -> next until filter met (gold/elixir/dark thresholds)
- [x] Deploy v1: border-relative edge (no zoom, D-016), heroes + abilities, battle ends by itself
- [x] Surrender on stalled damage (damage %, D-028; was the damage bar, D-018)
- [ ] Deploy v3: multi-side spread, spells
- [x] Return home; army refills instantly in current CoC (army review Attack! handled), wait+retry if not ready
- [x] Farm loop CLI: `cob farm` with stats and stop rules
- [x] Minimal GUI: device select, start/stop, loot filter, live log, stats

## M3 Village maintenance
- [x] Collect collectors (zoom-aware) + zoom-out before each cycle
- [x] Loot cart (tombstones skipped: unreliable, no reward)
- [ ] Chests / daily rewards
- [x] Walls (cheapest first, opt-in, D-020 spend safety)
- [ ] Auto upgrade buildings/lab with policy (pure function, tested)
- [x] CC request (opt-in)

## M4 Robustness + multi
- [x] Breaks/humanization (tap jitter, breaks between cycles)
- [ ] Session limits per day, PopupWatcher thread
- [ ] Profiles + multi-account switch; multi LDPlayer instance (ldconsole)
- [ ] Notifications (Discord webhook / Telegram) optional

## M5 Extras
- [ ] Clan Games, events, ranked signup
- [x] Builder Base attacks (two stages, boat both ways, GUI mode)
- [ ] Google Play Games backend (parked: fixed 1920x1080 HUD scale, FEATURE-013)

## M6 More devices + platforms (v0.2.0)
- [x] Real Android phones over ADB (display mode + restore, root pinch, D-023, FEATURE-012)
- [x] Wireless ADB (pair / connect / USB to Wi-Fi) + Restore phone screen button (D-024)
- [x] Linux packages in releases (.deb, .rpm, AppImage)
- [x] Deploy points checked against the red line; per-card placement check (D-022)
- [ ] No-root pinch injector for phones (app_process + InputManager) - deferred by the user
- [ ] Scale-aware vision (any HUD scale) - needed for Google Play Games
