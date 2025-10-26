"""PixelScopeViewer - A scientific image viewer with analysis tools.

This package provides a Qt-based image viewer optimized for scientific
and technical images with the following features:

Core Features:
    - Multi-image loading and navigation
    - Pixel-aligned selection with keyboard editing
    - Zoom in/out with smooth scaling
    - Bit-shift operations for raw/scientific data visualization

Analysis Tools:
    - Histogram with linear/logarithmic scales
    - Line profiles (horizontal/vertical, absolute/relative)
    - Channel selection for multi-channel images
    - Difference image creation
    - CSV export of analysis data

UI Components:
    - Main viewer window (ImageViewer)
    - Analysis dialog with tabbed interface (AnalysisDialog)
    - Help dialog with keyboard shortcuts (HelpDialog)
    - Difference dialog (DiffDialog)

Image I/O:
    - PIL-based image loading
    - NumPy array to QImage conversion
    - Support for common formats: PNG, JPEG, TIFF, BMP

Package Structure:
    - core/: UI-independent utilities (image I/O)
    - ui/: UI components (viewer, widgets, dialogs)
    - ui/dialogs/: Dialog windows
    - ui/dialogs/analysis/: Analysis dialog and controls

Quick Start:
    from PixelScopeViewer import main
    main()

Dependencies:
    - PySide6: Qt for Python
    - numpy: Array operations
    - Pillow: Image loading
    - matplotlib (optional): For histogram and profile plots
"""

from .app import main
from .ui import ImageViewer, HelpDialog, DiffDialog, AnalysisDialog, BrightnessDialog
from .core import numpy_to_qimage, pil_to_numpy, is_image_file, get_image_metadata

__version__ = "0.1.0"
__all__ = [
    "main",
    "ImageViewer",
    "HelpDialog",
    "DiffDialog",
    "AnalysisDialog",
    "BrightnessDialog",
    "numpy_to_qimage",
    "pil_to_numpy",
    "is_image_file",
    "get_image_metadata",
]
