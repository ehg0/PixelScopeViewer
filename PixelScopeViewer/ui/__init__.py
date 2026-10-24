"""UI component。"""

from PixelScopeViewer.ui.dialogs import AnalysisDialog, BrightnessDialog, DiffDialog, HelpDialog
from PixelScopeViewer.ui.utils import get_default_channel_colors
from PixelScopeViewer.ui.viewer import ImageViewer
from PixelScopeViewer.ui.widgets import ImageLabel

__all__ = [
    "ImageViewer",
    "ImageLabel",
    "HelpDialog",
    "DiffDialog",
    "AnalysisDialog",
    "BrightnessDialog",
    "get_default_channel_colors",
]
