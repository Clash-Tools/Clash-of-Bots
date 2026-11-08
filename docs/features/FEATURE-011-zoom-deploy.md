# FEATURE-011: Reliable zoom, checked deploys, Builder Base collection

Goal: fix the user's bug list (2026-10-21): boat not found home <-> BB, troops and heroes left in the
bar on both bases, BB troops swapped, BB elixir not collected. Design: D-021, D-022.

- `Navigator.zoom_out()`: pinch, compare a small grey copy of the playfield, repeat while it moves
  (>= 8 levels, max 3). Used by farm maintenance, `go_to_builder_base` (before the boat search and
  on arrival), AttackTask at battle start, BbAttackTask at each stage, and the BB_HOME `zoom` action
  (`tap bb_boat_icon else zoom else swipe ...`, one zoom per go_home).
- Templates: optional `scales` (best score wins); boat bubbles 0.9 at full zoom-out.
- `cob/tasks/deploy.py`: `tap_card` (card face y 775-815, clear of the upgrade arrow at ~840-870),
  `place_unit` (card changed after the ground tap = placed; spread retries, then 3x margin).
- `find_cards` replaces the badge reader for positions in both villages.
- `collect_builder_base`: every bb_collect_gold / elixir / gems bubble, re-check, up to 3 rounds;
  `FarmParts.bb_maintain` runs it before Builder Base cycles.

Live (LDPlayer 14, 2026-10-21):
| Run | Result |
|---|---|
| BB attack | zoom-out per stage; 7 + 4 cards placed (each card turned green = deployed) |
| BB attack + boat home | 7 + 3 placed, one card refused twice then placed at the 3rd spot; home after 1 drag |
| Home attack | zoom-out, bar read (old reader had lost 3 cards), 3 heroes placed, 91 % |
| BB collect | gold +10.5k, elixir +10.5k, gems tapped |
| BB farm cycle (loop) | collect check + attack 7 + 3, +122k gold |

Known: a collector on the far top edge of the BB map stays off screen at full zoom-out (not tapped).
