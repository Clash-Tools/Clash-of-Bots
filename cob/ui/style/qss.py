"""Application stylesheet generated from the tokens (D-026). Widgets opt in through objectName or
dynamic properties (card, role, chip, tone) so plain Qt widgets keep a sensible default look."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from cob.ui.style import tokens as t
from cob.ui.style.fonts import load_fonts


def _arrow_file() -> str:
    """QSS can only show images from files: write the tinted dropdown arrow once to the cache folder."""
    from cob.core.paths import user_data_dir
    from cob.ui.style.icons import pixmap

    path = user_data_dir() / "cache" / f"expand_more_{t.ON_SURFACE_VARIANT.lstrip('#')}.png"  # per theme
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        pixmap("expand_more", 18, t.ON_SURFACE_VARIANT, dpr=1.0).save(str(path))
    return path.as_posix()


def stylesheet() -> str:
    arrow = _arrow_file()
    return f"""
QWidget {{ color: {t.ON_SURFACE}; font-family: "{t.FONT_BODY}"; font-size: 14px; }}
QMainWindow, QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t.BG}; }}
QWidget#topbar {{ background: {t.SURFACE_LOW}; border-bottom: 1px solid {t.DIVIDER}; }}
QWidget#rail {{ background: {t.SURFACE_LOW}; }}
QWidget#statusStrip {{ background: {t.SURFACE_LOWEST}; border-top: 1px solid {t.DIVIDER}; }}
QWidget#statusStrip QLabel {{ color: {t.ON_SURFACE_VARIANT}; font-size: 11px; }}

QFrame[card="true"] {{ background: {t.SURFACE}; border-radius: {t.RADIUS_CARD}px; }}
QFrame[card="low"] {{ background: {t.SURFACE_LOW}; border-radius: {t.RADIUS_CARD}px; }}
QFrame[card="well"] {{ background: {t.SURFACE_LOWEST}; border-radius: {t.RADIUS}px; }}
QFrame[card] QLabel {{ background: transparent; }}

QLabel[role="display"] {{ font-family: "{t.FONT_HEADING}"; font-size: 32px; font-weight: 700; }}
QLabel[role="headline"] {{ font-family: "{t.FONT_HEADING}"; font-size: 24px; font-weight: 600; }}
QLabel[role="title"] {{ font-family: "{t.FONT_HEADING}"; font-size: 18px; font-weight: 600; }}
QLabel[role="eyebrow"] {{ font-size: 11px; font-weight: 600; color: {t.ON_SURFACE_VARIANT}; letter-spacing: 1px; }}
QLabel[role="eyebrowAccent"] {{ font-size: 11px; font-weight: 600; color: {t.PRIMARY}; letter-spacing: 1px; }}
QLabel[role="muted"] {{ color: {t.ON_SURFACE_VARIANT}; font-size: 12px; }}
QLabel[role="stat"] {{ font-family: "{t.FONT_MONO}"; font-size: 28px; font-weight: 600; }}
QLabel[role="mono"] {{ font-family: "{t.FONT_MONO}"; font-size: 12px; color: {t.ON_SURFACE_VARIANT}; }}
QLabel[role="tag"] {{ background: {t.SURFACE_HIGH}; color: {t.ON_SURFACE_VARIANT}; border-radius: {t.RADIUS_SM}px;
                     padding: 2px 8px; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}

QPushButton, QToolButton {{ background: {t.SURFACE_HIGH}; color: {t.ON_SURFACE}; border: none;
                          border-radius: {t.RADIUS}px; padding: 8px 14px; font-weight: 500; }}
QPushButton:hover, QToolButton:hover {{ background: {t.SURFACE_HIGHEST}; }}
QPushButton:pressed {{ background: {t.SURFACE_BRIGHT}; }}
QPushButton:disabled, QToolButton:disabled {{ background: {t.SURFACE_HIGH}; color: {t.OUTLINE}; }}
QPushButton#primary {{ background: {t.PRIMARY_CONTAINER}; color: {t.ON_PRIMARY_CONTAINER};
                      border-radius: {t.RADIUS_PILL}px; min-height: 52px; padding: 0 28px; font-weight: 700;
                      font-size: 14px; letter-spacing: 1px; }}
QPushButton#primary:hover {{ background: {t.PRIMARY_HOVER}; }}
QPushButton#primary:disabled {{ background: {t.SURFACE_HIGHEST}; color: {t.OUTLINE}; }}
QPushButton#danger {{ background: {t.ERROR_CONTAINER}; color: {t.ON_ERROR_CONTAINER};
                     border-radius: {t.RADIUS_PILL}px; min-height: 52px; padding: 0 28px; font-weight: 700;
                     font-size: 14px; letter-spacing: 1px; }}
QPushButton#danger:hover {{ background: {t.DANGER_HOVER}; }}
QPushButton#tonal {{ background: {t.SECONDARY_CONTAINER}; color: {t.ON_SURFACE}; }}
QPushButton#text {{ background: transparent; color: {t.PRIMARY}; padding: 6px 8px; }}
QPushButton#text:hover {{ background: {t.PRIMARY_TINT}; }}
QPushButton[chip="true"] {{ background: {t.SURFACE_HIGH}; color: {t.ON_SURFACE_VARIANT}; border-radius: 12px;
                          padding: 4px 12px; font-size: 12px; min-height: 16px; }}
QPushButton[chip="true"]:checked {{ background: {t.SECONDARY_CONTAINER}; color: {t.ON_SURFACE}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit, QDateEdit {{
    background: {t.SURFACE_HIGHEST}; border: 1px solid {t.BORDER_SOFT}; border-radius: {t.RADIUS}px;
    padding: 8px 12px; selection-background-color: {t.PRIMARY_CONTAINER}; }}
QSpinBox, QDoubleSpinBox, QLineEdit[mono="true"] {{ font-family: "{t.FONT_MONO}"; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {t.PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url("{arrow}"); width: 18px; height: 18px; }}
QComboBox QAbstractItemView {{ background: {t.SURFACE_HIGH}; border: 1px solid {t.OUTLINE_VARIANT};
                              selection-background-color: {t.SECONDARY_CONTAINER}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

QTableView, QTableWidget {{ background: transparent; border: none; gridline-color: transparent;
                          alternate-background-color: {t.SURFACE_LOW}; selection-background-color: {t.SECONDARY_CONTAINER}; }}
QHeaderView::section {{ background: {t.SURFACE_HIGH}; color: {t.ON_SURFACE_VARIANT}; font-size: 11px; font-weight: 600;
                       border: none; padding: 10px 12px; }}
QPlainTextEdit, QTextEdit {{ background: {t.SURFACE_LOWEST}; border: none; border-radius: {t.RADIUS}px;
                            font-family: "{t.FONT_MONO}"; font-size: 12px; padding: 8px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t.SURFACE_HIGHEST}; border-radius: 4px; min-height: 32px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t.SURFACE_HIGHEST}; border-radius: 4px; min-width: 32px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QToolTip {{ background: {t.SURFACE_HIGHEST}; color: {t.ON_SURFACE}; border: none; padding: 6px 8px; }}
QProgressBar {{ background: {t.SURFACE_HIGHEST}; border: none; border-radius: 3px; max-height: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {t.PRIMARY}; border-radius: 3px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 2px solid {t.OUTLINE}; }}
QCheckBox::indicator:checked {{ background: {t.PRIMARY}; border-color: {t.PRIMARY}; }}
QMenu {{ background: {t.SURFACE_HIGH}; border: 1px solid {t.OUTLINE_VARIANT}; padding: 4px; }}
QMenu::item:selected {{ background: {t.SECONDARY_CONTAINER}; }}
"""


def apply(app: QApplication) -> None:
    """Fonts + Fusion palette (for widgets QSS does not reach) + stylesheet."""
    load_fonts()
    app.setStyle("Fusion")
    p = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, t.BG), (QPalette.ColorRole.WindowText, t.ON_SURFACE),
        (QPalette.ColorRole.Base, t.SURFACE_HIGHEST), (QPalette.ColorRole.AlternateBase, t.SURFACE_LOW),
        (QPalette.ColorRole.Text, t.ON_SURFACE), (QPalette.ColorRole.Button, t.SURFACE_HIGH),
        (QPalette.ColorRole.ButtonText, t.ON_SURFACE), (QPalette.ColorRole.Highlight, t.PRIMARY_CONTAINER),
        (QPalette.ColorRole.HighlightedText, t.ON_PRIMARY_CONTAINER), (QPalette.ColorRole.Link, t.PRIMARY),
        (QPalette.ColorRole.ToolTipBase, t.SURFACE_HIGHEST), (QPalette.ColorRole.ToolTipText, t.ON_SURFACE),
        (QPalette.ColorRole.PlaceholderText, t.OUTLINE),
    ):
        p.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.OUTLINE))
    app.setPalette(p)
    app.setStyleSheet(stylesheet())
