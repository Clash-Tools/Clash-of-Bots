# FEATURE-003: M2 navigator, popup recovery and search loop

Goal: from any game state, get back to HOME safely; first piece of the M2 farm loop.
Design: `cob/screens/navigator.py` + per-screen `to_home` action in screens.toml (data, D-010); D-015.

M2 plan (approved 2026-10-18), one PR each:
1. Navigator + popup recovery  <- this feature
2. Search loop: Find a Match -> read loot -> Next until filter passes; `--dry-run` ends battle unattacked
3. Attack v1: one-edge deploy, heroes last, abilities after delay, end when damage stalls
4. Army-full check + `cob farm` loop with stats; GUI after M2

Default farm settings (approved; %LOCALAPPDATA%\ClashOfBots\farm.json, clamped on load): attack if
gold+elixir >= 800k or dark >= 8k; max 40 Nexts then take the CURRENT base (CoC cannot go back to an
earlier one, so "best seen" is only logged as best_skipped); stop if own gold < 50k; no spells in v1;
end battle when damage unchanged 15 s after full deploy or 30 s left.

Actions (`to_home`): `wait` | `back` | `tap <tpl> [<tpl>...]` (taps first visible template centre).
| Screen | Action |
|---|---|
| POPUP_RELOAD | tap reload_button / reload_game |
| SHOP, BUILDER_MENU, ARMY, POPUP_GENERIC | tap their close X |
| BATTLE_END | tap return_home |
| ATTACK_SEARCH | tap end_battle |
| ATTACK_MENU | Android Back |
| LOADING, SEARCHING, BATTLE | wait (surrender comes with PR 3) |
| UNKNOWN | no input; restart app if game not in front (after 5 s) or still unknown after 45 s; once |

Rules: act only after 2 consecutive equal classifications; re-confirm after every action;
overall timeout 240 s (covers a battle running out); stop event aborts.

CLI: `cob screen -s SERIAL` (live classify), `cob home -s SERIAL` (navigate, prints steps).

Live results (LDPlayer 14, 2026-10-18):
| Start | Steps | Time |
|---|---|---|
| Connection lost | tap TRY AGAIN > loading | 8.6 s |
| Attack menu | Back | 4.4 s |
| Army | tap X > Back | 6.9 s |
| Shop | tap shop X | 4.4 s |
| Builder menu | tap builder X | 4.4 s |
| Game killed | restart (not in front) > loading | 33.4 s |
Search -> End Battle verified on fixtures only (live costs gold; runs live in PR 2).

Found live and fixed:
- Back on an UNKNOWN screen (builder menu) exited CoC -> no blind input on UNKNOWN; BUILDER_MENU screen.
- LDPlayer 14 has no `monkey` -> app_start resolves the launcher activity and uses `am start`.
- Shop opens ~4.5 s after the tap; anything tapped meanwhile lands inside it. The navigator is safe
  (confirms screen before each tap); task code must wait for the expected screen too.

## PR 2: search loop (`cob/tasks/search.py`)
Flow: go_home -> own gold check (bar) -> Battle -> Find a Match -> [army review: Attack!] -> per base:
read loot (2 equal reads) -> filter -> Next (wait for the old base to leave before reading again).
Outcome: accepted | max_nexts (both attack) | low_gold | failed (both go home). `cob search --dry-run`
always ends with End Battle; `run(dry_run=False)` stays on the accepted base for the attack task.

Found live: Find a Match now opens the army review screen (green Attack!) before searching, at least
while the Clan Castle is empty; Edit Army shows the same screen with a brown Battle button instead.

Live (LDPlayer 14): first base accepted 920k in 42 s (home -> home); forced 3 Nexts: 4 bases, ~8-20 s
each, 12/12 loot values correct by eye, own gold dropped exactly 4 x 1400.

## Log
- 2026-10-18 (Claude Opus 5.5, Windows): search loop, farm config, army review step.
- 2026-10-18 (Claude Opus 5.5, Windows): navigator, BUILDER_MENU, end_battle, CLI, live tests.
