"""Backward-compatible shim for moved proxy model.

LoadedOnlyProxyModel now lives in
`PixelScopeViewer.ui.dialogs.features.widgets.proxy`.
"""

from .widgets.proxy import LoadedOnlyProxyModel

__all__ = ["LoadedOnlyProxyModel"]
