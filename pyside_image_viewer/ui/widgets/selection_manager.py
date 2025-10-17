"""Selection management mixin for image widgets.

This module provides selection creation, moving, and resizing functionality.
"""

from typing import Optional
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import Qt, QRect, QPoint


class SelectionManagerMixin:
    """Mixin for selection rectangle management.

    This mixin adds:
    - Left-drag: Create new selection rectangle (pixel-aligned)
    - Right-drag: Move existing selection
    - Left-drag on edges/corners: Resize selection

    Features:
    - 8 grab points (4 corners + 4 edges) for resizing
    - Cursor shape feedback during hover
    - Pixel-aligned selection

    Required attributes from base class:
    - showing, viewer, selection_rect, scale
    - _orig_pixmap, _qimage
    - _widget_to_image_point, _image_to_widget_x, _image_to_widget_y
    - _widget_rect_to_image
    """

    def __init_selection_manager__(self):
        """Initialize selection manager state."""
        self.selection_rect: Optional[QRect] = None
        self.dragging = False
        self._moving = False
        self._resizing = False
        self._resize_edge = None  # 'left', 'right', 'top', 'bottom', 'tl', 'tr', 'bl', 'br'
        self.start_point = QPoint()
        self._start_img = None
        self._move_start_img = None
        self._move_orig_img_rect = None
        self._resize_start_img = None
        self._resize_orig_img_rect = None
        self._edge_grab_distance = 8  # pixels from edge to trigger resize

    def mousePressEvent(self, ev):
        """Handle mouse press for selection operations."""
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
        """Handle mouse move for selection operations."""
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
                self._notify_selection_changed()
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
                self._notify_selection_changed()
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
                self._notify_selection_changed()

        # Notify parent of mouse move
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
        """Handle mouse release for selection operations."""
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
                self._notify_selection_changed()
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
                self._notify_selection_changed()
            return
        if ev.button() == Qt.RightButton:
            # finish moving
            if getattr(self, "_moving", False):
                self._moving = False
                self._move_start_img = None
                self._move_orig_img_rect = None
                self.dragging = False
                self.update()
                self._notify_selection_changed()
            return

    def paint_selection(self, painter: QPainter):
        """Paint the selection rectangle.

        Args:
            painter: QPainter to use for painting
        """
        if self.selection_rect and not self.selection_rect.isNull():
            pen = QPen(QColor(0, 0, 255), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.selection_rect)

    def get_selection_in_image_coords(self) -> Optional[QRect]:
        """Get the current selection rectangle in image coordinates.

        Returns:
            QRect in image pixel coordinates, or None if no selection.
        """
        if not self.selection_rect or self.selection_rect.isNull():
            return None
        return self._widget_rect_to_image(self.selection_rect)

    def set_selection_full(self):
        """Set selection to full image."""
        if not self.showing:
            return
        disp_w = int(self._orig_pixmap.width() * self.scale) if not self._orig_pixmap.isNull() else 0
        disp_h = int(self._orig_pixmap.height() * self.scale) if not self._orig_pixmap.isNull() else 0
        self.selection_rect = QRect(0, 0, max(1, disp_w), max(1, disp_h))
        self.update()

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

    def _notify_selection_changed(self):
        """Notify viewer of selection change during drag operations."""
        if self.viewer and self.selection_rect and not self.selection_rect.isNull():
            self.viewer.on_selection_changed(self.selection_rect)
