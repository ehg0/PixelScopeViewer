"""表示領域を示す thumbnail の navigator widget。"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from ...core.image_io import numpy_to_qimage


class NavigatorWidget(QGroupBox):
    """thumbnail 上に表示領域を赤枠で示し、クリック位置へ表示領域を移動する widget。"""

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
        sa = self.viewer.scroll_area
        sa.horizontalScrollBar().valueChanged.connect(self.update_thumbnail)
        sa.verticalScrollBar().valueChanged.connect(self.update_thumbnail)
        sa.viewport().installEventFilter(self)

        # クリックで表示領域を移動する
        self.thumbnail_label.installEventFilter(self)
        self.thumb_rect = None  # thumbnail 座標での表示領域 (x, y, w, h)

        self.update_thumbnail()

    def eventFilter(self, obj, event):
        try:
            if obj is self.viewer.scroll_area.viewport() and event.type() == QEvent.Resize:
                self.update_thumbnail()
            elif (
                obj is self.thumbnail_label
                and event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
            ):
                self.handle_mouse_press(event)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def handle_mouse_press(self, event: QMouseEvent):
        """クリックした位置が中心になるよう表示領域を移動する。"""
        if self.thumb_rect is None:
            return

        pixmap = self.thumbnail_label.pixmap()
        if not pixmap:
            return

        thumb_width = pixmap.width()
        thumb_height = pixmap.height()

        # label は AlignTop | AlignHCenter なので、pixmap は水平方向のみ中央寄せされる
        label_width = self.thumbnail_label.width()
        x_offset = (label_width - thumb_width) / 2
        y_offset = 0

        mouse_pos = event.pos()

        if not (
            x_offset <= mouse_pos.x() <= x_offset + thumb_width and y_offset <= mouse_pos.y() <= y_offset + thumb_height
        ):
            return

        pixmap_x = mouse_pos.x() - x_offset
        pixmap_y = mouse_pos.y() - y_offset

        # 画像座標に変換する
        img = self.viewer.images[self.viewer.current_index]["array"]
        h, w = img.shape[:2]
        scale_factor = min(thumb_width / w, thumb_height / h)

        img_x = pixmap_x / scale_factor
        img_y = pixmap_y / scale_factor

        viewport_width = self.viewer.scroll_area.viewport().width()
        viewport_height = self.viewer.scroll_area.viewport().height()

        # クリック位置が viewport の中心になる scroll 位置を求める
        widget_click_x = img_x * self.viewer.scale
        widget_click_y = img_y * self.viewer.scale

        h_scroll = widget_click_x - viewport_width / 2
        v_scroll = widget_click_y - viewport_height / 2

        h_scroll = max(0, min(h_scroll, self.viewer.image_label.width() - viewport_width))
        v_scroll = max(0, min(v_scroll, self.viewer.image_label.height() - viewport_height))

        scroll_area = self.viewer.scroll_area
        scroll_area.horizontalScrollBar().setValue(int(h_scroll))
        scroll_area.verticalScrollBar().setValue(int(v_scroll))

        event.accept()

    def update_thumbnail(self):
        """thumbnail と表示領域の枠を更新する。"""
        if self.viewer.current_index is None or not self.viewer.images:
            self.thumbnail_label.clear()
            self.thumb_rect = None
            return

        img_data = self.viewer.images[self.viewer.current_index]
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

        scale_factor = min(scaled_pixmap.width() / w, scaled_pixmap.height() / h)

        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        h_scroll = scroll_area.horizontalScrollBar().value()
        v_scroll = scroll_area.verticalScrollBar().value()

        # 表示領域を画像座標 → thumbnail 座標に変換する
        img_x = h_scroll / self.viewer.scale
        img_y = v_scroll / self.viewer.scale
        img_w = viewport_width / self.viewer.scale
        img_h = viewport_height / self.viewer.scale

        thumb_x = int(img_x * scale_factor)
        thumb_y = int(img_y * scale_factor)
        thumb_w = int(img_w * scale_factor)
        thumb_h = int(img_h * scale_factor)

        self.thumb_rect = (thumb_x, thumb_y, thumb_w, thumb_h)

        painter = QPainter(scaled_pixmap)
        pen = QPen(QColor(255, 68, 68, 255), 2)
        painter.setPen(pen)
        painter.drawRect(thumb_x, thumb_y, thumb_w, thumb_h)
        painter.end()

        self.thumbnail_label.setPixmap(scaled_pixmap)
