# FEATURE-008: Collect resources + camera zoom (M3 start)

Goal: collect gold / elixir / dark elixir from collectors during farming, spending nothing.

`cob/tasks/collect.py` CollectTask:
- bubbles `collect_gold|elixir|dark` (colour templates, whole village, HUD boxes excluded)
- one tap on a bubble collects EVERY collector of that type, so one tap per type per round, then
  re-capture; a second tap would hit a bare collector and open "Boost Production!" (gems)
- camera zoom differs between sessions: the zoom is found from the best bubble match over
  scales 0.8-1.3, then all bubbles are matched at that scale
- ends with go_home, which closes anything opened by accident (BOOST_DIALOG: X only)

Camera: `AdbDevice.pinch()` sends a two-finger pinch as raw multi-touch events (`sendevent`, MT protocol B,
touch node found with `getevent -lp`). Farm maintenance zooms out at home before every cycle. (Later
measured: the battle camera does NOT inherit the village zoom; battles zoom out themselves, D-022.)

Settings: farm.json `collect_minutes` (default 10, 0 = off), Settings tab field.

Found live while building this (fixed in the same branch):
- LDPlayer's own real-money "Top-Up via LDPlayer" offer over the game -> LDPLAYER_TOPUP (close X only)
- "Welcome Back Chief!" dialog ate the map drags meant for the boat -> WELCOME_BACK (Back)

Live (2026-10-19): collect +102,520 gold +96,173 elixir; 2 farm cycles with zoom-out + collect:
2/2 attacks, +3.42M gold, +2.10M elixir, +17.9k dark.

## Loot cart and tombstones (branch feat/collect-extras)
- Loot cart: dashed "Collect" label over the wagon (map, whole frame) -> tap the wagon -> "Loot Cart" panel
  -> Collect. Live: +138,824 gold, +135,733 elixir, +1,694 dark (exactly the cart contents).
- Tombstones: not collected. At default zoom they are ~15 px; the template hit decorations at 0.85 and
  missed most real ones at 0.9, and removing them yields nothing in the current game. Revisit only with a
  better signal (e.g. building-info name) if obstacles start blocking deploys.

## Log
- 2026-10-19 (Claude Opus 5.5, Windows): loot cart; tombstones evaluated and skipped.
- 2026-10-19 (Claude Opus 5.5, Windows): collect task, zoom-out, top-up / welcome-back / boost screens.
