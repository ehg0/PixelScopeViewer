"""汎用の custom Qt widget。"""

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QSlider

# ROI の辺・角（core.roi.hit_test_edge の戻り値）に hover したときの cursor
_EDGE_CURSORS = {
    "tl": Qt.SizeFDiagCursor,
    "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor,
    "bl": Qt.SizeBDiagCursor,
    "left": Qt.SizeHorCursor,
    "right": Qt.SizeHorCursor,
    "top": Qt.SizeVerCursor,
    "bottom": Qt.SizeVerCursor,
}


def set_value_silently(widget, value) -> None:
    """valueChanged などの signal を発火させずに widget の値を設定する。"""
    with QSignalBlocker(widget):
        widget.setValue(value)


def edge_cursor(edge: str | None) -> Qt.CursorShape:
    """ROI の辺・角に対応する cursor を返す。辺の外は矢印。"""
    return _EDGE_CURSORS.get(edge, Qt.ArrowCursor)


class StepSlider(QSlider):
    """wheel 1 回で 1 step だけ動く QSlider。"""

    def wheelEvent(self, event):
        # 回転方向のみを使う（上: 正 / 下: 負）
        delta = event.angleDelta().y()

        if delta > 0:
            self.setValue(self.value() + 1)
        elif delta < 0:
            self.setValue(self.value() - 1)

        # OS 側の複数行 scroll を打ち消す
        event.accept()
