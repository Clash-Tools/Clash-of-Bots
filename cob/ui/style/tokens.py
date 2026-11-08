"""Design tokens (Material 3, seed #0F766E). Single source for colours, type and spacing.

The module values below are the dark theme with the teal accent. `apply(theme, accent)` rebinds them to
another theme (dark, light, AMOLED) and accent (#102). Widgets read the tokens when they are built and
some modules keep them in import-time constants, so apply() runs at start-up, before any UI module is
imported (cob.ui.app); a change in Settings takes effect after a restart.
"""

from __future__ import annotations

# Surfaces, lowest to highest: depth is shown by stepping through these, not by shadows.
BG = "#081425"
SURFACE_LOWEST = "#040E1F"
SURFACE_LOW = "#111C2D"
SURFACE = "#152031"
SURFACE_HIGH = "#1F2A3C"
SURFACE_HIGHEST = "#2A3548"
SURFACE_BRIGHT = "#2F3A4C"

ON_SURFACE = "#D8E3FB"
ON_SURFACE_VARIANT = "#BDC9C6"
OUTLINE = "#889391"
OUTLINE_VARIANT = "#3E4947"

PRIMARY = "#80D5CB"
ON_PRIMARY = "#003733"
PRIMARY_CONTAINER = "#0F766E"
ON_PRIMARY_CONTAINER = "#A3FAEF"

SECONDARY = "#B9C7DF"
SECONDARY_CONTAINER = "#3C4A5E"
ON_SECONDARY_CONTAINER = "#ABB9D1"

TERTIARY = "#FFB77D"  # warnings, break state, "current step"
TERTIARY_CONTAINER = "#A15600"
ON_TERTIARY_CONTAINER = "#FFE6D5"

ERROR = "#FFB4AB"
ERROR_CONTAINER = "#93000A"
ON_ERROR_CONTAINER = "#FFDAD6"

# Semantic colours used outside the M3 scheme in the designs.
GOLD = "#E0A800"
ELIXIR = "#B847D9"
DARK_ELIXIR = SECONDARY
SUCCESS = "#2DD4BF"

FONT_BODY = "Inter"
FONT_HEADING = "Roboto Flex"
FONT_MONO = "JetBrains Mono"

# Spacing scale (px) and radii.
XS, SM, MD, LG, XL, XXL = 4, 8, 16, 24, 32, 48
# Qt drops a border-radius larger than half the height: pill radius = half of the 52 px CTA height.
RADIUS_SM, RADIUS, RADIUS_CARD, RADIUS_SHEET, RADIUS_PILL = 4, 8, 12, 16, 26

# Shell geometry.
TOPBAR_H, RAIL_W, STATUS_H = 64, 96, 40

# Overlays and dividers: white on dark themes, black on the light one.
OVERLAY_SOFT = "rgba(255,255,255,0.06)"  # icon dots, faint fills
OVERLAY = "rgba(255,255,255,0.12)"  # pressed / selected fills
BORDER_SOFT = "rgba(255,255,255,0.05)"  # input borders
DIVIDER = "rgba(62,73,71,0.4)"
DIVIDER_STRONG = "rgba(62,73,71,0.6)"
WARNING_TINT = "rgba(161,86,0,0.30)"  # warning banner / break pill background
PRIMARY_HOVER = "#138A80"  # primary button hover (container one step lighter)
PRIMARY_TINT = "rgba(128,213,203,0.08)"  # text button hover
DANGER_HOVER = "#B3261E"

THEMES = {
    "dark": {},  # the module defaults above
    "amoled": {  # true black for OLED screens
        "BG": "#000000", "SURFACE_LOWEST": "#000000", "SURFACE_LOW": "#0A0A0A", "SURFACE": "#121212",
        "SURFACE_HIGH": "#1A1A1A", "SURFACE_HIGHEST": "#242424", "SURFACE_BRIGHT": "#2C2C2C",
        "ON_SURFACE": "#E6E6E6", "ON_SURFACE_VARIANT": "#BDBDBD", "OUTLINE": "#8A8A8A",
        "OUTLINE_VARIANT": "#333333", "SECONDARY": "#C4C4C4", "SECONDARY_CONTAINER": "#2A2A2A",
        "ON_SECONDARY_CONTAINER": "#CFCFCF", "DARK_ELIXIR": "#C4C4C4", "DIVIDER": "rgba(255,255,255,0.10)",
        "DIVIDER_STRONG": "rgba(255,255,255,0.16)",
    },
    "light": {
        "BG": "#F5FAF9", "SURFACE_LOWEST": "#FFFFFF", "SURFACE_LOW": "#EEF5F3", "SURFACE": "#E8EFED",
        "SURFACE_HIGH": "#E2E9E7", "SURFACE_HIGHEST": "#D9E1DF", "SURFACE_BRIGHT": "#F5FAF9",
        "ON_SURFACE": "#161D1C", "ON_SURFACE_VARIANT": "#3F4947", "OUTLINE": "#6F7977",
        "OUTLINE_VARIANT": "#BEC9C6", "SECONDARY": "#4A6360", "SECONDARY_CONTAINER": "#CCE8E4",
        "ON_SECONDARY_CONTAINER": "#051F1D", "TERTIARY": "#8A5100", "TERTIARY_CONTAINER": "#FFDCC2",
        "ON_TERTIARY_CONTAINER": "#2D1600", "ERROR": "#BA1A1A", "ERROR_CONTAINER": "#FFDAD6",
        "ON_ERROR_CONTAINER": "#410002", "GOLD": "#A07800", "ELIXIR": "#9C2FBE", "DARK_ELIXIR": "#3B4A63",
        "SUCCESS": "#0F766E",
        "OVERLAY_SOFT": "rgba(0,0,0,0.05)", "OVERLAY": "rgba(0,0,0,0.08)", "BORDER_SOFT": "rgba(0,0,0,0.08)",
        "DIVIDER": "rgba(0,0,0,0.10)", "DIVIDER_STRONG": "rgba(0,0,0,0.16)",
        "WARNING_TINT": "rgba(255,183,125,0.45)", "DANGER_HOVER": "#93000A",
    },
}

# Accent: PRIMARY, ON_PRIMARY, PRIMARY_CONTAINER, ON_PRIMARY_CONTAINER for dark and for light themes.
ACCENTS = {
    "teal": (("#80D5CB", "#003733", "#0F766E", "#A3FAEF"), ("#006A63", "#FFFFFF", "#9DF2E8", "#00201D")),
    "blue": (("#A8C7FA", "#062E6F", "#1F5FBF", "#D6E3FF"), ("#1F5FBF", "#FFFFFF", "#D6E3FF", "#001B3E")),
    "purple": (("#D0BCFF", "#381E72", "#6B4FBB", "#EADDFF"), ("#6750A4", "#FFFFFF", "#EADDFF", "#21005D")),
    "orange": (("#FFB68A", "#522300", "#A04A00", "#FFDBC8"), ("#994700", "#FFFFFF", "#FFDBC8", "#321200")),
    "pink": (("#FFB0C8", "#5E1133", "#A33E66", "#FFD9E2"), ("#A33E66", "#FFFFFF", "#FFD9E2", "#3E001D")),
    "green": (("#9CD67D", "#0C3900", "#3A7A1F", "#B7F397"), ("#3A6A1F", "#FFFFFF", "#B7F397", "#082100")),
}

THEME, ACCENT = "dark", "teal"
_DEFAULTS = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, str)}


def _shade(color: str, factor: float) -> str:
    """#RRGGBB lighter (factor > 1) or darker (< 1)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(c * factor))) for c in (r, g, b)))


def _rgba(color: str, alpha: float) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def apply(theme: str = "dark", accent: str = "teal") -> None:
    """Rebind the colour tokens to `theme` and `accent` (unknown names fall back to dark / teal)."""
    theme = theme if theme in THEMES else "dark"
    accent = accent if accent in ACCENTS else "teal"
    g = globals()
    g.update(_DEFAULTS)
    g.update(THEMES[theme])
    primary, on_primary, container, on_container = ACCENTS[accent][theme == "light"]
    g.update(PRIMARY=primary, ON_PRIMARY=on_primary, PRIMARY_CONTAINER=container,
             ON_PRIMARY_CONTAINER=on_container, THEME=theme, ACCENT=accent,
             PRIMARY_HOVER=_shade(container, 0.92 if theme == "light" else 1.17),
             PRIMARY_TINT=_rgba(primary, 0.08))
