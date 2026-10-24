"""ROI 操作に対応した画像表示 widget。"""

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QWheelEvent

from PixelScopeViewer.core.constants import MAX_ZOOM_SCALE, MIN_ZOOM_SCALE, ZOOM_STEP
from PixelScopeViewer.core.roi import hit_test_edge, move_rect, rect_from_points, resize_rect
from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.common.widgets import edge_cursor
from PixelScopeViewer.ui.viewer.widgets.base_image_label import BaseImageLabel


class ImageLabel(BaseImageLabel):
    """pixel 単位に吸着する ROI の作成・移動・リサイズに対応した画像表示 widget。

    左 drag で作成、右 drag で移動、辺・角の左 drag でリサイズ、矢印キーで 1 pixel（Shift で 10 pixel）移動する。
    roi_rect は widget 座標で持つ。
    """

    def __init__(self, viewer, parent=None):
        super().__init__(viewer, parent)
        self.roi_rect: QRect | None = None
        self.dragging = False
        # drag の種類: 'create', 'move', 'resize' のいずれか
        self._drag_mode = None
        self._resize_edge = None
        # drag 開始時のマウス位置と ROI（画像座標）
        self._drag_start_img = None
        self._drag_orig_img_rect: QRect | None = None

    def set_image(self, qimg: QImage, scale: float = 1.0):
        """画像を表示する。ROI は画像座標を保ったまま新しい倍率に合わせる。"""
        prev_sel_img = None
        if self.roi_rect and self._qimage is not None and not self._qimage.isNull():
            prev_sel_img = self.get_roi_in_image_coords()

        super().set_image(qimg, scale)

        self.roi_rect = self._image_rect_to_widget(prev_sel_img) if prev_sel_img is not None else None

    def clear(self):
        super().clear()
        self.roi_rect = None

    # --- ROI ---
    def get_roi_in_image_coords(self) -> QRect | None:
        """ROI を画像座標で返す。ROI がない場合は None。"""
        if not self.roi_rect:
            return None
        return self._widget_rect_to_image(self.roi_rect)

    def set_roi_full(self):
        """画像全体を ROI にする。"""
        if not self.showing:
            return
        disp_w = int(self._orig_pixmap.width() * self.scale) if not self._orig_pixmap.isNull() else 0
        disp_h = int(self._orig_pixmap.height() * self.scale) if not self._orig_pixmap.isNull() else 0
        self.roi_rect = QRect(0, 0, max(1, disp_w), max(1, disp_h))
        self.update()

    def _get_resize_edge(self, pos: QPoint) -> str | None:
        """cursor 付近にある ROI の辺・角を返す。"""
        if not self.roi_rect:
            return None
        return hit_test_edge(pos.x(), pos.y(), self.roi_rect.getRect(), inclusive=True)

    def _set_roi_from_image_rect(self, rect: tuple[int, int, int, int]):
        self.roi_rect = self._image_rect_to_widget(QRect(*rect))

    def _notify_roi_changed(self):
        if self.viewer and self.roi_rect:
            self.viewer.on_roi_changed(self.roi_rect)

    # --- event ---
    def paintEvent(self, event):
        # 基底クラスで画像を描画した後、ROI を重ねて描画する
        super().paintEvent(event)
        if self.roi_rect:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(theme.ROI_COLOR), 1))
            painter.drawRect(self.roi_rect)

    def mousePressEvent(self, ev):
        if not self.showing:
            return

        pos = ev.position().toPoint()
        edge = self._get_resize_edge(pos)
        img_pt = self._widget_to_image_point(pos)

        if ev.button() == Qt.LeftButton:
            self.dragging = True
            self._drag_start_img = img_pt
            if edge:
                self._drag_mode = "resize"
                self._resize_edge = edge
                self._drag_orig_img_rect = self.get_roi_in_image_coords()
            else:
                self._drag_mode = "create"
                # クリック直後から 1 pixel の ROI を表示する
                if img_pt is not None:
                    self.roi_rect = QRect(self._image_to_widget_x(img_pt[0]), self._image_to_widget_y(img_pt[1]), 1, 1)
        elif ev.button() == Qt.RightButton and self.roi_rect and self.roi_rect.contains(pos) and not edge:
            # ROI の内側（辺以外）を右クリックしたときのみ移動を開始する
            self.dragging = True
            self._drag_mode = "move"
            self._drag_start_img = img_pt
            self._drag_orig_img_rect = self.get_roi_in_image_coords()

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()
        # ROI の辺に hover したら cursor を変える
        if self.showing and not self.dragging and self.roi_rect:
            self.setCursor(edge_cursor(self._get_resize_edge(pos)))

        if self.showing and self.dragging:
            cur_img = self._widget_to_image_point(pos)
            if cur_img is None:
                return
            self._apply_drag(cur_img)
            self.update()
            self._notify_roi_changed()

        # 親に画像範囲内へ clamp したマウス位置を通知する
        if hasattr(self.parent(), "on_mouse_move"):
            if self.showing and not self._orig_pixmap.isNull():
                disp_w = int(self._orig_pixmap.width() * self.scale)
                disp_h = int(self._orig_pixmap.height() * self.scale)
                pos = QPoint(max(0, min(pos.x(), max(0, disp_w - 1))), max(0, min(pos.y(), max(0, disp_h - 1))))
            self.parent().on_mouse_move(pos)

    def _apply_drag(self, cur_img: tuple[int, int]):
        """drag 中のマウス位置（画像座標）に合わせて ROI を作成・移動・リサイズする。"""
        if self._drag_mode == "create":
            if self._drag_start_img is not None:
                self._set_roi_from_image_rect(rect_from_points(self._drag_start_img, cur_img))
            return
        if self._drag_start_img is None or self._drag_orig_img_rect is None:
            return
        orig = self._drag_orig_img_rect.getRect()
        img_w, img_h = self._qimage.width(), self._qimage.height()
        if self._drag_mode == "resize":
            self._set_roi_from_image_rect(resize_rect(orig, self._resize_edge, *cur_img, img_w, img_h))
        elif self._drag_mode == "move":
            dx = cur_img[0] - self._drag_start_img[0]
            dy = cur_img[1] - self._drag_start_img[1]
            self._set_roi_from_image_rect(move_rect(orig, dx, dy, img_w, img_h))

    def mouseReleaseEvent(self, ev):
        if not self.showing:
            return
        # 左 button は作成・リサイズ、右 button は移動の終了
        expected = Qt.RightButton if self._drag_mode == "move" else Qt.LeftButton
        if not self.dragging or ev.button() != expected:
            return
        if self._drag_mode == "create":
            end_img = self._widget_to_image_point(ev.position().toPoint())
            if end_img is not None:
                self._apply_drag(end_img)
        self.dragging = False
        self._drag_mode = None
        self._resize_edge = None
        self._drag_start_img = None
        self._drag_orig_img_rect = None
        self.update()
        self._notify_roi_changed()

    def keyPressEvent(self, e):
        # 矢印キーで ROI を 1 pixel（Shift で 10 pixel）移動する
        offsets = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        if not self.roi_rect or e.key() not in offsets:
            super().keyPressEvent(e)
            return

        # 画像 pixel 単位の移動量を表示 pixel に換算する
        img_delta = 10 if e.modifiers() & Qt.ShiftModifier else 1
        delta = max(1, int(img_delta * self.scale))
        dx, dy = offsets[e.key()]
        new_rect = self.roi_rect.translated(dx * delta, dy * delta)

        # 画像の範囲内に収める
        disp_w = int(self._orig_pixmap.width() * self.scale) if not self._orig_pixmap.isNull() else 0
        disp_h = int(self._orig_pixmap.height() * self.scale) if not self._orig_pixmap.isNull() else 0
        if new_rect.left() < 0:
            new_rect.moveLeft(0)
        if new_rect.top() < 0:
            new_rect.moveTop(0)
        if new_rect.right() >= disp_w:
            new_rect.moveRight(disp_w - 1)
        if new_rect.bottom() >= disp_h:
            new_rect.moveBottom(disp_h - 1)

        self.roi_rect = new_rect
        self.update()
        if self.viewer:
            self.viewer.on_roi_changed(self.roi_rect)

    def wheelEvent(self, event: QWheelEvent):
        if not self.showing or self.viewer.state.current_index is None:
            event.ignore()
            return

        # Ctrl なしの場合は親の scroll に任せる
        modifiers = event.modifiers()
        if not (modifiers & Qt.ControlModifier):
            event.ignore()
            return

        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            event.ignore()
            return

        # キーボード操作と同様に 2 倍 / 1/2 倍で zoom する
        current_scale = self.viewer.state.scale
        new_scale = current_scale * ZOOM_STEP if angle_delta > 0 else current_scale / ZOOM_STEP

        new_scale = max(MIN_ZOOM_SCALE, min(MAX_ZOOM_SCALE, new_scale))

        # status bar に表示中の座標を中心に zoom する
        self.viewer.zoom_manager.set_zoom_at_status_coords(new_scale)

        event.accept()
