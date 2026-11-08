# FEATURE-002: M1 vision + screen classifier

Goal: answer "what is on screen" and "what number is there" fast and reliably at 1600x900.
Design: D-008 (TOML metadata), D-009 (glyph digits + tesseract text), D-010 (data-driven classifier).

Modules:
- `cob/vision/frame.py` Frame caches gray/HSV per capture; Region = (x, y, w, h)
- `cob/vision/templates.py` TemplateStore: lazy PNG load + cache, per-template region/threshold/gray
- `cob/vision/match.py` match (best hit) / match_all (greedy NMS on score map)
- `cob/vision/color.py` hsv_fraction (RED/GREEN/WHITE presets)
- `cob/vision/ocr.py` DigitReader (glyph templates), TesseractOCR (lazy, bundled-path lookup)
- `cob/vision/agree.py` read_stable: N consecutive equal reads
- `cob/screens/classifier.py` ScreenClassifier over assets/templates/1600x900/screens.toml
- CLI: `cob crop`, `cob match`, `cob classify`

Status: real anchors for 10 screens + search-loot glyphs captured on LDPlayer 14; 68 tests pass incl. 28 on
real frames (tests/fixtures/frames, JPEG q95, D-013). Read regions in assets/templates/1600x900/regions.toml.

Screens: LOADING, POPUP_RELOAD, SHOP, ARMY, POPUP_GENERIC, BATTLE_END, BATTLE, SEARCHING, ATTACK_SEARCH,
ATTACK_MENU, HOME (priority order). Notes:
- BATTLE keys on "Overall Damage" (search also shows End Battle); ARMY outranks POPUP_GENERIC (own close X).
- Two close-X variants (army style, log style). Anchors never include costs (D-014).
- POPUP_RELOAD covers both TRY AGAIN (connection lost) and RELOAD GAME ("Anyone there?" idle disconnect).
- SHOP (real-money offers) is detected by its own close X so the bot only ever closes it.
- Own resources (top-right bar) use the loot font: same glyphs, regions.toml [bar].
- Builder menu open (right-side list) hides the Battle button -> UNKNOWN; caller should close it.
- Known UNKNOWNs: blank clouds before text, button pop-in frames (~0.66), fades. Callers use read_stable.

Measured on 80 live frames: every labelled screen correct; DigitReader 78/78 loot values on 19 bases.
classify ~40-130 ms per frame (all screens checked).

Next:
1. Speed: classify only likely screens first (current screen + neighbours) to cut ~100 ms.

Measured: full-frame gray match ~54 ms on 1600x900 (Linux dev box); regions should cut to <5 ms.

## Log
- 2026-10-18 (Claude Opus 5.5): engine + CLI + synthetic tests.
- 2026-10-18 (Claude Opus 5.5, Windows): bar reading, idle-reload fix, SHOP screen; okay_button dropped.
- 2026-10-18 (Claude Opus 5.5, Windows): real anchors, loot glyphs, SEARCHING/ATTACK_MENU screens, fixtures.
