# Stitch screens: implementation spec

Source: Google Stitch projects (downloaded 2026-10-26).

- Desktop: project `6214944815886347243`, 12 screens (one is the logo, one has no screenshot).
- Mobile: project `13326886373149690245`, 22 screens (one is the logo, one is an "interactive prototype suite"; the four "Home - ..." screens are 2560 px tablet/desktop layouts, the rest are 780 px phone layouts = 390 CSS px @2x).

Files: `desktop/<slug>.html|.png|-preview.png`, `mobile/<slug>.html|.png|-preview.png`, logos as `.svg` + `.png`.
All screenshots are rendered at **2x DPR**: a 2560 px PNG is a 1280 CSS px layout. Sizes below are CSS px.

Rendering caveats (do not copy into the Qt UI):
- In every Stitch screenshot the headings fall back to a serif font and the header logo shows its alt text. The intended
  heading font is **Roboto Flex**; the logo is the shield + robot head emblem (`desktop/clash-of-bots-logo.svg`).
- Several labels use made-up telemetry ("SHA-256 9f2e...7d1a", "Heuristic Detection Score 0.02", "Level 3 Hardened",
  "Vulkan API", "PID 14902", "Tesseract-Engine-v5", "OCR FPS 45.2"). They are decoration. The feature table marks them DROP.
- The header in the "Dashboard — Idle State" HTML says `Running`. A script in the page rewrites the header and footer to the
  idle versions, which are documented below. The screenshot shows the idle versions.
- `gshield` (used twice) is not a Material Symbols name and renders as text. Use `shield` or `gpp_good` instead.

---

## 1. Design tokens

Both projects use the same Material 3 dark scheme, generated from seed `#0F766E` (teal). They are **dark only**: `<html class="dark">` on every
screen, and there is no light palette anywhere. The desktop Settings screen shows a disabled "Light" theme button with the
tooltip "Light theme disabled for analytical dark room safety".

### 1.1 Colours (identical in all 33 HTML files)

| Token | Hex | Qt use |
|---|---|---|
| background / surface / surface-dim | `#081425` | QMainWindow / page background |
| surface-container-lowest | `#040E1F` | status strip, video/log wells, inset inputs |
| surface-container-low | `#111C2D` | nav rail, header, secondary cards |
| surface-container | `#152031` | default card |
| surface-container-high | `#1F2A3C` | buttons (tonal), chips, hover, raised rows |
| surface-container-highest / surface-variant | `#2A3548` | text inputs, toasts, menus, kbd keys |
| surface-bright | `#2F3A4C` | pressed / bright surface |
| on-surface / on-background / inverse-surface | `#D8E3FB` | primary text |
| on-surface-variant | `#BDC9C6` | secondary text, inactive nav |
| outline | `#889391` | disabled text, idle dot, axis labels |
| outline-variant | `#3E4947` | dividers (used at 40 % alpha) |
| primary / surface-tint / primary-fixed-dim | `#80D5CB` | accent text, active dots, links, focus |
| on-primary | `#003733` | text on primary |
| primary-container | `#0F766E` | main CTA (Start Farming), selected segment, "Running" pill |
| on-primary-container | `#A3FAEF` | text on primary-container |
| primary-fixed | `#9CF2E8` | |
| on-primary-fixed / on-primary-fixed-variant | `#00201D` / `#00504A` | |
| inverse-primary | `#006A63` | |
| secondary / secondary-fixed-dim | `#B9C7DF` | Dark Elixir numbers, neutral accents |
| on-secondary | `#233144` | |
| secondary-container | `#3C4A5E` | active nav item, selected chip/tab |
| on-secondary-container | `#ABB9D1` | |
| secondary-fixed / on-secondary-fixed / -variant | `#D5E3FC` / `#0D1C2E` / `#3A485B` | |
| tertiary / tertiary-fixed-dim | `#FFB77D` | warnings, "current step" radar icon, break state |
| on-tertiary | `#4D2600` | |
| tertiary-container | `#A15600` | "On Break" badge (35 % alpha) |
| on-tertiary-container | `#FFE6D5` | |
| tertiary-fixed / on-tertiary-fixed / -variant | `#FFDCC3` / `#2F1500` / `#6E3900` | |
| error | `#FFB4AB` | error text, destructive text buttons |
| on-error | `#690005` | |
| error-container | `#93000A` | Kill Switch, STOP buttons, safety-stop banner |
| on-error-container | `#FFDAD6` | text on error-container |
| inverse-on-surface | `#263143` | |

Hard-coded colours used outside the tokens. Add them as semantic tokens:

| Name (proposed) | Hex | Where |
|---|---|---|
| resource-gold | `#E0A800` | Gold icons and numbers (29 uses), "Gold Safe Floor" swatch |
| resource-elixir | `#B847D9` (desktop) / `#D946EF` (mobile) | Elixir icons and numbers. `#E066FF` and `#9333EA` are also used once or twice |
| resource-dark | `#B9C7DF` (= secondary) | Dark Elixir |
| danger-strong | `#B3261E`, pressed `#8F1D16` | mobile "Emergency Stop" FAB |
| success | `#2DD4BF` (one use) or primary `#80D5CB` | "Victory", OK ticks |
| scrim | `rgba(0,0,0,0.6–0.7)` | modal / bottom-sheet backdrops |
| subtle-border | `rgba(255,255,255,0.05)` (`border-white/5`), `0.10` | card borders on Automation Settings |

The existing `cob/ui/theme.py` uses a Discord-like grey palette (`#1E1F22` / `#2B2D31`) with gold accent `#E8B02C`, and
`#D06AD6` for elixir in the stats tiles. All of that is replaced.

### 1.2 Typography

| Token | Desktop font | Mobile font | Size / line height | Weight | Letter spacing |
|---|---|---|---|---|---|
| display-lg | Roboto Flex | Roboto Flex | 36 / 44 | 700 | mobile −0.02em |
| display-lg-mobile | Roboto Flex | Roboto Flex | 28 / 36 | 700 | −0.01em |
| headline-md | Roboto Flex | Roboto Flex | 24 / 32 | 600 | mobile −0.01em |
| headline-sm | Roboto Flex | (n/a) | 20 / 28 | 600 | |
| title-lg | Roboto Flex | Roboto Flex | 18 / 24 | 600 | |
| title-md | Roboto Flex | Roboto Flex | 16 / 24 | 500 | |
| body-lg | Inter | Roboto Flex | desktop 16 / 24, mobile 14 / 20 | 400 | |
| body-md | Inter | (n/a) | 14 / 20 | 400 | |
| body-sm | Inter | (n/a) | 12 / 16 | 400 | |
| label-lg | Inter | Roboto Flex | desktop 14 / 20 (500), mobile 12 / 16 (600, 0.02em) | | |
| label-md | Inter | (n/a) | 12 / 16 | 500 | |
| label-sm | Inter | Roboto Flex | 11 / 16 (desktop 600), 11 / 14 (mobile 500, 0.03em) | | |
| body-code | (Tailwind `font-mono` default stack) | JetBrains Mono | 13 / 18 | 500 | |

- Desktop body font is **Inter** (weights 400/500/600). Headings use **Roboto Flex** (500/600/700).
- Numbers, timestamps, log lines and coordinates use monospace. The desktop pages fall back to the browser's mono stack, so
  use **JetBrains Mono** (400/500/600) on desktop as well for consistency.
- Stat values are monospace and large: running tiles `text-[22px]` to `text-[28px]` mono semibold, history KPIs 36 px Roboto Flex.
- Section eyebrows (for example "AUTOMATION COPILOT", "CYCLES LIMIT") are label-sm, uppercase, letter-spacing ~0.08em, in on-surface-variant
  or primary.
- Material Symbols icon sizes seen: 14, 15 (status strip), 16, 18 (buttons), 20, 22 (nav rail), 24, 28, 48.

### 1.3 Shape, spacing, elevation

| Token | Value | Qt |
|---|---|---|
| radius DEFAULT | 4 px | inputs in dense rows, tags |
| radius md | 6 px (Tailwind default) | segmented items |
| radius lg | 8 px | buttons, inputs, table header ends, log well |
| radius xl | 12 px | **cards** (default), nav items |
| radius 2xl | 16 px (Tailwind default) | Automation Settings sections, modal sheets |
| radius 3xl | 24 px | phone notification mockups |
| radius full | 9999 px | pills, chips, CTA buttons, status pill, avatar |
| CTA button | h 48–56 px, radius 28 px (pill) | Start / Stop farming |
| space-xs / sm / md / lg / xl / xxl | 4 / 8 / 16 / 24 / 32 / 48 px | layout margins |
| margin-desktop | 32 px | main content horizontal padding |
| gutter-desktop | 24 px | grid gap between cards |
| margin / gutter (mobile) | 16 px | |
| Card padding | 16 px (`p-space-md`) or 24 px (`p-space-lg` / `p-6`) | |

Elevation uses Tailwind default shadows on a dark background, so they are subtle:

| Class | CSS | Qt |
|---|---|---|
| shadow-sm | `0 1px 2px rgba(0,0,0,.05)` | none (skip) |
| shadow-md | `0 4px 6px -1px rgba(0,0,0,.1), 0 2px 4px -2px rgba(0,0,0,.1)` | QGraphicsDropShadowEffect blur 8, dy 3, alpha 40 (optional) |
| shadow-xl | `0 20px 25px -5px rgba(0,0,0,.1), 0 8px 10px -6px …` | blur 24, dy 10, alpha 50 (stop buttons, toasts) |
| shadow-2xl | `0 25px 50px -12px rgba(0,0,0,.25)` | modals / wizard |
| custom | `0 4px 16px rgba(15,118,110,.35–.4)` | teal glow under the primary CTA |
| shadow-inner | inset | inset wells (video, inputs): approximate with a darker bg (`#040E1F`) + 1 px top border |

QSS has no `box-shadow`. Show depth through the surface colour steps (lowest → highest), and add
`QGraphicsDropShadowEffect` only on floating elements (toast, modal, unsaved-changes bar). Effects on many cards are slow.

### 1.4 QSS starter (token → stylesheet)

```css
/* page */            QMainWindow, QWidget#page { background:#081425; color:#D8E3FB; font-family:"Inter"; font-size:14px; }
/* nav rail */        QWidget#rail { background:#111C2D; }
/* header */          QWidget#topbar { background:#111C2D; }          /* 90 % alpha + blur in the design */
/* status strip */    QWidget#statusStrip { background:#040E1F; color:#BDC9C6; font-size:11px; }
/* cards */           QFrame[card="true"] { background:#152031; border-radius:12px; }
                      QFrame[card="low"]  { background:#111C2D; border-radius:12px; }
/* headings */        QLabel[role="title"] { font-family:"Roboto Flex"; font-size:18px; font-weight:600; }
                      QLabel[role="eyebrow"] { font-size:11px; font-weight:600; color:#BDC9C6; text-transform:uppercase; }
                      QLabel[role="stat"] { font-family:"JetBrains Mono"; font-size:24px; font-weight:600; }
/* buttons */         QPushButton { background:#1F2A3C; color:#D8E3FB; border:none; border-radius:8px; padding:6px 12px; }
                      QPushButton:hover { background:#2A3548; }
                      QPushButton#primary { background:#0F766E; color:#A3FAEF; border-radius:28px; min-height:52px; font-weight:700; }
                      QPushButton#danger  { background:#93000A; color:#FFDAD6; border-radius:28px; min-height:52px; font-weight:700; }
                      QPushButton:disabled { background:#2A3548; color:#889391; }
/* inputs */          QLineEdit, QSpinBox, QComboBox { background:#2A3548; border:1px solid rgba(255,255,255,0.05); border-radius:8px; padding:8px 12px; font-family:"JetBrains Mono"; }
                      QLineEdit:focus, QSpinBox:focus { border:1px solid #80D5CB; }
/* chips */           QPushButton[chip="true"] { border-radius:9999px; padding:4px 12px; font-size:11px; }
                      QPushButton[chip="true"]:checked { background:#3C4A5E; }
/* table */           QTableView { background:transparent; gridline-color:transparent; alternate-background-color:#111C2D; }
                      QHeaderView::section { background:#1F2A3C; color:#BDC9C6; font-size:11px; font-weight:600; border:none; padding:10px 12px; }
```

---

## 2. Desktop app shell (common to every desktop screen)

Fixed regions. The layout is 1280 CSS px wide and the body has `min-w-[1280px]`. At 1440–1600 px only the main area grows.

| Region | Size | Content |
|---|---|---|
| Top bar | full width × **64 px**, `surface-container-low` @ 90 % + backdrop blur, padding 0 16 px | left: logo (h 32) + "Clash of Bots" (title-lg 600) + 1×20 px divider (`outline-variant`/40) + **device pill** (`surface-container`, radius full, px 12 py 6): 8 px status dot (primary) + "Pixel 7 Pro (USB)" (label-md) + `expand_more` 16 px, clickable → device picker. Right (gap 16): **run-state pill**, **Kill Switch** button, **avatar** (32 px circle, `primary` bg, `person` icon in on-primary) |
| Navigation rail | **96 px** wide, left, between top bar and status strip, `surface-container-low`, py 8 | 7 items, each full-width button, py 8, radius xl. Icon in a 56×32 rounded-full "pill" + label-sm 11 px under it. Active: `secondary-container` bg, `on-surface` text, semibold. Inactive: `on-surface-variant`, hover `surface-container-high` |
| Main | left 96, top 64, bottom 40; padding 32 px horizontal (`margin-desktop`), ~24–32 px top | scrolls vertically |
| Status strip (footer) | full width × **40 px**, `surface-container-lowest` @ 95 %, label-sm, `on-surface-variant` | left: dot + "Connected: ADB over USB (500 Mbps)", `radar` (tertiary) + "Current step: **Searching for a base (Skip #14)...**". Right: `timer` + "Session: **02h 14m 32s**" (mono), `verified_user` (primary) + "Safety Guard Active • 0 resource limits reached" |

Navigation rail items (in order, label → Material Symbol, `data-path`):

| # | Label | Icon | Path | Desktop screen |
|---|---|---|---|---|
| 1 | Dashboard | `dashboard` | dashboard | Dashboard (idle / running / stopped) |
| 2 | Devices | `devices` | devices | **no desktop screen** (only in the prototype suite: "Devices & ADB Wireless Pairing") |
| 3 | Automation | `smart_toy` | automation | Automation Settings |
| 4 | Safety | `shield` | safety-and-schedule | Safety & Schedule |
| 5 | History | `history` | history | History |
| 6 | Logs | `terminal` | logs | Logs |
| 7 | Settings | `settings` | settings | Settings |

Run-state pill and Kill Switch per state:

| State | Pill | Kill Switch | Footer "Current step" | Footer right |
|---|---|---|---|---|
| Idle | `surface-container-high`, 10 px `outline` dot, "IDLE" (label-md semibold, uppercase, tracking-wider) | disabled: `surface-container-high`, `outline` text, opacity 50 %, tooltip "Kill Switch inactive (Bot is idle)" | `hourglass_empty` + "Ready (Awaiting start)" | "Session: 00h 00m 00s", "Safety Guard Active • Spending Locked" |
| Running | `primary-container` / `on-primary-container`, pinging `primary` dot, "RUNNING" | `error-container` / `on-error-container`, `stop_circle` 18 px + "KILL SWITCH", hover `error` / `on-error`, tooltip "Emergency Kill Switch" | `radar` (tertiary) + live step text | live session timer |
| Stopped by safety | same markup as running in the HTML. Use a red "STOPPED" pill (`error-container`) | disabled | last step | frozen timer |

Global key: **Esc** = stop (the "STOP BOT ESC" / "Stop Farming (Esc)" buttons). The Safety screen also shows a global
hotkey **Ctrl + Shift + S**.

---

## 3. Screens

Widths below are given for a 1440 px window (content area 1440 − 96 rail − 64 padding = **1280 px**). The 1600 px
values are in brackets (content **1440 px**). In a 12-column grid with 24 px gaps, one column is 84.7 px [98 px]. So 8 col = **845 px [952]**,
4 col = **411 px [464]**, 7 col = **737 [829]**, 5 col = **519 [587]**, 9 col = **954 [1074]**, 3 col = **302 [342]**.

### D1. Dashboard — Idle State (`desktop/dashboard-idle-state`)

Purpose: the pre-run "Mission Control". Pick the mode and limits, check the device and safety guardrails, press Start.

Layout:
- Page header row: left eyebrow "AUTOMATION COPILOT" (primary) • "Profile: Balanced Farming v2.4"; H1 **"Mission Control"**
  (headline-md). Right: chip `sensors` "Screen feed: Active" + mono "30 FPS"; tonal button `sync` **Recalibrate**.
- Grid 12 col, gap 24: **left col-span-8** (845 px), **right col-span-4** (411 px), both stacked with a 24 px gap.

Left column:
1. **Live Game View** card (`surface-container`, radius xl, shadow-md). Header bar: `videocam` + "Live Game View" + mono
   chip "1920×1080"; right: "last updated 2 s ago" + tonal pill button `photo_camera` **Grab picture**.
   Body: 16:9 dark well (`surface-container-lowest`, ~270–420 px tall) with overlays: top-left glass chip
   "● DETECTED SCENE / Home village"; mono chip `crop_free` "Confidence: 99.4%"; top-right `speed` "Latency: 14ms".
   Empty state centre: 80 px round icon `devices`, "Pixel 7 Pro Screen Stream", "Device mirrored in high-fidelity ADB
   pipeline. Tap "Grab picture" to refresh raw canvas buffer.", chip `check_circle` "Village Coordinates Mapped".
   Bottom corners (mono, faint): "[0,0] Top-Left Root", "Clash Automation SDK Core v4.12", "[1920,1080] Viewport".
   Card footer: "● Touch Injector: Ready", "● OCR Engine: Idle", right mono "Stream Buffer: H.264 60Hz Hardware Acceleration".
2. **Active Cycle Pipeline** card (p 24): `linear_scale` + title; right tag "SEQUENTIAL STATE MACHINE". 5-step horizontal
   stepper (`grid-cols-5`, connector line): 44 px circles with ring-4 of the card colour.
   1 `energy_savings_leaf` "1. Collect" badge **Primed** (primary-container); 2 `travel_explore` "2. Search" Queued;
   3 `swords` "3. Attack" Queued; 4 `cottage` "4. Return" Queued; 5 `coffee` "5. Break" Pending.
   Info row: `info` "Collector clearing will trigger immediately once farming begins." + mono "Cycle heuristic:
   Normal-Human randomized jitter".

Right column:
3. **Run Configuration** card: title + `tune` icon. Segmented control (lowest bg, p 4, radius xl): `home` **Home Village**
   (selected = primary-container) | `construction` **Builder Base**. Two fields side by side: "CYCLES LIMIT" number
   input `0` with suffix "0 = ∞", help "Unlimited continuous"; "TIME LIMIT" `120` suffix "mins", help "2h 00m hard stop".
   Full-width CTA 56 px pill `play_arrow` **START FARMING** (primary-container, teal glow).
4. **Stat tiles** 2×3 grid (gap 12, each `surface-container`, p 14, radius xl): GOLD `monetization_on` (gold) "0"
   "+0 harvested"; ELIXIR `water_drop` (elixir) "0" "+0 harvested"; DARK ELIXIR `opacity` "0" "+0 harvested";
   ATTACKS `swords` "0" "0 won / 0 lost"; CYCLES `autorenew` "0" "Session complete: 0%"; LOOT / HR `trending_up` "0"
   "/ hr" "Awaiting sample run". The icon sits in a 28 px tinted circle at the top right.
5. **Last Completed Cycle** card, tag "HISTORICAL": "Victory (3 Stars)", "Duration: 3m 12s", resource row
   `monetization_on` +340,000, `water_drop` +310,000, `opacity` +1,850; "Army returned intact • Next hero healing: Ready".
6. **Active Safety Guardrails** card: title, mono "3 / 3 OK"; text "Procedural guardrails active to keep user device
   telemetry indistinguishable from organic human interactions."; chips: `coffee` "Breaks every 8 cycles", `lock`
   "Spending: OFF" `check`, `schedule` "Daily limit 4 h".
7. Toast (hidden; bottom): `info` "To begin cycle, connect Pixel 7 Pro with USB debugging confirmed."

States/interactions: Home/Builder toggle (JS `setMode`); Grab picture updates the timestamp to "last updated just now"; Start shows the
toast when no device is connected; Recalibrate.

### D2. Dashboard — Running State (`desktop/dashboard-running-state`)

Same grid (8 / 4).

Left:
1. **Device Surface Mirror** card (shadow-xl): `videocam`, "Device Surface Mirror" + tag "LIVE OCR STREAM", subtitle "Real-time
   pixel feed via ADB Scrcpy pipeline"; right chip "● 30 FPS • 14ms latency", button `photo_camera` **Grab frame**, "2s ago".
   Live frame (16:9, radius xl) with overlays: "● STAGE: SEARCH & MATCHMAKING"; chip `filter_center_focus`
   "Target: G > 350k | E > 350k | DE > 2.5k"; detection box labels "DE TANK #1", "CONF: 98.4%", "3,200 DE DETECTED";
   bottom bar: `autorenew` (tertiary) "Filtering base **#14**: Elixir criteria unmet (210k < 350k)", right mono
   "NEXT SCAN: 1.8s | TOWN HALL: 15 (Rushed)".
2. **Active Loop Sequence**: `linear_scale` title, right mono "Loop iteration: 14 / ∞". Five step cards (`grid-cols-5`,
   each p 12, radius lg, with a 4 px progress bar at the bottom): 01 Collect "Carts & Mines emptied" (done `check`, full
   bar); **ACTIVE** Search "Evaluating skip #14" (raised `surface-container-high`, `sync` icon, 70 % bar); 03 Queued Attack
   "Sneaky Goblin SmartDrop"; 04 Queued Return Home "Auto re-arm & donate"; `bedtime` "In 2 cycles" Rest Break "15m human
   sleep jitter" (tertiary).

Right:
3. **Automation Session**: title + chip `tune` "Adaptive Delay"; segmented Home Village (secondary-container) | Builder
   Base (locked while running); two mini stats "CYCLE COUNT 14 / ∞", "SESSION REMAINING 38m / 120m"; CTA 56 px
   `stop_circle` **STOP FARMING (ESC)** (error-container, radius 28).
4. **Cumulative Yield** `monitoring`, right "Session #089". 2×3 tiles: Gold 2,450,000 "+720k / hr"; Elixir 2,890,000
   "+810k / hr"; Dark Elixir 18,400 "+5,200 / hr"; Attacks 11 "10 won / 1 lost"; Cycles 14 "0 crashes / clean";
   Aggregate Rate `trending_up` **1.53M** "Resources / hr".
5. **Last Cycle Victory** "Cycle #13 • 4m ago": three stars, "100% Destruction • Duration: 2m 14s"; 3 mono chips
   "G: +410k", "E: +380k", "DE: +2.4k".
6. **Active Guardrails** "3 / 3 Active", list rows with trailing `check_circle`: `coffee` "Breaks every 8 cycles" /
   "Break #2 in 2 cycles (approx. 7 min)"; `lock` "Spending: STRICT OFF" / "Zero gems used verified"; `schedule` "Daily
   limit: 4h 00m" / "1h 42m elapsed (42.5%)".

### D3. Dashboard — Stopped by Safety Rule (`desktop/dashboard-stopped-by-safety-rule`)

- Full-width **alert banner** above the grid (`error-container`, radius xl, p 16): `gpp_maybe` (filled) +
  "Automation Halted by Safety Guard" + badge "Tripped"; body "Continuous operation reached the maximum safe daily session
  threshold (4h 00m limit). Humanized rest protocol triggered…". Buttons: **Dismiss & Stand Down** (surface-highest pill),
  `rule_folder` **Review & Adjust Rules** (inverted: on-error-container bg / error-container text).
- Left col-span-8:
  - **Device Viewport Stream** "Pixel 7 Pro (2340x1080)", `history` "halted 45s ago (16:42:10)", **Grab Picture**. The frame
    is dimmed, with a red pill `pan_tool` "Safety Hold • Input Inhibited", watermark "FRAME BUFFER LOCKED", and a centred glass panel
    `timer_off` "Session Threshold Interlock" / "ADB input daemon suspended…" / mono "FPS: 0.0 (PAUSED)",
    "INHIBITOR: GUARD_TIME_LIMIT" / "HUMANIZER COOLDOWN ACTIVE".
  - **Active Operational Pipeline** "Current Stage: Rest & Deliberate Delay": 5 steps, 01–04 with `check_circle` and
    results ("Mines & pumps cleared", "14 bases filtered", "2 Stars (78% yield)", "Troops retrained"); 05 Break in
    error-container `shield` "Mandatory 30m Safety Rest" + pulsing 3 % tertiary bar.
  - **Runtime Interlock Audit Trail** `terminal`, "LOG_REF: #EVT-40912-RL": 5 mono log lines (time, [TAG], message):
    `[CYCLE_28]`, `[TELEMETRY]`, `[INTERLOCK]` (RULE_VIOLATION…), `[HUMANIZER]`, `[DAEMON]`.
- Right col-span-4:
  - **Active Automation Run** "PID 14902": segmented control (disabled), "Cycles Completed 28 / 28 max — Batch complete",
    "Daily Run Limit `lock` 4.0h / 4h — LOCKED"; tertiary box `hourglass_top` "Cooldown Active — 29m 15s mandatory delay
    before next allowed execution."; disabled `play_disabled` **Restart Automation (Locked)**; small error link `warning`
    "Force Safety Override (Confirm PIN)".
  - **Session Totals (Frozen)** `lock_clock`: Gold 4,120,000 (+1.03M/h), Elixir 3,850,000 (+962k/h), Dark Elixir
    26,100 (+6,525/h), Attacks 28 (26W / 2L, 92.8 % Win), Total Cycles 28 "Target Reached", Loot / Hour 1.99M / hr.
  - **Last Completed Cycle** `verified` "Cycle #28 @ 16:42:10", "★★ 2 Stars (78%)", "+490k G / +420k E / +3.1k DE",
    `security` "Troops discharged safely. Clean return to village perimeter."
  - **Guardrail Health Check** (`surface-container-low`) "PASS": key/value rows Triggered Rule "Daily continuous limit
    (>4h)", Device Thermal Sensor "39.4°C (Normal)", Session Tap Count "3,420 randomized inputs", Heuristic Anomalies
    "0 detected"; footer "Humanized Anti-Ban Engine v4.2" / "Defensive Interlock Engaged".

### D4. Dashboard / "Automation Operations" (`desktop/dashboard`, identical HTML in `desktop/clash-of-bots-automation-operations`, no screenshot for the latter)

An alternative, denser **running** dashboard without the 8/4 split:
1. Session header card (`surface-container-low`, p 24, flex row): eyebrow "Active Session • Profile: Gold & Elixir Farm
   (TH13 Default) • Strategy: Smart Barch v3.4.1"; H1 "Automation Operations Center"; sub "Real-time heuristics,
   randomized micro-delays, and continuous telemetry stream for connected device Pixel 7 Pro." Right: 48 px pill
   `stop_circle` **STOP BOT** + kbd "ESC" (error-container); `coffee` **Pause (15m Break)**; 48 px round `shield`
   ("View Safety Logs").
2. **KPI row** `xl:grid-cols-4` (each ~308 px at 1440): Loot Gold `monetization_on` "+820k / hr" **3,840,000** with a
   capacity bar "Target cap: 12,000,000 — 32% filled"; Loot Elixir 4,150,000 (34.5 %); Dark Elixir 28,450 / 180,000
   (15.8 %); Raid Record `military_tech` "12 Raids (91.6% Win)", "+64 Trophies", "11 Wins • 1 Loss", "Avg duration: 2m 18s".
3. Grid `lg:grid-cols-12`: **Target Base OCR & Vision Scanner** (≈8 col: "FPS: 45.2 • RES: 1920x1080", 270 px frame with
   mono detection chips "[CV_MATCH] TH13 Confirmed (98.4%)", "Gold Mine #4: 92% Full", "Elixir Collector #2: 88% Full",
   "Eagle Artillery: Inactive / Unloaded", "Evaluating Match #14 (Skip threshold: Min 450k/450k)", "Heuristic Latency:
   42ms"; then 3 criteria tiles "Min. Gold Threshold ≥ 450,000 `done`", "Min. Elixir Threshold ≥ 450,000 `done`", "Dead Base
   Indicator — Exterior Tombs `verified`") and **Safety Guard & Device Health** (≈4 col: "Level 3 Hardened"; rows `cable` ADB
   Transport Pipeline "USB Direct @ 18ms latency" STABLE; `schedule` Auto-Rest Pacer "02h 14m / 04h 00m" + bar + "Scheduled
   mandatory 30m pause in 1h 46m"; `gesture` Humanized Input Trajectories "Bézier curves + 1.8-3.4s jitter"; `device_thermostat`
   Battery & SoC Thermals "Battery: 38.2°C • CPU Load: 14%" OPTIMAL; `lock_reset` Resource Spending Lock "Zero Gem/Magic
   Item use enforced"; footer "Safety Engine SHA-256: 9f2e...7d1a", link "Guardrail Policy").
4. **Recent Raid Operations** `history_edu`, "Session Raids: 12", buttons `filter_list` "Filter 3-Stars", `file_download`
   "Export CSV". Table columns: Timestamp | Opponent / Base Type | Gold Looted | Elixir Looted | Dark Elixir | Outcome |
   Duration | Execution Intelligence. Demo rows: 14:28:10 VikingRaider_88 "TH13 Dead" +512,400 +540,800 +3,900 `star` "3 Stars
   (100%)" 2m 14s "Perimeter collector sweep with Barbarian distraction wall"; 14:12:45 ShadowClaw "TH12 Farm" … "2 Stars
   (74%)"; 13:54:02 ApexTitan_X "TH13 Ring" … 3 Stars; 13:38:19 GhostTown_21 "TH12 Max" `close` "0 Stars (42%)". Footer
   "Showing last 4 of 12 logged battles in active session", Previous (disabled) / Next.

Recommendation: take the KPI row and the raid table from D4 and use the D1/D2/D3 8/4 grid as the dashboard.

### D5. Automation Settings (`desktop/automation-settings`, very tall: 2936 CSS px)

Header: eyebrow "AUTOMATION ENGINE • RULES & LOGIC", H1 "Automation Settings", sub "Configure attack heuristics,
resource collection thresholds, building upgrades, and safety guard limits." Right: ghost `restart_alt` **Restore
defaults**; profile selector card `tune` "ACTIVE PROFILE / Balanced Farming v2.4" + tag "Custom" + `unfold_more`.

Grid: **left col-span-3 (302 px) sticky category list** + **right col-span-9 (954 px) sections**, gap 24.

Category list (`surface-container-low`, radius 2xl, p 10; title "Rule Categories"). Each row has an icon, title and subtitle, and
anchor-scrolls to its section: `swords` Farming "Attack thresholds & search" [Configured]; `construction` Builder Base "Auto
attacks & clock tower"; `paid` Resource Collectors "Mines, pumps & cart"; `shield_person` Clan Castle "Troop request
scheduling"; `military_tech` Clan Games [NEW] "Challenge filters"; `upgrade` Auto-Upgrades [NEW] "Walls & lab upgrades";
`psychology` Scripting & Delays "Bézier curves & jitter".

Sections (each `surface-container`, radius 2xl, p 24, header = 40 px icon tile + title + subtitle; right side = status tag
or toggle):
1. `radar` **Farming Heuristics**: "Set algorithmic target search criteria…", tag "4 Rules Configured". 2-col fields
   (label + range hint + mono input with suffix + help):
   "Minimum Gold + Elixir [Combined] [100k – 2,000k]" `450` "k / raid": "Will skip bases unless total recoverable resources
   exceed this sum."; "Minimum Dark Elixir [DE] [0 – 10,000]" `3,500` "DE": "Secondary filter…"; "Max 'Next' Searches
   [5 – 150]" `45` "skips" `info` "Prevents gold burn when bases are scarce in current league."; "Keep At Least X Own Gold
   [50k – 5,000k]" `1,000` "k gold": "Ensures safety reserve buffer for next-search search fees."
2. `cabin` **Builder Base** (header toggle ON): "Loot Priority Selection" 3-way segmented Gold | Elixir | **Both
   (Balanced)**; toggle row "Clock Tower Boost — Automatically fires boost when free charge is off cooldown." ON.
3. `savings` **Collectors & Loot Cart**: "Collect resources every N minutes [5 – 180]" `20` mins ("Clicks all active Gold
   Mines, Elixir Collectors, and Dark Drills."); toggles "Auto-collect Loot Cart on detection" ON, "Check Clan Castle
   Treasury" ON.
4. `fort` **Clan Castle Requests**: "Request troops every N minutes [10 – 120]" `15` mins ("Respects clan donation cooldown
   timers automatically."); info box "Chat String Automation — Posts a natural message to clan chat: "Any ground troops /
   siege machine for farming. Thanks!" — Dispatches with non-deterministic typing speed jitter (45–120 WPM equivalent)."
5. `military_tech` **Clan Games Automation** [NEW] (header toggle ON): "Eligible Challenge Categories to Accept" as
   toggle chips: Loot / Raiding ✓, Destroy Buildings ✓, Builder Base Raids ✓, Hero Tasks ✓, Star Collection, Spell
   Casting; toggle "Skip challenges that require Gems or Super Troops" ON.
6. `upgrade` **Auto-Upgrades Engine** tag "SPENDS LOOT", right `lock` "Safety Guard Active". Warning box `warning`
   "Spending Guard Active — Upgrades directly spend your in-game resources…". 3 module cards: `fence` Auto-Upgrade Walls ON
   + "Max walls per run: `2` wall(s)"; `apartment` Village Buildings OFF "Disabled. Builders will remain idle until turned
   on."; `science` Laboratory Research ON. "Upgrade Priority Strategy" segmented `sell` **Cheapest First** |
   `format_list_numbered` Priority Custom List | `speed` Shortest Time First. "Resource Reserves to Keep (Safety Minimums)":
   Gold Safe Floor `2,000,000`, Elixir Safe Floor `2,000,000`, Dark Elixir Floor `50,000`.
7. `fingerprint` **Humanized Bézier Jitter & Pauses** tag "Active": read-only tiles "Bézier Swipe Deviation ±14.8px",
   "Session Break Jitter 5–12 min".
8. Floating **unsaved-changes bar** (bottom centre, max-w 4xl, `surface-container-highest`/95, radius 2xl, shadow-2xl):
   "Unsaved configuration changes detected — Modified fields in **Farming Heuristics** and **Auto-Upgrades**", **Discard**,
   `check` **Save Changes** (primary-container).

### D6. Safety & Schedule (`desktop/safety-and-schedule`)

Header: `security` eyebrow "Safety Engine • Policy & Schedule" + tag "Guards Active"; H1 "Safety & Schedule"; sub
"Configure humanized break intervals, operational limits, fail-safe disconnect triggers, and protective spending
guardrails."; right card `verified_user` "Security Preset — Level 3 Hardened (Recommended)", button `restart_alt`
**Restore Safety Defaults**.

Grid: **left col-span-7 (737 px)** + **right aside col-span-5 (519 px)**.

Left (`surface-container-low` cards):
1. `bedtime` **Humanized Breaks & Pacing**, tag "Jitter Engine Active": "Rest after about N cycles (Range 3–25)" `8`
   cycles; "Rest length (Range 10–90 min)" `25` minutes per session; toggle "Randomise rest timing & duration — Adds ±15%
   gaussian jitter…" ON; info strip `gesture` "Touch Curve & Drag Latency: 1.8s – 3.4s — Bézier Spline Interpolation Active".
2. `timelapse` **Daily Operating Limits**, tag "Resets at 00:00 UTC": "Max hours of play per day (1.0 – 8.0 h)" `4.0`
   + progress "Today's Accumulated 02h 14m / 04h 00m — 56% of daily quota exhausted"; "Max attacks per day (10 – 80)" `35`
   + progress "Attacks Dispatched 14 of 35 — 21 attacks remaining today"; sub-card `nights_stay` **Quiet Hours (Sleep
   Window)** toggle ON, text, "Sleep From `23:00` to Wake At `07:00`", `schedule` "Duration: 8.0h silent period".
3. `power_settings_new` **Automatic Stop Rules & Fail-Safes**, tag "4 Rules Armed". Rows (icon, title, description,
   control): `wifi_off` Disconnect Timeout "Stop after `3` min"; `devices` Multi-Session Collision toggle ON;
   `error` Consecutive Failures "Stop after `2` cycles"; `visibility_off` Unknown Screen Watchdog toggle ON ("…for more
   than 60s. Captures diagnostic screenshot…").

Right:
4. `lock` **Spending Guardrails** "Core Engine Firmware Invariants", tag "Hard-Lock • Read-Only". Three `verified` rows:
   "Never spends gems or real currency", "Exact cost verification before upgrade", "Strict safety reserve maintenance
   (Gold 500k, Elixir 500k, DE 10k)"; footer `gavel` "Cryptographically validated against tampering (v4.18.2 firmware)".
5. `keyboard` **Global Emergency Stop** "System-wide input override", tag "Active Hook": kbd keys **Ctrl** + **Shift** +
   **S** (S in error-container); **Change Keybind**; text "Instantly terminates all ADB touch injection…even when the
   application window is minimized…".
6. `warning` **Important Account Safety Notice**: ToS text, link "Read Safe Automation Guidelines →"; footer "Heuristic
   Detection Score 0.02 / 1.00 — Undetectable".

### D7. History (`desktop/history`)

Header: H1 "History & Analytics" + tag "● Live Sync Active"; sub "Review operational raid logs, farming efficiency trends,
and resource yields over time." Right: date range button `calendar_month` "Oct 18, 2024 – Oct 25, 2024" + tag "Last 7
Days" `expand_more`; segmented **All** | Home Village | Builder Base; `file_download` **Export All**.

1. **KPI row** `xl:grid-cols-6` (≈193 px each at 1440): TOTAL GOLD `monetization_on` **48.25M** `trending_up` "+6.4M vs
   prev. 7d"; TOTAL ELIXIR `water_drop` 52.80M "+7.1M"; DARK ELIXIR `science` 342.6K "+48K"; TOTAL ATTACKS `swords` 184
   "172 Wins (93.5% Win)"; UPTIME RUN `timelapse` 36.5 h "~5.2h / day • Safe"; AVG YIELD / HR `speed` 2.76M "Gold + Elixir
   blended".
2. Charts row `lg:grid-cols-12`: **Loot Yield Velocity** (col-span-7, 737 px) legend Gold (orange) / Elixir (light) /
   Dark Elixir (x100) (teal dashed), area + line chart over 24 h (x 00:00–23:00, y 0–2.0M), hover tooltip "PEAK @ 14:00 G:
   850k / hr, E: 920k / hr, DE: 6.4k / hr"; footer `insights` "Top farming surge: 12:00 – 16:00…", "Resolution: 1hr bins".
   **Attacks vs Safety Cap** (col-span-5, 519 px) `shield`, tag "Safe Threshold", sub "Strict maximum cap of 35 raids /
   day…": bar chart Mon–Today (26, 31, 28, 34, 18, 30, 17*), dashed cap line "CAP: 35 RAIDS / DAY", today bar lighter;
   legend Victories (93.5%) / Trophy Dumps (6.5%), "0 Over-cap warnings".
3. **Raid Operations Log** card: `format_list_bulleted` title + chip "184 attacks recorded"; search field `search`
   placeholder **"Search target, mode, strategy..."**; `filter_list` Filters; `download` **Export CSV** (primary-container);
   dev-only "Simulate 0 Results". Table columns: TIMESTAMP (`arrow_downward` sort) | VILLAGE / TARGET (tag "Home • TH13" +
   strategy "Sneaky Goblin") | GOLD YIELD | ELIXIR YIELD | DARK ELIXIR | STARS & DMG ("★★★ 100%") | DURATION | OPERATION
   RESULT (chips: `military_tech` Victory (3★), `done` Victory (2★), `star` Stage Cleared, `flag` Trophy Drop (-24)).
   Six demo rows (14:28:10 … 12:18:22). Empty state: "No raid runs recorded for this criteria" + **Reset Filter &
   Search** + **Go to Dashboard**. Footer: "Showing 1 – 6 of 184 raids", "Rows per page: [10 | 25 | 50]", "Page 1 of 19",
   `chevron_left` / `chevron_right`.

### D8. Logs (`desktop/logs`)

1. Header card (`surface-container-low`): "System & Operational Logs" + tag "Live Ingestion"; meta "Session #089 •
   `schedule` Running 02h 14m 32s • Host: daemon-worker-linux-x86_64 • PID 18492". Buttons `content_copy` **Copy
   Visible**, `folder_open` **Open Folder**, `verified_user` **Save Sanitized Diagnostics** (primary) with hover tooltip "Zero-Leak
   Guardrail — Player tokens, Google Play credentials, MACs, and device UDIDs are stripped automatically via regex
   scrubbing."
2. Filter row: search input `search` placeholder **"Filter logs by keyword, tag, or regex... [Ctrl+F]"**; level chips with
   counts: **ALL 342** (selected), INFO 298, WARN 32, ERROR 12 (error tint), DEBUG 0 (disabled); checkbox
   `vertical_align_bottom` "Follow tail" (checked).
3. Terminal well (`surface-container-lowest`, radius xl, shadow-2xl, mono): title bar "runtime.stdout.ipc — /dev/pts/3",
   "Encoding: UTF-8 • `sensors` Pipeline Stream Stable (30 FPS)". Lines: line number | time `14:20:45.008` | level badge
   (INFO / WARN / ERROR) | `[Module.Tag]` | message with highlighted values. **ERROR rows expand** into a detail card:
   288 px screenshot thumbnail ("2340×1080 • 14:21:04", `zoom_in` Full Image), "Failure Cause", "Interlock Action",
   pipeline info, buttons `bug_report` **Submit Diagnostic Dump** / **Ignore Overlay Pattern**. A second error shows a 3-tile
   metrics grid (DEVICE THERMAL 39.8°C, INJECTION DELAY 284ms, FAILSAFE STATE RECOVERED) + "Auto-Resolved".
4. Footer: `list_alt` "Showing 342 lines (Filtered from 1,420 lines) • Buffer: 4.2 MB • clash_bot_2024-10-25.log";
   checkbox "Wrap lines"; `delete_sweep` **Clear View**.

### D9. Settings (`desktop/settings`)

Header: eyebrow `tune` "Runtime Environment & Host Orchestration", H1 "Preferences", sub; right chips "Daemon: PID 19824",
`lock` "Local Memory Only". Grid **7 / 5**.

Left:
1. `palette` **Appearance & Localization** tag "v4.18-UI": "Interface Color Theme" 3-way (`brightness_auto` Auto |
   `light_mode` Light (disabled, opacity 60) | `dark_mode` **OLED Dark**); "Application Language" select: English (United
   States) [en-US], Deutsch [de-DE], Español [es-419], Français [fr-FR], 中文 [zh-CN], 日本語 [ja-JP];
   `verified` "100% string localization verified".
2. `terminal` **System Integration & Dispatcher**, button `send_time_extension` **Test Dispatch**: toggles "Start Minimized
   to System Tray" ON, "Launch on Operating System Startup" OFF ("Register systemd unit or Windows Run registry entry…");
   sub-card `notifications_active` "Telemetry Notification Rules — 3 of 3 Active": checkboxes Safety Guard Stop ("Tripwire
   halts bot"), Vision Anomaly ("OCR match fails"), Rest Periods ("Humanized breaks").
3. `folder_data` **Data & Local Persistence**, tag "142.4 MB Used": "Application Working Storage Directory" `dns`
   "~/.clash-of-bots/data/profiles/default/" + `open_in_new` **Open Folder**; usage bar legend Vision Models (84 MB) / ADB
   Screencaps (42 MB) / Execution Logs (16.4 MB); `file_download` **Export Config (.json)**, `file_upload` **Import
   Config**; error text button `restart_alt` **Reset to Factory Defaults**.

Right:
4. `system_update_alt` **Release Channel** tag "Up to date": segmented `verified` **Stable** | Beta | Nightly; info "Stable
   Track: Recommended for daily resource accumulation…"; "v4.18.2-stable (x86_64)", "Last polled 15 minutes ago";
   `sync` **Check Now**.
5. **Zero-Cloud Privacy Guarantee** (gradient card) `enhanced_encryption` "100% Local Sandboxed Execution", text, mono ticks
   "In-memory OCR only", "Zero outbound metrics".
6. **About**: logo, "Clash of Bots" + tag STABLE, "Build 2024.11-rc4 • Revision a8f09d2"; "Release Changelog Notes" + link
   "View GitHub Commits →"; 3 entries (v4.18.2 Today, v4.18.1 4 days ago, v4.18.0 Nov 12); "Licensed under GNU GPLv3",
   links Documentation • Safety Advisory.
7. Toast `notifications` "System Dispatcher Active — OS toast notifications successfully registered".

### D10. First-Run Setup Wizard (`desktop/first-run-setup-wizard`)

Modal over a dimmed dashboard (scrim `surface-container-lowest`/80). Dialog **max-w 860 px**, `surface-container-low`,
radius xl, shadow-2xl.
- Header: `security` (filled) "Initial Setup & Device Bridge" + tag "v3.4.2", sub "High-reliability local automation
  pipeline provisioning"; right chip `lock` "100% Offline Engine".
- Stepper `grid-cols-5` (clickable): 1. Welcome ✓, 2. Risk Notice ✓, 3. Target ✓, 4. Handshake ✓, 5. Diagnostics (current).
  The HTML contains all 5 step sections:
  1. **Welcome**: `terminal` "Deterministic Automation Engine", H "Your Autonomous Strategy Co-Pilot", paragraph, 3 feature
     cards: `shield` "100% Local & Sandboxed", `psychology` "Anti-Detection Jitter", `analytics` "Smart Resource Farming".
  2. **Risk Notice**: `gavel` "Legal & Safe Usage Mandate", "Terms of Service & Account Safety Notice", warning box
     "Third-Party Platform Disclaimers…", 2 tiles (`verified` local kill switch, `timer` forced rest breaks), required
     checkbox "I acknowledge the platform risks, take full responsibility for my accounts, and will execute initial runs
     on secondary test villages."
  3. **Target**: "Select Target Execution Environment" — 3 radio cards: `desktop_windows` **LDPlayer 9 / BlueStacks**
     [Recommended] "127.0.0.1:5555" (selected, ring-2 primary); `usb` **Android Phone (USB)** [Lowest Latency] "Pixel 7 Pro
     (ADB)"; `wifi_tethering` **Android Phone (Wi-Fi)** [Wireless] "Pair wirelessly via QR code…" "192.168.1.144:42311".
  4. **Handshake**: "Active Handshake & Authorization": device card `phone_android` "Google Pixel 7 Pro (Panther)" "Serial:
     28161FDH30043J • Android 14 (API 34)" [Authorized]; 3 tiles Negotiated Transport "USB 3.2 (500 Mbps)", Screen Mirror
     Native "2340 x 1080 @ 60 FPS", ADB Touch Injection `check_circle` Ready; button `touch_app` "Send Test Ping (1.2ms)".
  5. **Diagnostics**: "System Pre-Flight Health Check", `refresh` "All 4/4 Checks Passed"; rows `hub` Local ADB Daemon &
     Subprocess Bridge (Operational), `photo_camera` OpenCV Vision & Template Matcher, `stream` Screen Mirror Frame Buffer,
     `emergency_home` Safety Interlocks & Emergency Kill-switch "Global hotkey armed: Ctrl + Shift + S" (Armed);
     `verified_user` "Device & Sandbox ready. No manual driver installation required." + "Ready to Run".
- Footer: `arrow_back` Previous Step | Exit Wizard | `arrow_forward` **Go to Dashboard** (primary, pill).

### D11. Logo (`desktop/clash-of-bots-logo.svg` 512², png 1024²)

Flat teal (`#0F766E`) shield outline with a robot head. Use it for the app icon (replaces the runtime-drawn
`theme.app_icon()`), the top bar and About.

### D12. Desktop flows only in the prototype suite (`mobile/clash-of-bots-interactive-prototype-suite`)

The prototype suite has a desktop sidebar (Home Dashboard `grid_view`, Automation Rules `precision_manufacturing`,
Devices & Pairing `devices` [badge 1], Battle Telemetry `timeline`, Safety Guardrails `shield_lock`, Setup Wizard `rocket_launch`)
and documents three desktop flows:
- "Desktop 1: Onboarding → Idle → Running → Stop (Cycle Recorded)"
- "Desktop 2: Devices → Add Device → Scan QR → Pairing → Connected": **Devices & ADB Wireless Pairing** "Manage physical and
  wireless Android endpoints…", `add_circle` **Add Device (Scan QR)**, device card `phone_android` "Google Pixel 8
  192.168.1.104:5555 • Android 14" [Connected] with Accessibility ✓ OK, Latency 18 ms, Battery 88% (Charging), Display
  1080p Calibrated, "Paired via Wi-Fi ADB", **Inspect Telemetry**; pairing dialog `qr_code_scanner` "Pair Wireless Device"
  "Protocol: Wireless ADB over TLS" "Awaiting Scan...". **This is the only spec for the "Devices" rail item.**
- "Desktop 3: Automation → Danger Upgrades → Danger Auth Bottom Sheet → Save": toggle "Auto-Spend Gems for Instant Lab
  Finish" [DANGER ZONE] → modal "Confirm Gem Spending — IRREVERSIBLE BOT PERMISSION … type SPEND" → **Authorize Gem
  Spend**. (Conflicts with the hard "never spends gems" rule: do not build.)

---

### Mobile (Android companion) screens

Mobile token differences: Roboto Flex everywhere (no Inter) and JetBrains Mono for code. Bottom nav bar (fixed,
`surface-container-high`/90): Home `dashboard`|`home`, Automation `smart_toy`, History `history`, Settings `settings`
(the Safety screen swaps History for Safety `shield`). Active item: `primary` text, or a pill `primary-container`/30. Top app bar:
logo + "Clash of Bots" + screen subtitle + overflow `more_vert` + avatar. Wizard screens have a fixed bottom bar (Back |
Continue `arrow_forward`). The four **Home** screens are 1280 CSS px tablet layouts with a 256 px left drawer (Home `grid_view`,
Automation `smart_toy`, History `timeline`, Devices `devices`, Safety Rules `shield_lock`, Settings `settings`; footer card
"Runtime Engine — Daemon v2.4.1", "Status: Idle", `wifi` "Wi-Fi Android (192.168.1.104)").

None of the mobile screens can be built in this repo: **there is no Android app**. The bot drives the phone from
the PC over ADB. They are listed so the desktop can borrow states and texts, and for a later Android companion.

| # | Screen (slug) | Purpose / content |
|---|---|---|
| M1 | Home - Idle State (`home-idle-state`) | Breadcrumb "Dashboard › Home Overview" + "ADB-NET #4029"; state-preview tabs Idle / Running / On Break / Safety Stop; hero card "Bot is Standby" with connected device "Pixel 8 Pro — USB ADB (120ms latency)", tiles "Current Sequence: No active sequence — Next: Attack & Collect", "Active Runtime: Session 00:00:00 (Idle)"; big pill `play_arrow` **Start Automation** "Single tap launch • All 4 safety guardrails armed"; "Village Target:" segmented `cottage` Home Village / `construction` Builder Base; 6 stat tiles (Gold Collected, Elixir Collected, Dark Elixir, Attacks Completed "Target: Min 400k loot", Cycles Run "Average 14m/cycle", Loot per Hour "— / hr"); **Last Automation Cycle** (42m ago, 12m 14s, Success, +28 trophies, "Shield state: Expired"); **Safety & Guardrails 4/4** (Breaks ON "15m every 2h", Spending OFF, Daily limit 3 h "1h 14m used today", `battery_charging_full` Battery > 20 % "84% plugged"), link "Configure safety rules →" |
| M2 | Home - Running State | Status "Running" + `schedule` 01:24:38 + `coffee` "Next break in: 35m 22s"; "Automating: Home Village Routine", "Targeting Town Hall 14+ Dead Bases with >450k Gold/Elixir"; `radar` "Step 4 of 7: Deploying Barchers (Wave 2) on South-East Perimeter..." "[Detection: Clear, 0 delays]"; red FAB `stop` **Emergency Stop** "HALTS EXECUTION INSTANTLY" (`#B3261E`); tiles with "+460k this hour" etc., Loot per Hour 1.33M "+12% above daily target"; **Last Cycle Telemetry** "Attack #6", "Search took 4 skips", "Troop Training Queued 74% Ready (~1m 40s)", "Troop comp: BArch Lv9", button "View Detailed Battle Logs"; Safety tiles incl. "Device Battery 78% (Charging)"; "All 8 pre-flight safety assertions passed"; "Edit Guardrails" |
| M3 | Home - On Break State | Badge `coffee` **On Break** (tertiary-container/35) "Safety Trigger #B-04", H "Mandatory Safety Break in Progress", "Scheduled resume at 15:45:00"; **circular countdown ring** "Remaining 05:18 of 15:00 min total", "65% Elapsed • Anti-pattern interval: 14m 42s"; buttons `stop_circle` **Cancel Automation**, `warning` **Skip Break (Not recommended)** → dialog "Bypass Safety Break?" **Keep Resting** / **Force Resume** (tertiary); tiles with "Capacity: 73%"; Last Cycle Summary; guardrails "Break 2 of 3 today" |
| M4 | Home - Stopped by Safety Rule State | Disabled `lock` **Start Bot (Locked)**; gradient hero `security` "Stopped by safety rule", "Tripped at 16:04:12 UTC", H "Automation Halted: Low Battery Safety Threshold Tripped", reason card `shield_lock` "Battery Level Protection — Triggered — Minimum 20% charge required. Phone reported 18% (Discharging)", Device State `battery_alert` 18 %, `power` "Plug in charger to clear safety lock…", buttons `receipt_long` **View Safety Log**, `restart_alt` **Acknowledge & Reset**; "Frozen Session Snapshot Run #1402"; tiles with `ac_unit` "Session frozen"; **Last Cycle Execution** mini log with status tags OK / SUCCESS / DONE / GUARD_TRIP / CLEAN_EXIT; guardrail rows with the tripped one in error-container "TRIPPED" |
| M5 | Onboarding 1: Welcome | 144 px round logo, chip `verified_user` "Personal Automation Assistant", H "Clash of Bots", 3 feature rows (`devices` 100% On-Device, `shield_with_heart` Safety-First Engine, `lock_reset` No Game Credentials Needed), "Build 2.4.0 • Android 11+ Ready", Back / Continue |
| M6 | Onboarding 2: Risk and Consent | "Step 2 of 5 — Safety Verification"; `gpp_maybe` "Important Ban-Risk Notice" [Advisory] (Supercell ToS), tiles Secondary Account Recommendation / Humanized Jitter & Sleep Cycles (`neurology`); `security` "100% Device-Isolated Sandbox"; link `menu_book` "Safety Architecture Whitepaper & Terms"; consent checkbox "I understand the risks and confirm I will use a test account."; `close` **Decline & Exit Setup** |
| M7 | Onboarding 3: Choose Control Method | radio cards: `accessibility_new` **Accessibility** "Standard mode (no root)" [Recommended] (✓ Works on most Android phones, Pinch-to-zoom supported natively, No computer or unlocked bootloader needed; `info` Restricted Settings step); `terminal` **Shizuku** "ADB-level bridge" (needs re-start after reboot); `lock` **Root** disabled "Not available on this phone — No su binary detected"; **Next: Permissions** |
| M8 | Onboarding 4: Permissions Checklist | "STEP 4 OF 5" 80 %; rows with Granted / **Grant** buttons: Screen capture (MediaProjection), Accessibility service (+ "Android 13+ Restricted Settings Guide" 4 numbered steps, **Open App Info**), Display over other apps, Notifications, Ignore battery optimisation; "3 of 5 permissions configured • 2 pending actions"; **Next: Health Check** |
| M9 | Onboarding 5: Health Check & Ready | progress bar 100 %; card `verified` "Ready to Automate — Passed" (Mode: Accessibility, Protection: Safe Limits ON, Auto-Stop: 4 hrs); "System Diagnostics 4 of 4 Verified": `sports_esports` Game installed "com.supercell.clashofclans found (v16.800.2)", `aspect_ratio` Screen size supported "1080 x 2400 (20:9), 420 DPI", `security` Permissions, `pinch` Zoom works (+ `replay` test); `rocket_launch` **Enter Dashboard**; `science` "Run dry-run simulation" |
| M10 | Onboarding - Permissions & Setup | alternative 3-step onboarding: "Step 1 of 3: System Diagnostics 2 / 4 Ready"; cards Accessibility Service (Configured), Floating Overlay Bubble (Action Needed → **Grant Access**), Unrestricted Background "Doze Mode Whitelist" (**Whitelist App**), Persistent Notification; "Safety & Fair Play Engine — Active"; **Continue to Game Setup**, "Skip & configure manually in Settings" |
| M11 | Automation Configuration | profile card "Smart Trophy & Farm" (`tune` Switch; chips Safety Guard Active, 5 Modules Enabled, ADB Loop: 120ms); accordions: `agriculture` Farming (Min Gold 450,000 / Min Elixir 450,000 / Min Dark Elixir 4,000, Dead Base Detector switch, **range slider** Max "Next" 45 (10–150), Deployment Strategy BArch / Sneaky Gobs / Four-Finger); `construction` Builder Base (Auto-Attack for Daily Star Bonus, Clock Tower Auto-Boost, Hero Machine Auto-Ability); `account_balance_wallet` Resource Collectors "Every 15m" (Gold Mines, Elixir Pumps, DE Drills, Gem Mine checkboxes; Auto-Collect Treasury); `castle` Clan Castle & Troops (request message text field "Reinforce please / Loons or Sneakies", Safe Donation Relay); `military_tech` Clan Games & Events (Prioritize Fast Raids, Trash Stagnant Challenges); **Upgrades & Auto-Spending** [Strict Guard] (Auto-Upgrade Walls, Defenses & Heroes, `diamond` Spend Gems…); unsaved bar Discard / Save; bottom sheet "Enable Resource Spending? — Type SPEND to authorize" **Confirm & Enable** |
| M12 | Safety | header "Guardrails Active — Shield Enforced", stats Local Checks 14/14, Risk Score, Sandbox Isolated; **Hardware Emergency Stop** "Press Volume Down 3× quickly" + Test Gesture Simulation; Zero-Spend Guarantee (Gems / Magic Items / Real-Money IAP: BLOCKED, POLICY-IMMUTABLE); Fatigue & Break Schedule (Micro-breaks 3–8m every 45–60m, Long Rest 25–40m every 3 hrs, Gaussian Jitter ±15%); Limits & Scheduling (Daily Farming Cap 3.5 / 5.0 hrs, Quiet Hours 11:00 PM – 07:00 AM); Device & Hardware Guardrails (Stop on Incoming Call, Stop on Screen Lock, Battery Threshold 20 % stepper −/+, Thermal Watchdog "Stop if > 41.0°C", Unknown Screen Watchdog > 60s) |
| M13 | History & Run Analytics | tabs Run History / Diagnostic Logs; "Safety Engine Armored — Optimal"; Total Runtime 14h 32m (+1.8h today, 4 sessions); Total Loot Gold 8.4M / Elixir 7.9M / Dark 42.1k; Win Rate 98.2 %; **Loot Velocity** chart with range chips Last 24h / 7 Days / 30 Days ("Max 720k/hr"); **Recent Sessions** cards (time range, duration • mode, status chip Completed / Safety Break / Stopped / Auto-Stopped, G/E/DE grid, attacks, stop cause "Quiet hours reached", "Floating bubble stop", "Incoming call guard") |
| M14 | Diagnostic Logs | `enhanced_encryption` "Privacy Shield v3.1" + **Share Diagnostics**, sanitizer note; search "Search log messages, modules, or tags..."; chips All 1,248 / SAFETY 12 / ACTIONS 580 / WARNING 142 / ERROR 26 / INFO 1,080; log cards (time, level icon + label, [Module], message); empty state "No logs matching filter" **Reset filters**; sticky bar Live Scroll toggle, `delete_sweep`, **Export ▾** (Sanitized JSON / Raw Plaintext (.txt) / Copy to Clipboard) |
| M15 | Settings | "Offline-First Engine — Air-Gapped"; theme grid Dark Slate (Active) / Material You / Follow OS / High Noon (Light); "Dual Indicator Badges" switch; App Language "English (United States) EN-US"; Android notification channels (Session Progress & Milestones, Safety Stops & Defense Guards [Crucial], Foreground Daemon Status); Updates "v2.4.1 Up to Date" **Check**, Release Stream Stable / Beta / Alpha, "Background Release Polling — Query GitHub releases manifest on launch", "View Release Notes on GitHub"; Backup **Export Config** / **Import Config**; "Zero Diagnostic Transmission"; `delete_forever` **Purge All Automation Profiles & Logs**; about "v2.4.1 (Build 1842 - ARM64-v8a)", Release Notes • OSS Licenses • Repository |
| M16 | Use with Desktop - Pairing & Trusted Computers | "Zero-Config Desktop Pairing — Scan the QR code displayed in the Clash of Bots Desktop application…", Wi-Fi "Home-5GHz (192.168.1.42)"; camera viewfinder "Align desktop QR code within frame" (flashlight, "Enter code manually", flip camera); request sheet "DESKTOP-PRO-X9 [NEW REQUEST] IP 192.168.1.105, Fingerprint SHA-256…, Allow this computer to control the game while the bot runs?" → **Always allow from this computer** / **Allow once (this session only)** / **Deny**; "Trusted Computers (2)" list with **Remove**, "Require biometrics" toggle; dialog "Enter Pairing Code" 6 digit boxes ("…shown in Clash of Bots Desktop under Settings > Link Phone") **Verify & Link** |
| M17 | Permissions & Diagnostic Health | active control method card (Accessibility Service, Android 14, package) **Switch Driver** / **Run Health Check**; alert "1 Action Needed — battery optimizer revoked…" **Re-whitelist Service**; Permissions Matrix 4 of 6 (incl. Shizuku ADB Bridge "Setup"); Diagnostics Sandbox: Touch & Pinch Sandbox, Display Canvas Spec 1080 × 2400; Security & Privacy Boundary; sticky "1 Permission Needs Fix — Resolve (1)" |
| M18 | Persistent Android Notifications | system preview tabs Shade Mode / Lock Screen; ongoing notification "Automation Active • Attacking", "Searching for targets — Skipped 14 bases…", Gold 485,200 / Elixir 520,840 / Dark 2,410 / Raid Success 4 of 4, "Scheduled Break in 18m 42m / 60m"; actions **Pause**, **Emergency Stop**, **Dashboard**; lock-screen redacted version "Automation active in background — Resource and target details hidden" + **Stop Bot**; comparison table |
| M19 | Floating Control Overlay (In-Game) | in-game HUD strip "Bot Controlling Screen • Tap Overlay to Pause", mini counters 1.82M / 2.40M, `shield` 14h 22m, "NEXT »"; 48 px floating bubble (logo + play badge); expanded panel "Running 01:24:18", "Searching next match: Nexting — Filter: >350k Gold / 350k Elixir", 2×2 tiles (Gold Loot +165k/hr, Elixir +190k/hr, Dark Elixir Steady, Attacks 4 / 12 max 100% 3★), **Pause**, **Stop Bot**, "Clash of Bots Companion — Open App" |
| M20 | Interactive Prototype Suite | clickable state machine of both suites (see D12) with Material 3 shared-axis transitions (320 ms, cubic-bezier(0.05, 0.7, 0.1, 1.0)) |
| M21 | Logo (`mobile/clash-of-bots-logo.svg` 120², png 240²) | small version of the emblem |

---

## 4. Feature mapping

Legend: **EXISTING** = the data/behaviour is in the code today (named). **PARTIAL** = some of it exists and the UI needs a
small hook. **NEW** = not in the code. Effort S (< ½ day), M (1–3 days), L (> 3 days or needs new vision/OCR work).
Qt = can be built with PySide6 now (`pyside6-essentials` 6.11.2, which has **no QtCharts**, so draw charts with QPainter or
add `pyside6-addons`). **DROP** = decorative/fake metric. Recommend leaving it out.

### 4.0 Shell

| UI element | Status | Code / notes |
|---|---|---|
| Nav rail 7 items | NEW S, Qt | replace `QTabWidget` in `MainWindow.__init__` (`cob/ui/main_window.py:157-162`) with a rail + `QStackedWidget`. Tabs today: Farm, Settings, Setup, History, Log |
| Device pill + picker | EXISTING | `list_devices()`, `device_combo`, `refresh_devices()` in `main_window.py`; LDPlayer via `cob/device/ldplayer.py`, phones via `adb.py`/`phone.py` |
| Run-state pill (Idle/Running/Stopped/On break) | PARTIAL S | `_set_running()`, `on_break()` (signal `FarmWorker.resting`), `on_finished()` (`FarmStats.stop_reason`) |
| Kill Switch | EXISTING | `MainWindow.stop()` → `FarmWorker.request_stop()` ("finishes the current step": not instant) |
| Esc shortcut | NEW S, Qt | `QShortcut(Qt.Key_Escape)`. There is no shortcut in the code today |
| Avatar | DROP | no accounts |
| Status strip: connection | PARTIAL S | serial is known; transport (USB / Wi-Fi / LDPlayer) is derivable from the serial (`ip:port` = Wi-Fi). "500 Mbps" DROP |
| Status strip: current step | NEW S | `FarmTask` has no step callback; add `on_step(str)` next to `on_cycle`/`on_break` in `cob/tasks/farm.py` and a `FarmWorker.step` signal. `CycleResult.nexts` gives "Skip #N" after the fact |
| Status strip: session timer | NEW S, Qt | QTimer from start time; `FarmStats.seconds` at the end |
| Status strip: safety summary | PARTIAL S | from `FarmConfig` (breaks, `wall_upgrades`=0 → "Spending Locked") |
| Logo / app icon | NEW S | replace the painted `theme.app_icon()` with `clash-of-bots-logo.svg` (QtSvg is available) |
| Dark M3 palette | NEW S, Qt | rewrite `cob/ui/theme.py` (`apply_dark`) with the tokens in §1 |
| System tray | EXISTING | `_make_tray()`, `_notify()` |

### 4.1 Dashboard (D1–D4)

| UI element | Status | Code / notes |
|---|---|---|
| Profile name in breadcrumb / profile selector | NEW M, Qt | one `farm.json` only (`cob/core/config.py`). Profiles = several JSON files + a picker. ROADMAP M4 lists profiles as open |
| Home Village / Builder Base segmented | EXISTING | `mode_combo` ("home"/"bb"), `FarmWorker(mode=…)`, `bb_farm_task` in `cob/tasks/wiring.py` |
| Cycles limit (0 = ∞) | EXISTING | `cycles_spin` → `FarmLimits.max_cycles` (`cob/tasks/farm.py`) |
| Time limit (mins) | EXISTING | `minutes_spin` → `FarmLimits.max_minutes` |
| Start Farming / Stop Farming | EXISTING | `MainWindow.start()` / `stop()` |
| Live game view + Grab picture | EXISTING | `FarmWorker.preview` (480×270, every 2 s: `PREVIEW_EVERY_S`), `grab_preview()` / `_grab()` |
| "Detected scene / Home village" | EXISTING | screen name from `ScreenClassifier.classify` (`cob/screens/classifier.py`) via the preview signal (`preview_screen` label) |
| Confidence % | NEW S | `Match.score` exists (`cob/vision/match.py`); `Classification.matches` holds the anchor scores. Expose the best score |
| Latency / FPS chips | PARTIAL S | `cob bench` (`cli.py`) measures capture/tap latency; live view is ~0.5 fps by design. Show honest "updated Xs ago". "30 FPS", "H.264 60Hz" DROP |
| Resolution chip | EXISTING | 1600×900 contract (`TARGET_SIZE`, D-006). Design shows 1920×1080 / 2340×1080: use the real value |
| Cycle pipeline stepper (Collect → Search → Attack → Return → Break) | NEW S–M, Qt | the steps exist: `FarmTask._cycle` (maintenance = collect/walls/request in `FarmParts.maintain`, `search`, `attack`), `_take_break`. Needs the `on_step` callback |
| Per-step result text ("14 bases filtered", "Carts emptied") | PARTIAL S | `CycleResult.nexts`, `CollectTask` result (`loot_cart` flag in `cob/tasks/collect.py`) |
| Stat tiles Gold/Elixir/DE/Attacks/Cycles/Loot-per-hr | EXISTING | `_stats_box()` / `_show_stats()` using `FarmStats.gained`, `.attacks`, per-hour computation (tooltip has all three) |
| Per-resource "/hr" under each tile | EXISTING data | `_show_stats` already computes gold/elixir/dark per hour |
| "won / lost", stars, % destruction, "Victory (3 Stars)" | NEW M–L | `CycleResult.attack` is only "done"/"failed"; needs result-screen OCR of stars + %. `cob/attack/damage.py` reads damage % (partial) |
| "0 crashes / clean" | EXISTING data | cycles with `search == "error"` in `FarmStats.cycles` |
| "Session complete: x%" | NEW S | cycles / `max_cycles` |
| Last completed cycle | EXISTING | `on_cycle()` → `stat_labels["Last cycle"]` |
| Guardrail chips: breaks every N | EXISTING | `FarmConfig.break_every` |
| Guardrail: "Break #2 in 2 cycles" | PARTIAL S | `FarmTask._next_break` is internal: expose it |
| Guardrail: Spending OFF | EXISTING | `FarmConfig.wall_upgrades == 0`; the bot never spends gems (CONSTRAINTS / D-020) |
| Guardrail: Daily limit 4 h | NEW M | no daily accounting (ROADMAP M4 "Session limits per day" open). Feasible from `history.csv` seconds per day |
| Target thresholds overlay "G > 350k / E > 350k / DE > 2.5k" | PARTIAL | the code has **combined** gold+elixir (`min_gold_elixir`) OR dark (`min_dark`), not separate G/E. Show the real rule |
| "Filtering base #14: criteria unmet (210k < 350k)" | PARTIAL S | `SearchTask` (`cob/tasks/search.py`) reads loot per base and logs it; emit a structured event |
| Town Hall level, detection boxes, "DE TANK #1" | NEW L | no TH / building detection |
| Storage "Target cap 12,000,000 — 32 % filled" | NEW M | own resources are read (`own_resources`), capacity is not |
| Trophies +64 | NEW M | no trophy OCR |
| Pause (15m Break) | NEW S | manual break = call `_take_break`-like wait from the GUI |
| Recent raids table | EXISTING data | `cob/core/history.py` (`read`, `COLUMNS`). Opponent name / base type / strategy narrative = NEW L / DROP |
| Export CSV | EXISTING | `export_history()` |
| Filter 3-Stars | NEW (needs stars) | |
| Safety banner "Halted by Safety Guard" + reason | EXISTING data | `FarmStats.stop_reason`: "N failures in a row", "own gold below reserve", "stopped on …" (village open on another device), "device lost: …", "N cycles done", "N min elapsed" |
| Audit trail (last N log lines) | EXISTING data | `LogBridge.line` (`cob/ui/log_bridge.py`) |
| Cooldown lock / "Restart (Locked)" / Force override PIN | NEW M / DROP (PIN) | no cooldown concept |
| Frozen frame + "Safety Hold" overlay | NEW S, Qt | reuse the last preview frame |
| Device thermal / battery / CPU | NEW M | phones only (`adb shell dumpsys battery`); n/a for LDPlayer |
| Session tap count | NEW S | count in the device wrapper (`cob/device/base.py`) |
| Session #089, PID, SHA-256, "Level 3 Hardened", Heuristic anomalies | DROP (session # could come from `logs/sessions` count, S) | |

### 4.2 Automation Settings (D5)

| UI element | Status | Code / notes |
|---|---|---|
| Minimum Gold + Elixir (combined) | EXISTING | `FarmConfig.min_gold_elixir` (0–10 M; design range 100k–2,000k, shown in k) |
| Minimum Dark Elixir | EXISTING | `FarmConfig.min_dark` (0–500k; design 0–10k) |
| Max 'Next' searches | EXISTING | `FarmConfig.max_nexts` (0–500; design 5–150) |
| Keep at least X own gold | EXISTING | `FarmConfig.min_own_gold` |
| Restore defaults | EXISTING | `defaults_button` → `FarmConfig()` |
| Save / Discard + unsaved bar | PARTIAL S, Qt | `save_filter()` / `load_filter()` exist; dirty tracking is NEW |
| Category side list (anchor scroll) | NEW S, Qt | QListWidget + `QScrollArea.ensureWidgetVisible` |
| Builder Base enable toggle | PARTIAL | BB is a run **mode** (`mode_combo`), not a toggle alongside home farming |
| BB loot priority Gold/Elixir/Both | NEW M | |
| Clock Tower boost | NEW M | no clock tower code |
| Collect every N minutes | EXISTING | `FarmConfig.collect_minutes`, `FarmParts.maintenance`, `CollectTask` (home) and `collect_builder_base` (BB) |
| Auto-collect loot cart | EXISTING behaviour, NEW S toggle | `CollectTask._loot_cart` always runs during collect |
| Clan Castle treasury | NEW M | |
| Request troops every N minutes | EXISTING | `FarmConfig.request_minutes`, `RequestTask` (`cob/tasks/request.py`) |
| Chat string automation (custom message, typing jitter) | DROP / NEW M | the code posts the game's **saved** message and types nothing ("Nothing is typed by the bot"). Show it as read-only info |
| Clan Games automation + category chips | NEW L | ROADMAP M5 open |
| Auto-upgrade walls + max per run | EXISTING | `FarmConfig.wall_upgrades`, `WallTask` (`cob/tasks/walls.py`) |
| Village buildings / laboratory upgrades | NEW L | ROADMAP M3 "Auto upgrade buildings/lab" open |
| Upgrade priority: Cheapest first | EXISTING (walls) | walls pick the cheapest visible row; other strategies NEW |
| Gold / Elixir safe floor | PARTIAL S | one `FarmConfig.wall_reserve` for both; split = S |
| Dark Elixir floor | NEW (no DE spending exists) | |
| "SPENDS LOOT" warning + type-SPEND confirm sheet | NEW S, Qt | good fit for enabling `wall_upgrades > 0` (D-020 spend safety) |
| Bézier swipe deviation | NEW M | `Humanizer` (`cob/core/human.py`) jitters tap points only; swipes are straight |
| Session break jitter 5–12 min | EXISTING | `FarmTask._take_break` (0.6×–1.4× `break_minutes`) |
| Deployment strategy (BArch / Sneaky Gobs / Four-Finger, mobile M11) | NEW L | `AttackTask` deploys whatever army is trained along one edge |
| Dead base detector (mobile M11, D4 "Exterior Tombs") | NEW L | |

### 4.3 Safety & Schedule (D6)

| UI element | Status | Code / notes |
|---|---|---|
| Rest after about N cycles | EXISTING | `FarmConfig.break_every` (±2 random) |
| Rest length | EXISTING | `FarmConfig.break_minutes` (0.6–1.4×) |
| Randomise toggle | EXISTING (always on), NEW S toggle | |
| Max hours per day + today's progress | NEW M, Qt | needs per-day accounting (history.csv `time` + `seconds`) and a stop rule in `FarmTask._loop` |
| Max attacks per day + progress | NEW S–M | count today's `attack == "done"` rows in `history.csv` |
| Quiet hours | NEW M | scheduler; a stop/resume rule |
| Disconnect timeout | PARTIAL | device lost → `FarmTask._try_recover` (`max_recoveries=2`, relaunch LDPlayer) then stop "device lost"; no minutes setting |
| Multi-session collision | EXISTING | navigator stop action ("village open on another device") → `found.reason.startswith("stopped on")` in `FarmTask._cycle` |
| Consecutive failures | EXISTING, NEW S to expose | `FarmLimits.max_failures_in_row = 3` (not in farm.json) |
| Unknown screen watchdog | PARTIAL | `Navigator` (`unknown_check_s` 5 s → checks game in front, `unknown_restart_s` 45 s → restarts the game, `save_snapshot`). "Stop instead" option = S |
| Spending guardrails (read-only) | EXISTING | no gem path anywhere; walls exact-cost/affordable/reserve/post-check (`cob/tasks/walls.py`, D-020) |
| Global emergency stop Ctrl+Shift+S | NEW M | window-level `QShortcut` is S; system-wide hotkey needs native API (Win `RegisterHotKey`, X11/Wayland differ) |
| Account safety notice | NEW S (static text) | |
| Security preset / detection score / "cryptographically validated firmware" | DROP | |

### 4.4 History (D7)

| UI element | Status | Code / notes |
|---|---|---|
| KPI totals (gold, elixir, DE, attacks, uptime, avg/hr) | EXISTING data | `history.read()` columns `gained_*`, `attack`, `seconds`; aggregate in UI (S) |
| "vs prev. 7d" deltas | NEW S | |
| Date range picker | NEW S, Qt | filter on `time` column |
| All / Home / Builder Base filter | NEW S | `history.csv` has **no mode column**: add `mode` to `COLUMNS` |
| Export All / Export CSV | EXISTING | `export_history()` |
| Loot Yield Velocity line/area chart | NEW M, Qt | no QtCharts in `pyside6-essentials`; custom QPainter widget (or add `pyside6-addons`) |
| Attacks vs safety cap bar chart | NEW M, Qt | same; cap depends on daily attack limit (NEW) |
| Raid table: timestamp, yields, duration | EXISTING | `time`, `gained_gold/elixir/dark`, `seconds` (current `HISTORY_COLUMNS` in `main_window.py`) |
| Village / TH / strategy column | NEW L | |
| Stars & DMG, Victory / Trophy drop result chips | NEW M–L | needs result OCR |
| Search, Filters, sort, pagination, empty state | NEW S, Qt | `QSortFilterProxyModel` + `QTableView` |

### 4.5 Logs (D8)

| UI element | Status | Code / notes |
|---|---|---|
| Live log view | EXISTING | `LogBridge` / `QtLogHandler` → `append_log` (`QPlainTextEdit`, 2000 lines) |
| Session file name in footer | EXISTING | `session_log_file()` (`cob/core/log.py`, keeps 30 sessions) |
| Open Folder | EXISTING | `log_dir()` + `QDesktopServices` |
| Level chips with counts, regex filter | NEW S, Qt | `QtLogHandler` emits a formatted string; emit `(level, name, msg, time)` instead |
| Follow tail / wrap / clear view / copy visible | NEW S, Qt | |
| Error rows with screenshot | PARTIAL M | `save_snapshot()` (`cob/core/snapshots.py`) writes frames on unknown screens; link path into the log record |
| Save Sanitized Diagnostics (zip + scrub serials/IPs) | NEW M | |
| Submit Diagnostic Dump / Ignore Overlay Pattern | DROP / NEW L (anchor learning) | |
| Header meta: session running time | NEW S | host/PID DROP |

### 4.6 Settings (D9)

| UI element | Status | Code / notes |
|---|---|---|
| Theme Auto / Light / Dark | PARTIAL | dark only (`apply_dark`); keep dark, drop the others or add light later (M) |
| Language select | NEW L | no i18n |
| Start minimized to tray | NEW S | tray exists (`_make_tray`) |
| Launch on OS startup | NEW M | Windows Run key / XDG autostart `.desktop` |
| Notification rules (safety stop, vision anomaly, rest) | PARTIAL S | `_notify()` fires on finished/failed only; per-rule toggles + break notification NEW |
| Test Dispatch | NEW S | `tray.showMessage` |
| Data folder + Open | EXISTING | `user_data_dir()` (`cob/core/paths.py`: `%LOCALAPPDATA%\ClashOfBots` / `~/.local/share/ClashOfBots`). Design path is wrong |
| Storage breakdown | NEW S | sizes of `logs/`, captures, snapshots |
| Export / Import config (.json) | PARTIAL S | `save_farm_config(cfg, path)` / `load_farm_config(path)` take a path already |
| Reset to factory defaults | NEW S | `FarmConfig()` + delete farm.json |
| Release channel / Check now | NEW M | GitHub releases API; `scripts/release.py` exists for publishing only |
| Version / build | EXISTING | `cob.__version__` (window title) |
| Changelog notes | EXISTING data | `CHANGELOG.md` |
| Privacy card | NEW S (static) | true: bot is local-only |
| License line | check | `pyproject.toml` has no license field and there is no LICENSE file: do not print "GPLv3" until decided |

### 4.7 Setup wizard (D10) and Devices (D12)

| UI element | Status | Code / notes |
|---|---|---|
| Wizard frame + 5-step stepper | NEW M, Qt | `QDialog` + `QStackedWidget`; persist "wizard done" flag |
| Welcome / Risk consent checkbox | NEW S | |
| Target: LDPlayer / USB phone / Wi-Fi phone | EXISTING | LDPlayer (`cob/device/ldplayer.py`), phones (`cob/device/phone.py`), Wi-Fi (`cob/device/wireless.py`) |
| Wi-Fi pairing via QR | EXISTING | `cob/device/qr_pair.py` + `cob/ui/qr_dialog.py` (D-025) |
| Nearby phones discovery | EXISTING | `cob/device/discovery.py` (`nearby`, `auto_connect`), `find_nearby()` |
| Manual pair code / connect | EXISTING | `wireless.pair`, `wireless.connect`, Setup tab Pair/Connect |
| USB → Wi-Fi switch, restore phone screen | EXISTING | `wireless.usb_to_wifi`, `run_phone("restore")` |
| Handshake card (model, serial, Android version) | PARTIAL S | `phone_checks` reports model; Android version via `getprop` (S) |
| Send Test Ping | PARTIAL S | `cob bench` measures tap latency |
| Diagnostics checklist | EXISTING | `cob/device/checks.py` `run_checks` / `phone_checks` (`Check(name, ok, detail, fix)`): LDPlayer installed / running / resolution, ADB connection, screen size, Clash installed, phone unlocked, zoom (pinch), display mode; fixes LAUNCH / RESIZE (`fix()`) |
| Devices page: device cards (connected, latency, battery, display calibrated) | PARTIAL M | list + checks exist; battery/latency NEW S each |
| Remembered Wi-Fi phones | EXISTING | `wireless.known()` / `remember` / `forget` (natural "trusted devices" list) |

### 4.8 Mobile screens

| Screen | Status |
|---|---|
| M1–M4 Home states | Same data as D1–D3 (see 4.1). Desktop should borrow: **On Break** state (countdown ring, "Skip break" + confirm dialog; data from `FarmWorker.resting` seconds: EXISTING), battery-threshold stop (NEW M, phones), "Stopped" cause texts |
| M5–M10 Onboarding, M17 permissions | NEW L, **not PySide6**: needs an Android app (Accessibility / Shizuku / MediaProjection). The current design drives the phone from the PC over ADB. Desktop wizard equivalents exist (4.7) |
| M11 Automation config | Same as D5 (4.2) |
| M12 Safety | Same as D6 plus phone-only guards: stop on call / screen lock / battery / thermal (NEW M via ADB `dumpsys` polling from the PC; volume-key stop needs an Android app) |
| M13–M14 History / logs | Same as D7 / D8 |
| M15 Settings | Same as D9; notification channels are Android-only |
| M16 Pairing & trusted computers | The **reverse direction** of today: Android's own Wireless-debugging QR scanner already scans the desktop QR (`qr_pair.py`). A custom in-app scanner / trust list needs the Android app (NEW L) |
| M18 Persistent notification, M19 floating overlay | NEW L, Android app only. Desktop analogue: tray tooltip/menu with live counters (S) |

---

## 5. Suggested desktop implementation order

1. **Theme + tokens** (`cob/ui/theme.py`): palette from §1, QSS, bundled fonts (Inter, Roboto Flex, JetBrains Mono,
   Material Symbols Outlined) via `QFontDatabase.addApplicationFont`, `icon(name, size, color, filled)` helper (QLabel or
   QIcon painted from the Material Symbols font by ligature/codepoint). New logo SVG as app icon. **S–M**
2. **Shell**: top bar (logo, device pill, state pill, Kill Switch), 96 px nav rail, `QStackedWidget`, 40 px status strip;
   Esc shortcut; split `main_window.py` (752 lines) into `cob/ui/pages/*.py` + `cob/ui/widgets/*.py`. **M**
3. **Shared widgets** (used by most pages): `Card` (title row + icon + tag), `StatTile` (eyebrow, mono value, sub line,
   icon dot), `Chip`/`Tag`, `SegmentedControl`, `ToggleRow` (title, description, switch), `NumberField` (mono input +
   suffix + range hint + help), `StepPipeline` (5 steps), `Banner` (error/tertiary), `Toast`, `EmptyState`,
   `UnsavedBar`, `KbdKeys`. **M**
4. **Dashboard** idle / running / stopped / on-break as one page with state-driven sections (D1 + D2 + D3, KPI tiles from
   D4). Add `on_step` + `FarmWorker.step` signal and a session timer. Reuses StatTile, Card, StepPipeline, Banner. **M**
5. **Automation** page (D5) bound to `FarmConfig`: Farming, Collectors, Clan Castle, Walls (+ SPEND confirm), with NEW
   features shown as disabled "coming soon" rows or omitted. Reuses ToggleRow, NumberField, SegmentedControl, UnsavedBar. **M**
6. **Safety & Schedule** (D6): breaks (existing), stop rules (existing: expose `max_failures_in_row`), spending card,
   then NEW daily hours / attacks limit and quiet hours (engine work in `FarmTask`). Shares widgets with 5. **M** (+ M for
   daily limits)
7. **History** (D7): KPI row (StatTile), table with proxy filter + export; add `mode` column to `history.csv`; charts
   later (QPainter). **M**
8. **Logs** (D8): structured log signal, level chips, filter, follow tail, open folder; sanitized diagnostics zip later.
   **S–M**
9. **Devices** page (prototype D12) + **Setup wizard** (D10): reuse `checks.py`, `qr_dialog.py`, discovery, wireless;
   wizard on first run. **M**
10. **Settings** (D9): data folder, export/import config, tray/autostart, notifications, version/changelog. **S–M**

Shared components by screen:

| Component | D1-3 Dash | D4 Ops | D5 Auto | D6 Safety | D7 Hist | D8 Logs | D9 Set | D10 Wiz |
|---|---|---|---|---|---|---|---|---|
| Card + header | x | x | x | x | x | x | x | x |
| StatTile | x | x |  |  | x |  |  |  |
| SegmentedControl | x |  | x |  | x |  | x |  |
| ToggleRow / switch |  |  | x | x |  |  | x |  |
| NumberField |  |  | x | x |  |  |  |  |
| Chip / Tag | x | x | x | x | x | x | x | x |
| StepPipeline | x |  |  |  |  |  |  | x (stepper) |
| Banner (error/warn) | x |  | x | x |  |  |  | x |
| Data table | (recent) | x |  |  | x |  |  |  |
| Log line view | x (audit) |  |  |  |  | x |  |  |
| Progress bar | x | x |  | x |  |  | x |  |
| Toast / UnsavedBar | x |  | x |  |  |  | x |  |

---

## 6. Icons and fonts to bundle

### Fonts

| Font | Weights | Use | Source |
|---|---|---|---|
| Inter | 400, 500, 600 | desktop body / labels | Google Fonts (OFL) |
| Roboto Flex | 400, 500, 600, 700 (variable) | headings (desktop), everything (mobile) | Google Fonts (OFL) |
| JetBrains Mono | 400, 500, 600 | numbers, timestamps, logs | Google Fonts / JetBrains (OFL) |
| Material Symbols Outlined | variable (FILL 0–1, wght 100–700, GRAD, opsz 20–48) | all icons. Filled variant (`FILL 1`) used for status icons | Google Fonts (Apache 2.0). Use `QFont.setVariableAxis("FILL", 1)` (Qt ≥ 6.7) or render filled icons from the static Filled font |

Ship the TTF/OTF files in `assets/fonts/` and register them with `QFontDatabase.addApplicationFont`. The full Material Symbols
variable font is ~10 MB; subset to the names below (e.g. `pyftsubset --text-file` with ligatures, or map names → codepoints).

### Material Symbols used

Desktop (132):
analytics apartment arrow_back arrow_downward arrow_forward autorenew bedtime brightness_auto bug_report cabin cable
calendar_month check check_circle chevron_left chevron_right close coffee construction content_copy cottage crop_free
dark_mode dashboard delete_sweep desktop_windows devices device_thermostat dns done done_all download emergency_home
energy_savings_leaf enhanced_encryption error expand_more fence file_download file_upload filter_center_focus filter_list
fingerprint flag folder_data folder_open format_list_bulleted format_list_numbered fort gavel gesture gpp_maybe
history history_edu home hourglass_empty hourglass_top hub info insights keyboard light_mode linear_scale list_alt lock
lock_clock lock_reset military_tech monetization_on monitoring nights_stay notifications notifications_active opacity
open_in_new paid palette pan_tool person phone_android photo_camera play_arrow play_disabled power_settings_new psychology
radar refresh restart_alt rule_folder savings schedule science search security sell send_time_extension sensors settings
shield shield_person smart_display smart_toy speed star stop_circle stream swords sync system_update_alt terminal
timelapse timer timer_off touch_app travel_explore trending_up tune unfold_less unfold_more upgrade usb verified
verified_user vertical_align_bottom videocam visibility visibility_off warning water_drop wifi_off wifi_tethering zoom_in
(`gshield` in the HTML is invalid: use `shield`.)

Mobile only (additional, for a future Android app or reuse):
accessibility_new account_balance_wallet ac_unit add add_circle adjust ads_click agriculture android app_settings_alt
arrow_circle_up arrow_drop_down aspect_ratio battery_alert battery_charging_80 battery_charging_90 battery_charging_full
battery_full battery_saver battery_std block bluetooth bolt bubble_chart build build_circle cancel carpenter castle chat
circle cleaning_services close_fullscreen cloud_download cloud_off data_object delete delete_forever description diamond
do_not_disturb_on drive_file_rename_outline electric_bolt equalizer fact_check flashlight_off flashlight_on
flip_camera_android fmd_bad format_image_left front_hand gite grid_view group handyman healing help_outline
history_toggle_off horizontal_rule hotel ios_share lan laptop_chromebook laptop_windows layers lock_open manage_search
menu_book more_vert neurology pause pause_circle phone_in_talk phonelink_lock picture_in_picture_alt pinch power
precision_manufacturing priority_high published_with_changes push_pin qr_code_scanner query_stats queue_play_next
radio_button_checked radio_button_unchecked receipt_long remove replay restore_page ring_volume rocket_launch
screen_lock_portrait screen_search_desktop screen_share screenshot_monitor settings_suggest share shield_lock
shield_with_heart shuffle signal_cellular_4_bar signal_cellular_alt sports_esports square stacked_line_chart
stay_current_portrait stop swap_horiz target task_alt timeline toll track_changes translate trending_flat upgrade
vibration volume_down widgets wifi
