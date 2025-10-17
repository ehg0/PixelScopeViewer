"""Base image display widget with coordinate conversion utilities.

This module provides the foundation for image display with zoom support.
"""

from typing import Optional
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QPainter, QImage
from PySide6.QtCore import Qt, QRect, QPoint


class BaseImageLabel(QLabel):
    """Base class for image display with zoom and coordinate conversion.

    This class handles:
    - Image display with scaling
    - Coordinate conversion between widget and image coordinates
    - Basic painting

    Attributes:
        viewer: Parent ImageViewer instance
        scale: Current zoom scale factor
        _orig_pixmap: Original pixmap (before scaling)
        _qimage: Source QImage
        showing: Whether an image is currently displayed
    """

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._orig_pixmap = QPixmap()
        self._qimage: Optional[QImage] = None
        self.scale = 1.0
        self.showing = False

    def set_image(self, qimg: QImage, scale: float = 1.0):
        """Set the image to display with optional scaling.

        Args:
            qimg: QImage to display
            scale: Zoom scale factor (1.0 = original size)
        """
        self._qimage = qimg
        self.scale = scale
        if qimg.isNull():
            self._orig_pixmap = QPixmap()
            self.setFixedSize(0, 0)
            self.showing = False
            return
        self._orig_pixmap = QPixmap.fromImage(qimg)
        disp_w = int(self._orig_pixmap.width() * self.scale)
        disp_h = int(self._orig_pixmap.height() * self.scale)
        self.setFixedSize(max(1, disp_w), max(1, disp_h))
        self.showing = True
        self.update()

    def clear(self):
        """Clear the displayed image."""
        self._orig_pixmap = QPixmap()
        self._qimage = None
        self.setFixedSize(0, 0)
        self.showing = False
        self.update()

    def paintEvent(self, event):
        """Paint the image."""
        painter = QPainter(self)
        if not self._orig_pixmap.isNull():
            painter.save()
            painter.scale(self.scale, self.scale)
            painter.drawPixmap(0, 0, self._orig_pixmap)
            painter.restore()

    # --- Coordinate conversion utilities ---
    def _display_scale_factor(self) -> Optional[float]:
        """Return displayed pixels per source image pixel."""
        if self._qimage is None or self._qimage.isNull():
            return None
        return float(self.scale) if self.scale and self.scale > 0 else None

    def _widget_to_image_point(self, pt: QPoint) -> Optional[tuple[int, int]]:
        """Convert widget coordinates to image pixel coordinates.

        Args:
            pt: Point in widget coordinates

        Returns:
            (x, y) in image coordinates, or None if no image
        """
        factor = self._display_scale_factor()
        if factor is None or factor == 0 or self._qimage is None:
            return None
        ix = int(pt.x() / factor)
        iy = int(pt.y() / factor)
        ix = max(0, min(ix, self._qimage.width() - 1))
        iy = max(0, min(iy, self._qimage.height() - 1))
        return (ix, iy)

    def _image_to_widget_x(self, ix: int) -> int:
        """Convert image x-coordinate to widget x-coordinate."""
        factor = self._display_scale_factor() or 1.0
        return int(round(ix * factor))

    def _image_to_widget_y(self, iy: int) -> int:
        """Convert image y-coordinate to widget y-coordinate."""
        factor = self._display_scale_factor() or 1.0
        return int(round(iy * factor))

    def _image_rect_to_widget(self, img_rect: QRect) -> QRect:
        """Convert image rectangle to widget rectangle.

        Args:
            img_rect: Rectangle in image coordinates

        Returns:
            Rectangle in widget coordinates
        """
        left = self._image_to_widget_x(img_rect.left())
        top = self._image_to_widget_y(img_rect.top())
        right_ex = self._image_to_widget_x(img_rect.left() + img_rect.width())
        bottom_ex = self._image_to_widget_y(img_rect.top() + img_rect.height())
        w = max(1, right_ex - left)
        h = max(1, bottom_ex - top)
        return QRect(left, top, w, h)

    def _widget_rect_to_image(self, widget_rect: QRect) -> Optional[QRect]:
        """Convert widget rectangle to image rectangle.

        Args:
            widget_rect: Rectangle in widget coordinates

        Returns:
            Rectangle in image coordinates, or None if no image
        """
        if self._qimage is None or self._qimage.isNull():
            return None

        src_w = self._qimage.width()
        src_h = self._qimage.height()
        disp_w = int(self._orig_pixmap.width() * self.scale)
        disp_h = int(self._orig_pixmap.height() * self.scale)

        if not (disp_w and disp_h and src_w and src_h):
            return None

        fx = disp_w / src_w
        fy = disp_h / src_h

        left = int(widget_rect.left() / fx)
        top = int(widget_rect.top() / fy)
        right_ex = int((widget_rect.left() + widget_rect.width()) / fx)
        bottom_ex = int((widget_rect.top() + widget_rect.height()) / fy)

        left = max(0, min(left, src_w))
        top = max(0, min(top, src_h))
        right_ex = max(0, min(right_ex, src_w))
        bottom_ex = max(0, min(bottom_ex, src_h))

        w = max(0, right_ex - left)
        h = max(0, bottom_ex - top)
        return QRect(left, top, w, h)
