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
            self.dragging = True

    def mouseMoveEvent(self, ev):
        if self.showing and self.dragging:
            rect = QRect(self.start_point, ev.position().toPoint()).normalized()
            self.selection_rect = rect
            self.update()
        if hasattr(self.parent(), "on_mouse_move"):
            self.parent().on_mouse_move(ev.position().toPoint())

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.showing:
            self.dragging = False
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
        if not self.selection_rect:
            return None
        s = self.scale
        rect = QRect(
            int(self.selection_rect.x() / s),
            int(self.selection_rect.y() / s),
            int(self.selection_rect.width() / s),
            int(self.selection_rect.height() / s),
        )
        return rect

    def set_selection_full(self):
        if not self.showing:
            return
        w, h = self._pixmap.width(), self._pixmap.height()
        self.selection_rect = QRect(0, 0, w, h)
        self.update()
