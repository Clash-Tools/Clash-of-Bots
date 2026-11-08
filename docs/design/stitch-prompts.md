# Google Stitch prompts: Clash of Bots desktop + Android

How to use
1. Stitch generates one platform per project. Make two projects: **Desktop** (choose *Web*, frame 1440x900)
   and **Android** (choose *Mobile*).
2. In each project, paste **Part A (design system)** together with that platform's **overview prompt**
   (Part B0 or C0) first. Then paste one screen prompt at a time (B1, B2, ... / C1, C2, ...) and ask
   for the light and dark versions. One screen per message gives much better results than one huge
   prompt.
3. When the screens look right, use the flow prompts in Part D to link them into a clickable prototype.
   Export to Figma or HTML/CSS for us to implement from.
4. Do not upload game screenshots or Supercell art. Every game image in a design is a grey
   placeholder labelled "Game view".

---------------------------------------------------------------------------------------------------

## Part A: design system (paste first in BOTH projects)

```
Design system for "Clash of Bots", a personal automation assistant for a mobile strategy game.
It runs on Windows/Linux desktop and as an Android app. Use Google Material Design 3 (Material You).

Brand
- Name: Clash of Bots. Logo: a simple rounded robot head inside a shield outline, flat, single
  colour. Do NOT use any Supercell or Clash of Clans logo, characters, fonts, buildings or game art.
- Personality: calm, trustworthy, technical but friendly. A safety-first tool, not a "hack" tool.
  No skulls, no neon hacker look.

Colour (Material 3 tonal palettes)
- Seed / primary: deep teal #0F766E. Secondary: slate blue #475569. Tertiary: warm amber #D97706.
- Error #B3261E. Success #1B873F. Warning #B26A00.
- Resource accents, used ONLY for loot numbers and icons: Gold #E0A800 (coin icon),
  Elixir #B847D9 (droplet icon), Dark elixir #4B3A63 (dark droplet icon).
- Both light and dark themes. Dark is the default on desktop. Android follows the system theme and
  supports dynamic colour (Material You), falling back to the teal palette.

Type
- Roboto Flex (Android) / Inter (desktop). Numbers use tabular figures.
- Display 36, Headline 24, Title 18, Body 14, Label 12.

Shape, spacing, motion
- Corner radius 12 for cards, 28 for FABs and big buttons, 8 for chips. 8 dp spacing grid.
- Elevation through tonal surfaces (surface-container levels), not heavy shadows.
- Motion: Material 3 emphasized easing, 200-300 ms. Running state shows a subtle pulsing ring on
  the status indicator.

Components to define
- Status pill: Idle (grey), Connecting (blue), Running (teal, pulsing), On break (amber),
  Paused (slate), Stopped by safety rule (red with a shield icon).
- Stat tile: icon, label, big tabular number, small delta ("+120k this hour").
- Device card: device-type icon (emulator / USB phone / Wi-Fi phone), name, serial, connection
  badge, health dots.
- Check row: label, short explanation, result (OK / Needs fix / Checking spinner), "Fix" button.
- Danger toggle: a switch that opens a confirmation dialog before turning ON (used for anything that
  spends in-game resources).
- Big Start/Stop control: an extended FAB "Start" (teal) that turns into a filled "Stop" (red) while
  running. Stop must always be reachable in one tap.
- Empty, loading (skeleton), error and offline states for every list.

Accessibility
- WCAG AA contrast in both themes, 48 dp minimum touch targets, every icon has a text label or
  tooltip, never colour alone for status (always icon + text).
```

---------------------------------------------------------------------------------------------------

## Part B: Desktop app (Windows / Linux), project type Web, 1440x900, also check 1280x720

### B0. Desktop overview (paste with Part A)
```
Desktop app for "Clash of Bots" using the design system above. Window min size 1280x720, resizable.
Layout: Material 3 navigation rail on the left with these destinations:
Dashboard, Devices, Automation, Safety & schedule, History, Logs, Settings.
Top app bar: app logo + name, the selected device chip (name + status dot, click to switch),
the global status pill, and a small always-visible red "Stop" icon button when running.
A bottom status strip shows: device connection, current step ("Searching for a base...") and
session timer. Generate the Dashboard first.
```

### B1. Dashboard
```
Dashboard screen. Left two thirds: a "Live view" card with a 16:9 grey placeholder labelled
"Game view", an overlay chip at the top-left showing the detected screen ("Home village"), a
"Grab picture" text button and a "last updated 2 s ago" caption. Below it, a horizontal activity
timeline of the current cycle: Collect, Search, Attack, Return home, Break, with the current step
highlighted.
Right third: the run card with a segmented button "Home village | Builder Base", two number fields
"Cycles (0 = unlimited)" and "Time limit (minutes)", and a large extended FAB "Start farming".
Under it, a 2x3 grid of stat tiles: Gold, Elixir, Dark elixir (with resource icons and colours),
Attacks, Cycles, Loot per hour. Under that, a "Last cycle" card (time, loot gained, stars, result)
and a "Safety" card listing active rules as chips: "Breaks every 8 cycles", "Spending: OFF",
"Daily limit 4 h". Show three variants: Idle, Running (Stop button red, pulsing status), and
Stopped by a safety rule (red banner with the reason and a "Review" button).
```

### B2. Devices
```
Devices screen. Sections: "Connected" (device cards), "Found on your network" (phones announcing
wireless debugging nearby, each with a "Paired" or "Not paired" badge and a Connect / Pair button),
"Emulators" (LDPlayer instances with Start and Fix resolution buttons).
Primary button "Add device" opens a dialog with three tabs:
1) "Scan QR (recommended)": a large QR code, a 120-second countdown ring, numbered steps
   ("On your phone: Settings > Developer options > Wireless debugging > Pair device with QR code"),
   and a live status line that goes Waiting for phone -> Pairing -> Connected (with a checkmark).
2) "Pairing code": fields for IP:port and the 6-digit code.
3) "USB": "Plug in your phone and allow USB debugging", then a "Switch this phone to Wi-Fi" button.
Selecting a device opens a right-side detail panel: health check rows (Connection, Screen
resolution / display mode, Phone unlocked, Zoom support (root), Game installed) each with OK or
Fix, plus "Restore phone screen", "Forget device" (destructive, needs confirmation) and an
"Auto-reconnect on this network" switch.
```

### B3. Automation
```
Automation settings screen with a left list of sections and the form on the right:
- Farming: Minimum gold + elixir, Minimum dark elixir, Max "Next" searches, Keep at least X own gold.
- Builder Base: on/off, loot priority (Gold / Elixir / Both).
- Collect: collect resources every N minutes, collect loot cart.
- Clan Castle: request troops every N minutes (note: "Posts a message to clan chat").
- Clan Games (NEW): enable, challenge types to accept as filter chips (Loot, Destroy, Builder Base,
  Hero), skip challenges that need gems.
- Upgrades (NEW, spends resources): walls per cycle, buildings, laboratory, upgrade order
  (cheapest first / priority list), reserve to keep. These use danger toggles and a "Spending"
  warning card.
Number fields show units and valid ranges. A sticky bottom bar appears when there are unsaved
changes: "Unsaved changes - Discard / Save". A "Restore defaults" text button sits at the top right.
```

### B4. Safety & schedule
```
Safety & schedule screen. Cards:
- Breaks: rest after about N cycles, rest length, randomise (on).
- Daily limits: max hours of play per day, max attacks per day, quiet hours (time range picker).
- Stop rules: stop when the device disconnects for more than X minutes, when the village is opened
  on another device, after N failed cycles in a row, on any unknown screen for more than 60 s.
- Spending guardrails (read-only info card with a lock icon): "Never spends gems or real money",
  "Exact cost check before every upgrade", "Keeps your reserve".
- Emergency stop: shows the global hotkey (Ctrl+Shift+S) with a "Change" button.
- Risk notice card: "Automating the game is against its terms of service and can get an account
  banned. Use a test account." with a "Read more" link.
```

### B5. History
```
History screen. Top: date range picker and a mode filter (All / Home village / Builder Base).
Summary row of stat tiles (Total gold, elixir, dark, attacks, hours run, average loot per hour).
A line chart "Loot per hour" (gold, elixir, dark lines in the resource colours) and a bar chart
"Attacks per day". Below, a data table (time, mode, gold, elixir, dark, stars, duration, result)
with sorting, paging and an "Export CSV" button. Empty state: illustration + "No runs yet".
```

### B6. Logs
```
Logs screen: a monospace log view with coloured level tags (INFO, WARN, ERROR), search field,
level filter chips, a "Follow" switch, "Copy", "Open logs folder" and "Save diagnostics (private
data removed)" buttons. Each error line can expand to show the saved snapshot thumbnail.
```

### B7. Settings & About
```
Settings screen: theme (System / Light / Dark), language, start minimised to tray, desktop
notifications (on stop, on error, on break), update channel (Stable / Beta / Alpha) with "Check for
updates", data location with "Open folder", import/export settings. About card: version,
release channel badge, "What's new" (changelog list), licence, "All data stays on this computer".
```

### B8. First-run onboarding (desktop)
```
First-run wizard as a centred dialog with a stepper (5 steps):
1. Welcome: what the app does in two lines.
2. Risk and consent: the terms-of-service / ban risk notice, a checkbox "I understand and will use a
   test account", and Continue (disabled until ticked).
3. Choose your device: three large selectable cards: "LDPlayer emulator", "Android phone (USB)",
   "Android phone (Wi-Fi, scan a QR)".
4. Connect: reuses the matching Add-device content.
5. Health check: check rows running one by one, then "All set" with a "Go to dashboard" button.
```

---------------------------------------------------------------------------------------------------

## Part C: Android app, project type Mobile, 412x915 portrait (also a 600 dp foldable variant)

### C0. Android overview (paste with Part A)
```
Android app for "Clash of Bots" using the design system above, Material 3 with dynamic colour.
The bot runs ON this phone and controls the game on the same phone. Bottom navigation bar with 4
destinations: Home, Automation, History, Settings. Top app bar with the logo, the status pill and an
overflow menu. While running, a persistent notification and a small floating control bubble over
other apps are always visible. Generate the onboarding first.
```

### C1. Onboarding and control method
```
Onboarding flow, one screen per step, with a progress indicator:
1. Welcome: logo, one-line description, "Get started".
2. Risk and consent: the terms-of-service and ban-risk notice, a checkbox
   "I understand and will use a test account", and "All data stays on this phone. We never ask for
   your game login."
3. Choose control method: three selectable cards with badges and pros/cons:
   - "Accessibility (no root)" - badge "Recommended". Pros: works on most phones, zoom by pinch.
     Cons: one extra Android permission step.
   - "Shizuku" - badge "Needs Shizuku app". Pros: precise input. Cons: re-start Shizuku after every
     reboot.
   - "Root" - badge "Rooted phones only". Pros: fastest, full control. Cons: needs Magisk/KernelSU.
   Show "Not available on this phone" disabled states with the reason.
4. Permissions checklist for the chosen method. Each row has an icon, a plain-language reason
   ("Lets the app see the game screen") and a Grant button that turns into a checkmark:
   Screen capture, Accessibility service (with a collapsible guide for Android 13+ "Allow restricted
   settings": App info > three dots > Allow restricted settings), Display over other apps (floating
   control), Notifications, Ignore battery optimisation, and for Shizuku "Shizuku permission" /
   for root "Superuser access".
5. Health check: rows for Game installed, Screen size supported, Permissions, Zoom works,
   then "Ready".
```

### C2. Home
```
Home screen: a large status card at the top (status pill, current step, session timer and a
circular progress ring during breaks). A big extended FAB "Start" that becomes a red "Stop".
Segmented button "Home village | Builder Base". A 2x3 grid of stat tiles (Gold, Elixir, Dark
elixir with resource icons; Attacks, Cycles, Loot per hour). A "Last cycle" card and a "Safety"
card with chips (Breaks ON, Spending OFF, Daily limit 3 h, Battery > 20 %). Show Idle, Running,
On break, and Stopped by safety rule variants.
```

### C3. Floating control and notification
```
Design the floating control used while the game is in front:
- Collapsed: a 48 dp round bubble with the logo and a coloured status ring, draggable to any edge.
- Expanded: a small card with status, current step, Pause/Resume, Stop (red), and "Open app".
- A "bot is controlling your screen" thin coloured border option around the screen.
Also design the persistent foreground notification: title "Clash of Bots - Running", text with the
current step and loot this session, actions "Pause" and "Stop". And a lock-screen-safe variant.
```

### C4. Automation (mobile)
```
Automation screen with collapsible sections (same groups and fields as desktop: Farming, Builder
Base, Collect, Clan Castle, Clan Games, Upgrades). Spending settings use danger toggles that open a
confirmation bottom sheet where the user types "SPEND" to enable. Sticky Save bar when changed.
```

### C5. Safety (mobile)
```
Safety screen: breaks, daily limits, quiet hours, and auto-stop rules specific to phones: stop on
incoming call, on screen lock, below X % battery, when the phone gets hot, when the game shows an
unknown screen for more than 60 s. Emergency stop gesture card: "Press volume down three times
quickly to stop". The read-only spending guardrails card with a lock icon.
```

### C6. Control method & permissions (Settings sub-page)
```
Shows the active control method with a health summary, a list of every permission with its current
state (Granted / Missing / Revoked by the system) and a Fix button, "Switch method", "Run health
check" and "Test tap & pinch" (draws a test pattern). An explanation card: "What the app can and
cannot do: it only taps inside the game while running; it cannot read your messages or other apps;
it stops when you leave the game."
```

### C7. Companion / desktop link (optional mode)
```
"Use with desktop" screen: scan the QR shown by the desktop app to let the desktop bot use this
phone over Wi-Fi without developer options. Camera viewfinder with a QR frame, then a "Connected to
DESKTOP-NAME" confirmation with a trust question "Allow this computer to control the game while the
bot runs?" (Allow once / Always / Deny), and a list of trusted computers with "Remove".
```

### C8. History, Logs, Settings
```
History: summary tiles, a loot-per-hour chart and a list of runs (card per run).
Logs: filterable log list with a "Share diagnostics (private data removed)" action.
Settings: theme (System / Light / Dark / Dynamic colour), language, notifications, update check
(from GitHub releases) with the channel (Stable / Beta / Alpha), export/import settings, data
("All data stays on this phone", Delete all data), About (version, what's new, licences).
```

---------------------------------------------------------------------------------------------------

## Part D: prototype flows (after the screens exist)

```
Link the screens into a clickable prototype:
Desktop flow 1: Onboarding (5 steps) -> Dashboard (Idle) -> Start farming -> Dashboard (Running)
-> Stop -> Dashboard (Idle) with the last cycle filled in.
Desktop flow 2: Devices -> Add device -> Scan QR -> status goes Waiting -> Pairing -> Connected ->
device card appears in "Connected" -> detail panel -> health checks all OK.
Desktop flow 3: Automation -> Upgrades -> turn on a danger toggle -> confirmation dialog -> Save bar.
Android flow 1: Welcome -> Consent -> Choose method (Accessibility) -> Permissions (grant each) ->
Health check -> Home (Idle) -> Start -> Home (Running) + floating bubble + notification -> Stop.
Android flow 2: Settings -> Control method -> a permission shows "Revoked by the system" -> Fix ->
back to Granted.
Use Material 3 transitions (shared axis between steps, container transform from FAB to running
card).
```

## Part E: safety requirements every screen must respect
- One-tap Stop is always visible while running: top bar and FAB on desktop; FAB, notification,
  floating bubble and volume-key gesture on Android.
- The app never asks for a game login, email or password.
- Spending is off by default. Turning it on needs explicit confirmation (typed "SPEND" on Android).
- Every permission is explained in plain words before Android asks for it.
- A visible indicator is shown whenever the bot controls the screen.
- The ToS / ban risk is shown once in onboarding and is reachable from the Safety screen.
- All data is local. Exports and diagnostics remove private data.
