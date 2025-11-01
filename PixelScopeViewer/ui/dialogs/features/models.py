"""Backward-compatible shim for moved table models.

The concrete implementations now live in
`PixelScopeViewer.ui.dialogs.features.widgets.tables`.
"""

from .widgets.tables import (
    FeaturesTableModel,
    SimpleDictTableModel,
    AnnotationsTableModel,
)

__all__ = [
    "FeaturesTableModel",
    "SimpleDictTableModel",
    "AnnotationsTableModel",
]
