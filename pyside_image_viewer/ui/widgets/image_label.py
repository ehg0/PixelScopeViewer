"""Integrated image display widget with ROI support.

This module combines all widget functionality into a single ImageLabel class.
"""

from typing import Optional
from PySide6.QtGui import QPixmap, QPainter, QImage, QWheelEvent
from PySide6.QtCore import Qt, QRect

from .base_image_label import BaseImageLabel
from .roi_manager import RoiManagerMixin
from .roi_editor import RoiEditorMixin


class ImageLabel(RoiManagerMixin, RoiEditorMixin, BaseImageLabel):
    """Image display widget with pixel-aligned ROI and drag support.

    Features:
    - Left-drag: Create new ROI rectangle (pixel-aligned)
    - Right-drag: Move existing ROI (press inside ROI to start)
    - Left-drag on edges/corners: Resize ROI (8 grab points)
    - Arrow keys: Move ROI by 1 image pixel
    - Shift+Arrow keys: Move ROI by 10 image pixels

    The ROI is always snapped to pixel boundaries based on the current
    zoom level. Visual feedback is provided during dragging.

    Attributes:
        viewer: Parent ImageViewer instance
        roi_rect: Current ROI rectangle in widget coordinates (QRect)
        scale: Current zoom scale factor
    """

    def __init__(self, viewer, parent=None):
        """Initialize the ImageLabel widget.

        Args:
            viewer: Parent ImageViewer instance
            parent: Optional Qt parent widget
        """
        super().__init__(viewer, parent)
        self.__init_roi_manager__()

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
        if self.roi_rect and not self.roi_rect.isNull() and self._qimage is not None and not self._qimage.isNull():
            prev = self.get_roi_in_image_coords()
            if prev is not None:
                prev_sel_img = prev

        # Call base class to set image
        super().set_image(qimg, scale)

        # Restore previous selection rect at new scale if there was one
        if prev_sel_img is not None:
            self.roi_rect = self._image_rect_to_widget(prev_sel_img)
        else:
            self.roi_rect = None
        self.update()

    def clear(self):
        """Clear the displayed image and selection."""
        super().clear()
        self.roi_rect = None

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
        self.paint_roi(painter)

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel events for zooming with binary steps.

        Args:
            event: QWheelEvent containing wheel movement information
        """
        if not self.showing or self.viewer.current_index is None:
            event.ignore()
            return

        # Check if Ctrl key is pressed for zoom operation
        modifiers = event.modifiers()
        if not (modifiers & Qt.ControlModifier):
            # If Ctrl is not pressed, let the parent handle scrolling
            event.ignore()
            return

        # Get the scroll direction (positive = zoom in, negative = zoom out)
        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            event.ignore()
            return

        # Use binary steps like keyboard shortcuts (2x zoom in/out)
        current_scale = self.viewer.scale
        if angle_delta > 0:
            # Zoom in: multiply by 2
            new_scale = current_scale * 2
        else:
            # Zoom out: divide by 2
            new_scale = current_scale / 2

        # Set reasonable zoom limits (same as keyboard shortcuts)
        min_scale = 0.125  # 1/8x
        max_scale = 128.0  # 128x (extending range for better pixel-level work)
        new_scale = max(min_scale, min(max_scale, new_scale))

        # Apply zoom centered on the coordinates displayed in status bar
        self.viewer.set_zoom_at_status_coords(new_scale)

        # Accept the event
        event.accept()
