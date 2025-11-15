"""Navigator widget showing thumbnail with viewport rectangle."""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QMouseEvent
from PySide6.QtCore import Qt, QEvent, QPoint


class NavigatorWidget(QGroupBox):
    """Navigator widget displaying thumbnail image with viewport rectangle.

    Shows a scaled-down version of the current image with a red rectangle
    indicating the current viewport area. Clicking on the thumbnail moves
    the viewport to center on that position.
    """

    def __init__(self, viewer):
        super().__init__("Navigator")
        self.viewer = viewer

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(200, 200)
        self.thumbnail_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.thumbnail_label)
        layout.addStretch()  # Add stretch to push thumbnail to top

        # Connect to viewer signals
        # Assuming viewer has a signal for image/zoom changes
        self.viewer.scale_changed.connect(self.update_thumbnail)
        self.viewer.image_changed.connect(self.update_thumbnail)
        # Also update when user scrolls or viewport is resized
        sa = self.viewer.scroll_area
        sa.horizontalScrollBar().valueChanged.connect(self.update_thumbnail)
        sa.verticalScrollBar().valueChanged.connect(self.update_thumbnail)
        sa.viewport().installEventFilter(self)

        # For clicking to move viewport
        self.thumbnail_label.installEventFilter(self)
        self.thumb_rect = None  # Will store (x, y, w, h) of viewport in thumbnail coords

        self.update_thumbnail()

    def eventFilter(self, obj, event):
        # Refresh thumbnail rectangle when the viewport is resized
        try:
            if obj is self.viewer.scroll_area.viewport() and event.type() == QEvent.Resize:
                self.update_thumbnail()
            elif obj is self.thumbnail_label:
                if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                    self.handle_mouse_press(event)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def handle_mouse_press(self, event: QMouseEvent):
        """Handle left mouse button click to move viewport to clicked position."""
        if self.thumb_rect is None:
            return

        mouse_pos = event.pos()

        # Get thumbnail dimensions
        pixmap = self.thumbnail_label.pixmap()
        if not pixmap:
            return

        thumb_width = pixmap.width()
        thumb_height = pixmap.height()

        # Calculate pixmap offset in thumbnail_label
        # Label is set to Qt.AlignTop | Qt.AlignHCenter, so:
        # - Horizontally centered
        # - Vertically aligned to top
        label_width = self.thumbnail_label.width()
        label_height = self.thumbnail_label.height()
        x_offset = (label_width - thumb_width) / 2
        y_offset = 0  # Top-aligned, so no vertical offset

        mouse_pos = event.pos()

        # Check if click is within the pixmap area
        if not (
            x_offset <= mouse_pos.x() <= x_offset + thumb_width and y_offset <= mouse_pos.y() <= y_offset + thumb_height
        ):
            return  # Click outside pixmap, ignore

        # Convert click position relative to pixmap
        pixmap_x = mouse_pos.x() - x_offset
        pixmap_y = mouse_pos.y() - y_offset

        # Convert click position to image coordinates
        img = self.viewer.images[self.viewer.current_index]["array"]
        h, w = img.shape[:2]
        scale_factor = min(thumb_width / w, thumb_height / h)

        img_x = pixmap_x / scale_factor
        img_y = pixmap_y / scale_factor

        # Center the viewport on the clicked position
        viewport_width = self.viewer.scroll_area.viewport().width()
        viewport_height = self.viewer.scroll_area.viewport().height()

        # Calculate the top-left position of viewport in widget coordinates
        # to center the clicked image position in the viewport
        widget_click_x = img_x * self.viewer.scale
        widget_click_y = img_y * self.viewer.scale

        # Calculate scroll position to center the clicked point
        h_scroll = widget_click_x - viewport_width / 2
        v_scroll = widget_click_y - viewport_height / 2

        # Clamp to valid scroll range
        h_scroll = max(0, min(h_scroll, self.viewer.image_label.width() - viewport_width))
        v_scroll = max(0, min(v_scroll, self.viewer.image_label.height() - viewport_height))

        # Update scroll position
        scroll_area = self.viewer.scroll_area
        scroll_area.horizontalScrollBar().setValue(int(h_scroll))
        scroll_area.verticalScrollBar().setValue(int(v_scroll))

        event.accept()

    def update_thumbnail(self):
        """Update the thumbnail image and viewport rectangle."""
        if self.viewer.current_index is None or not self.viewer.images:
            self.thumbnail_label.clear()
            self.thumb_rect = None
            return

        img_data = self.viewer.images[self.viewer.current_index]
        h, w = img_data["array"].shape[:2]

        # Use cached thumbnail pixmap
        base_pixmap = img_data.get("thumbnail_pixmap")
        if not base_pixmap:
            # Fallback if thumbnail is not cached for some reason
            from ...core.image_io import numpy_to_qimage

            qimg = numpy_to_qimage(img_data["array"])
            base_pixmap = QPixmap.fromImage(qimg).scaled(
                self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        # Create a mutable copy to draw the viewport rectangle on
        scaled_pixmap = base_pixmap.copy()

        # Calculate viewport rectangle in thumbnail coordinates
        scale_factor = min(scaled_pixmap.width() / w, scaled_pixmap.height() / h)

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

        self.thumb_rect = (thumb_x, thumb_y, thumb_w, thumb_h)

        # Draw rectangle on pixmap
        painter = QPainter(scaled_pixmap)
        pen = QPen(QColor(255, 68, 68, 255), 2)  # Red color for viewport border
        painter.setPen(pen)
        painter.drawRect(thumb_x, thumb_y, thumb_w, thumb_h)
        painter.end()

        self.thumbnail_label.setPixmap(scaled_pixmap)
