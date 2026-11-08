# Constraints

The hard rules for every change are in [RULES.md](RULES.md). The short version:

- No gems or purchases; spend resources only with the cost read, affordable and verified afterwards.
- No input on an unrecognised screen.
- No network calls except the opt-in update check, user-configured notifications and the Clash of Clans
  API sync the user starts with their own key.
- No personal data in the repository; test screenshots are anonymised first.
- Never copy code or assets from other bots or decompiled programs.
- Only `cob/device/` talks to adb / ldconsole / win32; coordinates and thresholds live in data files.
- Every change on a branch with a pull request, green CI, Conventional Commits.
