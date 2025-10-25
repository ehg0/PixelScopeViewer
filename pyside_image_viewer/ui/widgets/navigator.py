"""Navigator widget showing thumbnail with viewport rectangle."""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QEvent


class NavigatorWidget(QGroupBox):
    """Navigator widget displaying thumbnail image with viewport rectangle.

    Shows a scaled-down version of the current image with a red rectangle
    indicating the current viewport area.
    """

    def __init__(self, viewer):
        super().__init__("Navigator")
        self.viewer = viewer

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(250, 250)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.thumbnail_label)

        # Connect to viewer signals
        # Assuming viewer has a signal for image/zoom changes
        self.viewer.scale_changed.connect(self.update_thumbnail)
        self.viewer.image_changed.connect(self.update_thumbnail)
        # Also update when user scrolls or viewport is resized
        sa = self.viewer.scroll_area
        sa.horizontalScrollBar().valueChanged.connect(self.update_thumbnail)
        sa.verticalScrollBar().valueChanged.connect(self.update_thumbnail)
        sa.viewport().installEventFilter(self)

        self.update_thumbnail()

    def eventFilter(self, obj, event):
        # Refresh thumbnail rectangle when the viewport is resized
        try:
            if obj is self.viewer.scroll_area.viewport() and event.type() == QEvent.Resize:
                self.update_thumbnail()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def update_thumbnail(self):
        """Update the thumbnail image and viewport rectangle."""
        if self.viewer.current_index is None or not self.viewer.images:
            self.thumbnail_label.clear()
            return

        img = self.viewer.images[self.viewer.current_index]["array"]
        h, w = img.shape[:2]

        # Create thumbnail pixmap
        from ...core.image_io import numpy_to_qimage

        qimg = numpy_to_qimage(img)
        pixmap = QPixmap.fromImage(qimg)

        # Scale to fit thumbnail size while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Calculate viewport rectangle in thumbnail coordinates
        scale_factor = min(self.thumbnail_label.width() / w, self.thumbnail_label.height() / h)

        # Get current viewport in image coordinates
        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        h_scroll = scroll_area.horizontalScrollBar().value()
        v_scroll = scroll_area.verticalScrollBar().value()

        # Convert to image coordinates
        img_x = h_scroll / self.viewer.scale
        img_y = v_scroll / self.viewer.scale
        img_w = viewport_width / self.viewer.scale
        img_h = viewport_height / self.viewer.scale

        # Convert to thumbnail coordinates
        thumb_x = int(img_x * scale_factor)
        thumb_y = int(img_y * scale_factor)
        thumb_w = int(img_w * scale_factor)
        thumb_h = int(img_h * scale_factor)

        # Draw rectangle on pixmap
        painter = QPainter(scaled_pixmap)
        pen = QPen(QColor(255, 68, 68, 255), 2)  # Red color for viewport border
        painter.setPen(pen)
        painter.drawRect(thumb_x, thumb_y, thumb_w, thumb_h)
        painter.end()

        self.thumbnail_label.setPixmap(scaled_pixmap)
