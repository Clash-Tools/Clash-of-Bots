# FEATURE-012: Real Android phones over ADB

Goal: farm on a real phone (USB debugging) with the same templates as LDPlayer. Design: D-023.
Also in this branch: deploy points checked against the real red line (D-022 addendum).

`cob/device/phone.py` PhoneDevice (`open_device` picks it for non-emulator serials):
- display mode while running: `wm size` (natural orientation), `wm density 240`, landscape rotation
  lock (Android 16 ignores the game's landscape request at 600 dp wide), screen on while plugged in;
  the phone's own values are saved to `%LOCALAPPDATA%\ClashOfBots\phones\<serial>.json` first and
  restored on stop / next run / `cob phone-reset SERIAL`
- HUD pad: the game keeps its HUD off the rounded screen corners on both sides, so the display is
  widened to 1600 + 2 x corner radius and frames are cropped / taps shifted by the radius
- lock screen: refuses to start with a clear message (`isKeyguardShowing=true`)
- USB drop: the farm loop's recovery waits for the phone (120 s) and turns the display mode back on
- pinch: raw `sendevent` is refused by SELinux on normal phones; on rooted phones (shell granted in
  Magisk / KernelSU) it runs through `su`. Events follow the panel's capabilities (goodix: no pressure
  axis, BTN_TOOL_FINGER + touch size) and its own units / orientation (`pinch_paths`)
- Setup tab: phone checks (connection, display mode, unlocked, Zoom (pinch), game installed)

Phone-only differences found live and handled generically:
| Symptom | Cause | Fix |
|---|---|---|
| game letterboxed in portrait | Android 16 large-screen orientation override | rotation lock |
| every screen UNKNOWN | HUD padded ~70-94 px from both edges | wider display + crop |
| loot OCR lost the first digit | first fit used the cutout (94), the game uses the corners (77) | pad = corner radius |
| no zoom | SELinux denies `sendevent` | `su` on rooted phones |
| boat not found | bubble drawn softer (0.76) | more scales, threshold 0.72 |
| army screen closed as a popup | dialogs ~2 % larger | army templates try 1.02 |
| surrender at "0 %" (real: 89 %) | right HUD +19 px | damage bar anchored to its label |

Live (moto g84 5G, Android 16, rooted, 2026-10-21):
| Run | Result |
|---|---|
| BB farm cycle | collect, 5 + 2 cards deployed, +10.2k gold |
| BB <-> home boat | 2 / 2 round trips |
| Home collect | gold, elixir, dark + loot cart |
| Home farm cycle | 11 cards read, all deployed, battle end at ~91 %, +559k gold +687k elixir |

Wireless + manual restore (feat/phone-wireless):
- `cob/device/wireless.py`: `pair` (adb server `host:pair:<code>:<addr>`, as `adb pair`), `connect`,
  `usb_to_wifi` (`adb tcpip 5555` + the phone's wlan0 IP), remembered addresses (`phones/wireless.json`)
  retried on device refresh and in the farm loop's reconnect
- phone record `phones/<ro.serialno>.json` = {"original": own values, "active": bot mode on}: kept
  after a restore, refreshed at the next start while inactive; Setup "Restore phone screen" and
  `cob phone-reset` restore it with force (also when "active" is already false)

Not done (user's choice): a no-root injector (app_process + InputManager) for phones without root.
Known: USB drops every ~20 min on the test phone (cable / power saving); recovery handles them.
Known (Wi-Fi, once): BB home not seen within 30 s after Return Home, so that attack's loot gain was not
recorded (cycle still counted as done); not reproduced, no frames saved.
Gotcha: LDPlayer's bundled adb (v34) can own the adb server and then lists no phones; use the
platform-tools adb (the release ships it in tools/adb) or set COB_ADB.

QR pairing + network discovery (feat/wireless-qr-mdns, D-025):
- `cob/device/discovery.py`: adb server mDNS (`host:mdns:check`, `host:mdns:services`); services
  `_adb-tls-connect._tcp` ("adb-<serial>-<random>") and `_adb-tls-pairing._tcp`; `nearby()`,
  `auto_connect()` (known phones only), `find_address(serial)`
- `cob/device/qr_pair.py`: QR session (random name/password, 2 min), `pair_and_connect()`
- reconnect: GUI refresh and farm-loop recovery use `reconnect_all()`; a Wi-Fi phone back on a new
  port or under adb's mDNS name is re-bound by hardware serial (`AdbDevice.rebind`)
- GUI Setup > Phone: "Scan QR to pair (Wi-Fi)", "Nearby phones" Find / Connect; CLI `pair-qr`, `discover`
Live (moto g84, Android 16, Linux laptop, adb 37, 2026-10-26):
| Test | Result |
|---|---|
| `cob discover` | phone found as AB12CD34EF at 192.168.1.201 (service name adb-AB12CD34EF-x1Yz9Q) |
| QR pairing (phone had forgotten the laptop) | scanned at ~7 s, paired + connected at 11.6 s |
| Wireless debugging off/on | new port 39957 -> 41949; adb reconnected by itself under the mDNS name |
Found live and fixed: adb auto-connects a freshly paired phone by mDNS name ~1-3 s after pairing, so
connecting by address as well listed the phone twice -> QR flow waits 5 s for adb first; reconnecting
remembered addresses skips phones adb already holds by mDNS name.
Notes: adb's browse is passive: a phone can take a few seconds to show up after Wireless debugging is
turned on. A phone that forgot this PC (empty "Paired devices") is announced but refuses the
connection -> pair again with the QR code.

Wi-Fi fallback (#79, 2026-10-26): mDNS was silent on the network; `wireless.reconnect_by_scan` scans
remembered phone IPs for the new Wireless debugging port. Live: phone back in 14.8 s (two open ports,
the first not adb), offline duplicate dropped, two absent IPs skipped in ~1 s each.

Attack surrender at ~0 % (#78, 2026-10-26): the troop card found no spot near the red line and all units
went to one far corner; the stall rule surrendered after 15 s at 0 % while they were still walking in.
The cycle's "gain" (dark +2,678 from a base with 576 dark) came from collected loot still flying into the
storages during the "before" read. Fixes: no-damage grace of 45 s (fills under 6 px count as no damage),
a snapshot on every stall surrender, own resources read only when two reads 1.5 s apart agree (else no
gain is recorded). Still open: why the troop card could not be placed near the line on that base.
