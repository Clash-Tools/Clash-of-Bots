# FEATURE-001: M0 foundations

Goal: runnable skeleton that can see and touch an LDPlayer instance, built into a Windows exe by CI.
Scope: uv project, `cob/` package, Device protocol, AdbDevice (raw screencap + input shell),
LdConsole + LDPlayerDevice, CLI (devices/capture/bench/ld-resize/selftest), tests, CI.
Design: see ARCHITECTURE.md device layer; D-002, D-003, D-006.
Status: code done; live LDPlayer + CI run NOT yet verified.

Open questions:
- Real capture latency on LDPlayer (expect 60-200 ms raw). If >250 ms -> scrcpy/minicap stream.
- `input tap` latency (expect 100-250 ms) -> M2 may need uiautomator2 or scrcpy control.
- LDPlayer adb serial: emulator-5554+2n assumed; fallback adb connect 127.0.0.1:5555+2n.

## Log
- 2026-10-18 (Claude Opus 5.5): skeleton + device layer + CI written; unit tests pass on Linux.
