"""Reusable UI v2 widgets matching the Stitch design system (docs/design/stitch/SCREENS.md section 5)."""

from cob.ui.widgets.basic import (
    Banner,
    Card,
    Chip,
    IconLabel,
    StatTile,
    StatusPill,
    UnsavedBar,
    eyebrow,
    hline,
    label,
)
from cob.ui.widgets.controls import NumberField, SegmentedControl, Switch, ToggleRow
from cob.ui.widgets.pipeline import StepPipeline
from cob.ui.widgets.tabs import CategoryTabs

__all__ = [
    "Banner", "Card", "CategoryTabs", "Chip", "IconLabel", "NumberField", "SegmentedControl", "StatTile",
    "StatusPill", "StepPipeline", "Switch", "ToggleRow", "UnsavedBar", "eyebrow", "hline", "label",
]
