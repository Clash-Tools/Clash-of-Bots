# FEATURE-009: Wall upgrades (M3)

Off by default: farm.json `wall_upgrades` (walls per cycle, 0 = never), `wall_reserve` (default 1,000,000).
Runs in farm maintenance after zoom-out / collect. Settings tab has both fields.

Flow (`cob/tasks/walls.py`): Build menu -> scroll to the END of the cost-sorted list, then back up to the
first "Wall" row = the cheapest wall -> its panel -> gold or elixir Upgrade hammer (icon colour decides;
the Wall Ring button is never a hammer) -> "Upgrade Wall to Level N?" -> checks -> Confirm -> home.

Spend safety (D-020):
- cost on the Confirm button read exactly with `digits/cost` glyphs; unknown digit -> refuse (no spend)
- cost text not red; coin/drop icon matches the resource; resource - cost >= reserve (else try the other)
- after Confirm, own resource must drop by the cost (+-1 %); otherwise walls stop for the rest of the run
- refusals save a snapshot and close everything via X; never gems, Wall Rings, Gold Pass ads
Glyphs so far: 0 1 4 5 (from live dialogs); other digits are added when a refusal snapshot shows them.

Live (2026-10-19): first run refused a 4,000,000 wall (digit 4 unknown) and showed the list scroll took
the first, not the cheapest, wall -> both fixed; rerun upgraded the cheapest wall for 5,000 gold,
gold 8,504,022 -> 8,499,022 verified.

## Log
- 2026-10-19 (Claude Opus 5.5, Windows): wall task, cost glyphs, spend checks, live upgrade.
