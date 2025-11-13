"""Image label for tile display with ROI support."""

from typing import Optional
import numpy as np
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QPainter, QPen, QImage, QColor, QMouseEvent, QKeyEvent, QWheelEvent
from PySide6.QtCore import Qt, QRect, Signal

from PixelScopeViewer.core.image_io import numpy_to_qimage
from PixelScopeViewer.ui.dialogs.display.core.compute import apply_brightness_adjustment


class TileImageLabel(QLabel):
    """Image label for displaying tiles with ROI support.

    This is a simplified version of ImageLabel for tiling comparison.
    It displays images with brightness adjustment and ROI visualization,
    but ROI editing is only enabled when the tile is active.
    """

    # Signals
    roi_changed = Signal(object)  # Emits [x, y, w, h] or None
    clicked = Signal()  # Emits on left click
    zoom_requested = Signal(float)  # Emits zoom factor (e.g., 2.0 or 0.5)
    hover_info = Signal(int, int, str)  # Emits (ix, iy, valueText)

    def __init__(self):
        """Initialize tile image label."""
        super().__init__()

        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMinimumSize(100, 100)
        self.setMouseTracking(True)

        # Image data
        self.array = None
        self.qimage = None
        self.zoom_factor = 1.0

        # Brightness parameters
        self.gain = 1.0
        self.offset = 0.0
        self.saturation = 1.0

        # ROI
        self.roi_rect = None  # [x, y, w, h] in image coordinates
        self.roi_editable = False

        # Tracking
        self._drag_start = None
        self._original_roi = None
        self._roi_drag_mode = None  # 'create', 'move', 'resize', or None
        self._resize_edge = None  # 'left', 'right', 'top', 'bottom', 'tl', 'tr', 'bl', 'br'
        self._edge_grab_distance = 8  # pixels from edge to trigger resize

    def set_image(self, array: np.ndarray, gain: float, offset: float, saturation: float):
        """Set image data with brightness parameters.

        Args:
            array: Image array to display
            gain: Brightness gain
            offset: Brightness offset
            saturation: Saturation value
        """
        self.array = array
        self.gain = gain
        self.offset = offset
        self.saturation = saturation

        self._update_display()

    def _update_display(self):
        """Update displayed image with current brightness parameters."""
        if self.array is None:
            self.clear()
            return

        # Apply brightness adjustment
        adjusted = apply_brightness_adjustment(
            self.array, gain=self.gain, offset=self.offset, saturation=self.saturation
        )

        # Convert to QImage
        self.qimage = numpy_to_qimage(adjusted)

        if self.qimage is None:
            self.clear()
            return

        # Create pixmap and apply current zoom
        pixmap = QPixmap.fromImage(self.qimage)
        if self.zoom_factor != 1.0:
            w = max(1, int(self.qimage.width() * self.zoom_factor))
            h = max(1, int(self.qimage.height() * self.zoom_factor))
            pixmap = pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        self.setPixmap(pixmap)
        # Ensure scroll area can scroll
        self.setFixedSize(pixmap.size())
        self.update()

    def update_brightness(self, gain: float, offset: float, saturation: float):
        """Update brightness parameters and refresh display.

        Args:
            gain: Brightness gain
            offset: Brightness offset
            saturation: Saturation value
        """
        self.gain = gain
        self.offset = offset
        self.saturation = saturation
        self._update_display()

    def set_roi(self, roi_rect: Optional[list]):
        """Set ROI rectangle.

        Args:
            roi_rect: ROI rectangle [x, y, w, h] in image coordinates or None
        """
        self.roi_rect = roi_rect
        self.update()

    def get_roi(self) -> Optional[list]:
        """Get current ROI rectangle.

        Returns:
            ROI rectangle [x, y, w, h] or None
        """
        return self.roi_rect

    def clear_roi(self):
        """Clear ROI."""
        self.roi_rect = None
        self.update()

    def set_roi_editable(self, editable: bool):
        """Set whether ROI is editable.

        Args:
            editable: Whether ROI can be edited
        """
        self.roi_editable = editable

    def paintEvent(self, event):
        """Paint image and ROI overlay."""
        super().paintEvent(event)

        if self.roi_rect is None or self.qimage is None:
            return

        # Draw ROI rectangle
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Convert ROI using current zoom (top-left aligned)
        # Use integer truncation to align with pixel boundaries
        scale = max(0.0001, float(self.zoom_factor))
        roi_x = int(self.roi_rect[0] * scale)
        roi_y = int(self.roi_rect[1] * scale)
        roi_w = int(self.roi_rect[2] * scale)
        roi_h = int(self.roi_rect[3] * scale)

        # Draw ROI border: active=red, inactive=gray
        if self.roi_editable:
            pen = QPen(QColor(255, 51, 51), 2, Qt.SolidLine)  # Red for active
        else:
            pen = QPen(QColor(170, 170, 170), 2, Qt.SolidLine)  # Gray for inactive

        painter.setPen(pen)
        painter.drawRect(roi_x, roi_y, roi_w, roi_h)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for ROI editing or activation."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            if self.roi_editable and self.qimage is not None:
                # Check if clicking on edge/corner for resize
                edge = self._get_resize_edge(event.pos())
                if edge:
                    # Start resizing
                    self._drag_start = event.pos()
                    self._original_roi = self.roi_rect.copy() if self.roi_rect else None
                    self._roi_drag_mode = "resize"
                    self._resize_edge = edge
                    return
                else:
                    # Start creating new ROI
                    self._drag_start = event.pos()
                    self._original_roi = self.roi_rect.copy() if self.roi_rect else None
                    self._roi_drag_mode = "create"
                    # Start a new ROI at the clicked point
                    ix, iy = self._widget_to_image_coords(event.pos())
                    self.roi_rect = [ix, iy, 0, 0]
                    self.roi_changed.emit(self.roi_rect)
                    self.update()
                    return
        elif event.button() == Qt.RightButton:
            if self.roi_editable and self.roi_rect is not None and self.qimage is not None:
                # Check if click is inside existing ROI (but not on edge)
                edge = self._get_resize_edge(event.pos())
                if not edge:
                    ix, iy = self._widget_to_image_coords(event.pos())
                    rx, ry, rw, rh = self.roi_rect
                    if rx <= ix < rx + rw and ry <= iy < ry + rh:
                        # Start moving the ROI
                        self._drag_start = event.pos()
                        self._original_roi = self.roi_rect.copy()
                        self._roi_drag_mode = "move"
                        return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for ROI editing (drag to create/resize or move)."""
        # Update cursor when hovering over ROI edges (not dragging)
        if self.roi_editable and self._drag_start is None and self.roi_rect is not None and self.qimage is not None:
            edge = self._get_resize_edge(event.pos())
            self._update_cursor_for_edge(edge)

        if self.roi_editable and self._drag_start is not None and self.qimage is not None:
            if self._roi_drag_mode == "create":
                # Creating/resizing ROI
                x0, y0 = self._widget_to_image_coords(self._drag_start)
                x1, y1 = self._widget_to_image_coords(event.pos())
                x = min(x0, x1)
                y = min(y0, y1)
                w = abs(x1 - x0)
                h = abs(y1 - y0)
                self.roi_rect = [x, y, w, h]
                self.roi_changed.emit(self.roi_rect)
                self.update()
                return
            elif self._roi_drag_mode == "resize" and self._original_roi is not None:
                # Resizing existing ROI
                curr_ix, curr_iy = self._widget_to_image_coords(event.pos())
                orig_x, orig_y, orig_w, orig_h = self._original_roi
                edge = self._resize_edge

                # Start with original rectangle
                new_x, new_y, new_w, new_h = orig_x, orig_y, orig_w, orig_h

                # Handle horizontal resize
                if edge in ("left", "tl", "bl"):
                    new_x = max(0, min(curr_ix, orig_x + orig_w - 1))
                    new_w = orig_x + orig_w - new_x
                elif edge in ("right", "tr", "br"):
                    new_right = max(orig_x, min(curr_ix, self.qimage.width() - 1))
                    new_w = new_right - orig_x + 1

                # Handle vertical resize
                if edge in ("top", "tl", "tr"):
                    new_y = max(0, min(curr_iy, orig_y + orig_h - 1))
                    new_h = orig_y + orig_h - new_y
                elif edge in ("bottom", "bl", "br"):
                    new_bottom = max(orig_y, min(curr_iy, self.qimage.height() - 1))
                    new_h = new_bottom - orig_y + 1

                # Ensure minimum size
                new_w = max(1, new_w)
                new_h = max(1, new_h)

                self.roi_rect = [new_x, new_y, new_w, new_h]
                self.roi_changed.emit(self.roi_rect)
                self.update()
                return
            elif self._roi_drag_mode == "move" and self._original_roi is not None:
                # Moving existing ROI
                start_ix, start_iy = self._widget_to_image_coords(self._drag_start)
                curr_ix, curr_iy = self._widget_to_image_coords(event.pos())
                dx = curr_ix - start_ix
                dy = curr_iy - start_iy

                orig_x, orig_y, orig_w, orig_h = self._original_roi
                new_x = max(0, min(self.qimage.width() - orig_w, orig_x + dx))
                new_y = max(0, min(self.qimage.height() - orig_h, orig_y + dy))

                self.roi_rect = [new_x, new_y, orig_w, orig_h]
                self.roi_changed.emit(self.roi_rect)
                self.update()
                return

        # Hover info emit (always active when not dragging ROI)
        if self.qimage is not None and self.array is not None:
            ix, iy = self._widget_to_image_coords(event.pos())
            try:
                val = self.array[iy, ix]
                if isinstance(val, np.ndarray) or (hasattr(val, "shape") and len(getattr(val, "shape", ())) > 0):
                    flat = np.array(val).ravel().tolist()
                    preview = ", ".join(str(x) for x in flat[:4])
                    text = f"[{preview}{', …' if len(flat) > 4 else ''}]"
                else:
                    text = str(val)
                # Truncate overly long text
                if len(text) > 60:
                    text = text[:57] + "…"
            except Exception:
                text = ""
            self.hover_info.emit(int(ix), int(iy), text)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release to finalize ROI."""
        if self.roi_editable and (event.button() == Qt.LeftButton or event.button() == Qt.RightButton):
            # If creating ROI and size is 0, make it 1x1 pixel
            if self._roi_drag_mode == "create" and self.roi_rect is not None:
                x, y, w, h = self.roi_rect
                if w == 0:
                    w = 1
                if h == 0:
                    h = 1
                # Ensure within bounds
                if self.qimage is not None:
                    w = min(w, self.qimage.width() - x)
                    h = min(h, self.qimage.height() - y)
                self.roi_rect = [x, y, w, h]
                self.roi_changed.emit(self.roi_rect)

            self._drag_start = None
            self._original_roi = None
            self._roi_drag_mode = None
            self._resize_edge = None
            self.update()
            return
        super().mouseReleaseEvent(event)

    def set_zoom(self, factor: float):
        """Set zoom factor.

        Args:
            factor: Zoom factor (currently not used in fit-to-tile mode)
        """
        self.zoom_factor = max(0.1, min(32.0, float(factor)))
        # Rebuild pixmap at new scale
        if self.qimage is not None:
            self._update_display()

    def fit_to_view(self):
        """Fit image to view (default behavior)."""
        # For scroll-based view, fit is a no-op here. Managed by parent.
        pass

    # --- Utilities ---
    def _widget_to_image_coords(self, pos) -> tuple[int, int]:
        """Convert widget position to image pixel coordinates with zoom clamping."""
        if self.qimage is None:
            return (0, 0)
        scale = max(0.0001, float(self.zoom_factor))
        ix = int(pos.x() / scale)
        iy = int(pos.y() / scale)
        ix = max(0, min(ix, self.qimage.width() - 1))
        iy = max(0, min(iy, self.qimage.height() - 1))
        return (ix, iy)

    def _get_resize_edge(self, pos) -> Optional[str]:
        """Determine which edge of the ROI is near the cursor.

        Args:
            pos: Cursor position in widget coordinates

        Returns:
            Edge identifier: 'tl', 'tr', 'bl', 'br', 'left', 'right', 'top', 'bottom', or None
        """
        if not self.roi_rect or self.qimage is None:
            return None

        # Convert ROI to widget coordinates
        scale = max(0.0001, float(self.zoom_factor))
        roi_x = int(self.roi_rect[0] * scale)
        roi_y = int(self.roi_rect[1] * scale)
        roi_w = int(self.roi_rect[2] * scale)
        roi_h = int(self.roi_rect[3] * scale)
        roi_right = roi_x + roi_w
        roi_bottom = roi_y + roi_h

        dist = self._edge_grab_distance
        px = pos.x()
        py = pos.y()

        # For small ROIs, reduce grab distance
        min_dimension = min(roi_w, roi_h)
        if min_dimension < dist * 2:
            dist = max(1, min_dimension // 3)

        # Check corners first
        if abs(px - roi_x) <= dist and abs(py - roi_y) <= dist:
            return "tl"  # top-left
        if abs(px - roi_right) <= dist and abs(py - roi_y) <= dist:
            return "tr"  # top-right
        if abs(px - roi_x) <= dist and abs(py - roi_bottom) <= dist:
            return "bl"  # bottom-left
        if abs(px - roi_right) <= dist and abs(py - roi_bottom) <= dist:
            return "br"  # bottom-right

        # Check edges
        if abs(px - roi_x) <= dist and roi_y <= py <= roi_bottom:
            return "left"
        if abs(px - roi_right) <= dist and roi_y <= py <= roi_bottom:
            return "right"
        if abs(py - roi_y) <= dist and roi_x <= px <= roi_right:
            return "top"
        if abs(py - roi_bottom) <= dist and roi_x <= px <= roi_right:
            return "bottom"

        return None

    def _update_cursor_for_edge(self, edge: Optional[str]):
        """Update cursor shape based on which edge is being hovered.

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

    def keyPressEvent(self, event: QKeyEvent):
        """Support nudging ROI with arrow keys (1px, Shift:10px)."""
        if self.roi_rect is None or self.qimage is None:
            super().keyPressEvent(event)
            return
        step = 10 if event.modifiers() & Qt.ShiftModifier else 1
        x, y, w, h = self.roi_rect
        if event.key() == Qt.Key_Left:
            x = max(0, x - step)
        elif event.key() == Qt.Key_Right:
            x = min(self.qimage.width() - w, x + step)
        elif event.key() == Qt.Key_Up:
            y = max(0, y - step)
        elif event.key() == Qt.Key_Down:
            y = min(self.qimage.height() - h, y + step)
        else:
            super().keyPressEvent(event)
            return
        self.roi_rect = [x, y, w, h]
        self.roi_changed.emit(self.roi_rect)
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        """Handle Ctrl+wheel for zoom; otherwise defer to default (scroll)."""
        if event.modifiers() & Qt.ControlModifier:
            dy = event.angleDelta().y()
            if dy == 0:
                event.accept()
                return
            factor = 2.0 if dy > 0 else 0.5
            self.zoom_requested.emit(factor)
            event.accept()
            return
        # Let parent scroll area handle scrolling
        event.ignore()
