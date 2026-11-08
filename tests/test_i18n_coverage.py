"""#141: with a pseudo-translation catalog, no English is left on any page.

Runs in a subprocess: module-level labels are translated at import, so the language has to be set before
the UI is imported, as cob.ui.app does at start-up."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = r'''
import json, os, re, sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from scripts.i18n import strings
from cob.core import i18n

folder = Path(sys.argv[2])
folder.mkdir(parents=True, exist_ok=True)
pseudo = {"_language": "Pseudo", **{k: "⟦" + k + "⟧" for k in strings()}}
(folder / "zz.json").write_text(json.dumps(pseudo), "utf-8")
i18n.catalog_dir = lambda: folder
assert i18n.set_language("zz") == "zz"

from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QGroupBox, QLabel, QLineEdit,
                               QTableWidget, QTextEdit, QWidget)

app = QApplication([])
from cob.ui.main_window import MainWindow
from cob.ui.wizard import SetupWizard

# The QR dialog starts a pairing session when built, so it is left out here (its strings are module
# constants and the title, checked by the extractor test like every other tr() call).
nothing = lambda *a: None
roots = [MainWindow(devices=lambda: [("Phone", "AB12CD34EF")]),
         SetupWizard(None, lambda: [("Phone", "AB12CD34EF")], nothing, nothing, nothing, nothing, nothing)]

texts = []
for root in roots:
    for w in [root, *root.findChildren(QWidget)]:
        if isinstance(w, (QLabel, QAbstractButton)):
            texts.append(w.text())
        if isinstance(w, QLineEdit):
            texts.append(w.placeholderText())
        if isinstance(w, QTextEdit):
            texts.append(w.placeholderText())
        if isinstance(w, QGroupBox):
            texts.append(w.title())
        if isinstance(w, QComboBox):
            texts += [w.itemText(i) for i in range(w.count())]
        if isinstance(w, QTableWidget):
            for i in range(w.columnCount()):
                item = w.horizontalHeaderItem(i)
                texts.append(item.text() if item else "")
        texts.append(w.toolTip())
        texts.append(w.windowTitle())

ALLOWED = set(sys.argv[3].split("|"))
left = set()
for t in texts:
    if t.startswith(("/", "http")) or ":\\" in t:  # paths and links
        continue
    rest = re.sub("⟦.*?⟧", " ", t, flags=re.S)
    rest = re.sub(r"<[^>]+>|&\w+;", " ", rest)  # rich-text tags and entities
    rest = re.sub(r"\S*[/\\]\S*", " ", rest)  # embedded paths
    for word in re.findall(r"\w+", rest):
        if re.search(r"[A-Za-z]{3,}", word) and word not in ALLOWED:
            left.add(t.strip())
            break
assert len([t for t in texts if t]) > 300, len(texts)  # the walk really saw the pages
print(json.dumps(sorted(left)))
'''

# Names, not words: product, emulator and device names, the test device's serial, and language names
# (each language is listed in its own language).
ALLOWED = ["Clash", "Bots", "LDPlayer", "Phone", "AB12CD34EF", "ADB", "USB", "GitHub", "English", "Pseudo",
           "ABC123"]  # + the player-tag placeholder


def test_no_english_left_with_a_pseudo_catalog(tmp_path):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "XDG_DATA_HOME": str(tmp_path / "data"),
           "LOCALAPPDATA": str(tmp_path / "data")}
    run = subprocess.run([sys.executable, "-c", PROBE, str(ROOT), str(tmp_path / "i18n"), "|".join(ALLOWED)],
                         capture_output=True, text=True, env=env, cwd=ROOT, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    left = json.loads(run.stdout.strip().splitlines()[-1])
    assert left == [], "untranslated text:\n" + "\n".join(left)
