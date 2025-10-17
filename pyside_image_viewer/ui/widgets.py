"""Custom Qt widgets for image display and interaction.

This module provides:
- ImageLabel: QLabel subclass with pixel-aligned selection and drag support
"""

from typing import Optional
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QImage
from PySide6.QtCore import Qt, QRect, QPoint


class ImageLabel(QLabel):
    """Image display widget with pixel-aligned selection and drag support.

    Features:
    - Left-drag: Create new selection rectangle (pixel-aligned)
    - Right-drag: Move existing selection (press inside selection to start)

    The selection is always snapped to pixel boundaries based on the current
    zoom level. Visual feedback is provided during dragging.

    Attributes:
        viewer: Parent ImageViewer instance
        selection_rect: Current selection rectangle in image coordinates (QRect)
        scale: Current zoom scale factor
    """

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)  # Enable keyboard focus for arrow key editing

        self._orig_pixmap = QPixmap()
        self.scale = 1.0
        self.selection_rect: Optional[QRect] = None
        self.dragging = False
        self._moving = False
        self._resizing = False
        self._resize_edge = None  # 'left', 'right', 'top', 'bottom', 'tl', 'tr', 'bl', 'br'
        self._move_start_img = None
        self._move_orig_img_rect = None
        self._resize_start_img = None
        self._resize_orig_img_rect = None
        self.showing = False
        self.start_point = QPoint()
        self._start_img = None
        self._edge_grab_distance = 8  # pixels from edge to trigger resize

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
            and hasattr(self, "_qimage")
            and not getattr(self, "_qimage", None) is None
        ):
            prev = self.get_selection_in_image_coords()
            if prev is not None:
                prev_sel_img = prev

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
        # restore previous selection rect at new scale if there was one
        if prev_sel_img is not None:
            # prev_sel_img is QRect in image coords
            left = self._image_to_widget_x(prev_sel_img.left())
            top = self._image_to_widget_y(prev_sel_img.top())
            right_ex = self._image_to_widget_x(prev_sel_img.left() + prev_sel_img.width())
            bottom_ex = self._image_to_widget_y(prev_sel_img.top() + prev_sel_img.height())
            w = max(1, right_ex - left)
            h = max(1, bottom_ex - top)
            self.selection_rect = QRect(left, top, w, h)
        else:
            self.selection_rect = None
        self.update()

    def clear(self):
        """Clear the displayed image and selection."""
        self._orig_pixmap = QPixmap()
        self.setFixedSize(0, 0)
        self.showing = False
        self.selection_rect = None
        self.update()

    def mousePressEvent(self, ev):
        if not self.showing:
            return
        self.start_point = ev.position().toPoint()

        # Check if clicking on selection edge for resizing
        edge = self._get_resize_edge(self.start_point)

        if ev.button() == Qt.LeftButton:
            if edge:
                # Start resizing
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_img = self._widget_to_image_point(self.start_point)
                self._resize_orig_img_rect = self.get_selection_in_image_coords()
                self.dragging = True
            else:
                # start selection creation
                self._moving = False
                self._resizing = False
                self._start_img = self._widget_to_image_point(self.start_point)
                # create minimal visible rect immediately
                if self._start_img is not None:
                    sx = self._image_to_widget_x(self._start_img[0])
                    sy = self._image_to_widget_y(self._start_img[1])
                    self.selection_rect = QRect(sx, sy, 1, 1)
                self.dragging = True
        elif ev.button() == Qt.RightButton:
            # start moving only if clicked inside selection (but not on edge)
            if self.selection_rect and self.selection_rect.contains(self.start_point) and not edge:
                self._moving = True
                self._resizing = False
                self._move_start_img = self._widget_to_image_point(self.start_point)
                self._move_orig_img_rect = self.get_selection_in_image_coords()
                self.dragging = True

    def mouseMoveEvent(self, ev):
        # Update cursor when hovering over selection edges
        if self.showing and not self.dragging and self.selection_rect:
            edge = self._get_resize_edge(ev.position().toPoint())
            self._update_cursor_for_edge(edge)

        if self.showing and self.dragging:
            cur_pt = ev.position().toPoint()

            # Resizing selection
            if self._resizing and self._resize_start_img is not None and self._resize_orig_img_rect is not None:
                cur_img = self._widget_to_image_point(cur_pt)
                if cur_img is None:
                    return

                orig = self._resize_orig_img_rect
                edge = self._resize_edge

                # Start with original rectangle
                new_left = orig.left()
                new_top = orig.top()
                new_width = orig.width()
                new_height = orig.height()

                # Handle horizontal resize (left/right edges and corners)
                if edge in ("left", "tl", "bl"):  # Left edge or left corners
                    new_left_candidate = max(0, min(cur_img[0], orig.left() + orig.width() - 1))
                    new_width = orig.left() + orig.width() - new_left_candidate
                    new_left = new_left_candidate
                elif edge in ("right", "tr", "br"):  # Right edge or right corners
                    new_right_candidate = max(orig.left(), min(cur_img[0], self._qimage.width() - 1))
                    new_width = new_right_candidate - orig.left() + 1

                # Handle vertical resize (top/bottom edges and corners)
                if edge in ("top", "tl", "tr"):  # Top edge or top corners
                    new_top_candidate = max(0, min(cur_img[1], orig.top() + orig.height() - 1))
                    new_height = orig.top() + orig.height() - new_top_candidate
                    new_top = new_top_candidate
                elif edge in ("bottom", "bl", "br"):  # Bottom edge or bottom corners
                    new_bottom_candidate = max(orig.top(), min(cur_img[1], self._qimage.height() - 1))
                    new_height = new_bottom_candidate - orig.top() + 1

                # Ensure minimum size
                new_width = max(1, new_width)
                new_height = max(1, new_height)

                # Convert to widget coordinates
                left = self._image_to_widget_x(new_left)
                top = self._image_to_widget_y(new_top)
                right_ex = self._image_to_widget_x(new_left + new_width)
                bottom_ex = self._image_to_widget_y(new_top + new_height)
                w = max(1, right_ex - left)
                h = max(1, bottom_ex - top)
                self.selection_rect = QRect(left, top, w, h)
                self.update()
                if self.viewer and self.selection_rect and not self.selection_rect.isNull():
                    try:
                        self.viewer.on_selection_changed(self.selection_rect)
                    except Exception:
                        pass
            # moving selection
            elif self._moving and self._move_start_img is not None and self._move_orig_img_rect is not None:
                cur_img = self._widget_to_image_point(cur_pt)
                if cur_img is None:
                    return
                dx = cur_img[0] - self._move_start_img[0]
                dy = cur_img[1] - self._move_start_img[1]
                orig = self._move_orig_img_rect
                if orig is None:
                    return
                new_x = max(0, min(orig.x() + dx, self._qimage.width() - orig.width()))
                new_y = max(0, min(orig.y() + dy, self._qimage.height() - orig.height()))
                left = self._image_to_widget_x(new_x)
                top = self._image_to_widget_y(new_y)
                right_ex = self._image_to_widget_x(new_x + orig.width())
                bottom_ex = self._image_to_widget_y(new_y + orig.height())
                w = max(1, right_ex - left)
                h = max(1, bottom_ex - top)
                self.selection_rect = QRect(left, top, w, h)
                self.update()
                if self.viewer and self.selection_rect and not self.selection_rect.isNull():
                    try:
                        self.viewer.on_selection_changed(self.selection_rect)
                    except Exception:
                        pass
            else:
                # creating new selection
                cur_img = self._widget_to_image_point(cur_pt)
                start_img = self._start_img
                if start_img is None or cur_img is None:
                    return
                x0 = min(start_img[0], cur_img[0])
                x1 = max(start_img[0], cur_img[0])
                y0 = min(start_img[1], cur_img[1])
                y1 = max(start_img[1], cur_img[1])
                left = self._image_to_widget_x(x0)
                top = self._image_to_widget_y(y0)
                right_ex = self._image_to_widget_x(x1 + 1)
                bottom_ex = self._image_to_widget_y(y1 + 1)
                w = max(1, right_ex - left)
                h = max(1, bottom_ex - top)
                self.selection_rect = QRect(left, top, w, h)
                self.update()
                if self.viewer and self.selection_rect and not self.selection_rect.isNull():
                    try:
                        self.viewer.on_selection_changed(self.selection_rect)
                    except Exception:
                        pass

        if hasattr(self.parent(), "on_mouse_move"):
            if self.showing and not self._orig_pixmap.isNull():
                disp_w = int(self._orig_pixmap.width() * self.scale)
                disp_h = int(self._orig_pixmap.height() * self.scale)
                p = ev.position().toPoint()
                p = QPoint(max(0, min(p.x(), max(0, disp_w - 1))), max(0, min(p.y(), max(0, disp_h - 1))))
                self.parent().on_mouse_move(p)
            else:
                self.parent().on_mouse_move(ev.position().toPoint())

    def mouseReleaseEvent(self, ev):
        if not self.showing:
            return
        if ev.button() == Qt.LeftButton:
            if self._resizing:
                # Finish resizing
                self._resizing = False
                self._resize_edge = None
                self._resize_start_img = None
                self._resize_orig_img_rect = None
                self.dragging = False
                self.update()
                if self.viewer and self.selection_rect and not self.selection_rect.isNull():
                    self.viewer.on_selection_changed(self.selection_rect)
            else:
                # Finish creating new selection
                self.dragging = False
                end_img = self._widget_to_image_point(ev.position().toPoint())
                start_img = self._start_img
                if start_img is not None and end_img is not None:
                    x0 = min(start_img[0], end_img[0])
                    x1 = max(start_img[0], end_img[0])
                    y0 = min(start_img[1], end_img[1])
                    y1 = max(start_img[1], end_img[1])
                    left = self._image_to_widget_x(x0)
                    top = self._image_to_widget_y(y0)
                    right_ex = self._image_to_widget_x(x1 + 1)
                    bottom_ex = self._image_to_widget_y(y1 + 1)
                    w = max(1, right_ex - left)
                    h = max(1, bottom_ex - top)
                    self.selection_rect = QRect(left, top, w, h)
                self.update()
                if self.viewer and self.selection_rect and not self.selection_rect.isNull():
                    self.viewer.on_selection_changed(self.selection_rect)
            return
        if ev.button() == Qt.RightButton:
            # finish moving
            if getattr(self, "_moving", False):
                self._moving = False
                self._move_start_img = None
                self._move_orig_img_rect = None
                self.dragging = False
                self.update()
                if self.viewer and self.selection_rect and not self.selection_rect.isNull():
                    self.viewer.on_selection_changed(self.selection_rect)
            return

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self._orig_pixmap.isNull():
            painter.save()
            painter.scale(self.scale, self.scale)
            painter.drawPixmap(0, 0, self._orig_pixmap)
            painter.restore()

        if self.selection_rect and not self.selection_rect.isNull():
            pen = QPen(QColor(0, 0, 255), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.selection_rect)

    def get_selection_in_image_coords(self):
        """Get the current selection rectangle in image coordinates.

        Returns:
            QRect in image pixel coordinates, or None if no selection.
        """
        if not self.selection_rect or self.selection_rect.isNull():
            return None
        if not hasattr(self, "_qimage") or self._qimage is None or self._qimage.isNull():
            return None

        disp_w = int(self._orig_pixmap.width() * self.scale)
        disp_h = int(self._orig_pixmap.height() * self.scale)
        src_w = self._qimage.width()
        src_h = self._qimage.height()
        if disp_w == 0 or disp_h == 0 or src_w == 0 or src_h == 0:
            return None

        fx = disp_w / src_w
        fy = disp_h / src_h

        left = int(self.selection_rect.left() / fx)
        top = int(self.selection_rect.top() / fy)
        right_ex = int((self.selection_rect.left() + self.selection_rect.width()) / fx)
        bottom_ex = int((self.selection_rect.top() + self.selection_rect.height()) / fy)

        left = max(0, min(left, src_w))
        top = max(0, min(top, src_h))
        right_ex = max(0, min(right_ex, src_w))
        bottom_ex = max(0, min(bottom_ex, src_h))

        w = max(0, right_ex - left)
        h = max(0, bottom_ex - top)
        return QRect(left, top, w, h)

    def _get_resize_edge(self, pos: QPoint) -> Optional[str]:
        """Determine which edge of the selection is near the cursor.

        Args:
            pos: Cursor position in widget coordinates

        Returns:
            Edge identifier: 'tl', 'tr', 'bl', 'br', 'left', 'right', 'top', 'bottom', or None
        """
        if not self.selection_rect or self.selection_rect.isNull():
            return None

        rect = self.selection_rect
        dist = self._edge_grab_distance

        # Check corners first (higher priority)
        if abs(pos.x() - rect.left()) <= dist and abs(pos.y() - rect.top()) <= dist:
            return "tl"  # top-left
        if abs(pos.x() - rect.right()) <= dist and abs(pos.y() - rect.top()) <= dist:
            return "tr"  # top-right
        if abs(pos.x() - rect.left()) <= dist and abs(pos.y() - rect.bottom()) <= dist:
            return "bl"  # bottom-left
        if abs(pos.x() - rect.right()) <= dist and abs(pos.y() - rect.bottom()) <= dist:
            return "br"  # bottom-right

        # Check edges
        if abs(pos.x() - rect.left()) <= dist and rect.top() <= pos.y() <= rect.bottom():
            return "left"
        if abs(pos.x() - rect.right()) <= dist and rect.top() <= pos.y() <= rect.bottom():
            return "right"
        if abs(pos.y() - rect.top()) <= dist and rect.left() <= pos.x() <= rect.right():
            return "top"
        if abs(pos.y() - rect.bottom()) <= dist and rect.left() <= pos.x() <= rect.right():
            return "bottom"

        return None

    def _update_cursor_for_edge(self, edge: Optional[str]):
        """Update cursor shape based on which edge is being hovered/grabbed.

        Args:
            edge: Edge identifier from _get_resize_edge()
        """
        if edge == "tl" or edge == "br":
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge == "tr" or edge == "bl":
            self.setCursor(Qt.SizeBDiagCursor)
        elif edge == "left" or edge == "right":
            self.setCursor(Qt.SizeHorCursor)
        elif edge == "top" or edge == "bottom":
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    # --- helper conversions between widget coords and source image pixel coords ---
    def _display_scale_factor(self) -> Optional[float]:
        """Return displayed pixels per source image pixel (fx, fy assumed equal since KeepAspectRatio used)."""
        if not hasattr(self, "_qimage") or self._qimage is None or self._qimage.isNull():
            return None
        return float(self.scale) if self.scale and self.scale > 0 else None

    def _widget_to_image_point(self, pt: QPoint):
        factor = self._display_scale_factor()
        if factor is None or factor == 0:
            return None
        ix = int(pt.x() / factor)
        iy = int(pt.y() / factor)
        ix = max(0, min(ix, self._qimage.width() - 1))
        iy = max(0, min(iy, self._qimage.height() - 1))
        return (ix, iy)

    def _image_to_widget_x(self, ix: int) -> int:
        factor = self._display_scale_factor() or 1.0
        return int(round(ix * factor))

    def _image_to_widget_y(self, iy: int) -> int:
        factor = self._display_scale_factor() or 1.0
        return int(round(iy * factor))

    def set_selection_full(self):
        if not self.showing:
            return
        disp_w = int(self._orig_pixmap.width() * self.scale) if not self._orig_pixmap.isNull() else 0
        disp_h = int(self._orig_pixmap.height() * self.scale) if not self._orig_pixmap.isNull() else 0
        self.selection_rect = QRect(0, 0, max(1, disp_w), max(1, disp_h))
        self.update()

    def keyPressEvent(self, e):
        """Handle keyboard input for selection editing.

        Args:
            e: QKeyEvent

        Arrow keys move the selection rectangle by 1 image pixel (original image coordinate).
        Shift+Arrow keys move by 10 image pixels.
        All movements operate in image coordinates and are converted to display coordinates,
        then clipped to image boundaries.
        """
        if not self.selection_rect or self.selection_rect.isNull():
            super().keyPressEvent(e)
            return

        # Delta in image pixels
        img_delta = 10 if e.modifiers() & Qt.ShiftModifier else 1
        # Convert to display pixels using current scale
        delta = int(img_delta * self.scale)
        if delta == 0:
            delta = 1  # Ensure at least 1 pixel movement in display coordinates

        new_rect = QRect(self.selection_rect)

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

        self.selection_rect = new_rect
        self.update()

        # Notify viewer of selection change
        if self.viewer:
            self.viewer.on_selection_changed(self.selection_rect)
