"""pyside_image_viewer package

This package is organized into subpackages:
- ui: UI components (viewer, widgets, dialogs)
- io: image input/output helpers
- analysis: image analysis utilities (future)

Legacy top-level modules are kept as thin wrappers for compatibility.
"""

from .main import main

# Re-export commonly used classes/functions from subpackages for convenience
from .ui.viewer import ImageViewer
from .ui.dialogs import HelpDialog
from .io.image_io import numpy_to_qimage, pil_to_numpy, is_image_file

__all__ = [
    "main",
    "ImageViewer",
    "HelpDialog",
    "numpy_to_qimage",
    "pil_to_numpy",
    "is_image_file",
]
