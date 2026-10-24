"""解析機能付きの画像ビューア PixelScopeViewer。"""

from PixelScopeViewer.app import main
from PixelScopeViewer.core import get_image_metadata, is_image_file, load_image
from PixelScopeViewer.ui.analysis import AnalysisDialog
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage
from PixelScopeViewer.ui.diff import DiffDialog
from PixelScopeViewer.ui.display import BrightnessDialog
from PixelScopeViewer.ui.viewer import ImageViewer
from PixelScopeViewer.ui.viewer.help_dialog import HelpDialog

__version__ = "0.2.1"
__all__ = [
    "main",
    "ImageViewer",
    "HelpDialog",
    "DiffDialog",
    "AnalysisDialog",
    "BrightnessDialog",
    "numpy_to_qimage",
    "load_image",
    "is_image_file",
    "get_image_metadata",
]
