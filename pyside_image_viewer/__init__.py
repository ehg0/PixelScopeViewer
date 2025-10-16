"""PySide6 Image Viewer - A simple image viewer with analysis tools.

Main components:
- ui.viewer: Main window with image display and navigation
- ui.dialogs: Help, Diff, and Analysis dialogs
- ui.widgets: Custom Qt widgets (ImageLabel)
- core.image_io: Image loading and conversion utilities
"""

from .main import main
from .ui import ImageViewer, HelpDialog, DiffDialog, AnalysisDialog
from .core import numpy_to_qimage, pil_to_numpy, is_image_file

__all__ = [
    "main",
    "ImageViewer",
    "HelpDialog",
    "DiffDialog",
    "AnalysisDialog",
    "numpy_to_qimage",
    "pil_to_numpy",
    "is_image_file",
]
