"""Category tabs: a list of categories on the left, one section shown at a time on the right (#101).

Used by settings-style pages instead of one long scrolling column."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from cob.core.i18n import tr
from cob.ui.style import tokens as t
from cob.ui.style.icons import icon
from cob.ui.widgets.basic import Card


class CategoryTabs(QWidget):
    changed = Signal(str)  # key of the category now shown

    def __init__(self, categories: list[tuple[str, str, str, str]], title: str = tr("Categories"),
                 list_width: int = 280):
        """categories: (key, icon, title, subtitle) in display order; add a section per key with add()."""
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(t.LG)
        card = Card(title, tone="low", padding=t.MD)
        card.setFixedWidth(list_width)
        self.buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for key, ic, name, subtitle in categories:
            # "&" marks a keyboard mnemonic in button text: double it to show it.
            b = QPushButton(f"  {name}\n  {subtitle}".replace("&", "&&"))
            b.setCheckable(True)
            b.setIcon(icon(ic, t.ON_SURFACE_VARIANT, 20))
            b.setStyleSheet(f"QPushButton {{ text-align: left; background: transparent; padding: 8px 10px; "
                            f"border-radius: 12px; color: {t.ON_SURFACE}; }} "
                            f"QPushButton:hover {{ background: {t.SURFACE_HIGH}; }} "
                            f"QPushButton:checked {{ background: {t.SECONDARY_CONTAINER}; "
                            f"color: {t.ON_SECONDARY_CONTAINER}; }}")
            b.clicked.connect(lambda _=False, k=key: self.open(k))
            self._group.addButton(b)
            card.body.addWidget(b)
            self.buttons[key] = b
        card.body.addStretch(1)
        lay.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        # Not a QStackedWidget: that is as tall as its tallest page, which stretched short sections.
        # Hidden widgets take no room in a box layout, so the open section keeps its own height.
        self.stack = QWidget()
        self._column = QVBoxLayout(self.stack)
        self._column.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack, 1, Qt.AlignmentFlag.AlignTop)
        self.sections: dict[str, QWidget] = {}
        self._first = categories[0][0] if categories else None
        self._current = self._first

    def add(self, key: str, widget: QWidget) -> QWidget:
        self.sections[key] = widget
        self._column.addWidget(widget)
        widget.hide()
        if key == self._first:
            self.open(key)
        return widget

    def open(self, key: str) -> None:  # not show(): that is QWidget's own method
        for k, w in self.sections.items():
            w.setVisible(k == key)
        self._current = key
        self.buttons[key].setChecked(True)
        self.changed.emit(key)

    def current(self) -> str:
        return self._current

    def set_visible(self, key: str, visible: bool) -> None:
        """Show or hide a category (feature flags); hiding the open one opens the first visible one."""
        self.buttons[key].setVisible(visible)
        if not visible and self._current == key:
            first = next((k for k, b in self.buttons.items() if k != key and not b.isHidden()), None)
            if first in self.sections:
                self.open(first)
