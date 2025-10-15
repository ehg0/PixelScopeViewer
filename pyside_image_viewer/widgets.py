from typing import Optional
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QRect, QPoint


class ImageLabel(QLabel):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMouseTracking(True)
        self._pixmap = QPixmap()
        self.scale = 1.0
        self.selection_rect: Optional[QRect] = None
        self.dragging = False
        self.showing = False
        self.start_point = QPoint()

    def set_qimage(self, qimg, scale: float = 1.0):
        self.scale = scale
        self._qimage = qimg
        if qimg.isNull():
            self._pixmap = QPixmap()
            self.setPixmap(self._pixmap)
            self.showing = False
            return
        pix = QPixmap.fromImage(qimg)
        if scale != 1.0:
            pix = pix.scaled(int(pix.width() * scale), int(pix.height() * scale), Qt.KeepAspectRatio)
        self._pixmap = pix
        self.setPixmap(self._pixmap)
        self.adjustSize()
        self.showing = True
        self.selection_rect = None
        self.update()

    def clear(self):
        self._pixmap = QPixmap()
        self.setPixmap(self._pixmap)
        self.showing = False
        self.selection_rect = None
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.showing:
            self.start_point = ev.position().toPoint()
            # store start in image pixel coords for pixel-step snapping
            self._start_img = self._widget_to_image_point(self.start_point)
            self.dragging = True

    def mouseMoveEvent(self, ev):
        if self.showing and self.dragging:
            cur_pt = ev.position().toPoint()
            cur_img = self._widget_to_image_point(cur_pt)
            start_img = getattr(self, "_start_img", None)
            if start_img is None or cur_img is None:
                return
            # integer image pixel coords
            x0 = min(start_img[0], cur_img[0])
            x1 = max(start_img[0], cur_img[0])
            y0 = min(start_img[1], cur_img[1])
            y1 = max(start_img[1], cur_img[1])
            # map back to widget/display coords to draw a rectangle that aligns with pixels
            left = self._image_to_widget_x(x0)
            top = self._image_to_widget_y(y0)
            right_ex = self._image_to_widget_x(x1 + 1)
            bottom_ex = self._image_to_widget_y(y1 + 1)
            w = max(1, right_ex - left)
            h = max(1, bottom_ex - top)
            self.selection_rect = QRect(left, top, w, h)
            self.update()

        if hasattr(self.parent(), "on_mouse_move"):
            if self.showing:
                # send clamped point in displayed-image pixel coords
                w, h = self._pixmap.width(), self._pixmap.height()
                p = ev.position().toPoint()
                p = QPoint(max(0, min(p.x(), max(0, w - 1))), max(0, min(p.y(), max(0, h - 1))))
                self.parent().on_mouse_move(p)
            else:
                self.parent().on_mouse_move(ev.position().toPoint())

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.showing:
            self.dragging = False
            # finalize selection snapped to image pixels
            end_img = self._widget_to_image_point(ev.position().toPoint())
            start_img = getattr(self, "_start_img", None)
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

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection_rect and not self.selection_rect.isNull():
            painter = QPainter(self)
            pen = QPen(QColor(0, 0, 255), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.selection_rect)

    def get_selection_in_image_coords(self):
        # Map the selection rectangle (which is in displayed/widget pixel coords)
        # to source image pixel coordinates using the actual displayed pixmap size
        # and the original QImage size. This is more accurate than dividing by
        # self.scale because KeepAspectRatio and integer rounding can change
        # the displayed dimensions.
        if not self.selection_rect or self.selection_rect.isNull():
            return None
        if not hasattr(self, "_qimage") or self._qimage is None or self._qimage.isNull():
            return None

        disp_w = self._pixmap.width()
        disp_h = self._pixmap.height()
        src_w = self._qimage.width()
        src_h = self._qimage.height()
        if disp_w == 0 or disp_h == 0 or src_w == 0 or src_h == 0:
            return None

        # factors: how many displayed pixels per source pixel
        fx = disp_w / src_w
        fy = disp_h / src_h

        left = int(self.selection_rect.left() / fx)
        top = int(self.selection_rect.top() / fy)
        # right/bottom are exclusive: map widget edge to source pixel index just past the last pixel
        right_ex = int((self.selection_rect.left() + self.selection_rect.width()) / fx)
        bottom_ex = int((self.selection_rect.top() + self.selection_rect.height()) / fy)

        # clamp to source bounds
        left = max(0, min(left, src_w))
        top = max(0, min(top, src_h))
        right_ex = max(0, min(right_ex, src_w))
        bottom_ex = max(0, min(bottom_ex, src_h))

        w = max(0, right_ex - left)
        h = max(0, bottom_ex - top)
        return QRect(left, top, w, h)

    # --- helper conversions between widget coords and source image pixel coords ---
    def _display_scale_factor(self) -> Optional[float]:
        """Return displayed pixels per source image pixel (fx, fy assumed equal since KeepAspectRatio used)."""
        if not hasattr(self, "_qimage") or self._qimage is None or self._qimage.isNull():
            return None
        src_w = self._qimage.width()
        disp_w = self._pixmap.width()
        if src_w <= 0:
            return None
        return float(disp_w) / float(src_w)

    def _widget_to_image_point(self, pt: QPoint):
        """Map a QPoint in widget/display coords to integer image pixel coords (x,y).

        Returns tuple (ix, iy) or None on failure.
        """
        factor = self._display_scale_factor()
        if factor is None or factor == 0:
            return None
        ix = int(pt.x() / factor)
        iy = int(pt.y() / factor)
        # clamp to valid pixel indices
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
        w, h = self._pixmap.width(), self._pixmap.height()
        self.selection_rect = QRect(0, 0, w, h)
        self.update()
