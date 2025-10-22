"""Custom Qt widgets for image display and interaction.

This package provides:
- ImageLabel: QLabel subclass with pixel-aligned selection and drag support
- NavigatorWidget: Thumbnail navigator with viewport rectangle
- DisplayInfoWidget: Display area information table
- ROIInfoWidget: ROI information and editing table
"""

from .image_label import ImageLabel
from .navigator import NavigatorWidget
from .display_info import DisplayInfoWidget
from .roi_info import ROIInfoWidget

__all__ = ["ImageLabel", "NavigatorWidget", "DisplayInfoWidget", "ROIInfoWidget"]
