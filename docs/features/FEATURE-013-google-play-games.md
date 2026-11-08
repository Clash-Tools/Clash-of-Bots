# FEATURE-013: Google Play Games for PC backend (PARKED)

Goal: farm in Clash of Clans running in the consumer Google Play Games for PC app (Windows).
Status: parked by the user on 2026-10-22 for a later release (v0.2.0 shipped without it).

Findings (spike, nothing committed):
- The consumer app has no adb (only the separate Developer Emulator exposes localhost:6520), so the
  backend drives the game window directly: capture, clicks, drags, Esc and mouse-wheel zoom all work
  in the background through ctypes, no new dependency.
- PrintWindow returned black frames: capture needs the window visible (not covered, not minimised).
- The game renders at a fixed 1920x1080 @ 240: scaled to 1600x900 the HUD is 0.83x of the templates,
  so the LDPlayer templates and fixed regions do not match.

Open decision (user): a Google Play Games resolution setting, if one exists, vs scale-aware vision
(templates and fixed regions at any HUD scale; would also help other screen sizes).

Plan once decided: `WindowDevice` implementing `cob.device.base.Device` (+ `pinch` via the wheel),
listed in `cob devices` / GUI / Setup checks, one home and one Builder Base cycle live, small tests.
