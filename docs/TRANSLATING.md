# Translating Clash of Bots

The app's text is English. Other languages come from JSON catalogs in `assets/i18n/` (#103).

## Add a language

1. `uv run python scripts/i18n.py extract`. This refreshes `assets/i18n/template.json` with every string the app shows.
2. Copy `template.json` to `<code>.json`, using a language code such as `de`, `fr`, `pt_BR`, or `hi`.
3. Set `"_language"` to the language's own name (`"Deutsch"`). Then fill in the values.
   - Leave a value empty and the app shows the English text for it.
   - Keep `{placeholders}` such as `{n}` exactly as they are.
4. `uv run python scripts/i18n.py check <code>` lists what is still missing.
5. In the app, open Settings > Appearance > Language and choose the language, then restart.

After app strings change, `uv run python scripts/i18n.py update <code>` adds the new keys to a catalog (empty) and drops the keys the app no longer uses.

## For developers

- Wrap user-facing text in `tr()` from `cob.core.i18n`, as in `tr("Run checks")`.
- Use named placeholders, as in `tr("Stops after {n} cycles", n=5)`. Don't build sentences from pieces.
- Leave out the leading spaces that sit between an icon and its text: `"  " + tr("Save")`.
- Never translate log messages, file names, or the product name.
- Run `scripts/i18n.py extract` after you change strings. A test fails when `template.json` is out of date.
- The language is set at start-up, before the UI is imported, the same way as the theme (D-029). Some labels are module-level constants, so a language change needs a restart.

Every page, the setup wizard, the QR dialog and the tray go through `tr()` (#141). `tests/test_i18n_coverage.py` loads a pseudo-translation of every string and fails on any English left on screen, so new text must be wrapped too.
