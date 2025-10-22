"""Keyboard-based ROI editing functionality.

This module provides arrow key editing for ROI rectangles.
"""

from PySide6.QtCore import Qt, QRect


class RoiEditorMixin:
    """Mixin for keyboard-based ROI editing.

    This mixin adds:
    - Arrow keys: Move ROI by 1 image pixel
    - Shift+Arrow keys: Move ROI by 10 image pixels

    Required attributes from base class:
    - roi_rect, viewer, scale
    - _orig_pixmap
    """

    def keyPressEvent(self, e):
        """Handle keyboard input for selection editing.

        Args:
            e: QKeyEvent

        Arrow keys move the selection rectangle by 1 image pixel (original image coordinate).
        Shift+Arrow keys move by 10 image pixels.
        All movements operate in image coordinates and are converted to display coordinates,
        then clipped to image boundaries.
        """
        if not self.roi_rect or self.roi_rect.isNull():
            super().keyPressEvent(e)
            return

        # Delta in image pixels
        img_delta = 10 if e.modifiers() & Qt.ShiftModifier else 1
        # Convert to display pixels using current scale
        delta = int(img_delta * self.scale)
        if delta == 0:
            delta = 1  # Ensure at least 1 pixel movement in display coordinates

        new_rect = QRect(self.roi_rect)

        if e.key() == Qt.Key_Left:
            new_rect.translate(-delta, 0)
        elif e.key() == Qt.Key_Right:
            new_rect.translate(delta, 0)
        elif e.key() == Qt.Key_Up:
            new_rect.translate(0, -delta)
        elif e.key() == Qt.Key_Down:
            new_rect.translate(0, delta)
        else:
            super().keyPressEvent(e)
            return

        # Clip to image boundaries
        disp_w = int(self._orig_pixmap.width() * self.scale) if not self._orig_pixmap.isNull() else 0
        disp_h = int(self._orig_pixmap.height() * self.scale) if not self._orig_pixmap.isNull() else 0

        # Constrain position
        if new_rect.left() < 0:
            new_rect.moveLeft(0)
        if new_rect.top() < 0:
            new_rect.moveTop(0)
        if new_rect.right() >= disp_w:
            new_rect.moveRight(disp_w - 1)
        if new_rect.bottom() >= disp_h:
            new_rect.moveBottom(disp_h - 1)

        self.roi_rect = new_rect
        self.update()

        # Notify viewer of selection change
        if self.viewer:
            self.viewer.on_roi_changed(self.roi_rect)
