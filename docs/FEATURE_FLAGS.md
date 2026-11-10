# Feature flags (D-038)

Work that is not finished, or not yet checked live, ships behind a flag in `cob/core/flags.py` so users
only see what works. Every flag has an issue, and the issue is on the
[project board](https://github.com/users/hrishi072/projects/3) with its **Feature flag** field set to
the flag's stage.

| Stage | Default | Meaning |
|---|---|---|
| beta | on | Finished and in use, still being polished |
| experimental | off | Built, but not checked live yet |
| incomplete | off | Only partly built, or only a placeholder |

## Turning flags on

- **App:** Settings > About > Developer options, turn on **Show developer options** and accept the
  warning (unfinished features may fail during a run; use a test account). Clicking the version text
  seven times is a shortcut without the question. A **Developer options** tab appears with a switch per
  flag. Changes apply after a restart; **Hide developer options** hides the tab again.
- **File:** `flags.json` in the user data folder: `{"developer": true, "flags": {"clan_games": true}}`.
  Only changes from the default are stored; a broken file means all defaults.
- **Environment:** `COB_FLAGS=clan_games,-builder_base` (on / off) overrides the file. Tests use this.

## Current flags

| Flag | Stage | What it shows | Issue |
|---|---|---|---|
| `builder_base` | beta | Dashboard Builder Base mode, Automation > Builder Base | #29 |
| `card_labelling` | beta | Cards page (label and export troop cards) | #19 |
| `profile_rotation` | experimental | Profiles > "Run in turn" and the per-profile checkbox | #2 |
| `coc_api_sync` | experimental | Settings API key, Profiles player tag + Sync, own units first on Cards | #45 |
| `live_stream` | experimental | Automation > Farming Heuristics "Live screen stream" switch | #37 |
| `clan_games` | incomplete | Automation > Clan Games (placeholder) | #1 |
| `building_upgrades` | incomplete | Automation > Upgrades note on buildings and lab | #3 |

## Inventory (2026-11-10)

Unused or incomplete things found in the app, and what happened to each:

| Item | State | Action |
|---|---|---|
| Clan Games tab | placeholder text only | behind `clan_games`; issue reference fixed (old #38 -> #1) |
| Building / lab upgrades note | text only, walls work | behind `building_upgrades`; reference fixed (old #40 -> #3) |
| Builder Base | attacks + collecting work; loot priority, Clock Tower, upgrades missing | `builder_base` (beta, on) |
| Run profiles in turn | built, not run live with two devices | `profile_rotation` (off) |
| Clash of Clans API sync | built, not checked with a live key | `coc_api_sync` (off) |
| Cards page | works; mostly needed for siege machines now | `card_labelling` (beta, on) |
| `MainWindow._coming_soon` | never called | removed |
| Live screen stream (PR #44) | built, not measured live | `live_stream` (off) |
| Setup wizard handshake stats | left out of the design on purpose | nothing to hide |
| Google Play Games, BlueStacks / MEmu, Android app | not in the app at all (#7, #35, #9) | nothing to hide |
| CLI developer commands (`crop`, `match`, `ui-gallery`, ...) | developer tools by design | stay |

## Adding a flag

1. Add a `Flag` to `FLAGS` (key, title, description, stage, issue) and check `flags.enabled("key")`
   where the feature's UI is built (hide the widgets; keep the code path testable).
2. Add the issue to the board with **Feature flag** = the stage.
3. When the feature is proven: move it to beta, then remove the flag and its checks once it has been
   beta for a release.
