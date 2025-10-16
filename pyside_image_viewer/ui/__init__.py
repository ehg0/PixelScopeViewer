"""UI components package."""

from .viewer import ImageViewer
from .widgets import ImageLabel
from .dialogs import HelpDialog, DiffDialog, AnalysisDialog

__all__ = ["ImageViewer", "ImageLabel", "HelpDialog", "DiffDialog", "AnalysisDialog"]
"""UI components for the image viewer (viewer, widgets, dialogs)."""


from .viewer import ImageViewer
from .widgets import ImageLabel
from .dialogs import HelpDialog

__all__ = ["ImageViewer", "ImageLabel", "HelpDialog"]
