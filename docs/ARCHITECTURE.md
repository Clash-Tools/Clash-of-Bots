# ARCHITECTURE (accepted 2026-10-18)

Goal: ACBot-style bot (ADB + OpenCV + Tesseract + PySide6), cleaner than both references,
LDPlayer first, Google Play Games later via same interfaces. Ships as Windows exe.

```
            +------------------- GUI (PySide6) -------------------+
            | profiles | task toggles | live view | stats | logs     |
            +-------------------------+----------------------------+
                                      | Qt signals (events only)
                              +-------v--------+
                              |   Scheduler    |  per-profile task queue, cooldowns,
                              |  (worker thr)  |  breaks, stop_event
                              +-------+--------+
                                      | runs
              +-----------------------v------------------------+
              |  Tasks: Farm, Collect, Walls, Upgrade, Army,   |
              |  CCRequest, ClanGames, Events, AccountSwitch   |
              +---+----------------------+---------------------+
                  | uses                 | uses
          +-------v-------+     +--------v---------+
          | ScreenNavigator|<--->| ScreenClassifier |  "which screen am I on?"
          | (go_to(HOME))  |     | + PopupWatcher   |  + recovery
          +-------+--------+     +--------+---------+
                  |                       |
          +-------v-----------------------v---------+
          | Vision: TemplateStore (cached, per-res), |
          | match/match_all/NMS, OCR (tesserocr/pool)|
          +-------------------+----------------------+
                              | frames / taps
          +-------------------v----------------------+
          | Device interface: capture(), tap(),      |
          | swipe(), hold(), key(), app_start/stop() |
          +------+------------------------+----------+
                 |                        |
       LDPlayerDevice (adb)     GooglePlayGamesDevice (later:
       - capture: adb raw        PrintWindow + SendMessage,
         screencap -> scrcpy     ideas from BasePilot)
         stream upgrade
       - input: uiautomator2 / scrcpy control
       - ldconsole: launch, resize, reboot
```

## Modules (package `cob/`)
| Module | Owns |
|---|---|
| `cob/device/` | `Device` protocol + backends (ldplayer, gpg). Only place touching adb/win32. |
| `cob/vision/` | template cache, matching, color checks, OCR wrapper, frame-agreement helpers |
| `cob/screens/` | screen definitions (data: anchors per screen), classifier, navigator, popup recovery |
| `cob/tasks/` | one file per feature; each task = small state machine with timeouts |
| `cob/attack/` | deploy geometry (diamond edges, 1/2/3/4-side), army presets, loot filter |
| `cob/core/` | scheduler, profiles, config (pydantic/dataclass JSON), stats, logging |
| `cob/ui/` | PySide6 window; talks to core only via signals |
| `assets/templates/<res>/` | PNG templates + `screens.yaml` (regions, thresholds) — data not code |

## Trust boundaries
- Input from game = pixels only (untrusted, noisy) -> every read confirmed across frames.
- Local config/profile JSON (user-editable) -> validated + clamped on load.
- Network: update checker only (optional, off by default). No telemetry.

## Fixed-resolution contract
Emulator forced to one resolution (1600x900 @ 240 DPI, landscape — D-006). Templates captured at that
resolution. Bot refuses to start on mismatch and offers to fix via ldconsole.
