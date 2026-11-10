# DEPENDENCIES

| Package | Pin | Why | Maintainer |
|---|---|---|---|
| adbutils | ==2.12.0 | Pure-Python adb server client (no adb subprocess per call); same lib family ACBot uses | openatx (codeskyblue) |
| numpy | >=2.2,<3 | Frame arrays | NumPy |
| opencv-python-headless | >=4.12,<5 | Template matching, image IO. Headless avoids Qt plugin clash with PySide6 (M2) | OpenCV team |
| pyside6-essentials | ==6.11.2 | GUI (D-001). Essentials only (QtCore/Gui/Widgets); the full `pyside6` meta-package adds ~400 MB of Addons (WebEngine, 3D) not needed. 6.11.2 over 6.12.0 (10 days old) for Nuitka plugin maturity | Qt Company |
| pytesseract | >=0.3.13 | Thin wrapper over tesseract.exe for rare text OCR (D-009); imported lazily | madmaze |
| av (PyAV) | ==19.0.2 | Decodes the phone's `screenrecord` H.264 stream for the opt-in live screen stream (D-037); imported only when it is on. BSD-3-Clause; the wheels bundle FFmpeg libraries under LGPL-2.1+ | PyAV-Org |
| segno | >=1.6 | Draws the Wi-Fi pairing QR code (D-025); pure Python, no sub-dependencies, BSD | Lars Heuer |
| pytest (dev) | >=8 | Tests | pytest-dev |
| ruff (dev) | >=0.6 | Lint/format | Astral |
| nuitka (build) | ==4.3.1 | Exe compile (D-003) | Kay Hayen |
| zstandard (build) | any | Nuitka compression support | indygreg |

Bundled binaries: `adb.exe` + DLLs from Google platform-tools (downloaded in CI from dl.google.com).
Secrets: none. No API keys anywhere in repo.

## Bundled assets (UI v2, D-026)
| Asset | Licence | Source | Where |
|---|---|---|---|
| Inter (variable) | SIL OFL 1.1 | github.com/google/fonts `ofl/inter` | assets/fonts/Inter.ttf (+ OFL-inter.txt) |
| Roboto Flex (variable) | SIL OFL 1.1 | github.com/google/fonts `ofl/robotoflex` | assets/fonts/RobotoFlex.ttf |
| JetBrains Mono (variable) | SIL OFL 1.1 | github.com/google/fonts `ofl/jetbrainsmono` | assets/fonts/JetBrainsMono.ttf |
| Material Symbols Outlined SVGs (132, outlined + filled) | Apache 2.0 | github.com/google/material-design-icons `symbols/web` | assets/icons/{outlined,filled} (+ LICENSE) |
Adding an icon: download `symbols/web/<name>/materialsymbolsoutlined/<name>_24px.svg` (+ `_fill1_24px.svg`);
`tests/test_ui_style.py` fails when UI code names an icon that is not bundled.
