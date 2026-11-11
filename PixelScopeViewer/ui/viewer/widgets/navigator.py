"""表示領域を示す thumbnail の navigator widget。"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage


class NavigatorWidget(QGroupBox):
    """thumbnail 上に表示領域を赤枠で示し、クリック位置へ表示領域を移動する widget。

    タイル比較モードでは各タイルの thumbnail をグリッドのまま並べ、全マスに同じ表示領域の枠を描く。
    マスの縮小倍率は表示中の画像の最大の幅・高さで共通にする。
    """

    def __init__(self, viewer):
        super().__init__("Navigator")
        self.viewer = viewer

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(200, 200)
        self.thumbnail_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.thumbnail_label)
        layout.addStretch()

        self.viewer.scale_changed.connect(self.update_thumbnail)
        self.viewer.image_changed.connect(self.update_thumbnail)
        # scroll や viewport の resize でも更新する
        self.viewer.view_changed.connect(self.update_thumbnail)

        # クリックで表示領域を移動する
        self.thumbnail_label.installEventFilter(self)
        # 画像 1 pixel あたりの thumbnail の pixel 数と、マス 1 つの thumbnail 上の大きさ
        self._factor: float | None = None
        self._cell_size: tuple[float, float] = (0.0, 0.0)
        # 枠を描く前のモザイク（タイル比較モード）と、その作成に使った表示内容
        self._mosaic: QPixmap | None = None
        self._mosaic_key = None

        self.update_thumbnail()

    def eventFilter(self, obj, event):
        if obj is self.thumbnail_label and event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.handle_mouse_press(event)
        return super().eventFilter(obj, event)

    def handle_mouse_press(self, event: QMouseEvent):
        """クリックした位置（タイル比較モードではそのマスの中の位置）が中心になるよう表示領域を移動する。"""
        pixmap = self.thumbnail_label.pixmap()
        if self._factor is None or not pixmap or pixmap.isNull():
            return

        # label は AlignTop | AlignHCenter なので、pixmap は水平方向のみ中央寄せされる
        x_offset = (self.thumbnail_label.width() - pixmap.width()) / 2
        px = event.pos().x() - x_offset
        py = event.pos().y()
        if not (0 <= px <= pixmap.width() and 0 <= py <= pixmap.height()):
            return

        cell_w, cell_h = self._cell_size
        img_x = (px % cell_w) / self._factor
        img_y = (py % cell_h) / self._factor

        scroll_area = self.viewer.scroll_area
        viewport = scroll_area.viewport()
        scale = self.viewer.state.scale
        h_scroll = img_x * scale - viewport.width() / 2
        v_scroll = img_y * scale - viewport.height() / 2
        label = self.viewer.image_label
        h_scroll = max(0, min(h_scroll, label.width() - viewport.width()))
        v_scroll = max(0, min(v_scroll, label.height() - viewport.height()))
        scroll_area.horizontalScrollBar().setValue(int(h_scroll))
        scroll_area.verticalScrollBar().setValue(int(v_scroll))

        event.accept()

    def _view_rect(self) -> tuple[float, float, float, float]:
        """表示領域を画像座標の (x, y, w, h) で返す。"""
        scroll_area = self.viewer.scroll_area
        s = self.viewer.state.scale
        return (
            scroll_area.horizontalScrollBar().value() / s,
            scroll_area.verticalScrollBar().value() / s,
            scroll_area.viewport().width() / s,
            scroll_area.viewport().height() / s,
        )

    def update_thumbnail(self):
        """thumbnail と表示領域の枠を更新する。"""
        if self.viewer.state.tile_mode:
            self._update_mosaic()
            return
        self._mosaic = None
        self._mosaic_key = None
        if self.viewer.state.current_index is None or not self.viewer.images:
            self.thumbnail_label.clear()
            self._factor = None
            return

        img_data = self.viewer.images[self.viewer.state.current_index]
        h, w = img_data["array"].shape[:2]

        base_pixmap = img_data.get("thumbnail_pixmap")
        if not base_pixmap:
            # cache がない場合はその場で生成する
            qimg = numpy_to_qimage(img_data["array"])
            base_pixmap = QPixmap.fromImage(qimg).scaled(
                self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        # cache を書き換えないよう copy に描画する
        scaled_pixmap = base_pixmap.copy()
        self._factor = min(scaled_pixmap.width() / w, scaled_pixmap.height() / h)
        self._cell_size = (float(scaled_pixmap.width()), float(scaled_pixmap.height()))
        self._draw_view_rects(scaled_pixmap, [(0.0, 0.0)])
        self.thumbnail_label.setPixmap(scaled_pixmap)

    def _update_mosaic(self):
        tiles = self.viewer.tiles
        canvas = tiles.canvas_size()
        if canvas is None:
            self.thumbnail_label.clear()
            self._factor = None
            return
        layout = tiles.layout
        visible = tiles.visible_images()
        box_w, box_h = self.thumbnail_label.width(), self.thumbnail_label.height()
        factor = min(box_w / (canvas[0] * layout.cols), box_h / (canvas[1] * layout.rows))
        cell_w, cell_h = canvas[0] * factor, canvas[1] * factor
        self._factor = factor
        self._cell_size = (cell_w, cell_h)

        key = (layout.rows, layout.cols, canvas, tuple(img["id"] if img else None for _, img in visible))
        if key != self._mosaic_key or self._mosaic is None:
            mosaic = QPixmap(max(1, round(cell_w * layout.cols)), max(1, round(cell_h * layout.rows)))
            mosaic.fill(QColor(theme.TILE_ROW_BACKGROUND))
            painter = QPainter(mosaic)
            for (r, c), img in visible:
                x0, y0 = c * cell_w, r * cell_h
                if img is not None:
                    h, w = img["array"].shape[:2]
                    thumb = img.get("thumbnail_pixmap")
                    if thumb is not None:
                        size = (max(1, round(w * factor)), max(1, round(h * factor)))
                        painter.drawPixmap(
                            round(x0), round(y0), thumb.scaled(*size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        )
                painter.setPen(QPen(QColor(theme.TILE_INACTIVE_BORDER), 1))
                painter.drawRect(round(x0), round(y0), round(cell_w) - 1, round(cell_h) - 1)
            painter.end()
            self._mosaic = mosaic
            self._mosaic_key = key

        pixmap = self._mosaic.copy()
        self._draw_view_rects(pixmap, [(c * cell_w, r * cell_h) for (r, c), _ in visible])
        self.thumbnail_label.setPixmap(pixmap)

    def _draw_view_rects(self, pixmap: QPixmap, origins: list[tuple[float, float]]):
        """各マスの原点 origins から、表示領域の枠を描く。"""
        x, y, w, h = (v * self._factor for v in self._view_rect())
        cell_w, cell_h = self._cell_size
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(theme.NAVIGATOR_VIEW_RECT_COLOR), 2))
        for ox, oy in origins:
            painter.save()
            painter.setClipRect(round(ox), round(oy), round(cell_w), round(cell_h))
            painter.drawRect(round(ox + x), round(oy + y), int(w), int(h))
            painter.restore()
        painter.end()
