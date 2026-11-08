# Hard rules

These apply to every change, whether a person or an AI agent writes it. A pull request that breaks one
is not merged, however useful it is otherwise. Changing a rule needs its own pull request and a decision
record in [DECISIONS.md](DECISIONS.md).

## 1. The bot must not hurt the account or the player

1. **No gems, no purchases.** The bot never spends gems, never buys anything, and never accepts an offer,
   terms or a consent dialog. Offers and pop-ups are closed only through their X.
2. **Verified spending only.** Gold, elixir or dark elixir are spent only when the cost is read from the
   screen, is affordable, leaves the configured reserve, and the result is checked afterwards.
3. **No blind input.** No tap, key or swipe on a screen the classifier did not confirm. An unknown screen
   is waited on, then the game is restarted; it never gets Back or a guessed tap.
4. **Never fight the player.** When the village is opened on another device the run stops, or waits only
   when the user switched that on.
5. **Nothing is posted for the user** except opt-in features that use the game's own saved text (troop
   requests). The bot never types into chat.
6. **Stop always works.** Every wait ends within one sleep step when Stop is pressed.
7. **Leave the device as it was.** Display size, density, rotation and stay-awake changes on a phone are
   saved first and always restored, also after a crash (`phone-reset`).

## 2. Privacy and network

8. **No network calls** except the opt-in update check (GitHub releases API), the notifications the
   user configures (Discord webhook, Telegram bot) and the Clash of Clans API sync the user starts with
   their own API key (D-035). No telemetry, no analytics, no crash upload.
9. **Send nothing about the user.** Update checks send no user data; alerts send only the alert text; the
   Clash of Clans API sync sends only the player tag, to the API address the user set.
10. **Secrets stay local.** Webhook URLs, bot tokens and API keys live only in the user data folder, are
    never logged, and never appear in error messages.
11. **Reports are private by default.** Failure reports never keep screenshots of other apps or the
    notification shade; exports warn that they may contain the player's village.
12. **No personal data in the repository.** Test screenshots are committed only after
    `scripts/anonymize_fixtures.py` has blurred player, clan and opponent names. No device serials, real
    IP addresses, account names, e-mail addresses or local paths in code, comments, docs or tests (use
    placeholders such as `AB12CD34EF` and `192.168.1.5`).

## 3. Code and content we may use

13. **Clean room.** Never copy code, templates, images or data files from other bots (MyBot, ACBot,
    BasePilot, ...) or from decompiled programs. Other projects may inspire an idea; the implementation is
    written from scratch. Templates are cropped by us from our own screens.
14. **Game data comes from the game.** Unit stats come from the separate
    [clash-of-bots-data](https://github.com/Clash-Tools/clash-of-bots-data) repository, built from the game's
    own files. No scraping of fan sites at run time.
15. **Licence.** The project is GPL-3.0. New dependencies must be GPL-compatible, pinned, and listed in
    [DEPENDENCIES.md](DEPENDENCIES.md) with the reason; ask before adding one.
16. **Not affiliated with Supercell.** The project is non-commercial, never uses Supercell's logos as its
    own branding, and keeps the Terms of Service warning in the README and the first-run wizard.

## 4. Architecture

17. Only `cob/device/` talks to adb, ldconsole or win32.
18. Screen coordinates, regions and thresholds live in data files under `assets/templates/<resolution>/`,
    not in code.
19. Facts about units (kind, housing space, targets) come from the unit database, not from per-unit code
    or card colours, once the database is wired in.
20. Every task ends on a known screen: on failure it returns home and writes a failure report.

## 5. Testing and process

21. **Vision changes ship with a real frame.** A new template, threshold or reader comes with an
    anonymised screenshot fixture and a test on it.
22. **Green before push and merge.** `ruff check` and the full `pytest` suite pass locally (the pre-push
    hook runs both) and in CI before a pull request is merged.
23. **Feature branches and pull requests** for every change; only release commits go straight to `main`
    ([RELEASING.md](RELEASING.md)). Commit messages follow Conventional Commits.
24. **"Verified" means live.** A pull request says whether the change ran on a real device or emulator;
    unit tests alone are "not verified live".
25. **Ask first** before changing packaging, CI secrets, or anything that publishes (releases, tags,
    repository settings).
