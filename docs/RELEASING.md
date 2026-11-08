# RELEASING

## Branch flow (D-012)
1. `git switch -c <type>/<short-name>` from fresh main (`feat/farm-loop`, `fix/ocr-loot`, `chore/...`).
2. Small signed conventional commits (`feat(scope): ...`, body bullets = changelog detail).
3. `git push -u origin <branch>` then `gh pr create --base main`. CI (`ci.yml`, Linux only) runs on the PR.
   Need the exe from a branch? Add label `build-exe` to the PR or run `build-exe` workflow manually.
   Linux packages from a branch: label `build-linux` or run the `build-linux` workflow (never publishes).
4. CI green -> fast-forward merge locally so commit signatures survive:
   `git switch main && git merge --ff-only <branch> && git push origin main` (PR auto-closes as merged),
   then delete the branch (`git push origin --delete <branch>`, `git branch -d <branch>`).
   If main moved: `git rebase main` on the branch first (re-signs commits), force-push branch, re-run CI.

## Versions (D-011)
SemVer 2.0 + channels. Single source: `__version__` in `cob/__init__.py` (pyproject reads it).

| Channel | Example | GitHub release | Meaning |
|---|---|---|---|
| Alpha | `0.2.0-alpha.3` | pre-release | early, features land, may break |
| Beta | `0.2.0-beta.1` | pre-release | feature complete, bug hunting |
| RC | `0.2.0-rc.1` | pre-release | ship-ready unless blocker |
| Stable | `0.2.0` | latest | recommended |

`X.Y.Z-alpha.0` = development, never released.
Bump rules: MAJOR = breaking config/profile format or behavior; MINOR = new features; PATCH = fixes only.
Exe file version (Windows Properties): `X.Y.Z.B`, B = 1000+N alpha, 2000+N beta, 3000+N rc, 9000 stable.

## Cutting a release (on main, clean, synced)
```
uv run python scripts/release.py alpha --dry-run     # preview version + changelog section
uv run python scripts/release.py alpha --push        # bump, CHANGELOG, signed commit + signed tag, push
```
Other channels: `beta`, `rc`, `stable`; new cycle after stable: `alpha --bump minor` (or `major`/`patch`).
Hand-written highlights: put them under `## [Unreleased]` in CHANGELOG.md before cutting; they move
into the release section. The rest is generated from conventional commits since the last tag
(commit body bullets become sub-items, so write good bodies).

The release commit is the one commit made directly on main (it only touches version + changelog).

Tag push runs `release.yml`: verify tag == version + changelog section exists + tests ->
in parallel: Windows Nuitka build + smoke test (`selftest`, `--version` match) and Linux build
(`_build-linux.yml`) -> GitHub release with every file + its `.sha256`, notes from CHANGELOG,
pre-release flag for alpha/beta/rc:

| File | Built by | Smoke test (blocks the release) |
|---|---|---|
| `ClashOfBots-<version>-win64.zip` | `scripts/build_windows.ps1` on windows-latest | on the runner |
| `ClashOfBots-<version>-x86_64.deb` | `scripts/build_linux.sh` (Nuitka + nfpm) on ubuntu-22.04 | installed in `ubuntu:24.04` |
| `ClashOfBots-<version>-x86_64.rpm` | same | installed in `fedora:44` |
| `ClashOfBots-<version>-x86_64.AppImage` | same (appimagetool) | run on ubuntu-24.04 |

Linux smoke (`scripts/smoke_linux.sh`): `--version` match, `selftest` from another folder, no
missing system library for the binary and Qt's xcb plugin, GUI still running after 15 s with
`QT_QPA_PLATFORM=offscreen`. Built on ubuntu-22.04 so it runs on glibc 2.35 or newer.
nfpm, appimagetool and the AppImage runtime are pinned by version + SHA-256 in `_build-linux.yml`.

Linux packages: tree in `/opt/clash-of-bots`, `clashofbots` and `cob` in `/usr/bin`, menu entry +
icon. They depend on the distro adb (`adb` / `android-tools`) and the Qt xcb runtime libraries
(`packaging/linux/nfpm.yaml`). The AppImage does not bundle adb (it must be on PATH) and uses
the GL / xcb libraries every desktop already has. Linux drives a real Android phone over adb:
no LDPlayer on Linux.

## CI cost controls
- Linux-only checks, PRs only, docs-only changes skipped, superseded runs cancelled.
- Windows (2x billed) only on release tags or opt-in (`build-exe` label / manual).
- Linux packages only on release tags or opt-in (`build-linux` label / manual).
- Nuitka compile cache + uv cache between runs.

## Rollback
- Bad release: `gh release edit <tag> --prerelease` or `gh release delete <tag>` (asks first),
  then fix on a branch and cut the next number. Never reuse or move a published tag.
