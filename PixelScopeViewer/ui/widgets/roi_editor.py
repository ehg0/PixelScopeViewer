"""キーボードによる ROI 移動。"""

from PySide6.QtCore import QRect, Qt


class RoiEditorMixin:
    """矢印キーで ROI を 1 pixel（Shift で 10 pixel）移動する mixin。"""

    def keyPressEvent(self, e):
        if not self.roi_rect or self.roi_rect.isNull():
            super().keyPressEvent(e)
            return

        # 画像 pixel 単位の移動量を表示 pixel に換算する
        img_delta = 10 if e.modifiers() & Qt.ShiftModifier else 1
        delta = int(img_delta * self.scale)
        if delta == 0:
            delta = 1

        new_rect = QRect(self.roi_rect)

        if e.key() == Qt.Key_Left:
            new_rect.translate(-delta, 0)
        elif e.key() == Qt.Key_Right:
            new_rect.translate(delta, 0)
        elif e.key() == Qt.Key_Up:
            new_rect.translate(0, -delta)
        elif e.key() == Qt.Key_Down:
            new_rect.translate(0, delta)
        else:
            super().keyPressEvent(e)
            return

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
