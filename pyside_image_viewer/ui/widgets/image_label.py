"""Integrated image display widget with selection support.

This module combines all widget functionality into a single ImageLabel class.
"""

from typing import Optional
from PySide6.QtGui import QPixmap, QPainter, QImage
from PySide6.QtCore import Qt, QRect

from .base_image_label import BaseImageLabel
from .selection_manager import SelectionManagerMixin
from .selection_editor import SelectionEditorMixin


class ImageLabel(SelectionManagerMixin, SelectionEditorMixin, BaseImageLabel):
    """Image display widget with pixel-aligned selection and drag support.

    Features:
    - Left-drag: Create new selection rectangle (pixel-aligned)
    - Right-drag: Move existing selection (press inside selection to start)
    - Left-drag on edges/corners: Resize selection (8 grab points)
    - Arrow keys: Move selection by 1 image pixel
    - Shift+Arrow keys: Move selection by 10 image pixels

    The selection is always snapped to pixel boundaries based on the current
    zoom level. Visual feedback is provided during dragging.

    Attributes:
        viewer: Parent ImageViewer instance
        selection_rect: Current selection rectangle in widget coordinates (QRect)
        scale: Current zoom scale factor
    """

    def __init__(self, viewer, parent=None):
        """Initialize the ImageLabel widget.

        Args:
            viewer: Parent ImageViewer instance
            parent: Optional Qt parent widget
        """
        super().__init__(viewer, parent)
        self.__init_selection_manager__()

    def set_image(self, qimg: QImage, scale: float = 1.0):
        """Set the image to display with optional scaling.

        Args:
            qimg: QImage to display
            scale: Zoom scale factor (1.0 = original size)

        The selection rectangle is preserved across image/scale changes
        when possible, maintaining its position in image coordinates.
        """
        # preserve previous selection in image coords (if any)
        prev_sel_img = None
        if (
            self.selection_rect
            and not self.selection_rect.isNull()
            and self._qimage is not None
            and not self._qimage.isNull()
        ):
            prev = self.get_selection_in_image_coords()
            if prev is not None:
                prev_sel_img = prev

        # Call base class to set image
        super().set_image(qimg, scale)

        # Restore previous selection rect at new scale if there was one
        if prev_sel_img is not None:
            self.selection_rect = self._image_rect_to_widget(prev_sel_img)
        else:
            self.selection_rect = None
        self.update()

    def clear(self):
        """Clear the displayed image and selection."""
        super().clear()
        self.selection_rect = None

    def paintEvent(self, event):
        """Paint the image and selection rectangle.

        Args:
            event: QPaintEvent
        """
        painter = QPainter(self)

        # Paint image (from base class)
        if not self._orig_pixmap.isNull():
            painter.save()
            painter.scale(self.scale, self.scale)
            painter.drawPixmap(0, 0, self._orig_pixmap)
            painter.restore()

        # Paint selection (from selection manager)
        self.paint_selection(painter)
