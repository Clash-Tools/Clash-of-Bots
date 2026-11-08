"""Command line entry: dev tools now, GUI launcher later.

  cob devices                 list adb devices and LDPlayer instances
  cob capture -s SERIAL       save one frame to captures/
  cob bench -s SERIAL         capture/tap latency
  cob ld-resize INDEX         set LDPlayer instance to 1600x900@240
  cob phone-reset SERIAL      give a phone its own display size back (any time)
  cob pair ADDR CODE          pair a phone over Wi-Fi (Android 11+ wireless debugging)
  cob connect ADDR            connect to a phone over Wi-Fi (IP:port)
  cob wifi SERIAL             switch a USB-connected phone to Wi-Fi
  cob crop FRAME NAME X Y W H cut a template PNG from a saved frame
  cob match FRAME NAME        test one template against a frame (or -s SERIAL for live)
  cob classify FRAME          which screen is this frame
  cob selftest                offline check used by CI smoke test
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

from cob import __version__
from cob.core.log import setup_logging
from cob.device.base import TARGET_SIZE, DeviceError

log = logging.getLogger("cob")

BOT_COMMANDS = {"farm", "bb", "attack", "search", "home", "bench", "gui"}


def _open_device(serial: str):
    from cob.device.phone import open_device

    return open_device(serial)  # phones: display mode on until the command exits


def cmd_devices(_args) -> int:
    from cob.device.adb import list_serials
    from cob.device.ldplayer import LdConsole
    from cob.device.phone import phone_label

    try:
        serials = list_serials()
        print("adb devices:", ", ".join(serials) or "(none)")
        for serial in serials:
            if label := phone_label(serial):
                print(f"{label} -> {serial}")
    except DeviceError as exc:
        print(f"adb: {exc}")
    try:
        for inst in LdConsole().list():
            size = f"{inst.width}x{inst.height}@{inst.dpi}" if inst.width else "?"
            state = "running" if inst.running else "stopped"
            print(f"LDPlayer #{inst.index} '{inst.name}' {state} {size} -> {inst.adb_serial}")
    except DeviceError as exc:
        print(f"LDPlayer: {exc}")
    return 0


def cmd_capture(args) -> int:
    import cv2

    dev = _open_device(args.serial)
    frame = dev.capture()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_{frame.shape[1]}x{frame.shape[0]}.png"
    cv2.imwrite(str(path), frame)
    print(f"saved {path}")
    if (frame.shape[1], frame.shape[0]) != TARGET_SIZE:
        print(f"warning: frame is not {TARGET_SIZE[0]}x{TARGET_SIZE[1]} (D-006)")
    return 0


def _timeit(fn, n: int) -> list[float]:
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return times


def _report(name: str, times: list[float]) -> None:
    p95 = sorted(times)[max(0, int(len(times) * 0.95) - 1)]
    print(f"{name:8s} n={len(times)} mean={statistics.mean(times):6.1f}ms "
          f"p95={p95:6.1f}ms min={min(times):6.1f}ms")


def cmd_bench(args) -> int:
    dev = _open_device(args.serial)
    dev.capture()  # warm-up
    _report("capture", _timeit(dev.capture, args.n))
    if args.tap:
        # Taps a corner of the status area; harmless on the CoC home screen but still a real input.
        _report("tap", _timeit(lambda: dev.tap(5, 5), max(3, args.n // 4)))
    return 0


def cmd_ld_resize(args) -> int:
    from cob.device.ldplayer import LdConsole

    LdConsole().set_resolution(args.index)
    print(f"instance {args.index} set to {TARGET_SIZE[0]}x{TARGET_SIZE[1]}; restart it to apply")
    return 0


def cmd_phone_reset(args) -> int:
    from cob.device.phone import restore

    restored = restore(args.serial)
    print(f"{args.serial}: display restored to {restored}" if restored
          else f"{args.serial}: nothing saved for this phone (the bot never changed it)")
    return 0


def cmd_pair(args) -> int:
    from cob.device.wireless import pair

    print(pair(args.address, args.code))
    print("now: cob connect <IP:port shown under Wireless debugging>")
    return 0


def cmd_pair_qr(_args) -> int:
    from cob.device import discovery, qr_pair

    ok, detail = discovery.available()
    if not ok:
        print(f"this adb cannot browse the network (mDNS): {detail}; use `cob pair` with the code")
        return 2
    session = qr_pair.new_session()
    print(qr_pair.qr_terminal(session.qr_text))
    print("\nPhone (same Wi-Fi, Android 11+): Developer options > Wireless debugging > "
          "Pair device with QR code, then scan. Ctrl+C cancels.")
    try:
        serial = qr_pair.pair_and_connect(session, on_status=print)
    except KeyboardInterrupt:
        print("cancelled")
        return 1
    print(f"connected: {serial}")
    return 0


def cmd_discover(_args) -> int:
    from cob.device import discovery

    ok, detail = discovery.available()
    if not ok:
        print(f"this adb cannot browse the network (mDNS): {detail}")
        return 2
    found = discovery.nearby()
    for n in found:
        state = "connected" if n.connected else "used before" if n.known else "new"
        print(f"{n.service.serial or n.service.name:20s} {n.service.address:22s} {state}")
    if not found:
        print("no phone with Wireless debugging on was found on this network")
    return 0


def cmd_connect(args) -> int:
    from cob.device.wireless import connect

    print(f"connected: {connect(args.address)}")
    return 0


def cmd_wifi(args) -> int:
    from cob.device.wireless import usb_to_wifi

    print(f"{args.serial} is now also at {usb_to_wifi(args.serial)}; the USB cable can be unplugged")
    return 0


def _load_frame(path: str):
    import cv2

    from cob.vision.frame import Frame

    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"cannot read image {path}")
    return Frame(img)


def _store(args):
    from cob.vision.templates import TemplateStore

    return TemplateStore(Path(args.templates) if args.templates else None)


def cmd_crop(args) -> int:
    import cv2

    frame = _load_frame(args.frame)
    x, y, w, h = args.x, args.y, args.w, args.h
    patch = frame.bgr[y : y + h, x : x + w]
    if patch.shape[:2] != (h, w):
        raise SystemExit(f"crop {x},{y},{w},{h} outside frame {frame.size}")
    root = _store(args).root
    root.mkdir(parents=True, exist_ok=True)
    out = root / f"{args.name}.png"
    cv2.imwrite(str(out), patch)
    pad = args.pad
    print(f"saved {out}\n\n[templates.{args.name}]\n"
          f"region = [{max(0, x - pad)}, {max(0, y - pad)}, {w + 2 * pad}, {h + 2 * pad}]")
    return 0


def cmd_match(args) -> int:
    from cob.vision.frame import Frame
    from cob.vision.match import match_all

    frame = _load_frame(args.frame) if args.frame else Frame(_open_device(args.serial).capture())
    tpl = _store(args).get(args.name)
    t0 = time.perf_counter()
    hits = match_all(frame, tpl, region=None if args.full else tpl.region, threshold=args.threshold)
    ms = (time.perf_counter() - t0) * 1000
    print(f"{args.name}: {len(hits)} hit(s) in {ms:.1f}ms (threshold {args.threshold or tpl.threshold})")
    for m in hits[:10]:
        print(f"  at {m.x},{m.y} center {m.center} score {m.score:.3f}")
    return 0 if hits else 1


def cmd_classify(args) -> int:
    from cob.screens import ScreenClassifier

    clf = ScreenClassifier(_store(args))
    for path in args.frames:
        t0 = time.perf_counter()
        result = clf.classify(_load_frame(path))
        ms = (time.perf_counter() - t0) * 1000
        anchors = ", ".join(f"{k}={m.score:.2f}" for k, m in result.matches.items())
        print(f"{path}: {result.screen} ({ms:.1f}ms) [{anchors}]")
    return 0


def cmd_screen(args) -> int:
    from cob.screens import ScreenClassifier
    from cob.vision.frame import Frame

    clf = ScreenClassifier(_store(args))
    result = clf.classify(Frame(_open_device(args.serial).capture()))
    anchors = ", ".join(f"{k}={m.score:.2f}" for k, m in result.matches.items())
    print(f"{result.screen} [{anchors}]")
    return 0


def cmd_home(args) -> int:
    from cob.screens import ScreenClassifier
    from cob.screens.navigator import NavConfig, Navigator

    clf = ScreenClassifier(_store(args))
    nav = Navigator(_open_device(args.serial), clf, NavConfig(timeout_s=args.timeout))
    t0 = time.perf_counter()
    result = nav.go_home()
    print(f"{'HOME' if result.ok else 'FAILED'} in {time.perf_counter() - t0:.1f}s; "
          f"steps: {' > '.join(result.steps) or '(none)'}")
    return 0 if result.ok else 1


def cmd_search(args) -> int:
    from cob.attack.loot import LootReader
    from cob.core.config import default_path, load_farm_config
    from cob.screens import ScreenClassifier
    from cob.screens.navigator import Navigator
    from cob.tasks.search import SearchTask
    from cob.vision.ocr import DigitReader
    from cob.vision.regions import load_regions

    store = _store(args)
    regions = load_regions(store.root)
    digits = DigitReader(store.load_dir("digits/loot"))
    cfg = load_farm_config()
    if args.max_nexts is not None:
        cfg = replace(cfg, max_nexts=args.max_nexts)
    print(f"farm config ({default_path()}): {cfg}")
    nav = Navigator(_open_device(args.serial), ScreenClassifier(store))
    task = SearchTask(nav, LootReader(digits, regions["loot"]), LootReader(digits, regions["bar"]), cfg)
    out = task.run(dry_run=True)
    for i, loot in enumerate(out.seen, 1):
        print(f"  base {i}: {loot}")
    print(f"{out.status} after {out.nexts} nexts: {out.loot or '-'}; own gold {out.own_gold}; "
          f"best skipped {out.best_skipped or '-'}{'; ' + out.reason if out.reason else ''}")
    return 0 if out.status in ("accepted", "max_nexts") else 1


def cmd_attack(args) -> int:
    """One farm cycle: search with the loot filter, attack the accepted base, return home."""
    from cob.tasks.wiring import build_farm

    parts = build_farm(args.serial, Path(args.templates) if args.templates else None)
    search, attack = parts.search, parts.attack
    t0 = time.perf_counter()
    found = search.run(dry_run=False)
    print(f"search {found.status} after {found.nexts} nexts: {found.loot or '-'}")
    if not found.attack:
        return 1
    out = attack.run()
    reason = f"; {out.reason}" if out.reason else ""
    print(f"attack {out.status} on edge {out.edge} ({out.points} points, {out.taps} taps), "
          f"deployed {out.deployed}, ended by {out.ended_by or '-'} at ~{out.damage:.0f}% damage "
          f"in {time.perf_counter() - t0:.0f}s{reason}")
    return 0 if out.status == "done" else 1


def cmd_farm(args) -> int:
    from cob.core.profiles import Profiles
    from cob.tasks.wiring import build_farm, farm_limits

    store = Profiles()
    profile = store.get(args.profile) if args.profile else store.active
    if profile is None:
        print(f"no profile {args.profile!r}; `cob profiles` lists them", file=sys.stderr)
        return 2
    serial = args.serial or profile.serial
    if not serial:
        print(f"profile {profile.name!r} has no device: pass -s SERIAL", file=sys.stderr)
        return 2
    cfg = store.load_config(profile.id)
    parts = build_farm(serial, Path(args.templates) if args.templates else None, cfg=cfg, profile=profile.id)
    recover = parts.recover
    limits = farm_limits(cfg, args.cycles, args.minutes, profile=profile.id)
    print(f"profile {profile.name} ({profile.id}) on {serial}")
    breaks = (f"break ~{limits.break_minutes:g} min every ~{limits.break_every} cycles"
              if limits.break_every else "no breaks")
    print(f"farming: {args.cycles or 'unlimited'} cycles, {args.minutes or 'no'} minute limit, {breaks}, "
          f"emulator relaunch {'on' if recover else 'off'}; Ctrl+C stops after saving stats")
    task = parts.farm_task(limits)
    stats = task.run()
    g = stats.gained
    print()
    print(f"{len(stats.cycles)} cycles, {stats.attacks} attacks in {stats.seconds / 60:.1f} min "
          f"({stats.stop_reason})")
    print(f"net gain: gold {g.gold:+,} elixir {g.elixir:+,} dark {g.dark:+,}")
    if stats.attacks:
        per_hour = 3600 / max(stats.seconds, 1)
        print(f"per hour: gold {g.gold * per_hour:+,.0f} elixir {g.elixir * per_hour:+,.0f} "
              f"dark {g.dark * per_hour:+,.0f}")
    return 0 if stats.attacks else 1


def cmd_profiles(_args) -> int:
    """List the profiles (#2): id, name, device, player tag, whether it runs in turn; * = active."""
    from cob.core.profiles import Profiles

    store = Profiles()
    for p in store.profiles:
        mark = "*" if p.id == store.active_id else " "
        print(f"{mark} {p.id:<20} {p.name:<24} {p.serial or '-':<24} {p.player_tag or '-':<12} "
              f"{'in turn' if p.rotation else ''}")
    return 0


def cmd_logs(args) -> int:
    """List session logs, or print / follow one (watch a running bot from a second terminal)."""
    from cob.core.log import log_dir, sessions_dir

    files = sorted(sessions_dir().glob("session-*.log"))
    if not args.follow and not args.show:
        print(f"logs folder: {log_dir()}")
        for f in files[-args.last:]:
            print(f"  {f.name}  {f.stat().st_size / 1024:8.1f} KB")
        return 0
    if not files:
        print("no session logs yet")
        return 1
    target = files[-1]  # newest = the running (or last) bot session
    with target.open(encoding="utf-8", errors="replace") as f:
        print(f"== {target}")
        print(f.read(), end="", flush=True)  # flush: output may be a pipe or file, not a console
        while args.follow:
            line = f.readline()
            if line:
                print(line, end="", flush=True)
            else:
                time.sleep(0.5)
    return 0


def cmd_gui(_args) -> int:
    from cob.ui.app import run_gui

    return run_gui()


def cmd_bb(args) -> int:
    """Builder Base attacks (two-stage battles), then back to the home village."""
    from cob.attack.geometry import load_attack_config
    from cob.screens import ScreenClassifier
    from cob.screens.navigator import Navigator
    from cob.tasks.builder import BbAttackTask, run_bb

    store = _store(args)
    border, deploy, bar, _ = load_attack_config(store.root)
    nav = Navigator(_open_device(args.serial), ScreenClassifier(store))
    t0 = time.perf_counter()
    results = run_bb(BbAttackTask(nav, border, deploy, bar), args.attacks)
    for i, r in enumerate(results, 1):
        print(f"  attack {i}: {r.status}, stages {r.stages}, deployed {r.deployed}"
              f"{'; ' + r.reason if r.reason else ''}")
    done = sum(r.status == "done" for r in results)
    print(f"{done}/{len(results)} Builder Base attacks done in {(time.perf_counter() - t0) / 60:.1f} min")
    return 0 if done else 1


def cmd_ui_gallery(args) -> int:
    """UI v2 widget gallery; --screenshot renders it offscreen to a PNG (visual review / CI)."""
    from PySide6.QtWidgets import QApplication

    from cob.ui.gallery import build_gallery
    from cob.ui.style import qss

    app = QApplication.instance() or QApplication([])
    qss.apply(app)
    w = build_gallery()
    if args.screenshot:
        w.widget().resize(1280, w.widget().sizeHint().height())
        ok = w.widget().grab().save(args.screenshot)
        print(f"saved {args.screenshot}" if ok else "screenshot failed")
        return 0 if ok else 1
    w.show()
    return app.exec()


def cmd_selftest(_args) -> int:
    """Offline sanity check of the frozen build: imports + raw decode + PNG encode."""
    import struct

    import adbutils  # noqa: F401
    import cv2
    import numpy as np

    from cob.device.screencap import decode_raw

    w, h = 4, 2
    raw = struct.pack("<IIII", w, h, 1, 0) + bytes([10, 20, 30, 255]) * (w * h)
    frame = decode_raw(raw)
    assert frame.shape == (h, w, 3) and tuple(frame[0, 0]) == (30, 20, 10), frame[0, 0]
    ok, _png = cv2.imencode(".png", frame)
    assert ok
    from cob.vision.templates import default_root

    templates = default_root()  # bundled next to the binary, found from any working directory
    assert any(templates.glob("*.png")), f"no templates bundled in {templates}"
    from PySide6 import QtWidgets  # GUI bundled (Nuitka pyside6 plugin)
    from PySide6.QtCore import qVersion

    assert QtWidgets.QApplication is not None
    print(f"selftest ok: cob {__version__}, python {sys.version.split()[0]}, "
          f"numpy {np.__version__}, cv2 {cv2.__version__}, qt {qVersion()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cob", description="Clash of Bots")
    p.add_argument("--version", action="version", version=f"cob {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("devices", help="list adb devices and LDPlayer instances").set_defaults(fn=cmd_devices)

    c = sub.add_parser("capture", help="save one frame")
    c.add_argument("-s", "--serial", required=True)
    c.add_argument("-o", "--out", default="captures")
    c.set_defaults(fn=cmd_capture)

    b = sub.add_parser("bench", help="measure capture/tap latency")
    b.add_argument("-s", "--serial", required=True)
    b.add_argument("-n", type=int, default=20)
    b.add_argument("--tap", action="store_true", help="also bench taps (sends real input)")
    b.set_defaults(fn=cmd_bench)

    r = sub.add_parser("ld-resize", help="set LDPlayer instance to the 1600x900 contract")
    r.add_argument("index", type=int)
    r.set_defaults(fn=cmd_ld_resize)

    pr = sub.add_parser("phone-reset", help="give a phone its own display size and density back")
    pr.add_argument("serial")
    pr.set_defaults(fn=cmd_phone_reset)

    pa = sub.add_parser("pair", help="pair a phone over Wi-Fi (Android 11+ wireless debugging)")
    pa.add_argument("address", help="IP:port from the phone's 'Pair device with pairing code' dialog")
    pa.add_argument("code", help="the 6-digit pairing code")
    pa.set_defaults(fn=cmd_pair)

    sub.add_parser("pair-qr", help="pair a phone by scanning a QR code (Android 11+, same Wi-Fi)"
                   ).set_defaults(fn=cmd_pair_qr)
    sub.add_parser("discover", help="list phones with Wireless debugging on in this network"
                   ).set_defaults(fn=cmd_discover)

    co = sub.add_parser("connect", help="connect to a phone over Wi-Fi")
    co.add_argument("address", help="IP:port, e.g. 192.168.1.5:5555")
    co.set_defaults(fn=cmd_connect)

    wf = sub.add_parser("wifi", help="switch a USB-connected phone to Wi-Fi (adb tcpip)")
    wf.add_argument("serial")
    wf.set_defaults(fn=cmd_wifi)

    def with_templates(sp):
        sp.add_argument("--templates", help="template folder (default assets/templates/1600x900)")
        return sp

    cr = with_templates(sub.add_parser("crop", help="cut a template from a saved frame"))
    cr.add_argument("frame")
    cr.add_argument("name")
    for k in ("x", "y", "w", "h"):
        cr.add_argument(k, type=int)
    cr.add_argument("--pad", type=int, default=40, help="search region padding for the snippet")
    cr.set_defaults(fn=cmd_crop)

    m = with_templates(sub.add_parser("match", help="test a template"))
    m.add_argument("frame", nargs="?")
    m.add_argument("name")
    m.add_argument("-s", "--serial", help="capture live instead of reading FRAME")
    m.add_argument("-t", "--threshold", type=float)
    m.add_argument("--full", action="store_true", help="search whole frame, ignore region")
    m.set_defaults(fn=cmd_match)

    cl = with_templates(sub.add_parser("classify", help="classify saved frames"))
    cl.add_argument("frames", nargs="+")
    cl.set_defaults(fn=cmd_classify)

    sc = with_templates(sub.add_parser("screen", help="classify the live screen"))
    sc.add_argument("-s", "--serial", required=True)
    sc.set_defaults(fn=cmd_screen)

    h = with_templates(sub.add_parser("home", help="navigate back to the home village (sends real input)"))
    h.add_argument("-s", "--serial", required=True)
    h.add_argument("--timeout", type=float, default=240.0)
    h.set_defaults(fn=cmd_home)

    se = with_templates(sub.add_parser(
        "search", help="dry run: search bases until the loot filter passes, then end without attacking"))
    se.add_argument("-s", "--serial", required=True)
    se.add_argument("--max-nexts", type=int, help="override max_nexts from farm.json (each Next costs gold)")
    se.set_defaults(fn=cmd_search)

    at = with_templates(sub.add_parser(
        "attack", help="one farm cycle: search, attack the first base that passes the filter, go home"))
    at.add_argument("-s", "--serial", required=True)
    at.set_defaults(fn=cmd_attack)

    fa = with_templates(sub.add_parser("farm", help="repeat search + attack until a limit or Ctrl+C"))
    fa.add_argument("-s", "--serial", help="device (default: the profile's device)")
    fa.add_argument("-p", "--profile", help="profile id (default: the active profile; `cob profiles`)")
    fa.add_argument("--cycles", type=int, default=5, help="stop after N cycles (0 = no limit, default 5)")
    fa.add_argument("--minutes", type=float, default=0, help="stop after N minutes (0 = no limit)")
    fa.set_defaults(fn=cmd_farm)

    sub.add_parser("profiles", help="list profiles (accounts / devices with their own settings)"
                   ).set_defaults(fn=cmd_profiles)

    gui = sub.add_parser("gui", help="open the window (also: start the exe without arguments)")
    gui.set_defaults(fn=cmd_gui)

    bb = with_templates(sub.add_parser("bb", help="Builder Base attacks (two stages), then back home"))
    bb.add_argument("-s", "--serial", required=True)
    bb.add_argument("--attacks", type=int, default=3)
    bb.set_defaults(fn=cmd_bb)

    lg = sub.add_parser("logs", help="list session logs; --follow watches the running bot's log")
    lg.add_argument("-f", "--follow", action="store_true", help="print the latest session and keep following")
    lg.add_argument("--show", action="store_true", help="print the latest session once")
    lg.add_argument("--last", type=int, default=10, help="how many session files to list")
    lg.set_defaults(fn=cmd_logs)

    ug = sub.add_parser("ui-gallery", help="show the UI v2 widget gallery")
    ug.add_argument("--screenshot", help="render offscreen to this PNG instead of opening a window")
    ug.set_defaults(fn=cmd_ui_gallery)

    sub.add_parser("selftest", help="offline build check").set_defaults(fn=cmd_selftest)
    return p


def launched_by_double_click() -> bool:
    """True when Explorer started us in a fresh console that closes as soon as we exit.

    Our process is then the only one attached to the console; from cmd/PowerShell the shell is too.
    """
    # Non-interactive stdin (CI, pipes) must never block on a pause.
    if sys.platform != "win32" or not sys.stdin or not sys.stdin.isatty():
        return False
    import ctypes

    procs = (ctypes.c_uint * 4)()
    return ctypes.windll.kernel32.GetConsoleProcessList(procs, 4) == 1


def _pause_if_double_clicked() -> None:
    if launched_by_double_click():
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    if not argv:
        # Double-click from Explorer: no args -> the GUI. If it cannot start, show usage instead of
        # argparse's error and keep the console open long enough to read it.
        try:
            return cmd_gui(None)
        except Exception:
            setup_logging()
            log.exception("GUI failed to start")
        parser.print_help()
        print("\nRun commands from cmd or PowerShell in this folder, e.g.:\n  ClashOfBots.exe devices")
        _pause_if_double_clicked()
        return 0
    args = parser.parse_args(argv)
    if args.cmd not in ("selftest", "logs"):  # reading logs must not start a session log of its own
        # Only bot runs get a session file; quick tools (crop, classify, devices) log to cob.log only.
        setup_logging(args.verbose, session=args.cmd in BOT_COMMANDS)
    try:
        return args.fn(args)
    except DeviceError as exc:
        log.error("%s", exc)
        return 2
    except Exception:
        log.exception("unexpected error")
        return 1
    finally:
        _pause_if_double_clicked()
