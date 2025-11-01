"""Backward-compatible shim for moved item delegate.

PlainTextDelegate now lives in
`PixelScopeViewer.ui.dialogs.features.widgets.delegate`.
"""

from .widgets.delegate import PlainTextDelegate

__all__ = ["PlainTextDelegate"]
