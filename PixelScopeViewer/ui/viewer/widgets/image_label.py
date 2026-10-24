"""ROI 操作に対応した画像表示 widget。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QWheelEvent

from PixelScopeViewer.core.constants import MAX_ZOOM_SCALE, MIN_ZOOM_SCALE, ZOOM_STEP
from PixelScopeViewer.ui.viewer.widgets.base_image_label import BaseImageLabel
from PixelScopeViewer.ui.viewer.widgets.roi_editor import RoiEditorMixin
from PixelScopeViewer.ui.viewer.widgets.roi_manager import RoiManagerMixin


class ImageLabel(RoiManagerMixin, RoiEditorMixin, BaseImageLabel):
    """pixel 単位に吸着する ROI の作成・移動・リサイズに対応した画像表示 widget。"""

    def __init__(self, viewer, parent=None):
        super().__init__(viewer, parent)
        self.__init_roi_manager__()

    def set_image(self, qimg: QImage, scale: float = 1.0):
        """画像を表示する。ROI は画像座標を保ったまま新しい倍率に合わせる。"""
        prev_sel_img = None
        if self.roi_rect and not self.roi_rect.isNull() and self._qimage is not None and not self._qimage.isNull():
            prev = self.get_roi_in_image_coords()
            if prev is not None:
                prev_sel_img = prev

        super().set_image(qimg, scale)

        if prev_sel_img is not None:
            self.roi_rect = self._image_rect_to_widget(prev_sel_img)
        else:
            self.roi_rect = None

    def clear(self):
        super().clear()
        self.roi_rect = None

    def paintEvent(self, event):
        # 基底クラスで画像を描画した後、ROI を重ねて描画する
        super().paintEvent(event)

        painter = QPainter(self)
        self.paint_roi(painter)

    def wheelEvent(self, event: QWheelEvent):
        if not self.showing or self.viewer.current_index is None:
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
        current_scale = self.viewer.scale
        new_scale = current_scale * ZOOM_STEP if angle_delta > 0 else current_scale / ZOOM_STEP

        new_scale = max(MIN_ZOOM_SCALE, min(MAX_ZOOM_SCALE, new_scale))

        # status bar に表示中の座標を中心に zoom する
        self.viewer.set_zoom_at_status_coords(new_scale)

        event.accept()
