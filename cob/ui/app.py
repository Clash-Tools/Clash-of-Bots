"""GUI entry point: `cob gui`, or the exe started without arguments (double-click)."""

from __future__ import annotations

import logging
import sys

from cob.core.log import setup_logging


def run_gui(argv: list[str] | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from cob.core import i18n, ui_settings
    from cob.ui.style import tokens

    # Before any widget module is imported: some keep token colours and translated labels in
    # import-time constants (#102, #103).
    prefs = ui_settings.load()
    tokens.apply(prefs.theme, prefs.accent)
    i18n.set_language(prefs.language)

    from cob.core.i18n import tr
    from cob.ui.log_bridge import LogBridge, QtLogHandler
    from cob.ui.main_window import MainWindow, reconnect_wifi
    from cob.ui.shell import logo_icon
    from cob.ui.style import qss

    setup_logging()
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    qss.apply(app)
    app.setWindowIcon(logo_icon())
    bridge = LogBridge()
    handler = QtLogHandler(bridge)
    logging.getLogger().addHandler(handler)
    window = MainWindow(tray=True, background_refresh=True, reconnect=reconnect_wifi)
    window.connect_log(bridge)
    if window.ui_settings.start_minimized and window.tray is not None:
        window.tray.showMessage("Clash of Bots",
                                tr("Running in the tray. Click the icon to open the window."))
    else:
        window.show()
    if not window.ui_settings.wizard_done:
        window.open_wizard()  # first start: guide to a working device (#51)
    try:
        return app.exec()
    finally:
        logging.getLogger().removeHandler(handler)
