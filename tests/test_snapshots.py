"""#170: failure reports (screen, extra images, log lines, details) and their zip export."""

import json
import logging
import zipfile

import numpy as np

from cob.core.snapshots import RecentLines, export_reports, list_reports, save_snapshot, snapshot_dir


def test_report_folder_has_screen_images_log_and_details(tmp_path):
    handler = RecentLines()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("cob.test_reports")
    logger.addHandler(handler)
    try:
        logger.warning("deploy refused at (10, 20)")
    finally:
        logger.removeHandler(handler)
    frame = np.zeros((10, 10, 3), np.uint8)
    path = save_snapshot(frame, "attack failed: no room/deploy", folder=tmp_path,
                         details={"edge": "top_left"}, images={"base": frame})
    assert path is not None and path.name == "screen.png" and path.is_file()
    report = path.parent
    assert " " not in report.name and "/" not in report.name
    assert (report / "base.png").is_file()
    assert "deploy refused at (10, 20)" in (report / "log.txt").read_text("utf-8")
    info = json.loads((report / "report.json").read_text("utf-8"))
    assert info["label"] == "attack failed: no room/deploy" and info["details"] == {"edge": "top_left"}


def test_reports_are_pruned_and_same_second_ones_kept_apart(tmp_path):
    frame = np.zeros((10, 10, 3), np.uint8)
    paths = [save_snapshot(frame, "same", folder=tmp_path) for _ in range(4)]
    assert all(paths) and len({p.parent for p in paths}) == 4
    save_snapshot(frame, "same", folder=tmp_path, keep=3)
    assert len(list_reports(tmp_path)) == 3


def test_snapshot_dir_is_in_isolated_user_data():
    assert "localappdata" in str(snapshot_dir()) or "xdg" in str(snapshot_dir())


def test_snapshot_never_raises(tmp_path):
    assert save_snapshot(None, "bad", folder=tmp_path) is None


def test_export_zips_reports_with_text_sanitized(tmp_path):
    frame = np.zeros((10, 10, 3), np.uint8)
    reports = tmp_path / "reports"
    reports.mkdir()
    save_snapshot(frame, "one", folder=reports, details={"addr": "192.168.0.153:42197"})
    log = tmp_path / "session.log"
    log.write_text("connected 192.168.0.153:42197\n", "utf-8")
    dest = tmp_path / "out.zip"
    assert export_reports(dest, folder=reports, logs=[log]) == 1
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
        assert any(n.endswith("/screen.png") for n in names) and "logs/session.log" in names
        text = "".join(z.read(n).decode() for n in names if n.endswith((".json", ".log", ".txt")))
    assert "192.168.0.153" not in text and "<ip>" in text


def test_other_apps_are_not_kept_in_reports(tmp_path):
    # Live 2026-11-05: the user picked up the phone mid-battle and the report kept a social-media profile.
    import cv2

    class Phone:
        def __init__(self, package):
            self.package = package

        def foreground_package(self):
            return self.package

    frame = np.full((10, 10, 3), 200, np.uint8)
    path = save_snapshot(frame, "other", folder=tmp_path, device=Phone("com.instagram.android"))
    assert path is not None and not (cv2.imread(str(path)) == 200).all()
    info = json.loads((path.parent / "report.json").read_text("utf-8"))
    assert info["details"]["foreground_app"] == "com.instagram.android"
    game = save_snapshot(frame, "game", folder=tmp_path, device=Phone("com.supercell.clashofclans"))
    assert (cv2.imread(str(game)) == 200).all()


def test_the_notification_shade_is_not_kept_either(tmp_path):
    # #178 live: the shade over the game showed a bank message; the game still had the app focus.
    import cv2

    from cob.device.adb import AdbDevice

    dev = AdbDevice.__new__(AdbDevice)
    dev.serial = "x"
    dev._shell = lambda cmd: "  mCurrentFocus=Window{c1f4e7e u0 NotificationShade}\n"
    assert dev.foreground_package() == "NotificationShade"
    frame = np.full((10, 10, 3), 200, np.uint8)
    path = save_snapshot(frame, "shade", folder=tmp_path, device=dev)
    assert not (cv2.imread(str(path)) == 200).all()
    dev._shell = lambda cmd: "  mCurrentFocus=Window{33292f5 u0 com.supercell.clashofclans/com.x.GameApp}\n"
    assert dev.foreground_package() == "com.supercell.clashofclans"
