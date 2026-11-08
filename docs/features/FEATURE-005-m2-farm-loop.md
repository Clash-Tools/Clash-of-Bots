# FEATURE-005: M2 farm loop

Goal: the first useful bot run: repeat search + attack with stats and safe stop rules.
M2 PR 4 of 4 (plan in FEATURE-003). GUI comes after M2.

`cob/tasks/farm.py` (steps injected as callables; CLI wires the real tasks):
- cycle: own resources at home -> SearchTask(dry_run=False) -> AttackTask -> own resources again;
  net gain = after - before (includes search costs and star bonus)
- stop: --cycles (default 5, 0 = none), --minutes, Ctrl+C (stats kept), own gold below reserve,
  village open on another device (immediately), device lost, 3 failures in a row
- army review without Attack! -> wait 60 s and retry; random 3-8 s pause between cycles
- errors inside a cycle are caught: device gone -> stop "device lost", others count as failures
- capture retries twice on short glitches

CLI: `cob farm -s SERIAL [--cycles N] [--minutes M]` prints per-cycle lines, totals and per-hour rates.
Logs: %LOCALAPPDATA%\ClashOfBots\logs\cob.log (rotating, DEBUG).

Live (LDPlayer 14, 2026-10-18):
Run 1: cycle 1 ok (+749k gold, +1.36M elixir, +11k dark, 191 s); LDPlayer then stopped mid-battle.
Run 2 (after relaunch, starting on the Android launcher -> navigator restarted CoC):
| Cycle | Nexts | Base (gold / elixir / dark) | Net gain (gold / elixir / dark) | Time |
|---|---|---|---|---|
| 1 | 1 | 821k / 759k / 4.1k | +1.05M / +1.32M / +5.6k | 267 s |
| 2 | 0 | 636k / 593k / 6.8k | +864k / +1.17M / +8.3k | 180 s |
| 3 | 0 | 646k / 757k / 14.9k | +1.16M / +987k / +16.4k | 230 s |
Total 11.6 min: +3.07M gold, +3.48M elixir, +30.3k dark (per-hour extrapolation is optimistic: gains
include star bonus / event rewards and short runs have no breaks).

Found live:
- LDPlayer stopped by itself mid-battle (adb device gone, capture returned 0 bytes); the error escaped
  the loop -> now caught and reported as "device lost". Relaunching the emulator is not automatic yet.

## Robustness (branch feat/relaunch-emulator)
- Device lost -> `LdConsole.ensure_running` relaunches the instance (index from the serial), waits
  until adb sees it (live: 29 s), navigator restarts CoC; max 2 relaunches per run.
- Fresh village can ignore the first Battle tap -> retry up to 3 taps, 8 s apart, while HOME shows.
- Failure snapshots: `%LOCALAPPDATA%\ClashOfBots\snapshots\` (newest 50) when a search/attack fails
  or the navigator restarts the game on an UNKNOWN screen. The first one found the next item.
- SEARCH_BLOCKED: "Unable to attack Village! Try again later." on the cloud screen (seen after
  battles were interrupted by killing the emulator) -> Return Home, farm waits 2 min, retries.
- Known: a spell card was once read as a single unit (card edge guessed 20 px off without an outline);
  effect is one spell cast at the deploy point. A dark-pixel badge detector was tried and was worse.

- Battle cut off by "Connection lost" (snapshot) -> attack fails fast instead of the 240 s timeout.

Live robustness runs (LDPlayer 14, 2026-10-18):
- LDPlayer quit on purpose mid-attack: device lost detected on the next tap, relaunched in 29 s,
  CoC restarted, home reached (twice).
- 3-cycle run after that: 1 win (+1.58M gold, +762k elixir, +18k dark), 1 battle cut by Connection
  lost, 1 search blocked (2 min wait). Interrupted battles seem to trigger the matchmaking block.
- Connection-lost popups were frequent today; cause outside the bot (network / emulator).

## Humanisation (branch feat/humanize, M4 start)
- Taps land at a random point in the middle 60 % of the matched button / card picture; deploy taps
  vary within 6 px (`cob/core/human.py`; tests pin exact centres with a disabled Humanizer).
- Breaks: farm.json `break_every` (default 8 cycles, +-2 random, 0 = off) and `break_minutes`
  (default 5, 0.6x..1.4x); the bot rests at home, Stop interrupts, the time limit counts it.
  GUI shows "on a break until HH:MM". Live: jittered taps hit every button in a full cycle (248 s).

## Log
- 2026-10-18 (Claude Opus 5.5, Windows): tap jitter, breaks between cycles.
- 2026-10-18 (Claude Opus 5.5, Windows): emulator relaunch, Battle-tap retry, snapshots, SEARCH_BLOCKED.
- 2026-10-18 (Claude Opus 5.5, Windows): farm loop, stats, stop rules, live runs.
