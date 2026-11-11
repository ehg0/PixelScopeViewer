"""zoom と座標変換に対応した画像表示 widget の基底クラス。"""

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel


class BaseImageLabel(QLabel):
    """zoom 表示と widget/画像座標の変換を行う QLabel。

    canvas size を設定すると、widget の大きさを画像より大きい canvas（画像座標）に合わせ、画像は左上に描く。
    タイル比較モードで全タイルの scroll 範囲を揃えるために使う。
    """

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._orig_pixmap = QPixmap()
        self._img_w = 0
        self._img_h = 0
        self._canvas: tuple[int, int] | None = None
        self.scale = 1.0
        self.showing = False

    def set_image(self, image: QImage | QPixmap, scale: float = 1.0):
        """画像を指定の zoom 倍率で表示する。"""
        pixmap = image if isinstance(image, QPixmap) else QPixmap.fromImage(image)
        self.scale = scale
        self._orig_pixmap = pixmap
        self.showing = not pixmap.isNull()
        self._img_w, self._img_h = (pixmap.width(), pixmap.height()) if self.showing else (0, 0)
        self._apply_size()
        self.update()

    def clear(self):
        self._orig_pixmap = QPixmap()
        self._img_w = self._img_h = 0
        self.showing = False
        self._apply_size()
        self.update()

    def set_canvas_size(self, size: tuple[int, int] | None, scale: float | None = None):
        """widget の大きさの基準にする canvas（画像座標の幅・高さ）を設定する。None の場合は画像の大きさにする。"""
        self._canvas = size
        if scale is not None:
            self.scale = scale
        self._apply_size()

    def _apply_size(self):
        w, h = self._img_w, self._img_h
        if self._canvas is not None:
            w, h = max(w, self._canvas[0]), max(h, self._canvas[1])
        if w == 0 or h == 0:
            self.setFixedSize(0, 0)
            return
        self.setFixedSize(max(1, int(w * self.scale)), max(1, int(h * self.scale)))

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
        if not self.showing or not self.scale or self.scale <= 0:
            return None
        return float(self.scale)

    def _widget_to_image_point(self, pt: QPoint) -> tuple[int, int] | None:
        """widget 座標を画像の範囲内に収めた pixel 座標に変換する。画像がない場合は None。"""
        factor = self._display_scale_factor()
        if factor is None:
            return None
        ix = max(0, min(int(pt.x() / factor), self._img_w - 1))
        iy = max(0, min(int(pt.y() / factor), self._img_h - 1))
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
