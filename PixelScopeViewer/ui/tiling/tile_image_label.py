"""複数画像比較の tile の画像表示 label。"""

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QLabel

from PixelScopeViewer.core.brightness import apply_brightness_adjustment
from PixelScopeViewer.core.constants import MAX_ZOOM_SCALE, MIN_ZOOM_SCALE, ZOOM_STEP
from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage


def format_pixel_value(val, max_len: int, fmt=str) -> str:
    """pixel 値を表示用の文字列にする。多 channel は先頭 4 つを [a, b, ...] で示し、max_len を超えたら省略する。"""
    if np.ndim(val) > 0:
        flat = np.ravel(val).tolist()
        text = f"[{', '.join(fmt(x) for x in flat[:4])}{', …' if len(flat) > 4 else ''}]"
    else:
        text = fmt(val)
    return text if len(text) <= max_len else text[: max_len - 3] + "…"


class TileImageLabel(QLabel):
    """brightness を適用した画像と ROI を表示する QLabel。ROI は active な tile でのみ編集できる。"""

    roi_changed = Signal(object)  # [x, y, w, h] または None
    clicked = Signal()
    zoom_requested = Signal(float, object)  # (倍率, マウス位置または None)
    hover_info = Signal(int, int, str)  # (x, y, 値の文字列)

    def __init__(self):
        super().__init__()

        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMinimumSize(100, 100)
        self.setMouseTracking(True)

        self.array = None
        self.qimage = None
        self.original_qimage = None  # ROI の計算に使う等倍の画像
        self.zoom_factor = 1.0

        # brightness 適用後の画像の cache
        self._cached_brightness_qimage = None
        self._cached_brightness_params = None

        self.gain = 1.0
        self.offset = 0.0
        self.upper_level = 1.0

        self.roi_rect = None  # 画像座標の [x, y, w, h]
        self.roi_editable = False

        # drag 操作の状態
        self._drag_start = None
        self._original_roi = None
        self._roi_drag_mode = None  # 'create', 'move', 'resize', or None
        self._resize_edge = None  # 'left', 'right', 'top', 'bottom', 'tl', 'tr', 'bl', 'br'
        self._edge_grab_distance = 8  # リサイズ判定に使う辺からの距離（pixel）

    def set_image(self, array: np.ndarray, gain: float, offset: float, upper_level: float):
        """画像と brightness を設定して表示を更新する。"""
        self.array = array
        self.gain = gain
        self.offset = offset
        self.upper_level = upper_level

        self._update_display()

    def _update_display(self):
        """brightness と zoom 倍率を適用して表示する。brightness が変わらなければ cache を使う。"""
        if self.array is None:
            self.clear()
            return

        current_brightness_params = (self.gain, self.offset, self.upper_level)
        brightness_changed = self._cached_brightness_params != current_brightness_params

        if brightness_changed or self._cached_brightness_qimage is None:
            adjusted = apply_brightness_adjustment(
                self.array, gain=self.gain, offset=self.offset, upper_level=self.upper_level
            )

            self._cached_brightness_qimage = numpy_to_qimage(adjusted)
            self._cached_brightness_params = current_brightness_params

            if self._cached_brightness_qimage is None:
                self.clear()
                return

        self.original_qimage = self._cached_brightness_qimage
        self.qimage = self.original_qimage

        target_w = max(1, int(self.original_qimage.width() * self.zoom_factor))
        target_h = max(1, int(self.original_qimage.height() * self.zoom_factor))

        # 正確に比較できるよう nearest neighbor で拡大縮小し、pixel 値を保つ
        pixmap = QPixmap.fromImage(self.original_qimage)
        if self.zoom_factor != 1.0:
            pixmap = pixmap.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.FastTransformation)

        self.setPixmap(pixmap)
        # scroll area で scroll できるようサイズを固定する
        self.setFixedSize(pixmap.size())
        self.update()

    def set_roi(self, roi_rect: list | None):
        """画像座標の ROI [x, y, w, h]（または None）を設定する。"""
        self.roi_rect = roi_rect
        self.update()

    def clear_roi(self):
        self.roi_rect = None
        self.update()

    def set_roi_editable(self, editable: bool):
        self.roi_editable = editable

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.roi_rect is None or self.qimage is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # pixel の境界に揃うよう、切り捨てで表示座標に変換する
        scale = max(0.0001, float(self.zoom_factor))
        roi_x = int(self.roi_rect[0] * scale)
        roi_y = int(self.roi_rect[1] * scale)
        roi_w = int(self.roi_rect[2] * scale)
        roi_h = int(self.roi_rect[3] * scale)

        # active はメインビューアと同じ緑、非 active は灰色
        if self.roi_editable:
            pen = QPen(QColor(theme.ROI_COLOR), 2, Qt.SolidLine)
        else:
            pen = QPen(QColor(theme.ROI_INACTIVE_COLOR), 2, Qt.SolidLine)

        painter.setPen(pen)
        painter.drawRect(roi_x, roi_y, roi_w, roi_h)

    def mousePressEvent(self, event: QMouseEvent):
        # 左: 辺・角ならリサイズ、それ以外は ROI 作成。右: ROI の内側なら移動
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            if self.roi_editable and self.qimage is not None:
                edge = self._get_resize_edge(event.pos())
                if edge:
                    self._drag_start = event.pos()
                    self._original_roi = self.roi_rect.copy() if self.roi_rect else None
                    self._roi_drag_mode = "resize"
                    self._resize_edge = edge
                    return
                else:
                    self._drag_start = event.pos()
                    self._original_roi = self.roi_rect.copy() if self.roi_rect else None
                    self._roi_drag_mode = "create"
                    ix, iy = self._widget_to_image_coords(event.pos())
                    self.roi_rect = [ix, iy, 0, 0]
                    self.roi_changed.emit(self.roi_rect)
                    self.update()
                    return
        elif event.button() == Qt.RightButton:
            if self.roi_editable and self.roi_rect is not None and self.qimage is not None:
                edge = self._get_resize_edge(event.pos())
                if not edge:
                    ix, iy = self._widget_to_image_coords(event.pos())
                    rx, ry, rw, rh = self.roi_rect
                    if rx <= ix < rx + rw and ry <= iy < ry + rh:
                        self._drag_start = event.pos()
                        self._original_roi = self.roi_rect.copy()
                        self._roi_drag_mode = "move"
                        return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # ROI の辺に hover したら cursor を変える
        if self.roi_editable and self._drag_start is None and self.roi_rect is not None and self.qimage is not None:
            edge = self._get_resize_edge(event.pos())
            self._update_cursor_for_edge(edge)

        if self.roi_editable and self._drag_start is not None and self.qimage is not None:
            if self._roi_drag_mode == "create":
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
                curr_ix, curr_iy = self._widget_to_image_coords(event.pos())
                orig_x, orig_y, orig_w, orig_h = self._original_roi
                edge = self._resize_edge

                new_x, new_y, new_w, new_h = orig_x, orig_y, orig_w, orig_h

                # 水平方向（左右の辺と角）
                if edge in ("left", "tl", "bl"):
                    new_x = max(0, min(curr_ix, orig_x + orig_w - 1))
                    new_w = orig_x + orig_w - new_x
                elif edge in ("right", "tr", "br"):
                    new_right = max(orig_x, min(curr_ix, self.qimage.width() - 1))
                    new_w = new_right - orig_x + 1

                # 垂直方向（上下の辺と角）
                if edge in ("top", "tl", "tr"):
                    new_y = max(0, min(curr_iy, orig_y + orig_h - 1))
                    new_h = orig_y + orig_h - new_y
                elif edge in ("bottom", "bl", "br"):
                    new_bottom = max(orig_y, min(curr_iy, self.qimage.height() - 1))
                    new_h = new_bottom - orig_y + 1

                new_w = max(1, new_w)
                new_h = max(1, new_h)

                self.roi_rect = [new_x, new_y, new_w, new_h]
                self.roi_changed.emit(self.roi_rect)
                self.update()
                return
            elif self._roi_drag_mode == "move" and self._original_roi is not None:
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

        # ROI の drag 中以外はマウス位置の値を通知する
        if self.qimage is not None and self.array is not None:
            ix, iy = self._widget_to_image_coords(event.pos())
            h, w = self.array.shape[:2]
            text = format_pixel_value(self.array[iy, ix], 60) if 0 <= iy < h and 0 <= ix < w else ""
            self.hover_info.emit(int(ix), int(iy), text)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.roi_editable and (event.button() == Qt.LeftButton or event.button() == Qt.RightButton):
            # 作成した ROI のサイズが 0 の場合は 1x1 にする
            if self._roi_drag_mode == "create" and self.roi_rect is not None:
                x, y, w, h = self.roi_rect
                if w == 0:
                    w = 1
                if h == 0:
                    h = 1
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
        self.zoom_factor = max(MIN_ZOOM_SCALE, min(MAX_ZOOM_SCALE, float(factor)))
        if self.qimage is not None:
            self._update_display()

    # --- 座標変換など ---
    def _widget_to_image_coords(self, pos) -> tuple[int, int]:
        """widget 座標を画像の範囲内の pixel 座標に変換する。"""
        if self.qimage is None:
            return (0, 0)
        scale = max(0.0001, float(self.zoom_factor))
        ix = int(pos.x() / scale)
        iy = int(pos.y() / scale)
        ix = max(0, min(ix, self.qimage.width() - 1))
        iy = max(0, min(iy, self.qimage.height() - 1))
        return (ix, iy)

    def _get_resize_edge(self, pos) -> str | None:
        """cursor 付近にある ROI の辺・角を返す。

        Returns:
            'tl', 'tr', 'bl', 'br', 'left', 'right', 'top', 'bottom' のいずれか。該当しない場合は None。
        """
        if not self.roi_rect or self.qimage is None:
            return None

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

        # 小さな ROI では判定距離を縮める
        min_dimension = min(roi_w, roi_h)
        if min_dimension < dist * 2:
            dist = max(1, min_dimension // 3)

        # 角を優先して判定する
        if abs(px - roi_x) <= dist and abs(py - roi_y) <= dist:
            return "tl"
        if abs(px - roi_right) <= dist and abs(py - roi_y) <= dist:
            return "tr"
        if abs(px - roi_x) <= dist and abs(py - roi_bottom) <= dist:
            return "bl"
        if abs(px - roi_right) <= dist and abs(py - roi_bottom) <= dist:
            return "br"

        if abs(px - roi_x) <= dist and roi_y <= py <= roi_bottom:
            return "left"
        if abs(px - roi_right) <= dist and roi_y <= py <= roi_bottom:
            return "right"
        if abs(py - roi_y) <= dist and roi_x <= px <= roi_right:
            return "top"
        if abs(py - roi_bottom) <= dist and roi_x <= px <= roi_right:
            return "bottom"

        return None

    def _update_cursor_for_edge(self, edge: str | None):
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
        # 矢印キーは scroll を同期するため親 dialog で処理する
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            event.ignore()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        # Ctrl+wheel で zoom、それ以外は親の scroll area で scroll する
        if event.modifiers() & Qt.ControlModifier:
            dy = event.angleDelta().y()
            if dy == 0:
                event.accept()
                return
            factor = ZOOM_STEP if dy > 0 else 1.0 / ZOOM_STEP
            self.zoom_requested.emit(factor, None)
            event.accept()
            return
        event.ignore()
