"""Devices & Wireless Pairing (#50, prototype flow "Desktop 2"): connected devices, phones found on the
network, QR pairing and the other connection methods. Health checks have their own page (#100).

The widgets keep the names the window used before (check_grid, wifi_address, …); MainWindow wires them.
Battery / latency tiles from the design are left out (no data yet, SCREENS.md 4.7)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cob.core.i18n import tr
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets import Card, IconLabel
from cob.ui.widgets import label as text


def device_icon(serial: str) -> str:
    if serial.startswith("emulator-"):
        return "desktop_windows"
    if ":" in serial or "._adb-tls-connect" in serial:
        return "wifi_tethering"
    return "usb"


def short_serial(serial: str) -> str:
    """adb's mDNS names are long: "adb-AB12CD34EF-x1Yz9Q._adb-tls-connect._tcp" -> "AB12CD34EF (Wi-Fi)"."""
    if "._adb-tls-connect" in serial and serial.startswith("adb-"):
        return tr("{serial} (Wi-Fi)", serial=serial[4:].split("-")[0])
    return serial


class _Row(QFrame):
    """List row: icon, title + subtitle, optional state tag, optional action button."""

    def __init__(self, icon_name: str, title: str, subtitle: str, tag: str = "", action: str = "",
                 accent: bool = False):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background: {t.SURFACE_HIGH if accent else t.SURFACE_LOW}; "
                           f"border-radius: {t.RADIUS_CARD}px; }} QLabel {{ background: transparent; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(t.MD, t.SM + 2, t.SM + 2, t.SM + 2)
        lay.setSpacing(t.MD)
        lay.addWidget(IconLabel(icon_name, 22, t.PRIMARY if accent else t.ON_SURFACE_VARIANT))
        texts = QVBoxLayout()
        texts.setSpacing(2)
        head = text(title)
        head.setStyleSheet("font-weight: 600;")
        texts.addWidget(head)
        texts.addWidget(text(subtitle, "mono"))
        lay.addLayout(texts, 1)
        if tag:
            lay.addWidget(text(tag.upper(), "tag"))
        self.button = QPushButton(action) if action else None
        if self.button:
            lay.addWidget(self.button)


class DevicesPage(QWidget):
    use_device = Signal(str)
    connect_address = Signal(str)
    refresh = Signal()  # Recheck: USB phones and LDPlayer instances (#100)

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(t.LG)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(text(tr("Devices & Wireless Pairing"), "headline"))
        titles.addWidget(text(tr("LDPlayer instances, USB phones and phones on your Wi-Fi."), "muted"))
        head.addLayout(titles, 1)
        self.qr_button = QPushButton("  " + tr("ADD DEVICE (SCAN QR)"), objectName="primary")
        self.qr_button.setIcon(icon("phone_android", t.ON_PRIMARY_CONTAINER, 20))
        self.qr_button.setToolTip(tr("Android 11+: pair a phone on the same Wi-Fi by scanning a QR code"))
        head.addWidget(self.qr_button, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(t.LG)
        left = QVBoxLayout()
        left.setSpacing(t.LG)
        right = QVBoxLayout()
        right.setSpacing(t.LG)
        cols.addLayout(left, 7)
        cols.addLayout(right, 5)
        root.addLayout(cols)

        self.connected_card = Card(tr("Connected"), "devices")
        self.recheck_button = QPushButton("  " + tr("Recheck"))
        self.recheck_button.setIcon(icon("refresh", t.ON_SURFACE, 18))
        self.recheck_button.setToolTip(tr("Look again for USB phones and LDPlayer (also reconnects Wi-Fi "
                                          "phones)"))
        self.recheck_button.clicked.connect(self.refresh)
        self.connected_card.header.addWidget(self.recheck_button)
        self.connected_box = QVBoxLayout()
        self.connected_box.setSpacing(t.SM)
        self.connected_card.body.addLayout(self.connected_box)
        left.addWidget(self.connected_card)

        nearby = Card(tr("Found on your network"), "travel_explore")
        self.find_button = QPushButton("  " + tr("Find"))
        self.find_button.setIcon(icon("refresh", t.ON_SURFACE, 18))
        nearby.header.addWidget(self.find_button)
        self.nearby_box = QVBoxLayout()
        self.nearby_box.setSpacing(t.SM)
        nearby.body.addLayout(self.nearby_box)
        self.nearby_hint = text(tr("Phones with Wireless debugging on, on the same Wi-Fi. Press Find."),
                                "muted", wrap=True)
        nearby.body.addWidget(self.nearby_hint)
        left.addWidget(nearby)

        other = Card(tr("Other ways to connect"), "cable")
        grid = QGridLayout()
        grid.setHorizontalSpacing(t.SM)
        grid.setVerticalSpacing(t.SM)
        self.pair_address = QLineEdit(placeholderText=tr("IP:port from 'Pair device with pairing code'"))
        self.pair_code = QLineEdit(placeholderText=tr("6-digit code"), maxLength=6)
        self.pair_code.setFixedWidth(140)
        self.pair_button = QPushButton(tr("Pair"))
        grid.addWidget(text(tr("PAIRING CODE"), "eyebrow"), 0, 0, 1, 3)
        grid.addWidget(self.pair_address, 1, 0)
        grid.addWidget(self.pair_code, 1, 1)
        grid.addWidget(self.pair_button, 1, 2)
        self.wifi_address = QLineEdit(placeholderText=tr("192.168.1.5:5555 (Wireless debugging: IP & port)"))
        self.connect_button = QPushButton(tr("Connect"))
        grid.addWidget(text(tr("CONNECT BY ADDRESS"), "eyebrow"), 2, 0, 1, 3)
        grid.addWidget(self.wifi_address, 3, 0, 1, 2)
        grid.addWidget(self.connect_button, 3, 2)
        other.body.addLayout(grid)
        usb = QHBoxLayout()
        self.wifi_button = QPushButton("  " + tr("Switch USB phone to Wi-Fi"))
        self.wifi_button.setIcon(icon("wifi_tethering", t.ON_SURFACE, 18))
        self.restore_button = QPushButton("  " + tr("Restore phone screen"))
        self.restore_button.setIcon(icon("restart_alt", t.ON_SURFACE, 18))
        self.restore_button.setToolTip(tr("Put back the phone's own screen size, density, rotation and "
                                          "screen-on setting (saved before the bot first changed them)"))
        usb.addWidget(self.wifi_button)
        usb.addWidget(self.restore_button)
        usb.addStretch(1)
        other.body.addLayout(usb)
        self.phone_status = text("", "muted", wrap=True)
        other.body.addWidget(self.phone_status)
        left.addStretch(1)

        right.addWidget(other)
        right.addStretch(1)

    # --- lists ----------------------------------------------------------------------------------

    @staticmethod
    def _clear(box: QVBoxLayout) -> None:
        # Detach now: deleteLater alone leaves the old rows painted until the next event loop turn.
        while box.count():
            item = box.takeAt(0)
            if w := item.widget():
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def set_devices(self, devices: list[tuple[str, str]], current: str | None) -> None:
        self._clear(self.connected_box)
        real = [(label, serial) for label, serial in devices if serial]
        for label, serial in real:
            selected = serial == current
            row = _Row(device_icon(serial), label, serial, tr("in use") if selected else "",
                       "" if selected else tr("Use"), accent=selected)
            if row.button:
                row.button.clicked.connect(lambda _=False, s=serial: self.use_device.emit(s))
            self.connected_box.addWidget(row)
        if not real:
            hint = tr("No device yet: start LDPlayer, plug in a phone with USB debugging, or add a phone "
                      "with the QR code.")
            self.connected_box.addWidget(text(hint, "muted", wrap=True))

    def set_nearby(self, found) -> None:
        """found: discovery.Nearby list."""
        self._clear(self.nearby_box)
        for n in found:
            s = n.service
            state = tr("connected") if n.connected else tr("used before") if n.known else tr("new")
            row = _Row("phone_android", s.serial or s.name, s.address, state,
                       "" if n.connected else tr("Connect"), accent=n.connected)
            if row.button:
                row.button.clicked.connect(lambda _=False, a=s.address: self.connect_address.emit(a))
            self.nearby_box.addWidget(row)
        self.nearby_hint.setText(tr("{n} phone(s) with Wireless debugging on.", n=len(found)) if found else
                                 tr("No phone found: same Wi-Fi? Wireless debugging on? (guest Wi-Fi and "
                                    "VPNs block this)"))
