# Clash of Bots

Windows farming bot for Clash of Clans on the LDPlayer emulator. It looks at the screen (ADB screenshots
+ OpenCV template matching) and taps like a player would. Windows app with a GUI, plus a command line.

> Using a bot breaks Supercell's Terms of Service and can get an account banned. Use an alt account.
> Clash of Bots is a non-commercial fan project and is not affiliated with, endorsed, sponsored or approved
> by Supercell. Clash of Clans and its names and art belong to Supercell.

## Features
- **Home village farming:** search with a loot filter (gold+elixir / dark elixir, max Nexts), attack along
  the best edge of the base, heroes and abilities, surrender when damage stops growing, return home.
- **Builder Base:** takes the boat over, fights both stages of each battle, collects the daily Star Bonus.
- **Village upkeep (opt-in where it spends or posts):** collect collectors and the loot cart, upgrade the
  cheapest walls with verified spending and a reserve, request clan castle troops.
- **Keeps running:** recognises 25+ screens and popups, recovers from disconnects, closes offers and
  dialogs only via their X, relaunches LDPlayer if it stops, takes random breaks, varies its taps.
- **GUI:** device picker, settings, live view of what the bot sees, stats, cycle history (CSV export),
  setup checks, live log, tray icon.
- **Logs:** one file per session in `%LOCALAPPDATA%\ClashOfBots\logs\sessions\`, plus `cob.log`.

## Requirements
- Windows 10/11, LDPlayer 9 or newer (tested on LDPlayer 14)
- LDPlayer instance at **1600x900, 240 DPI** (the Setup tab can fix this)
- LDPlayer Settings > Other settings > **ADB debugging: local connection**
- Clash of Clans installed and logged in on that instance

**Or a real Android phone** (USB debugging on, plugged in, unlocked, Clash of Clans logged in). While
the bot runs it switches the phone to landscape and a 1600x900-style display at 240 dpi (sized around
the rounded screen corners) and keeps the screen on; everything is put back when it stops. The phone's
own screen settings are saved the first time, so **Setup > Phone > Restore phone screen** (or
`ClashOfBots.exe phone-reset <serial>`) puts them back at any time, e.g. after a crash.

**Over Wi-Fi:** in Setup > Phone either
- Android 11+: on the phone, Developer options > *Wireless debugging* > *Pair device with pairing code*;
  enter that IP:port and the 6-digit code, press **Pair**, then enter the IP:port shown under Wireless
  debugging and press **Connect**; or
- phone on USB: pick it, press **Switch USB phone to Wi-Fi**, unplug the cable.
Connected addresses are remembered; the bot reconnects to them by itself after a Wi-Fi drop.
Zooming out needs **root** on a phone (Android blocks touch-event injection otherwise): grant superuser
to **Shell** (`com.android.shell`) in Magisk or KernelSU. Without root the bot still runs, but cannot
zoom; the Setup tab shows this as "Zoom (pinch)".

## Use
1. Download `ClashOfBots-<version>-win64.zip` from Releases, unzip, run `ClashOfBots.exe`.
2. Setup tab: Run checks, fix anything red.
3. Settings tab: loot filter, breaks, collecting, walls, troop requests.
4. Farm tab: pick the device and mode (Home village / Builder Base), Start farming.

Command line (same exe or `uv run cob` from source):
```
ClashOfBots.exe devices              # adb devices (phones by model) + LDPlayer instances
ClashOfBots.exe farm -s emulator-5554 --cycles 5
ClashOfBots.exe bb -s emulator-5554 --attacks 3
ClashOfBots.exe logs --follow        # watch the running bot's session log
```

## Linux (real Android phone)
On Linux the bot drives a real Android phone over adb (USB debugging on); there is no LDPlayer on Linux.
Download the package for your distro from Releases (x86_64, glibc 2.35+, e.g. Ubuntu 22.04+, Fedora):

```
sudo apt install ./ClashOfBots-<version>-x86_64.deb      # Debian / Ubuntu (pulls in adb)
sudo dnf install ./ClashOfBots-<version>-x86_64.rpm      # Fedora (pulls in android-tools); RHEL needs EPEL
```
Then start **Clash of Bots** from the app menu, or `clashofbots` (alias `cob`) in a terminal; with no
arguments it opens the GUI, otherwise it runs the command line (`clashofbots devices`, `clashofbots farm -s SERIAL`).
Files live in `/opt/clash-of-bots`, settings and logs in `~/.local/share/ClashOfBots/`.

AppImage (any distro, nothing installed): it does not bundle adb, so install it first
(`sudo apt install adb` / `sudo dnf install android-tools`), then:
```
chmod +x ClashOfBots-<version>-x86_64.AppImage
./ClashOfBots-<version>-x86_64.AppImage                  # add --appimage-extract-and-run without FUSE
```

## Settings
Stored in `%LOCALAPPDATA%\ClashOfBots\farm.json` (edited from the Settings tab, clamped on load):

| Setting | Default | Meaning |
|---|---|---|
| min_gold_elixir / min_dark | 800 000 / 8 000 | attack when either is reached |
| max_nexts | 40 | then take the current base |
| min_own_gold | 50 000 | stop searching below this |
| break_every / break_minutes | 8 / 5 | random breaks between cycles (0 = off) |
| collect_minutes | 10 | collect resources (0 = off) |
| wall_upgrades / wall_reserve | 0 / 1 000 000 | walls per cycle (0 = off), resources never spent below the reserve |
| request_minutes | 0 | request clan castle troops (0 = off; posts to clan chat) |

## Development
```
git config core.hooksPath .githooks       # once per clone: ruff + tests run before every push
uv sync --python 3.13 --group build
uv run ruff check .
uv run pytest -q
uv run cob gui
powershell ./scripts/build_windows.ps1   # local Nuitka exe build
./scripts/build_linux.sh                 # Linux: Nuitka build + .deb/.rpm/AppImage (needs nfpm, appimagetool)
```
Read the [hard rules](docs/RULES.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Docs: [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [testing](docs/TESTING.md),
[releasing](docs/RELEASING.md), [roadmap](docs/ROADMAP.md), features in [docs/features](docs/features).

## Licence
[GPL-3.0](LICENSE). Game screenshots in `tests/fixtures` and the templates in `assets/templates` are crops
of Clash of Clans screens, used only so the bot can recognise them; they remain Supercell's.
