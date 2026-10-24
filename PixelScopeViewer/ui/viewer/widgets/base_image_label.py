"""zoom と座標変換に対応した画像表示 widget の基底クラス。"""

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel


class BaseImageLabel(QLabel):
    """zoom 表示と widget/画像座標の変換を行う QLabel。"""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._orig_pixmap = QPixmap()
        self._qimage: QImage | None = None
        self.scale = 1.0
        self.showing = False

    def set_image(self, qimg: QImage, scale: float = 1.0):
        """画像を指定の zoom 倍率で表示する。"""
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
        self._orig_pixmap = QPixmap()
        self._qimage = None
        self.setFixedSize(0, 0)
        self.showing = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self._orig_pixmap.isNull():
            painter.save()
            painter.scale(self.scale, self.scale)
            painter.drawPixmap(0, 0, self._orig_pixmap)
            painter.restore()

    # --- 座標変換 ---
    def _display_scale_factor(self) -> float | None:
        """画像 1 pixel あたりの表示 pixel 数を返す。画像がない場合は None。"""
        if self._qimage is None or self._qimage.isNull() or not self.scale or self.scale <= 0:
            return None
        return float(self.scale)

    def _widget_to_image_point(self, pt: QPoint) -> tuple[int, int] | None:
        """widget 座標を画像の pixel 座標に変換する。画像がない場合は None。"""
        factor = self._display_scale_factor()
        if factor is None or self._qimage is None:
            return None
        ix = max(0, min(int(pt.x() / factor), self._qimage.width() - 1))
        iy = max(0, min(int(pt.y() / factor), self._qimage.height() - 1))
        return (ix, iy)

    def _image_to_widget_x(self, ix: int) -> int:
        factor = self._display_scale_factor() or 1.0
        return int(round(ix * factor))

    def _image_to_widget_y(self, iy: int) -> int:
        factor = self._display_scale_factor() or 1.0
        return int(round(iy * factor))

    def _image_rect_to_widget(self, img_rect: QRect) -> QRect:
        """画像座標の矩形を widget 座標に変換する。"""
        left = self._image_to_widget_x(img_rect.left())
        top = self._image_to_widget_y(img_rect.top())
        right_ex = self._image_to_widget_x(img_rect.left() + img_rect.width())
        bottom_ex = self._image_to_widget_y(img_rect.top() + img_rect.height())
        w = max(1, right_ex - left)
        h = max(1, bottom_ex - top)
        return QRect(left, top, w, h)

    def _widget_rect_to_image(self, widget_rect: QRect) -> QRect | None:
        """widget 座標の矩形を画像座標に変換する。画像がない場合は None。"""
        if self._qimage is None or self._qimage.isNull():
            return None

        src_w = self._qimage.width()
        src_h = self._qimage.height()
        disp_w = int(self._orig_pixmap.width() * self.scale)
        disp_h = int(self._orig_pixmap.height() * self.scale)

        if not all([disp_w, disp_h, src_w, src_h]):
            return None

        fx = disp_w / src_w
        fy = disp_h / src_h

        left = max(0, min(int(widget_rect.left() / fx), src_w))
        top = max(0, min(int(widget_rect.top() / fy), src_h))
        right_ex = max(0, min(int((widget_rect.left() + widget_rect.width()) / fx), src_w))
        bottom_ex = max(0, min(int((widget_rect.top() + widget_rect.height()) / fy), src_h))

        w = max(0, right_ex - left)
        h = max(0, bottom_ex - top)
        return QRect(left, top, w, h)
