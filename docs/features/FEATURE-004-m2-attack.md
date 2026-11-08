# FEATURE-004: M2 attack v1

Goal: attack the base the search accepted, without spells, and get home. M2 PR 3 of 4 (FEATURE-003 plan).
Design: D-016 (deploy from the red border), D-017 (troop bar from level badges; positions now D-021),
D-022 (zoom out at battle start, placement check).
Data: `assets/templates/1600x900/attack.toml` (border colours, UI boxes, deploy edge, bar thresholds).

Flow (`cob/tasks/attack.py`): confirmed ATTACK_SEARCH -> read troop bar on 2 agreeing frames ->
find base border -> pick deploy edge -> troops (tap card, tap edge points until the card greys out,
max 80 taps) -> single units (siege, heroes, CC) one tap each on the middle point -> 8 s ->
tap singles again (hero abilities) -> wait for BATTLE_END (240 s) -> Return Home.

Geometry (`cob/attack/geometry.py`): red no-deploy border pixels (HSV band wide enough for green and
dark scenery tints) projected on isometric axes u = y + 0.73x, v = y - 0.73x; 1st/99th percentiles give
the diamond. Points 25 px outside one edge, 12 along it, off-screen and UI points dropped; edge
"auto" = most usable points (camera position differs per battle).

Zoom: tried two-finger pinch via `sendevent` on /dev/input/event4 (MT protocol B, pressure needed).
Works in the village; in battle the result was inconsistent (one base zoomed in), so v1 never zooms.

Troop bar (`cob/attack/troops.py`): level badge (black square, white digits) finds each card; a thin
dark outline nearby snaps the exact edge. Kind: "xN" count + blue = troop, + purple = spell,
no count = single. Read once per battle (cards keep their place); later only "greyed out?" checks.
27/39 search frames read the full army; misses are fades, filtered by needing 2 equal reads.

Live (LDPlayer 14, 2026-10-18), 2 battles, both completed home -> home:
| Battle | Loot accepted | Edge | Taps | Result | Time |
|---|---|---|---|---|---|
| 1 | 871k gold / 264k elixir | top_left, 10 pts | 33 | 3 stars, 100%, +2.76M gold | 262 s |
| 2 | 596k / 572k | top_left, 10 pts | 33 | completed | 198 s |

Not done / deviations from the approved plan:
- No surrender on stalled damage (needs Overall Damage OCR + surrender confirm dialog); battles end
  by themselves (base destroyed, troops down, or 3 min timer).
- Event "Pick a Reward!" card pickers appear mid-battle and after stars; UNKNOWN today, they resolved
  on their own. Add as screens if they ever block.
- One fixed army tested (golems, wall breakers, siege, 4 heroes, 2 spells).

## v2 (branch feat/attack-v2)
- Surrender on stalled damage: the Overall Damage bar (cyan fill above the %) is read every 3 s after
  full deploy; no growth for 15 s -> Surrender -> "Surrender?" Okay (D-018). Loot already taken is kept.
  Live: forced stall (one golem) surrendered at ~5% after 18 s, home in 41 s. Normal battles kept
  growing to ~91% and ended by themselves (2 battles).
- Spell cards no longer read as single units: snap only to the card's own left outline (badge-15..-2)
  and judge count text against the bar's brightest pixels (faded frames). 44 frames: 0 misreads.
- Unclear base outline (painted red/orange scenery passed the colour filter) -> fitted outline > 1500 x
  1150 px is rejected; nothing deployed, End Battle is free, next cycle continues.
- Own-resource rows widened for 8-digit values (full elixir 23 000 000 lost its first digit).
- Still open: "30 s left" rule needs the battle timer (not read); spells still unused.

## Log
- 2026-10-18 (Claude Opus 5.5, Windows): v2 surrender on stall, spell-read fix, unclear-outline skip.
- 2026-10-18 (Claude Opus 5.5, Windows): border geometry, troop bar, attack task, 2 live battles.
