# FEATURE-007: Builder Base (M5)

Goal: farm Builder Base battles like the home village, and never get stuck there.
Status: screens, safe exit and the two-stage attack done (cob bb, GUI mode "Builder Base attacks").

## What a BB battle looks like (live, LDPlayer 14, BH with 2 stages, 2026-10-18)
1. BB_HOME (crossed-axes Battle) -> BB_ATTACK_MENU "Start Attack" (army preview, Find Now!)
2. Matchmaking clouds -> stage 1 base with "Battle starts in 60s" (deploy any time; deploying starts it)
3. Stage 1 battle: same Overall Damage panel as the home village (classified BATTLE)
4. Stage 1 at 100 % -> star, camera pans to stage 2 -> "Battle starts in 58s", bar gains a new card
   (stage-2 reinforcement); troops still alive carry over
5. Results: stars + "Total damage" (stage 1 + stage 2, max 200 %), rewards, Return Home (BB_RESULTS)
6. Loot: rewards come from the BB star / damage ladder (no loot filter needed; no Next in BB search)

## Screens (this PR)
| Screen | Anchor | Towards home |
|---|---|---|
| BB_HOME | bb_attack_button | tap bb_boat_icon, else zoom out (once), else drag the map to show the dock |
| BB_ATTACK_MENU | bb_start_attack_title | Back |
| BB_RESULTS | bb_return_home | tap bb_return_home |
| BB battle | overall_damage (shared) | wait |

Navigator syntax extended: `swipe x1 y1 x2 y2` and "A else B" (B runs only when A did nothing).

## Attack (branch feat/bb-attack)
- `cob/tasks/builder.py`: go_to_builder_base (boat bubble in either village, drag the map when it is off
  screen, max 4 drags), BbAttackTask (Find Now -> at every BB_STAGE_WAIT deploy the unused cards on one
  edge, abilities after 6 s -> results -> Return Home), run_bb for the CLI.
- New screens: BB_STAGE_WAIT ("Attacker" + "Battle starts in", threshold 0.9 vs "ends in" 0.72),
  BB_SEARCHING, BB_STAR_BONUS (daily reward over BB home: covered Battle + boat in the first live run).
- Navigator: go_home(arrive=...) so BB tasks clear popups without sailing back; drags capped at 4.
- GUI + loop: Builder Base mode reuses FarmTask (limits, breaks, Stop, relaunch, history); no resource
  gain is recorded for BB (BB resources are separate).
- Live: first run 1 two-stage battle ok, then Star Bonus blocked 2 attacks and the boat (fixed);
  rerun 2/2 attacks + boat home in 4.6 min; GUI mode 1 attack in 111 s.

## Earlier plan notes
- BbAttackTask: BB_HOME -> Find Now -> wait for stage 1 -> deploy all cards on one edge (same border
  geometry: verified on a BB base, 11 points) -> abilities -> when the stage-2 countdown appears,
  deploy remaining + reinforcement cards -> results -> Return Home -> boat home.
- Anchors still to cut: BB matchmaking clouds, stage countdown ("Battle starts in"), stage-2 marker.
- Daily star bonus: stop after the 8 stars of the day (0/8 shown on BB_HOME), optional.
- Getting TO Builder Base from the home village means tapping the boat on the map; its position moves
  with the camera (a blind tap selected a wall in testing), so it needs its own template + drag fallback.

## Log
- 2026-10-18 (Claude Opus 5.5, Windows): two-stage attack, Star Bonus, cob bb, GUI mode.
- 2026-10-18 (Claude Opus 5.5, Windows): BB frames, screens, exit path; live battle 3 stars / 100 %.
